from .base import EnergySource
from .sources import (
    BatterySource, GeothermalSource, HydroSource, SolarSource, ThermalSource, WindSource,
)


class EnergySourceFactory:
    """Crea la fuente correcta a partir de un identificador de texto."""

    _REGISTRY = {
        "solar": SolarSource,
        "eolica": WindSource,
        "hidroelectrica": HydroSource,
        "termica": ThermalSource,
        "geotermica": GeothermalSource,
        "bateria": BatterySource,
    }

    @classmethod
    def create_source(cls, source_type: str, name: str, capacity_kw: float) -> EnergySource:
        key = source_type.lower().strip()
        source_cls = cls._REGISTRY.get(key)
        if source_cls is None:
            raise ValueError(
                f"Tipo de fuente desconocido: '{source_type}'. "
                f"Tipos disponibles: {list(cls._REGISTRY.keys())}"
            )
        return source_cls(name=name, capacity_kw=capacity_kw)

    @classmethod
    def available_types(cls) -> list:
        return list(cls._REGISTRY.keys())

    @classmethod
    def register_source_type(cls, key: str, source_cls) -> None:
        cls._REGISTRY[key.lower()] = source_cls
