import random

from billing import methods as billing_methods
from core.anomaly_detector import AnomalyDetector
from core.commands import (
    CommandInvoker, SetFlexibleLoadCommand, SetPeakThresholdCommand, SetStrategyCommand,
    SourceFailureCommand, ToggleSourceCommand,
)
from core.access_control import Permission
from core.grid_composite import GridSector, SourceLeaf
from core.grid_mediator import GridOperationsMediator
from core.grid_monitor import GridMonitor
from core.grid_monitor_proxy import GridMonitorProxy
from core.grid_state import GridStateMachine
from core.grid_visitors import CapacityVisitor, EquipmentHealthVisitor, InactiveSourcesVisitor
from core.dispatch_strategies import FullCoverageStrategy, PeakShavingStrategy
from core import analytics
from core.load_balancer import LoadBalancer
from core.load_shifting import shift_peak_load
from core.memento import GridSetupMemento, MementoCaretaker
from core.observers import AlertCountObserver, DeficitObserver
from core.reports import BillingReport, OperationReport, RenewableReport
from energy_sources.factory import EnergySourceFactory
from billing.billing_system import DynamicBillingSystem
from simulation.data_simulator import simulate_daily_demand, simulate_daily_demand_flyweight


_STRATEGIES = {
    "gestion de picos": PeakShavingStrategy,
    "cobertura total": FullCoverageStrategy,
}


class _SetupOriginator:
    """Originator del Memento: la 'foto' es la configuración de la red que ve el usuario."""

    def __init__(self, facade: "SmartGridFacade"):
        self._facade = facade

    def create_memento(self, label: str = None) -> GridSetupMemento:
        return self._facade._capture_setup(label)

    def restore_memento(self, memento: GridSetupMemento) -> None:
        self._facade._apply_setup(memento)


