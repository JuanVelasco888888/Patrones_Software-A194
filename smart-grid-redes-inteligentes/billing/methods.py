"""Formas de cobro disponibles y comparación de cuál deja mejor margen a la empresa."""
from billing.billing_system import DynamicBillingSystem
from billing.calculation import (
    DemandChargeCalculation, PerKWhCalculation, ReactivePenaltyCalculation,
    TimeOfUseCalculation,
)

PEAK_HOURS = range(18, 22)

# nombre visible -> (cómo crear el cálculo, explicación para el usuario)
BILLING_METHODS = {
    "Precio simple": (
        PerKWhCalculation,
        "Energía consumida × precio de esa hora. Es la forma más básica de cobrar.",
    ),
    "Según el horario": (
        TimeOfUseCalculation,
        "El precio cambia según la franja: más barato de madrugada (0 a 6 h) y "
        "más caro de 6 pm a 10 pm.",
    ),
    "Con cargo por el pico del día": (
        lambda: DemandChargeCalculation(charge_per_kw=5.0),
        "Además del consumo, se cobra un extra según el momento de mayor demanda del día.",
    ),
    "Con recargo por mala eficiencia": (
        lambda: ReactivePenaltyCalculation(min_pf=0.90),
        "Se suma un recargo cuando la energía se usa de forma poco eficiente "
        "(factor de potencia bajo).",
    ),
}


def method_name_of(calculation) -> str:
    """Nombre visible de la forma de cobro que corresponde a un cálculo (o None)."""
    if calculation is None:
        return "Precio simple"
    for name, (factory, _) in BILLING_METHODS.items():
        if type(factory()) is type(calculation):
            return name
    return None


def compare_methods(hour_results, renewable_names: set, source_types: dict) -> list:
    """Vuelve a facturar el mismo día con cada forma de cobro y ordena por margen.

    No toca la simulación en curso: solo recalcula el cobro con las lecturas ya registradas.
    """
    from core import analytics

    split = analytics.generation_split(hour_results, renewable_names)
    rows = []
    for name, (factory, _) in BILLING_METHODS.items():
        billing = DynamicBillingSystem(calculation=factory())
        for r, share in zip(hour_results, split):
            billing.bill_reading(
                r.reading["hour"], r.reading["demand_kw"], r.reading["generation_kw"],
                share["renewable_kw"], power_factor=r.reading["power_factor"],
            )
        profit = analytics.profitability(hour_results, billing, source_types)
        revenue = profit["revenue"]
        peak_revenue = sum(i["cost"] for i in billing.invoice_items if i["hour"] in PEAK_HOURS)
        rows.append({
            "method": name, "revenue": revenue, "generation_cost": profit["generation_cost"],
            "margin": profit["margin"], "margin_pct": profit["margin_pct"],
            "peak_revenue_share": peak_revenue / revenue if revenue else 0.0,
        })
    return sorted(rows, key=lambda row: row["margin"], reverse=True)
