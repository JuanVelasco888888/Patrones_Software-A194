import math
import random

from .base import EnergySource, SourceCategory, StabilityClass


class SolarSource(EnergySource):
    """Solar: solo produce entre las 6:00 y las 18:00, con su máximo al mediodía."""

    def __init__(self, name: str, capacity_kw: float):
        super().__init__(name, capacity_kw, SourceCategory.RENOVABLE, StabilityClass.VARIABLE)

    def generate_output(self, hour: int) -> float:
        if not self.is_available or hour < 6 or hour > 18:
            return 0.0
        factor = max(0.0, math.sin(math.pi * (hour - 6) / 12))
        return round(self.effective_capacity_kw * factor * random.uniform(0.9, 1.0), 2)


class WindSource(EnergySource):
    """Eólica: producción intermitente que no depende de la hora."""

    def __init__(self, name: str, capacity_kw: float):
        super().__init__(name, capacity_kw, SourceCategory.RENOVABLE, StabilityClass.VARIABLE)

    def generate_output(self, hour: int) -> float:
        if not self.is_available:
            return 0.0
        return round(self.effective_capacity_kw * random.uniform(0.2, 0.9), 2)


class HydroSource(EnergySource):
    """Hidroeléctrica: producción estable con variaciones menores."""

    def __init__(self, name: str, capacity_kw: float):
        super().__init__(name, capacity_kw, SourceCategory.RENOVABLE, StabilityClass.ESTABLE)

    def generate_output(self, hour: int) -> float:
        if not self.is_available:
            return 0.0
        return round(self.effective_capacity_kw * random.uniform(0.75, 0.95), 2)


class GeothermalSource(EnergySource):
    """Geotérmica: producción estable a partir del calor de la tierra."""

    def __init__(self, name: str, capacity_kw: float):
        super().__init__(name, capacity_kw, SourceCategory.RENOVABLE, StabilityClass.ESTABLE)

    def generate_output(self, hour: int) -> float:
        if not self.is_available:
            return 0.0
        return round(self.effective_capacity_kw * random.uniform(0.80, 0.95), 2)


class ThermalSource(EnergySource):
    """Planta térmica (respaldo convencional): disponible bajo demanda."""

    def __init__(self, name: str, capacity_kw: float):
        super().__init__(name, capacity_kw, SourceCategory.CONVENCIONAL, StabilityClass.ESTABLE)

    def generate_output(self, hour: int) -> float:
        if not self.is_available:
            return 0.0
        return float(self.effective_capacity_kw)


class BatterySource(EnergySource):
    """Banco de baterías: guarda el excedente renovable y lo entrega cuando falta energía.

    Ayuda a suavizar la intermitencia del sol y el viento. Consultar cuánto puede
    entregar (generate_output) no gasta carga; solo discharge() la consume.
    """

    is_storage = True

    def __init__(self, name: str, capacity_kw: float, round_trip_efficiency: float = 0.90):
        super().__init__(name, capacity_kw, SourceCategory.RENOVABLE, StabilityClass.ESTABLE)
        self.round_trip_efficiency = round_trip_efficiency
        self.max_soc_kwh = capacity_kw * 2.0      # 2 horas de autonomía a plena potencia
        self.soc_kwh = self.max_soc_kwh * 0.5     # arranca a media carga

    @property
    def charge_level(self) -> float:
        return self.soc_kwh / self.max_soc_kwh if self.max_soc_kwh else 0.0

    def generate_output(self, hour: int) -> float:
        """Potencia que podría entregar ahora (no descarga la batería)."""
        if not self.is_available or self.soc_kwh <= 0:
            return 0.0
        return round(min(self.effective_capacity_kw, self.soc_kwh), 2)

    def charge(self, surplus_kw: float) -> float:
        """Guarda excedente. Devuelve los kW tomados del excedente."""
        if surplus_kw <= 0 or not self.is_available:
            return 0.0
        room_kwh = self.max_soc_kwh - self.soc_kwh
        taken = min(surplus_kw, self.effective_capacity_kw, room_kwh / self.round_trip_efficiency)
        self.soc_kwh += taken * self.round_trip_efficiency
        return round(taken, 2)

    def discharge(self, needed_kw: float) -> float:
        """Entrega hasta `needed_kw` y descuenta la carga usada. Devuelve los kW entregados."""
        delivered = min(max(needed_kw, 0.0), self.generate_output(0))
        self.soc_kwh -= delivered
        return round(delivered, 2)
