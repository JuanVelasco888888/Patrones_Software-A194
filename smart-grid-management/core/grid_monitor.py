"""
core/grid_monitor.py

PATRÓN SINGLETON
-----------------
GridMonitor es el único punto de verdad sobre el estado de la red:
fuentes registradas, lecturas de consumo/generación en tiempo real y
alertas de picos. Tiene sentido que sea único porque una red eléctrica
solo debe tener UN panel de monitoreo central; si cada módulo (balanceo
de carga, facturación, reportes) creara su propia copia del estado,
podrían quedar desincronizados entre sí.

Implementación thread-safe con "double-checked locking" para evitar
condiciones de carrera si en el futuro se usa en un servidor concurrente.
"""
import threading
from datetime import datetime


class GridMonitor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        # Evita que __init__ reinicie el estado cada vez que se llama GridMonitor()
        if self._initialized:
            return
        self.sources = []
        self.history = []
        self.alerts = []
        self._initialized = True

    # ---------- gestión de fuentes ----------
    def register_source(self, source) -> None:
        self.sources.append(source)

    # ---------- monitoreo en tiempo real ----------
    def record_reading(self, hour: int, demand_kw: float, generation_kw: float) -> dict:
        reading = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "hour": hour,
            "demand_kw": round(demand_kw, 2),
            "generation_kw": round(generation_kw, 2),
            "balance_kw": round(generation_kw - demand_kw, 2),
        }
        self.history.append(reading)
        return reading

    def register_alert(self, message: str) -> None:
        self.alerts.append(message)

    def current_state(self):
        return self.history[-1] if self.history else None

    def get_history(self) -> list:
        return list(self.history)

    def reset(self) -> None:
        """Reinicia el estado (útil para pruebas o para arrancar una nueva simulación)
        sin destruir la instancia única."""
        self.sources.clear()
        self.history.clear()
        self.alerts.clear()

    @classmethod
    def instance(cls) -> "GridMonitor":
        """Forma explícita de pedir la instancia única. Equivalente a GridMonitor()."""
        return cls()
