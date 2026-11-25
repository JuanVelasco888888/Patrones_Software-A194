from abc import ABC, abstractmethod

from core.grid_iterators import deficit_readings


class GridReport(ABC):
    """Template Method: generate() fija el esqueleto del reporte; cada módulo rellena sus pasos.

    Por qué aquí: los reportes de operación, facturación y renovables siguen la misma
    secuencia (recolectar datos → calcular métricas → dar formato). El esqueleto se escribe
    una vez y cada módulo solo aporta lo suyo, con lo que todos se ven y se descargan igual.
    """

    title = "Reporte"

    def generate(self) -> str:
        data = self.collect_data()
        metrics = self.compute_metrics(data)
        lines = [self.header(), *self.format_body(metrics), self.footer()]
        return "\n".join(line for line in lines if line)

    @abstractmethod
    def collect_data(self):
        raise NotImplementedError

    @abstractmethod
    def compute_metrics(self, data) -> dict:
        raise NotImplementedError

    @abstractmethod
    def format_body(self, metrics: dict) -> list:
        raise NotImplementedError

    # Hooks con comportamiento por defecto
    def header(self) -> str:
        return f"=== {self.title} ==="

    def footer(self) -> str:
        return ""


class OperationReport(GridReport):
    """Monitoreo y balanceo: horas, deficits y alertas."""
    title = "Operacion de la red"

    def __init__(self, monitor):
        self._monitor = monitor

    def collect_data(self):
        return self._monitor.get_history(), self._monitor.get_alerts()

    def compute_metrics(self, data) -> dict:
        history, alerts = data
        balances = [r["balance_kw"] for r in history]
        return {
            "hours": len(history),
            "deficit_hours": [r["hour"] for r in deficit_readings(history)],
            "avg_balance_kw": round(sum(balances) / len(balances), 2) if balances else 0.0,
            "alerts": len(alerts),
        }

    def format_body(self, m) -> list:
        return [
            f"Horas simuladas: {m['hours']}",
            f"Balance promedio: {m['avg_balance_kw']} kW",
            f"Horas en deficit: {m['deficit_hours'] or 'ninguna'}",
            f"Alertas emitidas: {m['alerts']}",
        ]


class BillingReport(GridReport):
    """Facturacion dinamica: costo total, desglose por tarifa y perdidas."""
    title = "Facturacion dinamica"

    def __init__(self, billing):
        self._billing = billing

    def collect_data(self):
        return self._billing

    def compute_metrics(self, billing) -> dict:
        return {
            "total": billing.total_cost(),
            "by_tariff": billing.summary_by_tariff(),
            "loss_kwh": billing.total_technical_loss_kwh(),
            "loss_cost": billing.total_technical_loss_cost(),
        }

    def format_body(self, m) -> list:
        lines = [f"Costo total: ${m['total']:.2f}"]
        lines += [f"  - {name}: ${cost:.2f}" for name, cost in m["by_tariff"].items()]
        lines.append(f"Perdidas tecnicas: {m['loss_kwh']:.2f} kWh (${m['loss_cost']:.2f})")
        return lines


class RenewableReport(GridReport):
    """Integracion de renovables: aporte renovable sobre la generacion total."""
    title = "Energias renovables"

    def __init__(self, root_sector, hours=range(24)):
        self._root = root_sector
        self._hours = hours

    def collect_data(self):
        return [(self._root.get_renewable_generation(h), self._root.get_generation(h))
                for h in self._hours]

    def compute_metrics(self, data) -> dict:
        renewable = sum(r for r, _ in data)
        total = sum(t for _, t in data)
        return {"renewable": round(renewable, 2), "total": round(total, 2),
                "share": round(renewable / total, 4) if total else 0.0}

    def format_body(self, m) -> list:
        return [
            f"Generacion renovable potencial: {m['renewable']} kWh",
            f"Generacion total potencial: {m['total']} kWh",
            f"Participacion renovable: {m['share']:.1%}",
        ]

    def footer(self) -> str:
        return "(Valores estimados con la capacidad disponible de cada fuente)"
