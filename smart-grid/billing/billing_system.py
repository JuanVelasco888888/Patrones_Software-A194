from .tariff_factory import TariffFactory
from .calculation import TariffCalculation
from .tariff_decorators import RenewableDiscountDecorator, PeakSurchargeDecorator


class DynamicBillingSystem:
    def __init__(self, calculation: TariffCalculation = None):
        self.calculation = calculation
        self.invoice_items = []
        self.technical_losses = []

    def bill_reading(self, hour: int, demand_kw: float,
                     generation_kw: float, renewable_kw: float,
                     power_factor: float = None) -> dict:
        renewable_ratio = (renewable_kw / generation_kw) if generation_kw else 0.0

        # 1. Crear la tarifa base con el Factory (Bridge)
        tariff = TariffFactory.create_tariff(
            hour, renewable_ratio, calculation=self.calculation
        )

        # 2. APLICAR DECORATORS dinámicamente (registramos cuáles se aplican)
        decoradores_aplicados = []
        if renewable_ratio >= 0.7:
            tariff = RenewableDiscountDecorator(tariff, discount_rate=0.10)
            decoradores_aplicados.append("Descuento renovable (-10%)")
        if 18 <= hour < 22:
            tariff = PeakSurchargeDecorator(tariff, surcharge_rate=0.15)
            decoradores_aplicados.append("Recargo pico (+15%)")

        # 3. Calcular el costo final (el Decorator ya aplicó sus ajustes)
        context = {"renewable_ratio": renewable_ratio}
        if power_factor is not None:
            context["power_factor"] = power_factor
        cost = tariff.compute_cost(demand_kw, hour, context=context)

        item = {
            "hour": hour,
            "demand_kwh": demand_kw,
            "tariff": tariff.name,
            "calculation": tariff.calculation.name,
            "price_per_kwh": tariff.price_per_kwh(),
            "cost": cost,
            "decorators": decoradores_aplicados if decoradores_aplicados else ["(ninguno)"],
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

    def summary_by_calculation(self) -> dict:
        summary = {}
        for item in self.invoice_items:
            summary.setdefault(item["calculation"], 0.0)
            summary[item["calculation"]] += item["cost"]
        return {k: round(v, 2) for k, v in summary.items()}

    # ---------- pérdidas técnicas ----------
    def record_technical_loss(self, hour: int, loss_kw: float,
                              price_per_kwh: float) -> dict:
        entry = {
            "hour": hour,
            "loss_kwh": round(loss_kw, 3),
            "estimated_cost": round(loss_kw * price_per_kwh, 4),
        }
        self.technical_losses.append(entry)
        return entry

    def total_technical_loss_kwh(self) -> float:
        return round(sum(e["loss_kwh"] for e in self.technical_losses), 2)

    def total_technical_loss_cost(self) -> float:
        return round(sum(e["estimated_cost"] for e in self.technical_losses), 2)