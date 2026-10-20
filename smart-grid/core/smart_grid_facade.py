from core.grid_monitor import GridMonitor
from core.grid_monitor_proxy import GridMonitorProxy
from core.load_balancer import LoadBalancer
from core.anomaly_detector import AnomalyDetector
from core.grid_composite import GridSector, SourceLeaf
from energy_sources.factory import EnergySourceFactory
from billing.billing_system import DynamicBillingSystem
from simulation.data_simulator import simulate_daily_demand, simulate_daily_demand_flyweight
from simulation.electrical_simulator import simulate_electrical_metrics


class SmartGridFacade:
    """
    Facade: Simplifica la ejecución de un ciclo completo de simulación.
    Oculta la complejidad de: Builder, Factory, Composite, Proxy, LoadBalancer,
    AnomalyDetector, DynamicBillingSystem y los simuladores.
    """

    def __init__(self, calculation=None, user_role: str = "admin"):
        # Usamos el Proxy para controlar el acceso al Singleton
        self.monitor = GridMonitorProxy(user_role=user_role)
        self.calculation = calculation
        # Guardamos el árbol Composite para que la UI pueda inspeccionarlo
        self._root_sector = None
        self._sector_renovables = None
        self._sector_convencional = None

    def get_root_sector(self):
        """Expone el árbol Composite para que la UI lo visualice."""
        return self._root_sector

    def get_sector_renovables(self):
        return self._sector_renovables

    def get_sector_convencional(self):
        return self._sector_convencional

    def run_simulation_cycle(self, config, verbose: bool = True,
                             use_flyweight: bool = False,
                             profile_type: str = "comercial"):
        """
        Ejecuta un ciclo completo de 24h con la configuración dada.

        Args:
            config: GridConfiguration (creada con Builder o Prototype)
            verbose: Si True, imprime el progreso por consola
            use_flyweight: Si True, usa perfiles de consumo compartidos (Flyweight)
            profile_type: Tipo de perfil para Flyweight ('residencial', 'comercial', 'industrial')
        """
        # 1. Construir la red con estructura de árbol (Composite)
        self.monitor.reset()
        self._root_sector = GridSector("Red Completa")
        self._sector_renovables = GridSector("Sector Renovables")
        self._sector_convencional = GridSector("Sector Convencional")

        for source_type, name, capacity in config.sources_spec:
            source = EnergySourceFactory.create_source(source_type, name, capacity)
            self.monitor.register_source(source)
            leaf = SourceLeaf(source)
            # Clasificamos la hoja en su sector correspondiente
            if source.category.value == "renovable":
                self._sector_renovables.add(leaf)
            else:
                self._sector_convencional.add(leaf)

        # Anidamos los sub-sectores dentro del sector raíz
        self._root_sector.add(self._sector_renovables)
        self._root_sector.add(self._sector_convencional)

        # 2. Configurar el balanceador y detector
        balancer = LoadBalancer(peak_threshold_kw=config.peak_threshold_kw)
        detector = AnomalyDetector()
        billing = DynamicBillingSystem(calculation=self.calculation)

        # 3. Simular demanda (usando Flyweight o el simulador clásico)
        if use_flyweight:
            demand_by_hour = simulate_daily_demand_flyweight(profile_type, seed=config.seed)
            if verbose:
                print(f"[Flyweight] Usando perfil compartido: {profile_type}")
        else:
            demand_by_hour = simulate_daily_demand(
                base_load_kw=config.base_load_kw,
                peak_load_kw=config.peak_load_kw,
                seed=config.seed,
            )

        if verbose:
            print("=" * 78)
            print(f"FACADE: Ejecutando simulación de 24h")
            print(f"Cálculo tarifario (Bridge): {billing.calculation.name if billing.calculation else 'Por kWh (default)'}")
            print("=" * 78)

        # 4. Bucle de simulación
        for hour, demand in demand_by_hour.items():
            total_generation = balancer.balance(hour, demand)

            # Usamos el Composite para obtener la generación renovable
            renewable_generation = self._root_sector.get_renewable_generation(hour)
            renewable_ratio = (renewable_generation / total_generation) if total_generation else 0.0

            metrics = simulate_electrical_metrics(hour, demand, renewable_ratio)
            anomalies = detector.detect(
                hour, metrics["voltage"], metrics["current"], metrics["power_factor"]
            )
            for msg in anomalies:
                self.monitor.register_alert(msg)

            balancer.stabilize_voltage(hour, renewable_ratio, anomalies)

            reading = self.monitor.record_reading(
                hour, demand, total_generation,
                voltage=metrics["voltage"], current=metrics["current"],
                power_factor=metrics["power_factor"],
                technical_loss_kw=metrics["technical_loss_kw"],
            )

            # Facturación con Decorators (Bridge + Decorator)
            invoice_item = billing.bill_reading(
                hour, demand, total_generation, renewable_generation,
                power_factor=metrics["power_factor"],
            )
            billing.record_technical_loss(
                hour, metrics["technical_loss_kw"], invoice_item["price_per_kwh"]
            )

            if verbose:
                status = "OK" if reading["balance_kw"] >= 0 else "DEFICIT"
                print(
                    f"Hora {hour:02d}:00 | Demanda: {demand:6.2f} kW | "
                    f"Gen: {total_generation:6.2f} kW | "
                    f"Balance: {reading['balance_kw']:7.2f} [{status:7s}] | "
                    f"Tarifa: {invoice_item['tariff']:18s} | "
                    f"Costo: ${invoice_item['cost']:.4f}"
                )

        if verbose:
            print("-" * 78)
            print("Resumen por tarifa (Bridge + Decorator):")
            for name, cost in billing.summary_by_tariff().items():
                print(f"  - {name:20s}: ${cost:.2f}")
            print(f"\nCOSTO TOTAL DEL DIA: ${billing.total_cost():.2f}")
            print(f"PERDIDAS TECNICAS: {billing.total_technical_loss_kwh():.2f} kWh (${billing.total_technical_loss_cost():.2f})")
            print("=" * 78)

        return billing, self.monitor