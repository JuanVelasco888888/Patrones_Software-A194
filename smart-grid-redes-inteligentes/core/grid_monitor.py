import threading
from datetime import datetime

from core.events import EventKind, EventPublisher, GridEvent
from core.memento import GridMonitorMemento


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
        self._publisher = EventPublisher()
        self._initialized = True

    # ---------- Observer ----------
    def subscribe(self, observer) -> None:
        self._publisher.subscribe(observer)

    def unsubscribe(self, observer) -> None:
        self._publisher.unsubscribe(observer)

    # ---------- gestión de fuentes ----------
    def register_source(self, source) -> None:
        self.sources.append(source)

    def set_source_active(self, name: str, active: bool) -> bool:
        """Activa/desactiva una fuente por nombre. Devuelve su estado previo."""
        for source in self.sources:
            if source.name == name:
                previous = source.is_active
                source.toggle(active)
                return previous
        raise KeyError(f"No existe la fuente '{name}'.")

    # ---------- monitoreo en tiempo real ----------
    def record_reading(self, hour: int, demand_kw: float, generation_kw: float,
                        voltage: float = None, current: float = None,
                        power_factor: float = None,
                        technical_loss_kw: float = None) -> dict:
        """
        Registra una lectura horaria. voltage, current, power_factor y
        technical_loss_kw son OPCIONALES para no romper código existente
        que solo pasaba demand_kw/generation_kw; si se proporcionan,
        enriquecen la lectura con el estado eléctrico de la red en esa hora.
        """
        reading = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "hour": hour,
            "demand_kw": round(demand_kw, 2),
            "generation_kw": round(generation_kw, 2),
            "balance_kw": round(generation_kw - demand_kw, 2),
            "voltage": round(voltage, 2) if voltage is not None else None,
            "current": round(current, 2) if current is not None else None,
            "power_factor": round(power_factor, 3) if power_factor is not None else None,
            "technical_loss_kw": round(technical_loss_kw, 2) if technical_loss_kw is not None else None,
        }
        self.history.append(reading)
        self._publisher.publish(GridEvent(EventKind.READING, dict(reading)))
        return reading

    def register_alert(self, message: str) -> None:
        self.alerts.append(message)
        self._publisher.publish(GridEvent(EventKind.ALERT, message))

    def get_alerts(self) -> list:
        return list(self.alerts)

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
        self._publisher.publish(GridEvent(EventKind.RESET))

    # ---------- Memento ----------
    def create_memento(self) -> GridMonitorMemento:
        return GridMonitorMemento.capture(self.sources, self.history, self.alerts)

    def restore_memento(self, memento: GridMonitorMemento) -> None:
        self.sources[:] = memento.sources
        for source, was_active in memento.source_states:
            source.toggle(was_active)
        self.history[:] = [dict(r) for r in memento.history]
        self.alerts[:] = memento.alerts
        self._replay_to_observers()

    def _replay_to_observers(self) -> None:
        """Re-sincroniza a los observadores con el estado restaurado."""
        self._publisher.publish(GridEvent(EventKind.RESET))
        for reading in self.history:
            self._publisher.publish(GridEvent(EventKind.READING, dict(reading)))
        for alert in self.alerts:
            self._publisher.publish(GridEvent(EventKind.ALERT, alert))

    @classmethod
    def instance(cls) -> "GridMonitor":
        """Forma explícita de pedir la instancia única. Equivalente a GridMonitor()."""
        return cls()
