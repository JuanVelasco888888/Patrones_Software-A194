from .tariff_factory import TariffFactory


class SistemadeFacturacionDinamico:
    def __init__(self):
        self.invoice_items = []
        self.technical_losses = []

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

    # ---------- pérdidas técnicas (fugas de energía en transmisión) ----------
    def record_technical_loss(self, hour: int, loss_kw: float, price_per_kwh: float) -> dict:
        """
        Registra la energía perdida técnicamente en una hora (por ejemplo,
        por resistencia en las líneas bajo alta corriente). Es energía que
        la compañía generó y pagó, pero que nunca llegó al cliente ni se
        facturó: representa una pérdida financiera directa.
        """
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
