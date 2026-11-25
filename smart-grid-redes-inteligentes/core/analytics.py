"""Indicadores del desempeño de la red durante el día (solo cálculos, sin interfaz)."""
import re
from statistics import pstdev

from simulation.electrical_simulator import VOLTAGE_NOMINAL

# Costo de generar 1 kWh segun el tipo de fuente (unidades de ejemplo, parametro academico).
GENERATION_COST_PER_KWH = {
    "SolarSource": 0.02, "WindSource": 0.03, "HydroSource": 0.04,
    "GeothermalSource": 0.05, "ThermalSource": 0.15, "BatterySource": 0.01,
}
DEFAULT_GENERATION_COST = 0.10
PEAK_HOURS = range(18, 22)

_ALERT_TYPES = (
    ("[falla]", "Falla de equipo"),
    ("pico de demanda", "Pico de demanda"),
    ("perdidas de energia", "Pérdidas elevadas"),
    ("estabilidad", "Estabilización de renovables"),
    ("voltaje", "Voltaje"),
    ("factor de potencia", "Eficiencia (factor de potencia)"),
    ("sobrecorriente", "Sobrecorriente"),
)


def load_stats(demand_by_hour: dict, threshold_kw: float) -> dict:
    """Qué tan 'picuda' es la curva de demanda."""
    if not demand_by_hour:
        return {"peak_kw": 0.0, "peak_hour": 0, "avg_kw": 0.0, "load_factor": 0.0,
                "hours_over_limit": 0, "excess_kwh": 0.0}
    values = list(demand_by_hour.values())
    peak, avg = max(values), sum(values) / len(values)
    return {
        "peak_kw": peak,
        "peak_hour": max(demand_by_hour, key=demand_by_hour.get),
        "avg_kw": avg,
        "load_factor": avg / peak if peak else 0.0,     # mas cerca de 1 = curva mas plana
        "hours_over_limit": sum(1 for v in values if v > threshold_kw),
        "excess_kwh": sum(max(0.0, v - threshold_kw) for v in values),
    }


def generation_split(hour_results, renewable_names) -> list:
    """Por hora, cuánto aporta lo renovable (incluye baterías) y cuánto el respaldo."""
    rows = []
    for r in hour_results:
        renewable = sum(kw for n, kw in r.trace.dispatched_by_source if n in renewable_names)
        backup = sum(kw for n, kw in r.trace.dispatched_by_source if n not in renewable_names)
        rows.append({"hour": r.reading["hour"], "renewable_kw": renewable, "backup_kw": backup})
    return rows


def renewable_energy_share(hour_results, renewable_names) -> float:
    split = generation_split(hour_results, renewable_names)
    renewable = sum(s["renewable_kw"] for s in split)
    total = renewable + sum(s["backup_kw"] for s in split)
    return renewable / total if total else 0.0


def voltage_stats(hour_results) -> dict:
    """Oscilación del voltaje sin y con estabilización."""
    raw, final = [], []
    for r in hour_results:
        v = r.reading.get("voltage")
        if v is None:
            continue
        final.append(v)
        raw.append(r.trace.voltage_raw if r.trace.voltage_raw is not None else v)
    if len(final) < 2:
        return {"raw_std": 0.0, "final_std": 0.0, "reduction_pct": 0.0,
                "raw_max_dev": 0.0, "final_max_dev": 0.0, "reinforced_hours": 0}
    raw_std, final_std = pstdev(raw), pstdev(final)
    return {
        "raw_std": raw_std, "final_std": final_std,
        "reduction_pct": (1 - final_std / raw_std) if raw_std else 0.0,
        "raw_max_dev": max(abs(v - VOLTAGE_NOMINAL) for v in raw),
        "final_max_dev": max(abs(v - VOLTAGE_NOMINAL) for v in final),
        "reinforced_hours": sum(1 for r in hour_results if r.trace.reinforcement_kw > 0),
    }


def profitability(hour_results, billing, source_types: dict) -> dict:
    """Ingresos por facturación menos costo de generar la energía."""
    revenue = billing.total_cost()
    generation_cost = sum(
        kw * GENERATION_COST_PER_KWH.get(source_types.get(name), DEFAULT_GENERATION_COST)
        for r in hour_results for name, kw in r.trace.dispatched_by_source
    )
    kwh_sold = sum(item["demand_kwh"] for item in billing.invoice_items)
    margin = revenue - generation_cost
    return {
        "revenue": revenue, "generation_cost": generation_cost, "margin": margin,
        "margin_pct": margin / revenue if revenue else 0.0,
        "kwh_sold": kwh_sold, "avg_price": revenue / kwh_sold if kwh_sold else 0.0,
    }


def consumption_by_tariff(billing) -> list:
    """Cuánta energía se vendió en cada tarifa y a qué costo."""
    rows = {}
    for item in billing.invoice_items:
        row = rows.setdefault(item["tariff"], {"tariff": item["tariff"], "kwh": 0.0, "cost": 0.0})
        row["kwh"] += item["demand_kwh"]
        row["cost"] += item["cost"]
    total = sum(r["kwh"] for r in rows.values())
    return [{**r, "share": r["kwh"] / total if total else 0.0} for r in rows.values()]


def peak_hours_share(billing) -> float:
    """Qué parte del consumo cae en la franja más cara (18 a 22 h)."""
    total = sum(i["demand_kwh"] for i in billing.invoice_items)
    peak = sum(i["demand_kwh"] for i in billing.invoice_items if i["hour"] in PEAK_HOURS)
    return peak / total if total else 0.0


def storage_summary(hour_results, battery_names) -> dict:
    """Cuánto excedente renovable se guardó en baterías y cuánto se entregó después."""
    charged = sum(r.trace.storage_charge_kw for r in hour_results)
    delivered = sum(kw for r in hour_results
                    for n, kw in r.trace.dispatched_by_source if n in battery_names)
    return {"charged_kwh": charged, "delivered_kwh": delivered,
            "has_storage": bool(battery_names)}


def equipment_wear_by_hour(hour_results) -> list:
    """Mayor desgaste de equipos al cierre de cada hora (0 a 1)."""
    return [{"hour": r.reading["hour"], "wear": r.trace.equipment_wear} for r in hour_results]


def classify_alerts(alerts) -> list:
    """Convierte los textos de alerta en filas (hora, tipo, detalle)."""
    rows = []
    for text in alerts:
        match = re.match(r"\[Hora (\d{2})\]", text) or re.search(r"\(hora (\d{2})\)", text)
        hour = int(match.group(1)) if match else None
        kind = next((label for key, label in _ALERT_TYPES if key in text.lower()), "Otro")
        detail = text.split("] ", 1)[-1] if text.startswith("[") else text
        rows.append({"hour": hour, "type": kind, "detail": detail})
    return rows
