from core.anomaly_chain import (
    CurrentCheck, ElectricalReading, LossCheck, PowerFactorCheck, VoltageCheck,
)
from simulation.electrical_simulator import VOLTAGE_NOMINAL, VOLTAGE_TOLERANCE


class AnomalyDetector:
    def __init__(self,
                 voltage_nominal: float = VOLTAGE_NOMINAL,
                 voltage_tolerance: float = VOLTAGE_TOLERANCE,
                 min_power_factor: float = 0.85,
                 max_current_amp: float = 400.0,
                 max_loss_ratio: float = 0.05):
        self.voltage_min = voltage_nominal * (1 - voltage_tolerance)
        self.voltage_max = voltage_nominal * (1 + voltage_tolerance)
        self.min_power_factor = min_power_factor
        self.max_current_amp = max_current_amp
        self.max_loss_ratio = max_loss_ratio
        self._chain = self._build_chain()

    def _build_chain(self) -> VoltageCheck:
        head = VoltageCheck(self.voltage_min, self.voltage_max)
        head.set_next(PowerFactorCheck(self.min_power_factor)) \
            .set_next(CurrentCheck(self.max_current_amp)) \
            .set_next(LossCheck(self.max_loss_ratio))
        return head

    def detect(self, hour: int, voltage: float, current: float,
               power_factor: float, demand_kw: float = 0.0,
               technical_loss_kw: float = 0.0) -> list:
        """Devuelve la lista de mensajes de anomalia (vacia si todo es normal)."""
        return self._chain.handle(
            ElectricalReading(hour, voltage, current, power_factor,
                              demand_kw, technical_loss_kw), []
        )
