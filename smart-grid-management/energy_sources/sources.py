import math
import random

from .base import EnergySource, SourceCategory


class SolarSource(EnergySource):
    """Fuente solar: solo produce entre las 6:00 y las 18:00, con pico al mediodía."""

    def __init__(self, name: str, capacity_kw: float):
        super().__init__(name, capacity_kw, SourceCategory.RENOVABLE)

    def generate_output(self, hour: int) -> float:
        if not self.is_active or hour < 6 or hour > 18:
            return 0.0
        factor = max(0.0, math.sin(math.pi * (hour - 6) / 12))
        eficiencia = random.uniform(0.9, 1.0)
        return round(self.capacity_kw * factor * eficiencia, 2)


class WindSource(EnergySource):
    """Fuente eólica: producción intermitente, no depende de la hora del día."""

    def __init__(self, name: str, capacity_kw: float):
        super().__init__(name, capacity_kw, SourceCategory.RENOVABLE)

    def generate_output(self, hour: int) -> float:
        if not self.is_active:
            return 0.0
        factor = random.uniform(0.2, 0.9)
        return round(self.capacity_kw * factor, 2)


class HydroSource(EnergySource):
    """Fuente hidroeléctrica: producción estable con variaciones menores."""

    def __init__(self, name: str, capacity_kw: float):
        super().__init__(name, capacity_kw, SourceCategory.RENOVABLE)

    def generate_output(self, hour: int) -> float:
        if not self.is_active:
            return 0.0
        factor = random.uniform(0.75, 0.95)
        return round(self.capacity_kw * factor, 2)


class ThermalSource(EnergySource):
    """Fuente convencional (planta térmica / respaldo de red): disponible bajo demanda."""

    def __init__(self, name: str, capacity_kw: float):
        super().__init__(name, capacity_kw, SourceCategory.CONVENCIONAL)

    def generate_output(self, hour: int) -> float:
        if not self.is_active:
            return 0.0
        return float(self.capacity_kw)
