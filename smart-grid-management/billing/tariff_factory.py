"""
billing/tariff_factory.py

PATRÓN FACTORY (segunda aplicación en el proyecto)
----------------------------------------------------
Encapsula la lógica de decisión de "Sistema de facturación dinámica":
según la hora del día y qué proporción de la energía despachada fue
renovable, decide qué objeto Tariff entregar. El resto del sistema
(DynamicBillingSystem) solo pide una tarifa y usa su precio; no conoce
las reglas de negocio detrás de la elección.
"""
from .tariff import OffPeakTariff, StandardTariff, PeakTariff, RenewableIncentiveTariff


class TariffFactory:
    PEAK_HOURS = range(18, 22)      # 18:00 - 21:59
    OFF_PEAK_HOURS = range(0, 6)    # 00:00 - 05:59

    @classmethod
    def create_tariff(cls, hour: int, renewable_ratio: float):
        """
        hour: hora del día (0-23).
        renewable_ratio: proporción (0.0 - 1.0) de la generación despachada
                         en esa hora que provino de fuentes renovables.
        """
        if renewable_ratio >= 0.7:
            return RenewableIncentiveTariff()
        if hour in cls.PEAK_HOURS:
            return PeakTariff()
        if hour in cls.OFF_PEAK_HOURS:
            return OffPeakTariff()
        return StandardTariff()
