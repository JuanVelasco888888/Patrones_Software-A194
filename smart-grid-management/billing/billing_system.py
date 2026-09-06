"""
billing/billing_system.py
Sistema de facturación dinámica: por cada lectura de consumo, pide a
TariffFactory la tarifa que corresponde y calcula el costo asociado.
"""
from .tariff_factory import TariffFactory


class SistemaDeFacturaciónDinámico:
    def __init__(self):
        self.invoice_items = []

    def bill_reading(self, hour: int, demand_kw: float,
                      generation_kw: float, renewable_kw: float) -> dict:
        renewable_ratio = (renewable_kw / generation_kw) if generation_kw else 0.0
        tariff = TariffFactory.create_tariff(hour, renewable_ratio)

        # Cada lectura representa 1 hora simulada -> kWh = kW * 1h
        cost = round(demand_kw * tariff.price_per_kwh(), 4)

        item = {
            "hour": hour,
            "demand_kwh": demand_kw,
            "tariff": tariff.name,
            "price_per_kwh": tariff.price_per_kwh(),
            "cost": cost,
        }
        self.invoice_items.append(item)
        return item

    def total_cost(self) -> float:
        return round(sum(item["cost"] for item in self.invoice_items), 2)

    def summary_by_tariff(self) -> dict:
        summary = {}
        for item in self.invoice_items:
            summary.setdefault(item["tariff"], 0.0)
            summary[item["tariff"]] += item["cost"]
        return {k: round(v, 2) for k, v in summary.items()}
