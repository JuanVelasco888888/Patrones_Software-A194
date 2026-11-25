import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EventKind(Enum):
    READING = "reading"
    ALERT = "alert"
    RESET = "reset"


@dataclass(frozen=True)
class GridEvent:
    kind: EventKind
    payload: Any = None


class GridObserver(ABC):
    """Observer: recibe los eventos que publica el GridMonitor."""

    @abstractmethod
    def update(self, event: GridEvent) -> None:
        raise NotImplementedError


class EventPublisher:
    """Subject reutilizable: mantiene suscriptores y los notifica."""

    def __init__(self):
        self._observers = []

    def subscribe(self, observer: GridObserver) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: GridObserver) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def publish(self, event: GridEvent) -> None:
        for observer in tuple(self._observers):
            try:
                observer.update(event)
            except Exception:  # un observador defectuoso no debe frenar el monitoreo
                logger.exception("Observer %s fallo al procesar %s",
                                 type(observer).__name__, event.kind)
