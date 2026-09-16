import math
import random


def simulate_daily_demand(base_load_kw: float = 30,
                           peak_load_kw: float = 90,
                           seed: int = 42) -> dict:
    """
    Genera 24 lecturas de demanda (una por hora, 0-23) con un patrón
    realista: consumo bajo de madrugada, un pico principal en el día
    y un pico secundario en la noche.
    """
    random.seed(seed)
    demand_by_hour = {}
    for hour in range(24):
        curva = (
            base_load_kw
            + (peak_load_kw - base_load_kw) * max(0, math.sin(math.pi * (hour - 6) / 12))
            + 15 * max(0, math.sin(math.pi * (hour - 18) / 6))
        )
        ruido = random.uniform(-3, 3)
        demand_by_hour[hour] = round(max(base_load_kw * 0.5, curva + ruido), 2)
    return demand_by_hour
