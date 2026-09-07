from core.grid_monitor import GridMonitor

# Tope de refuerzo de estabilización: no más de este % de la capacidad
# convencional/estable se usa para amortiguar variabilidad renovable.
STABILIZATION_CAP_RATIO = 0.15


class LoadBalancer:
    def __init__(self, peak_threshold_kw: float):
        self.peak_threshold_kw = peak_threshold_kw
        self.monitor = GridMonitor.instance()

    def balance(self, hour: int, demand_kw: float) -> float:
        """
        Reparte la generación entre las fuentes disponibles:
          1. Siempre despacha primero toda la energía renovable disponible.
          2. Si la demanda supera el umbral de pico y las renovables no
             alcanzan a cubrirla, activa fuentes convencionales para
             cubrir el déficit.

        Devuelve la generación total despachada (kW).
        """
        renewables = [s for s in self.monitor.sources if s.category.value == "renovable"]
        conventional = [s for s in self.monitor.sources if s.category.value == "convencional"]

        total_generation = sum(s.generate_output(hour) for s in renewables)

        if demand_kw > self.peak_threshold_kw:
            self.monitor.register_alert(
                f"[Hora {hour:02d}] Pico de demanda detectado "
                f"({demand_kw:.2f} kW > umbral {self.peak_threshold_kw:.2f} kW). "
                f"Activando fuentes de respaldo."
            )
            deficit = demand_kw - total_generation
            for source in conventional:
                if deficit <= 0:
                    break
                output = source.generate_output(hour)
                dispatch = min(output, deficit)
                total_generation += dispatch
                deficit -= dispatch

        return round(total_generation, 2)

    def stabilize_voltage(self, hour: int, renewable_ratio: float,
                           voltage_anomalies: list) -> float:
        """
        Si hay una anomalía de voltaje en la hora Y la generación de esa
        hora fue mayoritariamente renovable, despacha un pequeño refuerzo
        de generación estable (hidro o térmica) como medida de
        estabilización, independiente del umbral de pico.

        Devuelve el refuerzo despachado (kW); 0.0 si no hizo falta.
        """
        if not voltage_anomalies or renewable_ratio < 0.5:
            return 0.0

        stable_sources = [
            s for s in self.monitor.sources
            if s.__class__.__name__ in ("HydroSource", "ThermalSource")
        ]
        if not stable_sources:
            return 0.0

        cap = sum(s.capacity_kw for s in stable_sources) * STABILIZATION_CAP_RATIO
        reinforcement = 0.0
        for source in stable_sources:
            if reinforcement >= cap:
                break
            available = source.generate_output(hour)
            dispatch = min(available, cap - reinforcement)
            reinforcement += dispatch

        if reinforcement > 0:
            self.monitor.register_alert(
                f"[Hora {hour:02d}] Ajuste de estabilidad: se reforzaron "
                f"{reinforcement:.2f} kW de generacion estable para amortiguar "
                f"la variabilidad de las fuentes renovables."
            )
        return round(reinforcement, 2)
