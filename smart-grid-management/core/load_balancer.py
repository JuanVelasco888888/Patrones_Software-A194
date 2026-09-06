"""
core/load_balancer.py

Implementa "Balanceo de carga y gestión de picos": ante una demanda alta,
prioriza fuentes renovables y solo recurre a fuentes convencionales
(respaldo) cuando la demanda supera un umbral crítico.

Usa la instancia única de GridMonitor (Singleton) para saber qué fuentes
existen y para registrar alertas cuando detecta un pico.
"""
from core.grid_monitor import GridMonitor


class LoadBalancer:
    def __init__(self, peak_umbral_kw: float):
        self.peak_umbral_kw = peak_umbral_kw
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

        if demand_kw > self.peak_umbral_kw:
            self.monitor.register_alert(
                f"[Hora {hour:02d}] Pico de demanda detectado "
                f"({demand_kw:.2f} kW > umbral {self.peak_umbral_kw:.2f} kW). "
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
