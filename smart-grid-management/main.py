"""
main.py
Sistema de Gestión de Redes Inteligentes (Smart Grid) - Prototipo base.

Cubre, de forma simulada y SIN dependencias de IoT/hardware externo,
los cuatro pilares planteados:

  1. Monitoreo de consumo energético en tiempo real -> core.GridMonitor (Singleton)
  2. Balanceo de carga y gestión de picos            -> core.LoadBalancer
  3. Integración con energías renovables              -> energy_sources.EnergySourceFactory
  4. Sistema de facturación dinámica                  -> billing.SistemaDeFacturaciónDinámico + TariffFactory
"""
from core.grid_monitor import GridMonitor
from core.load_balancer import LoadBalancer
from energy_sources.factory import EnergySourceFactory
from billing.billing_system import SistemaDeFacturaciónDinámico
from simulation.data_simulator import simulate_daily_demand


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
    balancer = LoadBalancer(peak_umbral_kw=70)
    billing = SistemaDeFacturaciónDinámico()

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

        reading = monitor.record_reading(hour, demand, total_generation)
        invoice_item = billing.bill_reading(
            hour, demand, total_generation, renewable_generation
        )

        status = "OK" if reading["balance_kw"] >= 0 else "DEFICIT"
        print(
            f"Hora {hour:02d}:00 | Demanda: {demand:6.2f} kW | "
            f"Generacion: {total_generation:6.2f} kW | "
            f"Balance: {reading['balance_kw']:7.2f} kW [{status:7s}] | "
            f"Tarifa: {invoice_item['tariff']:18s} | Costo: ${invoice_item['cost']:.4f}"
        )

    print("-" * 78)
    if monitor.alerts:
        print("Alertas de pico de demanda generadas durante el dia:")
        for alert in monitor.alerts:
            print(f"  ! {alert}")
        print("-" * 78)

    print("Resumen de facturacion por tipo de tarifa:")
    for tariff_name, cost in billing.summary_by_tariff().items():
        print(f"  - {tariff_name:20s}: ${cost:.2f}")

    print(f"\nCOSTO TOTAL DEL DIA: ${billing.total_cost():.2f}")
    print("=" * 78)

    # Demostracion explicita de que GridMonitor es una unica instancia (Singleton)
    same_instance = GridMonitor() is GridMonitor.instance()
    print(f"\n¿GridMonitor es la misma instancia en todo el sistema? {same_instance}")


if __name__ == "__main__":
    run_simulation()
