"""
main.py
Sistema de Gestión de Redes Inteligentes (Smart Grid) - Prototipo base.

Cubre, de forma simulada y SIN dependencias de IoT/hardware externo,
los cuatro pilares planteados:

  1. Monitoreo de consumo energético en tiempo real -> core.GridMonitor (Singleton)
     + estado eléctrico (voltaje/corriente/factor de potencia) y
       detección de anomalías -> core.AnomalyDetector
  2. Balanceo de carga y gestión de picos            -> core.LoadBalancer
     + estabilización de voltaje ante variabilidad renovable -> LoadBalancer.stabilize_voltage
  3. Integración con energías renovables              -> energy_sources.EnergySourceFactory
  4. Sistema de facturación dinámica                  -> billing.DynamicBillingSystem + TariffFactory
     + seguimiento de pérdidas técnicas               -> DynamicBillingSystem.record_technical_loss

Además, demuestra dos patrones adicionales sobre la configuración de
entrada (sin tocar el Singleton en ningún momento):
  - Builder    -> core.GridBuilder ensambla la "receta" de un escenario
  - Prototype  -> GridConfiguration.clone() genera un segundo escenario
                  a partir del primero, para comparar resultados
"""
from core.grid_monitor import GridMonitor
from core.load_balancer import LoadBalancer
from core.anomaly_detector import AnomalyDetector
from core.grid_builder import GridBuilder
from core.grid_configuration import GridConfiguration
from energy_sources.factory import EnergySourceFactory
from billing.billing_system import DynamicBillingSystem
from simulation.data_simulator import simulate_daily_demand
from simulation.electrical_simulator import simulate_electrical_metrics


def default_configuration() -> GridConfiguration:
    """PATRON BUILDER: ensambla la configuracion base paso a paso, en vez
    de un constructor con varios parametros posicionales dificiles de
    ordenar a simple vista."""
    return (
        GridBuilder()
        .add_source("solar", "Panel Solar Norte", 40)
        .add_source("eolica", "Turbina Eolica 1", 25)
        .add_source("hidroelectrica", "Mini Hidroelectrica", 20)
        .add_source("termica", "Planta de Respaldo", 60)
        .set_peak_threshold(70)
        .set_demand_curve(base_load_kw=30, peak_load_kw=90)
        .set_seed(42)
        .build()
    )


def build_grid(config: GridConfiguration) -> GridMonitor:
    """Aplica una GridConfiguration sobre el monitor unico (Singleton):
    crea cada fuente con el Factory y la registra. GridMonitor.reset()
    limpia el estado anterior -- el Singleton nunca se duplica, solo se
    reutiliza para el siguiente escenario."""
    monitor = GridMonitor.instance()
    monitor.reset()

    for source_type, name, capacity in config.sources_spec:
        source = EnergySourceFactory.create_source(source_type, name, capacity)
        monitor.register_source(source)

    return monitor


def run_simulation(config: GridConfiguration, label: str, verbose: bool = True) -> dict:
    """Corre una simulacion de 24h para la configuracion dada y devuelve
    un resumen (para poder comparar escenarios generados con Prototype)."""
    monitor = build_grid(config)
    balancer = LoadBalancer(peak_threshold_kw=config.peak_threshold_kw)
    detector = AnomalyDetector()
    billing = DynamicBillingSystem()

    demand_by_hour = simulate_daily_demand(
        base_load_kw=config.base_load_kw,
        peak_load_kw=config.peak_load_kw,
        seed=config.seed,
    )

    if verbose:
        print("=" * 78)
        print(f"ESCENARIO: {label}")
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

        metrics = simulate_electrical_metrics(hour, demand, renewable_ratio)
        anomalies = detector.detect(
            hour, metrics["voltage"], metrics["current"], metrics["power_factor"]
        )
        for msg in anomalies:
            monitor.register_alert(msg)

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

        if verbose:
            status = "OK" if reading["balance_kw"] >= 0 else "DEFICIT"
            print(
                f"Hora {hour:02d}:00 | Demanda: {demand:6.2f} kW | "
                f"Generacion: {total_generation:6.2f} kW | "
                f"Balance: {reading['balance_kw']:7.2f} kW [{status:7s}] | "
                f"V: {metrics['voltage']:6.1f}V | FP: {metrics['power_factor']:.2f} | "
                f"Tarifa: {invoice_item['tariff']:18s} | Costo: ${invoice_item['cost']:.4f}"
            )

    if verbose:
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

    return {
        "label": label,
        "total_cost": billing.total_cost(),
        "technical_loss_kwh": billing.total_technical_loss_kwh(),
        "technical_loss_cost": billing.total_technical_loss_cost(),
        "alerts": len(monitor.alerts),
    }


def run_scenario_comparison() -> None:
    """Demuestra Prototype: clona la configuracion base para generar un
    segundo escenario (mas capacidad solar) y compara resultados, sin
    tocar en ningun momento el Singleton -- cada escenario corre por
    separado y GridMonitor se resetea entre uno y otro."""
    base_config = default_configuration()
    resumen_a = run_simulation(base_config, label="Base (configuracion original)")

    # PATRON PROTOTYPE: clonar la configuracion base y ajustar solo lo que
    # cambia, en vez de reconstruir todo desde cero con GridBuilder otra vez.
    escenario_b = base_config.clone(peak_threshold_kw=90)
    escenario_b.sources_spec = [
        (t, n, c * 1.5) if t == "solar" else (t, n, c)
        for (t, n, c) in escenario_b.sources_spec
    ]
    resumen_b = run_simulation(escenario_b, label="Clon (+50% capacidad solar, umbral 90kW)", verbose=False)

    print("\n" + "=" * 78)
    print("COMPARACION DE ESCENARIOS (misma instancia de GridMonitor, reutilizada)")
    print("=" * 78)
    for r in (resumen_a, resumen_b):
        print(
            f"{r['label']:45s} | Costo: ${r['total_cost']:8.2f} | "
            f"Perdidas: {r['technical_loss_kwh']:6.2f} kWh | Alertas: {r['alerts']}"
        )

    # Demostracion explicita de que GridMonitor sigue siendo una unica
    # instancia incluso despues de correr dos escenarios distintos.
    same_instance = GridMonitor() is GridMonitor.instance()
    print(f"\n¿GridMonitor sigue siendo la misma instancia tras ambos escenarios? {same_instance}")


if __name__ == "__main__":
    run_scenario_comparison()