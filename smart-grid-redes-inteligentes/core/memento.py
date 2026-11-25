from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Optional, Protocol


@dataclass(frozen=True)
class GridMonitorMemento:
    """Memento: instantanea inmutable del estado del GridMonitor."""
    sources: tuple
    history: tuple
    alerts: tuple
    # (fuente, estaba_activa). Sin esto el memento guardaba solo la referencia
    # al objeto y, al restaurar, las fuentes seguian como estuvieran en ese momento.
    source_states: tuple = ()

    @classmethod
    def capture(cls, sources, history, alerts) -> "GridMonitorMemento":
        return cls(
            sources=tuple(sources),
            history=tuple(MappingProxyType(dict(r)) for r in history),
            alerts=tuple(alerts),
            source_states=tuple((s, s.is_active) for s in sources),
        )


@dataclass(frozen=True)
class GridSetupMemento:
    """Memento: 'foto' de como esta configurada la red en un momento dado.

    Guarda lo que el usuario puede cambiar (fuentes encendidas/apagadas, limite
    de pico y modo de respaldo) mas una copia del estado del monitor.
    """
    label: str
    created_at: str
    source_states: tuple                 # ((nombre, activa), ...)
    peak_threshold_kw: Optional[float]
    strategy_name: Optional[str]         # None = automatica (segun el estado de la red)
    total_cost: Optional[float]
    monitor_memento: GridMonitorMemento
    flexible_load_pct: float = 0.0       # % de consumo que se puede mover a horas valle
    failed_sources: tuple = ()           # ((nombre, motivo), ...)

    @staticmethod
    def now() -> str:
        return datetime.now().isoformat(timespec="seconds")


class MementoOriginator(Protocol):
    def create_memento(self, *args, **kwargs): ...
    def restore_memento(self, memento) -> None: ...


class MementoCaretaker:
    """Caretaker: guarda y devuelve los puntos de guardado sin conocer su contenido.

    Por qué aquí: antes de probar un cambio fuerte (apagar fuentes, bajar el límite de pico,
    cambiar el modo de respaldo) el operador necesita poder volver a una situación conocida
    y comparar costos y alertas. El memento guarda esa "foto" sin exponer ni romper el
    estado interno del sistema.
    """

    def __init__(self, originator: MementoOriginator):
        self._originator = originator
        self._stack = []

    def save(self, *args, **kwargs):
        memento = self._originator.create_memento(*args, **kwargs)
        self._stack.append(memento)
        return memento

    def undo(self) -> bool:
        """Restaura el ultimo memento y lo saca de la pila."""
        if not self._stack:
            return False
        self._originator.restore_memento(self._stack.pop())
        return True

    def restore(self, index: int) -> bool:
        """Restaura el memento en `index` SIN borrarlo (se puede volver otra vez)."""
        if not 0 <= index < len(self._stack):
            return False
        self._originator.restore_memento(self._stack[index])
        return True

    def discard(self, index: int) -> bool:
        if not 0 <= index < len(self._stack):
            return False
        del self._stack[index]
        return True

    @property
    def mementos(self) -> tuple:
        return tuple(self._stack)

    @property
    def saved_count(self) -> int:
        return len(self._stack)
