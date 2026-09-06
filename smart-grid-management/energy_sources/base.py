"""
energy_sources/base.py
Interfaz común que deben cumplir todas las fuentes de energía
integradas a la red inteligente (renovables y convencionales).
"""
from abc import ABC, abstractmethod
from enum import Enum


class SourceCategory(Enum):
    RENOVABLE = "renovable"
    CONVENCIONAL = "convencional"


class EnergySource(ABC):
    """Contrato que debe implementar cualquier fuente de energía del sistema."""

    def __init__(self, name: str, capacity_kw: float, category: SourceCategory):
        self.name = name
        self.capacity_kw = capacity_kw
        self.category = category
        self.is_active = True

    @abstractmethod
    def generate_output(self, hour: int) -> float:
        """Devuelve la potencia generada (kW) para una hora del día (0-23)."""
        raise NotImplementedError

    def toggle(self, active: bool) -> None:
        """Activa o desactiva la fuente (por mantenimiento, falla, etc.)."""
        self.is_active = active

    def __repr__(self) -> str:
        estado = "activa" if self.is_active else "inactiva"
        return (f"<{self.__class__.__name__} '{self.name}' "
                f"cap={self.capacity_kw}kW ({self.category.value}, {estado})>")
