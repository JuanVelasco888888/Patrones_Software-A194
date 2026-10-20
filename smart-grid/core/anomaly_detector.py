from simulation.electrical_simulator import VOLTAGE_NOMINAL, VOLTAGE_TOLERANCE


class AnomalyDetector:
    def __init__(self,
                 voltage_nominal: float = VOLTAGE_NOMINAL,
                 voltage_tolerance: float = VOLTAGE_TOLERANCE,
                 min_power_factor: float = 0.85,
                 max_current_amp: float = 400.0):
        self.voltage_min = voltage_nominal * (1 - voltage_tolerance)
        self.voltage_max = voltage_nominal * (1 + voltage_tolerance)
        self.min_power_factor = min_power_factor
        self.max_current_amp = max_current_amp

    def detect(self, hour: int, voltage: float, current: float,
               power_factor: float) -> list:
        """Devuelve una lista de mensajes de anomalía (vacía si todo está
        dentro de rango normal)."""
        anomalies = []

        if voltage < self.voltage_min:
            anomalies.append(
                f"[Hora {hour:02d}] Anomalia de voltaje: caida a {voltage:.1f}V "
                f"(minimo aceptable {self.voltage_min:.1f}V)."
            )
        elif voltage > self.voltage_max:
            anomalies.append(
                f"[Hora {hour:02d}] Anomalia de voltaje: sobretension de {voltage:.1f}V "
                f"(maximo aceptable {self.voltage_max:.1f}V)."
            )

        if power_factor < self.min_power_factor:
            anomalies.append(
                f"[Hora {hour:02d}] Factor de potencia bajo: {power_factor:.2f} "
                f"(minimo esperado {self.min_power_factor:.2f})."
            )

        if current > self.max_current_amp:
            anomalies.append(
                f"[Hora {hour:02d}] Sobrecorriente detectada: {current:.1f}A "
                f"(limite {self.max_current_amp:.1f}A)."
            )

        return anomalies
