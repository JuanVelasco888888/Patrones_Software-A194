from core.dispatch_strategies import DispatchStrategy, PeakShavingStrategy
from core.grid_monitor import GridMonitor
from energy_sources.base import StabilityClass

STABILIZATION_CAP_RATIO = 0.15   # parte de la capacidad estable que puede usarse para reforzar
STABILIZATION_GAIN = 0.5         # a mayor desviación del voltaje, mayor refuerzo (proporcional)


class LoadBalancer:
    """Reparte la generación entre las fuentes para cubrir la demanda hora a hora.

    Orden de uso: renovables → baterías → respaldo convencional (según la estrategia vigente).
    """

    def __init__(self, peak_threshold_kw: float, strategy: DispatchStrategy = None):
        self.peak_threshold_kw = peak_threshold_kw
        self.monitor = GridMonitor.instance()
        self._strategy = strategy or PeakShavingStrategy()
        self.last_renewable_kw = 0.0     # renovable entregada en la última hora (incluye baterías)
        self.last_charge_kw = 0.0        # excedente guardado en baterías en la última hora
        self.last_effectiveness = 0.0    # qué tanto del refuerzo pedido se pudo dar (0 a 1)
        self._last_dispatch = {}

    @property
    def strategy(self) -> DispatchStrategy:
        return self._strategy

    def set_strategy(self, strategy: DispatchStrategy) -> None:
        self._strategy = strategy

    def set_peak_threshold(self, kw: float) -> float:
        if kw <= 0:
            raise ValueError("El umbral de pico debe ser mayor que 0.")
        previous, self.peak_threshold_kw = self.peak_threshold_kw, kw
        return previous

    def balance(self, hour: int, demand_kw: float, trace: dict = None) -> float:
        sources = self.monitor.sources
        generators = [s for s in sources if not s.is_storage]
        renewables = [s for s in generators if s.category.value == "renovable"]
        conventional = [s for s in generators if s.category.value == "convencional"]
        batteries = [s for s in sources if s.is_storage]

        dispatched = {}
        for s in renewables:
            dispatched[s.name] = round(s.generate_output(hour), 2)
        renewable_generation = sum(dispatched.values())

        if demand_kw > self.peak_threshold_kw:
            self.monitor.register_alert(
                f"[Hora {hour:02d}] Pico de demanda detectado "
                f"({demand_kw:.2f} kW > limite {self.peak_threshold_kw:.2f} kW). "
                f"Activando fuentes de respaldo."
            )

        # Excedente renovable -> se guarda en baterías
        self.last_charge_kw = 0.0
        surplus = renewable_generation - demand_kw
        for bat in batteries:
            if surplus <= 0:
                break
            taken = bat.charge(surplus)
            self.last_charge_kw += taken
            surplus -= taken

        # Faltante -> primero baterías, después respaldo convencional
        deficit = demand_kw - renewable_generation
        stored = backup = 0.0
        if deficit > 0:
            for bat in batteries:
                out = bat.discharge(deficit - stored)
                if out > 0:
                    dispatched[bat.name] = out
                    stored += out
            remaining = deficit - stored
            if remaining > 0:
                backup = self._strategy.dispatch_backup(
                    hour, demand_kw, remaining, conventional, self.peak_threshold_kw
                )
                left = backup
                for s in conventional:
                    if left <= 0:
                        break
                    out = min(s.generate_output(hour), left)
                    if out > 0:
                        dispatched[s.name] = round(out, 2)
                    left -= out

        self.last_renewable_kw = renewable_generation + stored
        self._last_dispatch = dispatched
        if trace is not None:
            trace.update(dispatched)
        return round(renewable_generation + stored + backup, 2)

    def stabilize_voltage(self, hour: int, renewable_ratio: float,
                          voltage_anomalies: list, voltage_error: float = 0.0) -> float:
        """Refuerza la red con la capacidad libre de fuentes estables cuando el voltaje oscila.

        Control proporcional: a mayor desviación del voltaje, más refuerzo se pide.
        """
        self.last_effectiveness = 0.0
        if not voltage_anomalies or renewable_ratio < 0.5:
            return 0.0
        stable = [s for s in self.monitor.sources
                  if s.stability is StabilityClass.ESTABLE and not s.is_storage and s.is_available]
        if not stable:
            return 0.0
        cap = sum(s.effective_capacity_kw for s in stable) * STABILIZATION_CAP_RATIO
        requested = cap * min(1.0, STABILIZATION_GAIN * abs(voltage_error) / 5.0)
        if requested <= 0:
            return 0.0
        reinforcement = 0.0
        for s in stable:
            if reinforcement >= requested:
                break
            spare = max(0.0, s.effective_capacity_kw - self._last_dispatch.get(s.name, 0.0))
            reinforcement += min(spare, requested - reinforcement)
        if reinforcement > 0:
            self.last_effectiveness = min(1.0, reinforcement / requested)
            self.monitor.register_alert(
                f"[Hora {hour:02d}] Ajuste de estabilidad: se reforzaron "
                f"{reinforcement:.2f} kW de generacion estable (voltaje {voltage_error:+.1f} V "
                f"respecto a lo normal) para amortiguar la variabilidad renovable."
            )
        return round(reinforcement, 2)

    def apply_current_stress(self, hour: int, current_amp: float) -> float:
        """Desgasta los equipos si la corriente es alta. Devuelve el mayor desgaste (0 a 1)."""
        worst = 0.0
        for source in self.monitor.sources:
            was_failed = source.failed
            wear = source.apply_current_stress(current_amp)
            worst = max(worst, wear)
            if source.failed and not was_failed:
                self.monitor.register_alert(
                    f"[Falla] La fuente '{source.name}' salio de servicio por sobrecarga sostenida "
                    f"(hora {hour:02d})."
                )
        return worst
