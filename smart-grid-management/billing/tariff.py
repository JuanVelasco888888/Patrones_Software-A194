"""
billing/tariff.py
Estrategias de tarifa que utiliza el sistema de facturación dinámica.
Cada tarifa concreta define únicamente su precio por kWh; la decisión de
CUÁL aplicar en cada momento vive en TariffFactory (billing/tariff_factory.py).
"""
from abc import ABC, abstractmethod


class Tariff(ABC):
    name = "Genérica"

    @abstractmethod
    def price_per_kwh(self) -> float:
        raise NotImplementedError


class OffPeakTariff(Tariff):
    """Tarifa de madrugada / baja demanda."""
    name = "Fuera de pico"

    def price_per_kwh(self) -> float:
        return 0.08


class StandardTariff(Tariff):
    """Tarifa para horas de demanda normal."""
    name = "Estandar"

    def price_per_kwh(self) -> float:
        return 0.12


class PeakTariff(Tariff):
    """Tarifa para horas pico (mayor costo, incentiva reducir consumo)."""
    name = "Pico"

    def price_per_kwh(self) -> float:
        return 0.22


class RenewableIncentiveTariff(Tariff):
    """Tarifa preferencial cuando la mayor parte de la energía es renovable."""
    name = "Incentivo renovable"

    def price_per_kwh(self) -> float:
        return 0.06
