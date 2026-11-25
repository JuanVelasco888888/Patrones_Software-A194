from dataclasses import dataclass

from core.grid_state import GridSnapshot
from simulation.electrical_simulator import VOLTAGE_NOMINAL, simulate_electrical_metrics

# Con refuerzo estable completo, la desviación del voltaje respecto al nominal se reduce a la mitad.
STABILIZATION_DAMPING = 0.5
# Se refuerza cuando el voltaje se desvía más de este porcentaje del nominal (antes de salir de rango).
VOLTAGE_TRIGGER_RATIO = 0.02


@dataclass(frozen=True)
class HourTrace:
    strategy_name: str
    dispatched_by_source: tuple
    anomalies: tuple
    state_previous: str
    state_current: str
    peak_threshold_kw: float
    voltage_raw: float = None         # voltaje ANTES de estabilizar
    reinforcement_kw: float = 0.0     # kW de fuentes estables usados para estabilizar
    storage_charge_kw: float = 0.0    # excedente renovable guardado en baterías
    equipment_wear: float = 0.0       # mayor desgaste de equipos al cierre de la hora (0 a 1)


@dataclass(frozen=True)
class HourResult:
    reading: dict
    invoice_item: dict
    state_name: str
    trace: HourTrace


class GridOperationsMediator:
    """Mediator: coordina, hora por hora, balanceador, detector, facturación y estado de la red.

    Por qué aquí: procesar una hora exige que los cuatro módulos del sistema se hablen
    en un orden preciso (balancear → medir → detectar → estabilizar → registrar → facturar →
    evaluar el estado). Ninguno conoce a los demás: solo el mediador conoce la secuencia,
    así un cambio en un módulo no obliga a modificar a los otros.
    """

    def __init__(self, monitor, balancer, detector, billing, state_machine, root_sector,
                 strategy_override=None):
        self._monitor = monitor
        self._balancer = balancer
        self._detector = detector
        self._billing = billing
        self._state_machine = state_machine
        self._root_sector = root_sector
        # Si se indica, manda sobre la estrategia que propone el estado de la red.
        self._strategy_override = strategy_override

    def process_hour(self, hour: int, demand_kw: float) -> HourResult:
        previous_state_name = self._state_machine.state.name
        strategy = self._strategy_override or self._state_machine.state.dispatch_strategy
        self._balancer.set_strategy(strategy)

        dispatched = {}
        total_generation = self._balancer.balance(hour, demand_kw, trace=dispatched)
        renewable_generation = self._balancer.last_renewable_kw
        renewable_ratio = (renewable_generation / total_generation) if total_generation else 0.0

        metrics = simulate_electrical_metrics(hour, demand_kw, renewable_ratio)
        anomalies = self._detector.detect(
            hour, metrics["voltage"], metrics["current"], metrics["power_factor"],
            demand_kw=demand_kw, technical_loss_kw=metrics["technical_loss_kw"],
        )
        for message in anomalies:
            self._monitor.register_alert(message)

        raw_voltage = metrics["voltage"]
        error = raw_voltage - VOLTAGE_NOMINAL
        deviates = abs(error) > VOLTAGE_NOMINAL * VOLTAGE_TRIGGER_RATIO
        reinforcement = self._balancer.stabilize_voltage(
            hour, renewable_ratio, ["desviacion de voltaje"] if deviates else [],
            voltage_error=error,
        )
        voltage = raw_voltage
        if reinforcement > 0:
            damping = STABILIZATION_DAMPING * self._balancer.last_effectiveness
            voltage = VOLTAGE_NOMINAL + error * (1 - damping)

        wear = self._balancer.apply_current_stress(hour, metrics["current"])

        reading = self._monitor.record_reading(
            hour, demand_kw, total_generation,
            voltage=voltage, current=metrics["current"],
            power_factor=metrics["power_factor"],
            technical_loss_kw=metrics["technical_loss_kw"],
        )
        invoice_item = self._billing.bill_reading(
            hour, demand_kw, total_generation, renewable_generation,
            power_factor=metrics["power_factor"],
        )
        self._billing.record_technical_loss(
            hour, metrics["technical_loss_kw"], invoice_item["price_per_kwh"]
        )

        state = self._state_machine.update(GridSnapshot(
            hour, demand_kw, total_generation, len(anomalies),
            self._balancer.peak_threshold_kw,
        ))

        trace = HourTrace(
            strategy_name=strategy.name,
            dispatched_by_source=tuple(sorted(dispatched.items())),
            anomalies=tuple(anomalies),
            state_previous=previous_state_name,
            state_current=state.name,
            peak_threshold_kw=self._balancer.peak_threshold_kw,
            voltage_raw=round(raw_voltage, 2),
            reinforcement_kw=reinforcement,
            storage_charge_kw=round(self._balancer.last_charge_kw, 2),
            equipment_wear=round(wear, 4),
        )
        return HourResult(reading, invoice_item, state.name, trace)
