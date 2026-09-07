import random

VOLTAGE_NOMINAL = 220.0        # voltios, tensión nominal de referencia
VOLTAGE_TOLERANCE = 0.05       # +-5% se considera operación normal
BASE_TECHNICAL_LOSS = 0.03     # 3% de pérdida técnica "de línea base"


def simulate_electrical_metrics(hour: int, demand_kw: float, renewable_ratio: float) -> dict:

    # --- Voltaje: cae ligeramente bajo alta demanda y se vuelve más ---
    # --- ruidoso cuanto mayor es la proporción de renovables. ---
    caida_por_demanda = min(demand_kw / 100.0, 1.0) * 6.0  # hasta -6V bajo carga alta
    ruido_renovable = renewable_ratio * random.uniform(-8.0, 8.0)
    voltage = VOLTAGE_NOMINAL - caida_por_demanda + ruido_renovable

    # --- Corriente: relación simple P = V * I (aprox. resistivo) ---
    current = (demand_kw * 1000) / voltage if voltage > 0 else 0.0

    # --- Factor de potencia: nominal alto, se degrada con más renovable ---
    # --- y con demanda alta, con una probabilidad baja de caída fuerte. ---
    power_factor = max(
        0.70,
        min(0.99, random.uniform(0.90, 0.99) - renewable_ratio * 0.08)
    )
    if random.random() < 0.05:  # 5% de probabilidad de una caída puntual
        power_factor -= random.uniform(0.10, 0.20)
        power_factor = max(0.60, power_factor)

    # --- Pérdidas técnicas: base + extra proporcional al estrés de ---
    # --- corriente (pérdidas resistivas ~ I^2, simplificadas a lineales). ---
    estres_corriente = max(0.0, (current - 250) / 250)  # >250A empieza a "estresar"
    loss_fraction = BASE_TECHNICAL_LOSS + estres_corriente * 0.04
    technical_loss_kw = demand_kw * loss_fraction

    return {
        "voltage": voltage,
        "current": current,
        "power_factor": power_factor,
        "technical_loss_kw": technical_loss_kw,
    }
