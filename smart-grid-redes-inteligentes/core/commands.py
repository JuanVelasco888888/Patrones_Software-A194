from abc import ABC, abstractmethod
from typing import Callable, Optional, Protocol

# Gancho opcional que se ejecuta DESPUES de aplicar o deshacer un comando.
# Sirve para que la UI/Facade recalcule la simulacion y el cambio se refleje
# en todas las secciones (generacion, costos, avisos), no solo en la fuente.
AppliedHook = Optional[Callable[[], None]]


class GridCommand(ABC):
    """Command: cada cambio que hace el operador queda encapsulado y se puede deshacer.

    Por qué aquí: el operador apaga fuentes, simula fallas, mueve el límite de pico o el
    consumo flexible para probar cómo responde la red. Al volverse objetos, esos cambios
    quedan en un historial, se validan en un solo lugar y se deshacen uno a uno sin
    reiniciar la simulación (balanceo de carga y operación segura).
    """

    @property
    @abstractmethod
    def description(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def execute(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def undo(self) -> None:
        raise NotImplementedError


class SourceSwitch(Protocol):
    def set_source_active(self, name: str, active: bool) -> bool: ...


class ThresholdSetter(Protocol):
    def set_peak_threshold(self, kw: float) -> float: ...


class _HookedCommand(GridCommand):
    """Base comun: guarda el valor previo y avisa al gancho tras cada cambio."""

    def __init__(self, on_applied: AppliedHook = None):
        self._previous = None
        self._done = False
        self._on_applied = on_applied

    @abstractmethod
    def _apply(self):
        """Aplica el cambio y devuelve el valor previo."""
        raise NotImplementedError

    @abstractmethod
    def _restore(self, previous) -> None:
        """Vuelve al valor previo."""
        raise NotImplementedError

    def _notify(self) -> None:
        if self._on_applied is not None:
            self._on_applied()

    def execute(self) -> None:
        self._previous = self._apply()
        self._done = True
        try:
            self._notify()
        except Exception:
            # Si el recalculo falla, no dejamos la red a medias: se revierte.
            self._restore(self._previous)
            self._previous = None
            self._done = False
            raise

    def undo(self) -> None:
        if not self._done:
            raise RuntimeError("El comando aun no se ejecuto.")
        self._restore(self._previous)
        self._notify()


class ToggleSourceCommand(_HookedCommand):
    """Activa/desactiva una fuente (mantenimiento, falla o reconexion)."""

    def __init__(self, receiver: SourceSwitch, source_name: str, active: bool,
                 on_applied: AppliedHook = None):
        super().__init__(on_applied)
        self._receiver = receiver
        self._source_name = source_name
        self._active = active

    @property
    def description(self) -> str:
        action = "encender" if self._active else "apagar"
        return f"{action} la fuente «{self._source_name}»"

    def _apply(self):
        return self._receiver.set_source_active(self._source_name, self._active)

    def _restore(self, previous) -> None:
        self._receiver.set_source_active(self._source_name, previous)


class SetPeakThresholdCommand(_HookedCommand):
    """Cambia el umbral de pico del balanceador de carga."""

    def __init__(self, receiver: ThresholdSetter, new_threshold_kw: float,
                 on_applied: AppliedHook = None):
        super().__init__(on_applied)
        self._receiver = receiver
        self._new = new_threshold_kw

    @property
    def description(self) -> str:
        return f"límite de pico → {self._new:g} kW"

    def _apply(self):
        return self._receiver.set_peak_threshold(self._new)

    def _restore(self, previous) -> None:
        self._receiver.set_peak_threshold(previous)


class StrategySetter(Protocol):
    def set_strategy_mode(self, name): ...


class SetStrategyCommand(_HookedCommand):
    """Cambia el modo de respaldo (None = automatico, segun el estado de la red)."""

    def __init__(self, receiver: StrategySetter, new_mode, on_applied: AppliedHook = None):
        super().__init__(on_applied)
        self._receiver = receiver
        self._new = new_mode

    @property
    def description(self) -> str:
        return f"modo de respaldo → {self._new or 'automático'}"

    def _apply(self):
        return self._receiver.set_strategy_mode(self._new)

    def _restore(self, previous) -> None:
        self._receiver.set_strategy_mode(previous)


class FlexibleLoadSetter(Protocol):
    def set_flexible_load_pct(self, pct): ...


class SetFlexibleLoadCommand(_HookedCommand):
    """Cambia cuanto consumo por encima del limite de pico puede moverse a horas valle."""

    def __init__(self, receiver: FlexibleLoadSetter, pct: float, on_applied: AppliedHook = None):
        super().__init__(on_applied)
        self._receiver = receiver
        self._new = pct

    @property
    def description(self) -> str:
        return f"consumo flexible → {self._new:g} %"

    def _apply(self):
        return self._receiver.set_flexible_load_pct(self._new)

    def _restore(self, previous) -> None:
        self._receiver.set_flexible_load_pct(previous)


class FailureSetter(Protocol):
    def set_source_failure(self, name, reason): ...


class SourceFailureCommand(_HookedCommand):
    """Provoca o repara una falla de equipo (reason=None repara)."""

    def __init__(self, receiver: FailureSetter, source_name: str, reason,
                 on_applied: AppliedHook = None):
        super().__init__(on_applied)
        self._receiver = receiver
        self._source_name = source_name
        self._reason = reason

    @property
    def description(self) -> str:
        if self._reason is None:
            return f"reparar la fuente «{self._source_name}»"
        return f"falla en la fuente «{self._source_name}» ({self._reason})"

    def _apply(self):
        return self._receiver.set_source_failure(self._source_name, self._reason)

    def _restore(self, previous) -> None:
        self._receiver.set_source_failure(self._source_name, previous)


class CommandInvoker:
    """Invoker: ejecuta comandos y mantiene el historial para deshacer."""

    def __init__(self):
        self._executed = []

    def execute(self, command: GridCommand) -> None:
        command.execute()  # si falla, no entra al historial
        self._executed.append(command)

    def undo_last(self) -> bool:
        if not self._executed:
            return False
        self._executed[-1].undo()  # solo se saca del historial si el undo funciona
        self._executed.pop()
        return True

    def clear(self) -> None:
        self._executed.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._executed)

    @property
    def history(self) -> tuple:
        return tuple(c.description for c in self._executed)
