from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ElectricalReading:
    hour: int
    voltage: float
    current: float
    power_factor: float
    demand_kw: float = 0.0
    technical_loss_kw: float = 0.0


class AnomalyCheck(ABC):
    """
    Chain of Responsibility (variante pipeline) para el monitoreo de la red.

    Por que aqui: una lectura debe pasar por varias revisiones independientes
    (voltaje, eficiencia, corriente, perdidas). Cada eslabon revisa lo suyo y pasa
    la lectura al siguiente, asi se detectan temprano todas las anomalias a la vez y
    se puede agregar una revision nueva sin tocar las existentes.
    """

    def __init__(self):
        self._next = None

    def set_next(self, nxt: "AnomalyCheck") -> "AnomalyCheck":
        self._next = nxt
        return nxt

    def handle(self, reading: ElectricalReading, anomalies: list) -> list:
        anomalies.extend(self._check(reading))
        if self._next is None:
            return anomalies
        return self._next.handle(reading, anomalies)

    @abstractmethod
    def _check(self, reading: ElectricalReading) -> list:
        raise NotImplementedError


class VoltageCheck(AnomalyCheck):
    def __init__(self, voltage_min: float, voltage_max: float):
        super().__init__()
        self._min = voltage_min
        self._max = voltage_max

    def _check(self, r):
        if r.voltage < self._min:
            return [f"[Hora {r.hour:02d}] Anomalia de voltaje: caida a {r.voltage:.1f}V "
                    f"(minimo aceptable {self._min:.1f}V)."]
        if r.voltage > self._max:
            return [f"[Hora {r.hour:02d}] Anomalia de voltaje: sobretension de {r.voltage:.1f}V "
                    f"(maximo aceptable {self._max:.1f}V)."]
        return []


class PowerFactorCheck(AnomalyCheck):
    def __init__(self, min_power_factor: float):
        super().__init__()
        self._min = min_power_factor

    def _check(self, r):
        if r.power_factor < self._min:
            return [f"[Hora {r.hour:02d}] Factor de potencia bajo: {r.power_factor:.2f} "
                    f"(minimo esperado {self._min:.2f})."]
        return []


class CurrentCheck(AnomalyCheck):
    def __init__(self, max_current_amp: float):
        super().__init__()
        self._max = max_current_amp

    def _check(self, r):
        if r.current > self._max:
            return [f"[Hora {r.hour:02d}] Sobrecorriente detectada: {r.current:.1f}A "
                    f"(limite {self._max:.1f}A)."]
        return []


class LossCheck(AnomalyCheck):
    """Avisa cuando se pierde demasiada energia al transportarla (perdidas tecnicas)."""

    def __init__(self, max_loss_ratio: float):
        super().__init__()
        self._max = max_loss_ratio

    def _check(self, r):
        if r.demand_kw <= 0:
            return []
        ratio = r.technical_loss_kw / r.demand_kw
        if ratio > self._max:
            return [f"[Hora {r.hour:02d}] Perdidas de energia elevadas: {ratio:.1%} de la demanda "
                    f"({r.technical_loss_kw:.2f} kW, limite {self._max:.0%})."]
        return []
