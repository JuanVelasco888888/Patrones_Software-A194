from core.grid_monitor import GridMonitor
from core.anomaly_detector import AnomalyDetector
from core.load_balancer import LoadBalancer
from energy_sources.factory import EnergySourceFactory
from billing.billing_system import SistemadeFacturacionDinamico
from simulation.electrical_simulator import simulate_electrical_metrics


def test_record_reading_is_backward_compatible():
    """La firma extendida de record_reading no debe romper llamadas viejas
    que solo pasaban hour/demand/generation."""
    monitor = GridMonitor.instance()
    monitor.reset()
    reading = monitor.record_reading(10, 50.0, 45.0)  # forma "vieja", sin metricas
    assert reading["voltage"] is None
    assert reading["technical_loss_kw"] is None
    assert reading["balance_kw"] == -5.0
    print("OK: record_reading sigue funcionando sin los parametros nuevos (compatibilidad).")


def test_record_reading_with_electrical_metrics():
    monitor = GridMonitor.instance()
    monitor.reset()
    reading = monitor.record_reading(
        10, 50.0, 45.0, voltage=218.5, current=210.3, power_factor=0.9,
        technical_loss_kw=1.5
    )
    assert reading["voltage"] == 218.5
    assert reading["power_factor"] == 0.9
    print("OK: record_reading guarda correctamente el estado electrico cuando se le pasa.")


def test_anomaly_detector_flags_low_voltage():
    detector = AnomalyDetector()
    anomalies = detector.detect(hour=5, voltage=190.0, current=100.0, power_factor=0.95)
    assert any("voltaje" in a.lower() for a in anomalies)
    print("OK: AnomalyDetector detecta voltaje fuera de rango.")


def test_anomaly_detector_no_false_positive_in_normal_range():
    detector = AnomalyDetector()
    anomalies = detector.detect(hour=5, voltage=220.0, current=100.0, power_factor=0.95)
    assert anomalies == []
    print("OK: AnomalyDetector no marca anomalias en condiciones normales.")


def test_electrical_simulator_returns_expected_keys():
    metrics = simulate_electrical_metrics(hour=12, demand_kw=50.0, renewable_ratio=0.5)
    for key in ("voltage", "current", "power_factor", "technical_loss_kw"):
        assert key in metrics
    print("OK: simulate_electrical_metrics devuelve las cuatro metricas esperadas.")


def test_billing_tracks_technical_losses():
    billing = SistemadeFacturacionDinamico()
    billing.record_technical_loss(hour=8, loss_kw=2.0, price_per_kwh=0.12)
    assert billing.total_technical_loss_kwh() == 2.0
    assert billing.total_technical_loss_cost() == 0.24
    print("OK: Sistema de Facturacion acumula perdidas tecnicas correctamente.")


def test_stabilize_voltage_only_acts_with_anomaly_and_high_renewable():
    monitor = GridMonitor.instance()
    monitor.reset()
    monitor.register_source(EnergySourceFactory.create_source("hidroelectrica", "Hidro Test", 20))
    monitor.register_source(EnergySourceFactory.create_source("termica", "Termica Test", 30))
    balancer = LoadBalancer(peak_threshold_kw=70)

    # Sin anomalias -> no deberia reforzar nada
    reinforcement = balancer.stabilize_voltage(hour=10, renewable_ratio=0.8, voltage_anomalies=[])
    assert reinforcement == 0.0

    # Con anomalia y alta proporcion renovable -> si deberia reforzar
    reinforcement = balancer.stabilize_voltage(
        hour=10, renewable_ratio=0.8, voltage_anomalies=["anomalia de prueba"]
    )
    assert reinforcement > 0.0
    print("OK: stabilize_voltage solo actua cuando hay anomalia y alta proporcion renovable.")


if __name__ == "__main__":
    test_record_reading_is_backward_compatible()
    test_record_reading_with_electrical_metrics()
    test_anomaly_detector_flags_low_voltage()
    test_anomaly_detector_no_false_positive_in_normal_range()
    test_electrical_simulator_returns_expected_keys()
    test_billing_tracks_technical_losses()
    test_stabilize_voltage_only_acts_with_anomaly_and_high_renewable()
    print("\nTodas las pruebas de las nuevas funcionalidades pasaron correctamente.")
