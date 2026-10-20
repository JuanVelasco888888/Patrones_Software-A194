from billing.tariff import Tariff
from billing.calculation import TariffCalculation

class TariffDecorator(Tariff):
    """Decorator base: envuelve una Tariff y delega el cálculo."""
    def __init__(self, wrapped_tariff: Tariff):
        self._wrapped = wrapped_tariff
        # Heredamos el cálculo del envuelto para no romper el Bridge
        super().__init__(calculation=wrapped_tariff.calculation)

    def price_per_kwh(self) -> float:
        return self._wrapped.price_per_kwh()

    def compute_cost(self, demand_kw: float, hour: int, context: dict = None) -> float:
        # Por defecto, delega en el envuelto
        return self._wrapped.compute_cost(demand_kw, hour, context)

class RenewableDiscountDecorator(TariffDecorator):
    """Añade un descuento si el ratio renovable es alto."""
    def __init__(self, wrapped_tariff: Tariff, discount_rate: float = 0.10):
        super().__init__(wrapped_tariff)
        self.discount_rate = discount_rate

    def compute_cost(self, demand_kw: float, hour: int, context: dict = None) -> float:
        base_cost = self._wrapped.compute_cost(demand_kw, hour, context)
        renewable_ratio = context.get("renewable_ratio", 0.0) if context else 0.0
        if renewable_ratio >= 0.7:
            return round(base_cost * (1 - self.discount_rate), 4)
        return base_cost

class PeakSurchargeDecorator(TariffDecorator):
    """Añade un recargo si es hora pico."""
    def __init__(self, wrapped_tariff: Tariff, surcharge_rate: float = 0.15):
        super().__init__(wrapped_tariff)
        self.surcharge_rate = surcharge_rate

    def compute_cost(self, demand_kw: float, hour: int, context: dict = None) -> float:
        base_cost = self._wrapped.compute_cost(demand_kw, hour, context)
        # Asumimos que PeakTariff ya sabe si es pico, pero aquí forzamos el recargo
        if 18 <= hour < 22:
            return round(base_cost * (1 + self.surcharge_rate), 4)
        return base_cost