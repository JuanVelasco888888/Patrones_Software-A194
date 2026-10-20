from .tariff import (
    OffPeakTariff, StandardTariff, PeakTariff, RenewableIncentiveTariff,
)
from .calculation import TariffCalculation


class TariffFactory:
    PEAK_HOURS = range(18, 22)      # 18:00 - 21:59
    OFF_PEAK_HOURS = range(0, 6)    # 00:00 - 05:59

    @classmethod
    def create_tariff(cls, hour: int, renewable_ratio: float,
                      calculation: TariffCalculation = None):
        """Crea la tarifa correspondiente e inyecta el cálculo (Bridge)."""
        if renewable_ratio >= 0.7:
            return RenewableIncentiveTariff(calculation)
        if hour in cls.PEAK_HOURS:
            return PeakTariff(calculation)
        if hour in cls.OFF_PEAK_HOURS:
            return OffPeakTariff(calculation)
        return StandardTariff(calculation)