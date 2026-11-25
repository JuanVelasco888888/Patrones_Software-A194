from abc import ABC, abstractmethod
from enum import Enum


class SourceCategory(Enum):
    RENOVABLE = "renovable"
    CONVENCIONAL = "convencional"


class StabilityClass(Enum):
    """Qué tan constante es la producción de la fuente (sirve para estabilizar el voltaje)."""
    ESTABLE = "estable"      # hidroeléctrica, geotérmica, térmica
    VARIABLE = "variable"    # solar, eólica


class EnergySource(ABC):
    """Contrato que debe cumplir cualquier fuente de energía del sistema."""

    is_storage = False   # las baterías guardan energía en lugar de producirla

    def __init__(self, name: str, capacity_kw: float, category: SourceCategory,
                 stability: StabilityClass = StabilityClass.VARIABLE,
                 max_current_amp: float = 400.0):
        self.name = name
        self.capacity_kw = capacity_kw
        self.category = category
        self.stability = stability
        self.max_current_amp = max_current_amp
        self.is_active = True
        self.failed = False
        self.failure_reason = ""
        self._degradation = 0.0          # 0.0 (sana) a 1.0 (inservible)

    # ---------- estado del equipo ----------
    @property
    def degradation(self) -> float:
        return self._degradation

    @property
    def effective_capacity_kw(self) -> float:
        """Capacidad disponible una vez descontado el desgaste por sobrecarga."""
        return round(self.capacity_kw * (1.0 - self._degradation), 2)

    @property
    def is_available(self) -> bool:
        return self.is_active and not self.failed

    @abstractmethod
    def generate_output(self, hour: int) -> float:
        """Potencia (kW) que puede entregar en la hora indicada (0-23)."""
        raise NotImplementedError

    def toggle(self, active: bool) -> None:
        """Enciende o apaga la fuente (mantenimiento, ahorro, etc.)."""
        self.is_active = active
        if active:
            self.failed = False
            self.failure_reason = ""

    def trip_failure(self, reason: str = "falla de equipo") -> None:
        """La fuente sale de servicio hasta que se repare."""
        self.failed = True
        self.is_active = False
        self.failure_reason = reason

    def repair(self) -> None:
        self.failed = False
        self.failure_reason = ""
        self.is_active = True
        self._degradation = 0.0

    def apply_current_stress(self, current_amp: float) -> float:
        """Desgasta el equipo si la corriente supera su límite; se recupera despacio si no.

        Devuelve el desgaste acumulado (0.0 a 1.0).
        """
        if current_amp <= self.max_current_amp:
            self._degradation = max(0.0, self._degradation - 0.01)
            return self._degradation
        excess = (current_amp - self.max_current_amp) / self.max_current_amp
        self._degradation = min(1.0, self._degradation + excess * 0.05)
        if self._degradation >= 0.95 and not self.failed:
            self.trip_failure("sobrecarga sostenida")
        return self._degradation

    @property
    def status_label(self) -> str:
        if self.failed:
            return "falla"
        return "activa" if self.is_active else "apagada"

    def __repr__(self) -> str:
        return (f"<{self.__class__.__name__} '{self.name}' cap={self.capacity_kw}kW "
                f"efectiva={self.effective_capacity_kw}kW ({self.category.value}, {self.status_label})>")
