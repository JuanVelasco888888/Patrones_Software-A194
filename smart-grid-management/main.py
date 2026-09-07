from core.grid_monitor import GridMonitor
from core.load_balancer import LoadBalancer
from core.anomaly_detector import AnomalyDetector
from energy_sources.factory import EnergySourceFactory
from billing.billing_system import SistemadeFacturacionDinamico
from simulation.data_simulator import simulate_daily_demand
from simulation.electrical_simulator import simulate_electrical_metrics


def build_grid() -> GridMonitor:
    """Crea las fuentes de energía con el Factory y las registra en el
    monitor único (Singleton)."""
    monitor = GridMonitor.instance()
    monitor.reset()  # estado limpio en cada ejecución de la demo

    sources_to_build = [
        ("solar", "Panel Solar Norte", 40),
        ("eolica", "Turbina Eolica 1", 25),
        ("hidroelectrica", "Mini Hidroelectrica", 20),
        ("termica", "Planta de Respaldo", 60),
    ]

    for source_type, name, capacity in sources_to_build:
        source = EnergySourceFactory.create_source(source_type, name, capacity)
        monitor.register_source(source)

    return monitor


def run_simulation() -> None:
    monitor = build_grid()
    balancer = LoadBalancer(peak_threshold_kw=70)
    detector = AnomalyDetector()
    billing = SistemadeFacturacionDinamico()

    demand_by_hour = simulate_daily_demand()

    print("=" * 78)
    print("SISTEMA DE GESTION DE REDES INTELIGENTES - SIMULACION DE 24 HORAS")
    print("=" * 78)
    print("Fuentes registradas en la red:")
    for s in monitor.sources:
        print(f"  - {s}")
    print("-" * 78)

    for hour, demand in demand_by_hour.items():
        total_generation = balancer.balance(hour, demand)
        renewable_generation = sum(
            s.generate_output(hour) for s in monitor.sources
            if s.category.value == "renovable"
        )
        renewable_ratio = (renewable_generation / total_generation) if total_generation else 0.0

        # --- Estado eléctrico de la red esta hora (voltaje, corriente, FP) ---
        metrics = simulate_electrical_metrics(hour, demand, renewable_ratio)
        anomalies = detector.detect(
            hour, metrics["voltage"], metrics["current"], metrics["power_factor"]
        )
        for msg in anomalies:
            monitor.register_alert(msg)

        # --- Estabilización: refuerzo de generación estable si hace falta ---
        balancer.stabilize_voltage(hour, renewable_ratio, anomalies)

        reading = monitor.record_reading(
            hour, demand, total_generation,
            voltage=metrics["voltage"], current=metrics["current"],
            power_factor=metrics["power_factor"],
            technical_loss_kw=metrics["technical_loss_kw"],
        )
        invoice_item = billing.bill_reading(
            hour, demand, total_generation, renewable_generation
        )
        billing.record_technical_loss(
            hour, metrics["technical_loss_kw"], invoice_item["price_per_kwh"]
        )

        status = "OK" if reading["balance_kw"] >= 0 else "DEFICIT"
        print(
            f"Hora {hour:02d}:00 | Demanda: {demand:6.2f} kW | "
            f"Generacion: {total_generation:6.2f} kW | "
            f"Balance: {reading['balance_kw']:7.2f} kW [{status:7s}] | "
            f"V: {metrics['voltage']:6.1f}V | FP: {metrics['power_factor']:.2f} | "
            f"Tarifa: {invoice_item['tariff']:18s} | Costo: ${invoice_item['cost']:.4f}"
        )

    print("-" * 78)
    if monitor.alerts:
        print("Alertas generadas durante el dia (picos, anomalias y estabilizacion):")
        for alert in monitor.alerts:
            print(f"  ! {alert}")
        print("-" * 78)

    print("Resumen de facturacion por tipo de tarifa:")
    for tariff_name, cost in billing.summary_by_tariff().items():
        print(f"  - {tariff_name:20s}: ${cost:.2f}")

    print(f"\nCOSTO TOTAL DEL DIA: ${billing.total_cost():.2f}")
    print(
        f"PERDIDAS TECNICAS ESTIMADAS: {billing.total_technical_loss_kwh():.2f} kWh "
        f"(${billing.total_technical_loss_cost():.2f})"
    )
    print("=" * 78)

    # Demostracion explicita de que GridMonitor es una unica instancia (Singleton)
    same_instance = GridMonitor() is GridMonitor.instance()
    print(f"\n¿GridMonitor es la misma instancia en todo el sistema? {same_instance}")


if __name__ == "__main__":
    run_simulation()
