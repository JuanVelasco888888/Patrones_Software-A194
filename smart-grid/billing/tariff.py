from abc import ABC, abstractmethod

from .calculation import TariffCalculation, PerKWhCalculation


class Tariff(ABC):
    name = "Genérica"

    def __init__(self, calculation: TariffCalculation = None):
        # El puente: cualquier tarifa concreta se combina con cualquier cálculo.
        self.calculation = calculation or PerKWhCalculation()

    @abstractmethod
    def price_per_kwh(self) -> float:
        raise NotImplementedError

    def compute_cost(self, demand_kw: float, hour: int,
                     context: dict = None) -> float:
        """Delega el cálculo al Implementor (Bridge en acción)."""
        return self.calculation.compute(
            demand_kw, hour, self.price_per_kwh(), context or {}
        )


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