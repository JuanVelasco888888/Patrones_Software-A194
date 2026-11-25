"""Objetivo 2: aplanar los picos de consumo moviendo demanda flexible a horas con holgura."""


def shift_peak_load(demand_by_hour: dict, threshold_kw: float, flexible_pct: float) -> dict:
    """Devuelve una curva de demanda nueva con los picos recortados.

    - Del consumo que pasa el limite de pico (threshold_kw), `flexible_pct` % se puede mover.
    - Ese consumo se reparte entre las horas que estan POR DEBAJO del limite, en proporcion
      a su holgura, sin llevarlas nunca por encima del limite (no se crean picos nuevos).
    - La energia total del dia se conserva (lo que sale de una hora entra en otra).
    """
    pct = max(0.0, min(100.0, float(flexible_pct))) / 100.0
    result = dict(demand_by_hour)
    if pct == 0:
        return result

    movable = {h: (d - threshold_kw) * pct for h, d in result.items() if d > threshold_kw}
    headroom = {h: threshold_kw - d for h, d in result.items() if d < threshold_kw}
    pool, room = sum(movable.values()), sum(headroom.values())
    if pool <= 0 or room <= 0:
        return result

    moved = min(pool, room)                 # si no hay holgura suficiente, se mueve menos
    for hour, amount in movable.items():
        result[hour] -= amount * (moved / pool)
    for hour, free in headroom.items():
        result[hour] += free * (moved / room)
    return {h: round(v, 2) for h, v in result.items()}