class SmartGridFacade:
    """Punto de entrada único: la interfaz pide acciones simples y aquí se coordina todo lo demás."""

    def __init__(self, calculation=None, user_role: str = "admin"):
        self.monitor = GridMonitorProxy(user_role=user_role)
        self.calculation = calculation
        self.deficit_observer = DeficitObserver()
        self.alert_observer = AlertCountObserver()
        self._invoker = CommandInvoker()
        self._caretaker = MementoCaretaker(_SetupOriginator(self))
        self._state_machine = GridStateMachine()
        self._balancer = None
        self._root_sector = None
        self._sector_renovables = None
        self._sector_convencional = None
        self._last_config = None
        self._last_profile_type = "comercial"
        self._last_use_flyweight = False
        self._hour_results = []
        self._billing = None
        self._threshold_kw = None        # None = usar el de la configuracion
        self._strategy_name = None       # None = automatica (segun el estado)
        self._flex_pct = 0.0             # % de consumo sobre el limite que se mueve a horas valle
        self._original_demand = {}       # demanda ANTES de aplanar picos
        self._failures = {}              # fuente -> motivo de la falla (sobreviven al recalculo)

    # ---------- exposición para UI ----------
    def get_billing(self):
        """Facturacion de la ULTIMA simulacion (se actualiza tras cada cambio)."""
        return self._billing

    def current_peak_threshold(self):
        if self._threshold_kw is not None:
            return self._threshold_kw
        return self._last_config.peak_threshold_kw if self._last_config else None

    def current_strategy_name(self):
        """None significa 'automatica'."""
        return self._strategy_name

    def current_flexible_load_pct(self) -> float:
        return self._flex_pct

    def get_original_demand(self) -> dict:
        return dict(self._original_demand)

    def performance_metrics(self) -> dict:
        """Indicadores del día que muestra la interfaz (ver core/analytics.py)."""
        hours = self._hour_results
        applied = {r.reading["hour"]: r.reading["demand_kw"] for r in hours}
        original = self.get_original_demand() or applied
        threshold = self.current_peak_threshold()
        sources = [leaf.source for sector in self._root_sector.children for leaf in sector.children]
        renewable_names = {leaf.source.name for leaf in self._sector_renovables.children}
        battery_names = {s.name for s in sources if s.is_storage}
        source_types = {s.name: type(s).__name__ for s in sources}
        billing = self._billing
        return {
            "demand_original": original,
            "demand_applied": applied,
            "load_original": analytics.load_stats(original, threshold),
            "load_applied": analytics.load_stats(applied, threshold),
            "generation_split": analytics.generation_split(hours, renewable_names),
            "renewable_share": analytics.renewable_energy_share(hours, renewable_names),
            "voltage": analytics.voltage_stats(hours),
            "profit": analytics.profitability(hours, billing, source_types),
            "tariff_table": analytics.consumption_by_tariff(billing),
            "peak_hours_share": analytics.peak_hours_share(billing),
            "alerts": analytics.classify_alerts(self.monitor.get_alerts()),
            "losses_kwh": billing.total_technical_loss_kwh(),
            "demand_kwh": sum(applied.values()),
            "storage": analytics.storage_summary(hours, battery_names),
            "wear_by_hour": analytics.equipment_wear_by_hour(hours),
            "renewable_names": renewable_names,
            "source_types": source_types,
        }

    def compare_billing_methods(self) -> list:
        """Vuelve a facturar el mismo día con cada forma de cobro (no altera la simulación)."""
        m = self.performance_metrics()
        return billing_methods.compare_methods(
            self._hour_results, m["renewable_names"], m["source_types"])

    def use_billing_method(self, calculation) -> None:
        """Cambia la forma de cobro y recalcula el día."""
        self.monitor.authorize(Permission.CONFIGURE, "change_billing_method")
        self.calculation = calculation
        self._resimulate_if_possible()

    def source_states(self) -> dict:
        return {s.name: s.is_active for s in self.monitor.sources}

    def _switch_states(self) -> dict:
        """Lo que el usuario dejó encendido o apagado (una fuente en falla cuenta como encendida:
        al repararla vuelve a servicio)."""
        return {s.name: (True if s.failed else s.is_active) for s in self.monitor.sources}

    def get_checkpoints(self) -> tuple:
        return self._caretaker.mementos

    def get_command_history(self) -> tuple:
        return self._invoker.history

    def get_checkpoint_count(self) -> int:
        return self._caretaker.saved_count

    def get_hour_results(self) -> tuple:
        return tuple(self._hour_results)

    def get_state_transitions(self) -> tuple:
        return self._state_machine.transitions

    def get_root_sector(self):
        return self._root_sector

    def get_sector_renovables(self):
        return self._sector_renovables

    def get_sector_convencional(self):
        return self._sector_convencional

    def capacity_summary(self) -> CapacityVisitor:
        visitor = CapacityVisitor()
        self._root_sector.accept(visitor)
        return visitor

    def equipment_health(self) -> EquipmentHealthVisitor:
        visitor = EquipmentHealthVisitor()
        self._root_sector.accept(visitor)
        return visitor

    def failed_sources(self) -> list:
        return self.equipment_health().failed

    def inactive_sources(self) -> InactiveSourcesVisitor:
        visitor = InactiveSourcesVisitor()
        self._root_sector.accept(visitor)
        return visitor

    def set_strategy(self, strategy_name: str = None) -> None:
        """Fija el modo de respaldo. None / 'automatica' = lo decide el estado de la red."""
        if self._balancer is None:
            raise RuntimeError("Ejecute una simulacion antes de cambiar la estrategia.")
        key = (strategy_name or "automatica").strip().lower()
        if key == "automatica":
            new = None
        elif key in _STRATEGIES:
            new = key
        else:
            raise ValueError(f"Estrategia desconocida: {strategy_name}")
        self.monitor.authorize(Permission.CONFIGURE, "set_strategy")
        self._invoker.execute(SetStrategyCommand(
            self, new, on_applied=self._resimulate_if_possible,
        ))

    def set_strategy_mode(self, name):
        """Receiver del comando: recuerda el modo para que sobreviva al recalculo."""
        previous, self._strategy_name = self._strategy_name, name
        return previous

    # ---------- comandos ----------
    def _recalculate(self, source_states: dict = None):
        self.run_simulation_cycle(
            self._last_config, verbose=False,
            use_flyweight=self._last_use_flyweight,
            profile_type=self._last_profile_type,
            preserve_source_state=True, source_states=source_states,
        )

    def _resimulate_if_possible(self):
        if self._last_config is not None:
            self._recalculate()

    def toggle_source(self, name: str, active: bool) -> None:
        if active and name in self._failures:
            raise ValueError(f"«{name}» está en falla. Repárala primero en «Operar la red».")
        self._invoker.execute(ToggleSourceCommand(
            self.monitor, name, active, on_applied=self._resimulate_if_possible,
        ))

    def report_source_failure(self, name: str, reason: str = "falla de equipo") -> None:
        """La fuente sale de servicio y la red se reacomoda con las demás."""
        self._require_source(name)
        self.monitor.authorize(Permission.MANAGE_SOURCES, "report_source_failure")
        self._invoker.execute(SourceFailureCommand(
            self, name, (reason or "").strip() or "falla de equipo",
            on_applied=self._resimulate_if_possible,
        ))

    def repair_source(self, name: str) -> None:
        self._require_source(name)
        if name not in self._failures:
            raise ValueError(f"«{name}» no está en falla.")
        self.monitor.authorize(Permission.MANAGE_SOURCES, "repair_source")
        self._invoker.execute(SourceFailureCommand(
            self, name, None, on_applied=self._resimulate_if_possible,
        ))

    def set_source_failure(self, name: str, reason):
        """Receiver del comando: recuerda la falla para que sobreviva al recalculo."""
        previous = self._failures.get(name)
        if reason is None:
            self._failures.pop(name, None)
        else:
            self._failures[name] = reason
        return previous

    def _require_source(self, name: str) -> None:
        if name not in self.source_states():
            raise KeyError(f"No existe la fuente '{name}'.")

    def change_peak_threshold(self, kw: float) -> None:
        if self._balancer is None:
            raise RuntimeError("Ejecute una simulacion antes de cambiar el umbral.")
        self.monitor.authorize(Permission.CONFIGURE, "change_peak_threshold")
        self._invoker.execute(SetPeakThresholdCommand(
            self, kw, on_applied=self._resimulate_if_possible,
        ))

    def set_flexible_load(self, pct: float) -> None:
        """Define cuanto consumo por encima del limite de pico se mueve a horas valle (0 a 100)."""
        if self._last_config is None:
            raise RuntimeError("Ejecute una simulacion antes de aplanar picos.")
        if not 0 <= pct <= 100:
            raise ValueError("El porcentaje debe estar entre 0 y 100.")
        self.monitor.authorize(Permission.CONFIGURE, "set_flexible_load")
        self._invoker.execute(SetFlexibleLoadCommand(
            self, float(pct), on_applied=self._resimulate_if_possible,
        ))

    def set_flexible_load_pct(self, pct: float) -> float:
        """Receiver del comando: recuerda el porcentaje para que sobreviva al recalculo."""
        previous, self._flex_pct = self._flex_pct, float(pct)
        return previous

    def set_peak_threshold(self, kw: float) -> float:
        """Receiver del comando: recuerda el umbral para que sobreviva al recalculo."""
        if kw <= 0:
            raise ValueError("El umbral de pico debe ser mayor que 0.")
        previous = self.current_peak_threshold()
        self._threshold_kw = kw
        if self._balancer is not None:
            self._balancer.set_peak_threshold(kw)
        return previous

    def undo_last_command(self) -> bool:
        return self._invoker.undo_last()

    # ---------- memento (puntos de guardado) ----------
    def save_checkpoint(self, label: str = None) -> GridSetupMemento:
        self.monitor.authorize(Permission.SNAPSHOT_SAVE, "save_checkpoint")
        return self._caretaker.save(label)

    def restore_checkpoint(self, index: int) -> bool:
        """Vuelve al punto de guardado `index` (el punto se conserva)."""
        if not 0 <= index < self._caretaker.saved_count:
            return False
        self.monitor.authorize(Permission.SNAPSHOT_RESTORE, "restore_checkpoint")
        return self._caretaker.restore(index)

    def rollback(self) -> bool:
        """Vuelve al ultimo punto de guardado."""
        return self.restore_checkpoint(self._caretaker.saved_count - 1)

    def delete_checkpoint(self, index: int) -> bool:
        return self._caretaker.discard(index)

    def _capture_setup(self, label: str = None) -> GridSetupMemento:
        n = self._caretaker.saved_count + 1
        return GridSetupMemento(
            label=(label or "").strip() or f"Punto {n}",
            created_at=GridSetupMemento.now(),
            source_states=tuple(self._switch_states().items()),
            peak_threshold_kw=self.current_peak_threshold(),
            strategy_name=self._strategy_name,
            total_cost=self._billing.total_cost() if self._billing else None,
            monitor_memento=self.monitor.create_memento(),
            flexible_load_pct=self._flex_pct,
            failed_sources=tuple(self._failures.items()),
        )

    def _apply_setup(self, memento: GridSetupMemento) -> None:
        if self._last_config is None:
            # Aun no se simulo nada: solo se puede restaurar el monitor.
            self.monitor.restore_memento(memento.monitor_memento)
            return
        self._threshold_kw = memento.peak_threshold_kw
        self._strategy_name = memento.strategy_name
        self._flex_pct = memento.flexible_load_pct
        self._failures = dict(memento.failed_sources)
        self._invoker.clear()  # esos comandos ya no corresponden a este punto
        self._recalculate(source_states=dict(memento.source_states))

    # ---------- reportes ----------
    def generate_reports(self, billing) -> dict:
        reports = {
            "operacion": OperationReport(self.monitor),
            "facturacion": BillingReport(billing),
            "renovables": RenewableReport(self._root_sector),
        }
        return {name: report.generate() for name, report in reports.items()}

    # ---------- escenarios ----------
    def compare_scenarios(self, base_config, variants: dict, verbose: bool = False) -> dict:
        from core.scenario_comparator import ScenarioComparator
        runner = lambda cfg: self.run_simulation_cycle(cfg, verbose=False)
        results = ScenarioComparator(runner).compare(base_config, variants)
        if verbose:
            base = results[0]
            print("=" * 60)
            print("COMPARATIVO DE ESCENARIOS")
            print("=" * 60)
            print(f"  base        : ${base.total_cost:.2f}")
            for r in results[1:]:
                signo = "+" if r.delta_vs_base >= 0 else ""
                print(f"  {r.name:12s}: ${r.total_cost:.2f}  ({signo}{r.delta_vs_base:.2f})")
            print("=" * 60)
        return {r.name: {"config": r.config, "costo": r.total_cost,
                         "reporte": r.report, "delta": r.delta_vs_base}
                for r in results}

    # ---------- simulacion ----------
    def run_simulation_cycle(self, config, verbose: bool = True,
                             use_flyweight: bool = False,
                             profile_type: str = "comercial",
                             preserve_source_state: bool = False,
                             source_states: dict = None,
                             flexible_load_pct: float = None):
        if config is not self._last_config:
            # Configuracion nueva: se olvidan los ajustes hechos sobre la anterior.
            self._threshold_kw = None
            self._strategy_name = None
            self._flex_pct = 0.0
            self._failures = {}
        if flexible_load_pct is not None:
            self._flex_pct = float(flexible_load_pct)
        self._last_config = config
        self._last_profile_type = profile_type
        self._last_use_flyweight = use_flyweight
        self._hour_results = []

        previous_states = {}
        if source_states is not None:
            previous_states = dict(source_states)
        elif preserve_source_state:
            previous_states = self._switch_states()

        self.monitor.reset()
        self._state_machine = GridStateMachine()
        self._build_grid(config)

        if previous_states:
            for source in GridMonitor.instance().sources:
                if source.name in previous_states:
                    source.toggle(previous_states[source.name])
        for source in GridMonitor.instance().sources:
            if source.name in self._failures:
                source.trip_failure(self._failures[source.name])
                self.monitor.register_alert(
                    f"[Falla] La fuente '{source.name}' esta fuera de servicio: "
                    f"{self._failures[source.name]}."
                )

        threshold = (self._threshold_kw if self._threshold_kw is not None
                     else config.peak_threshold_kw)
        self._balancer = LoadBalancer(peak_threshold_kw=threshold)
        billing = DynamicBillingSystem(calculation=self.calculation)
        self._billing = billing
        override = _STRATEGIES[self._strategy_name]() if self._strategy_name else None
        mediator = GridOperationsMediator(
            self.monitor, self._balancer, AnomalyDetector(), billing,
            self._state_machine, self._root_sector, strategy_override=override,
        )
        demand_by_hour = self._simulate_demand(config, use_flyweight, profile_type, verbose)
        self._original_demand = dict(demand_by_hour)
        if self._flex_pct > 0:
            demand_by_hour = shift_peak_load(demand_by_hour, threshold, self._flex_pct)

        if verbose:
            self._print_header(billing)

        self.monitor.subscribe(self.deficit_observer)
        self.monitor.subscribe(self.alert_observer)
        try:
            for hour, demand in demand_by_hour.items():
                # Mismo clima y ruido electrico en cada hora sin importar el escenario:
                # asi 'antes y despues' de un cambio se compara en igualdad de condiciones.
                random.seed(f"{config.seed}-{hour}")
                result = mediator.process_hour(hour, demand)
                self._hour_results.append(result)
                if verbose:
                    self._print_hour(hour, demand, result)
        finally:
            self.monitor.unsubscribe(self.deficit_observer)
            self.monitor.unsubscribe(self.alert_observer)

        if verbose:
            self._print_summary(billing)
        return billing, self.monitor

    def _build_grid(self, config) -> None:
        self._root_sector = GridSector("Red Completa")
        self._sector_renovables = GridSector("Sector Renovables")
        self._sector_convencional = GridSector("Sector Convencional")
        for source_type, name, capacity in config.sources_spec:
            source = EnergySourceFactory.create_source(source_type, name, capacity)
            self.monitor.register_source(source)
            sector = (self._sector_renovables if source.category.value == "renovable"
                      else self._sector_convencional)
            sector.add(SourceLeaf(source))
        self._root_sector.add(self._sector_renovables)
        self._root_sector.add(self._sector_convencional)

    @staticmethod
    def _simulate_demand(config, use_flyweight, profile_type, verbose) -> dict:
        if use_flyweight:
            if verbose:
                print(f"Perfil de consumo: {profile_type}")
            return simulate_daily_demand_flyweight(profile_type, seed=config.seed)
        return simulate_daily_demand(
            base_load_kw=config.base_load_kw,
            peak_load_kw=config.peak_load_kw,
            seed=config.seed,
        )

    @staticmethod
    def _print_header(billing) -> None:
        calc_name = billing.calculation.name if billing.calculation else "Por kWh"
        print("=" * 78)
        print("Simulación de un día completo (24 horas)")
        print(f"Forma de cobro: {calc_name}")
        print("=" * 78)

    @staticmethod
    def _print_hour(hour, demand, result) -> None:
        reading, item = result.reading, result.invoice_item
        status = "OK" if reading["balance_kw"] >= 0 else "DEFICIT"
        print(
            f"Hora {hour:02d}:00 | Demanda: {demand:6.2f} kW | "
            f"Gen: {reading['generation_kw']:6.2f} kW | "
            f"Balance: {reading['balance_kw']:7.2f} [{status:7s}] | "
            f"Situación: {result.state_name:10s} | "
            f"Respaldo: {result.trace.strategy_name:18s} | "
            f"Tarifa: {item['tariff']:18s} | Costo: ${item['cost']:.4f}"
        )

    @staticmethod
    def _print_summary(billing) -> None:
        print("-" * 78)
        print("Resumen por tarifa:")
        for name, cost in billing.summary_by_tariff().items():
            print(f"  - {name:20s}: ${cost:.2f}")
        print(f"\nCOSTO TOTAL DEL DIA: ${billing.total_cost():.2f}")
        print(f"PERDIDAS TECNICAS: {billing.total_technical_loss_kwh():.2f} kWh "
              f"(${billing.total_technical_loss_cost():.2f})")
        print("=" * 78)
