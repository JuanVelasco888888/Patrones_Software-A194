from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.dispatch_strategies import (
    DispatchStrategy, FullCoverageStrategy, PeakShavingStrategy,
)


@dataclass(frozen=True)
class GridSnapshot:
    """Datos de una hora que los estados usan para decidir la transicion."""
    hour: int
    demand_kw: float
    generation_kw: float
    anomaly_count: int
    peak_threshold_kw: float

    @property
    def has_deficit(self) -> bool:
        return self.generation_kw < self.demand_kw

    @property
    def is_stressed(self) -> bool:
        return self.demand_kw > self.peak_threshold_kw or self.anomaly_count > 0


class GridState(ABC):
    """State: situación operativa de la red (Normal, Pico, Emergencia).

    Por qué aquí: según la situación, el balanceador debe comportarse distinto (ahorrar
    respaldo en calma, cubrir todo faltante en emergencia). Cada estado decide a cuál
    estado pasa la red y qué estrategia de respaldo corresponde, y así el cambio de
    comportamiento es automático y no depende de condicionales repartidos por el código.
    """

    name = "Generico"

    @property
    @abstractmethod
    def dispatch_strategy(self) -> DispatchStrategy:
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, snapshot: GridSnapshot) -> "GridState":
        raise NotImplementedError


class NormalState(GridState):
    name = "Normal"

    @property
    def dispatch_strategy(self) -> DispatchStrategy:
        return PeakShavingStrategy()

    def evaluate(self, snapshot):
        if snapshot.has_deficit:
            return EmergencyState()
        return PeakState() if snapshot.is_stressed else self


class PeakState(GridState):
    name = "Pico"

    @property
    def dispatch_strategy(self) -> DispatchStrategy:
        return PeakShavingStrategy()

    def evaluate(self, snapshot):
        if snapshot.has_deficit:
            return EmergencyState()
        return self if snapshot.is_stressed else NormalState()


class EmergencyState(GridState):
    name = "Emergencia"

    @property
    def dispatch_strategy(self) -> DispatchStrategy:
        return FullCoverageStrategy()

    def evaluate(self, snapshot):
        if snapshot.has_deficit:
            return self
        return PeakState() if snapshot.is_stressed else NormalState()


@dataclass(frozen=True)
class StateTransition:
    hour: int
    previous: str
    current: str


class GridStateMachine:
    """Context: mantiene el estado actual y registra las transiciones."""

    def __init__(self, initial: GridState = None):
        self._state = initial or NormalState()
        self._transitions = []

    @property
    def state(self) -> GridState:
        return self._state

    @property
    def transitions(self) -> tuple:
        return tuple(self._transitions)

    def update(self, snapshot: GridSnapshot) -> GridState:
        next_state = self._state.evaluate(snapshot)
        if type(next_state) is not type(self._state):
            self._transitions.append(
                StateTransition(snapshot.hour, self._state.name, next_state.name)
            )
        self._state = next_state
        return next_state
