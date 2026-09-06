"""
energy_sources/factory.py

PATRÓN FACTORY (Factory Method / Simple Factory)
-------------------------------------------------
Centraliza la creación de fuentes de energía. El resto del sistema
(main.py, LoadBalancer, etc.) no necesita conocer las clases concretas
(SolarSource, WindSource, ...); solo pide un "tipo" a la fábrica.

Ventaja directa para el proyecto: "Integración con energías renovables"
se resuelve agregando nuevas fuentes al registro de la fábrica, sin tocar
el código que ya usa las fuentes existentes (principio abierto/cerrado).
"""
from .base import EnergySource
from .sources import SolarSource, WindSource, HydroSource, ThermalSource


class EnergySourceFactory:
    """Fábrica responsable de instanciar el tipo correcto de fuente de energía."""

    _REGISTRY = {
        "solar": SolarSource,
        "eolica": WindSource,
        "hidroelectrica": HydroSource,
        "termica": ThermalSource,
    }

    @classmethod
    def create_source(cls, source_type: str, name: str, capacity_kw: float) -> EnergySource:
        """
        Crea una fuente de energía a partir de un identificador de texto.

        Lanza ValueError si el tipo no está registrado.
        """
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
        """
        Permite extender la fábrica con nuevos tipos de fuente (p. ej. geotérmica,
        biomasa) sin modificar el código existente que ya la usa.
        """
        cls._REGISTRY[key.lower()] = source_cls
