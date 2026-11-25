from abc import ABC, abstractmethod


def _cover_deficit(hour: int, deficit_kw: float, sources) -> float:
    """Enciende fuentes de respaldo hasta cubrir el faltante. Devuelve los kW despachados."""
    dispatched = 0.0
    for source in sources:
        remaining = deficit_kw - dispatched
        if remaining <= 0:
            break
        dispatched += min(source.generate_output(hour), remaining)
    return dispatched


class DispatchStrategy(ABC):
    """Strategy: decide cuánta generación de respaldo se enciende cuando falta energía.

    Por qué aquí: el balanceo de carga puede seguir dos criterios opuestos: ahorrar
    (usar el respaldo caro solo si hace falta) o proteger (cubrir todo faltante para no
    dejar clientes sin energía). Cada criterio vive en su clase y se cambia en
    tiempo de ejecución, sin tocar el balanceador.
    """

    name = "Generica"

    @abstractmethod
    def dispatch_backup(self, hour: int, demand_kw: float, deficit_kw: float,
                        conventional: list, peak_threshold_kw: float) -> float:
        raise NotImplementedError


class PeakShavingStrategy(DispatchStrategy):
    """Ahorra respaldo: lo usa solo si hay un pico o si el faltante supera un margen tolerable.

    Un faltante pequeño (hasta `tolerance_ratio` de la demanda, 5 % por defecto) se acepta
    como margen normal de operación para no encender la planta más cara; uno mayor se cubre
    siempre, porque dejar clientes sin energía es una falla de la red.
    """

    name = "Gestion de picos"

    def __init__(self, tolerance_ratio: float = 0.05):
        self.tolerance_ratio = tolerance_ratio

    def dispatch_backup(self, hour, demand_kw, deficit_kw, conventional,
                        peak_threshold_kw):
        is_peak = demand_kw > peak_threshold_kw
        tolerable = deficit_kw <= demand_kw * self.tolerance_ratio
        if not is_peak and tolerable:
            return 0.0
        return _cover_deficit(hour, deficit_kw, conventional)


class FullCoverageStrategy(DispatchStrategy):
    """Protege la red: cubre cualquier faltante con respaldo, sin importar el límite de pico."""

    name = "Cobertura total"

    def dispatch_backup(self, hour, demand_kw, deficit_kw, conventional,
                        peak_threshold_kw):
        return _cover_deficit(hour, deficit_kw, conventional)
