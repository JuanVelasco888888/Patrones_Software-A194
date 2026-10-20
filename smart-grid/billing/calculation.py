from abc import ABC, abstractmethod


class TariffCalculation(ABC):
    """Implementor: define el contrato de cálculo de costo."""

    name = "Genérico"

    @abstractmethod
    def compute(self, demand_kw: float, hour: int,
                price_per_kwh: float, context: dict) -> float:
        raise NotImplementedError


class PerKWhCalculation(TariffCalculation):
    """Cálculo clásico: kWh consumidos × precio unitario."""
    name = "Por kWh"

    def compute(self, demand_kw, hour, price_per_kwh, context):
        return round(demand_kw * price_per_kwh, 4)


class TimeOfUseCalculation(TariffCalculation):
    """Cobro diferenciado por bloques horarios (TOU)."""
    name = "Tiempo de uso"

    BLOCKS = {
        "valle":    (range(0, 6),   0.8),
        "llano":    (range(6, 18),  1.0),
        "punta":    (range(18, 22), 1.3),
        "nocturno": (range(22, 24), 0.9),
    }

    def compute(self, demand_kw, hour, price_per_kwh, context):
        for _, (hours, factor) in self.BLOCKS.items():
            if hour in hours:
                return round(demand_kw * price_per_kwh * factor, 4)
        return round(demand_kw * price_per_kwh, 4)


class DemandChargeCalculation(TariffCalculation):
    """Cargo adicional por el pico máximo del día (demand charge)."""
    name = "Cargo por demanda"

    def __init__(self, charge_per_kw: float = 5.0):
        self.charge_per_kw = charge_per_kw
        self._peak_today = 0.0

    def compute(self, demand_kw, hour, price_per_kwh, context):
        self._peak_today = max(self._peak_today, demand_kw)
        base = demand_kw * price_per_kwh
        if hour == 23:  # se liquida al cierre del día
            base += self._peak_today * self.charge_per_kw
        return round(base, 4)

    def reset(self):
        self._peak_today = 0.0


class ReactivePenaltyCalculation(TariffCalculation):
    """Penaliza lecturas con factor de potencia bajo (cargo por reactiva)."""
    name = "Penalización reactiva"

    def __init__(self, min_pf: float = 0.90, penalty_ratio: float = 0.15):
        self.min_pf = min_pf
        self.penalty_ratio = penalty_ratio

    def compute(self, demand_kw, hour, price_per_kwh, context):
        base = demand_kw * price_per_kwh
        pf = context.get("power_factor", 1.0)
        if pf < self.min_pf:
            recargo = base * self.penalty_ratio * (self.min_pf - pf) / self.min_pf
            base += recargo
        return round(base, 4)