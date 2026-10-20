"""
main.py
Sistema de Gestión de Redes Inteligentes (Smart Grid) - Prototipo base.

Patrones implementados:
  Creacionales:
    - Singleton  -> GridMonitor
    - Factory    -> EnergySourceFactory, TariffFactory
    - Builder    -> GridBuilder
    - Prototype  -> GridConfiguration.clone()
  Estructurales:
    - Adapter    -> ConfigSource (JSON, CSV)
    - Bridge     -> Tariff × TariffCalculation
    - Composite  -> GridSector / SourceLeaf
    - Decorator  -> TariffDecorators (RenewableDiscount, PeakSurcharge)
    - Facade     -> SmartGridFacade
    - Flyweight  -> ConsumptionProfileFactory
    - Proxy      -> GridMonitorProxy
"""
import argparse

from core.grid_builder import GridBuilder
from core.grid_configuration import GridConfiguration
from core.config_source import ConfigSource
from core.adapters import JSONConfigAdapter, CSVConfigAdapter
from core.smart_grid_facade import SmartGridFacade
from billing.calculation import (
    PerKWhCalculation, TimeOfUseCalculation,
    DemandChargeCalculation, ReactivePenaltyCalculation,
)


# ---------- selección de Adapter ----------
def config_source_for(kind: str) -> ConfigSource:
    """Factory sencilla de Adapters: el cliente solo conoce ConfigSource."""
    adapters = {
        "json": JSONConfigAdapter(),
        "csv":  CSVConfigAdapter(),
    }
    if kind not in adapters:
        raise ValueError(f"Formato no soportado: {kind}. "
                         f"Disponibles: {list(adapters.keys())}")
    return adapters[kind]


# ---------- selección de Implementor del Bridge ----------
def calculation_for(kind: str):
    calcs = {
        "kwh":      PerKWhCalculation(),
        "tou":      TimeOfUseCalculation(),
        "demand":   DemandChargeCalculation(charge_per_kw=5.0),
        "reactive": ReactivePenaltyCalculation(min_pf=0.90),
    }
    if kind not in calcs:
        raise ValueError(f"Cálculo no soportado: {kind}. "
                         f"Disponibles: {list(calcs.keys())}")
    return calcs[kind]


def default_configuration() -> GridConfiguration:
    """PATRON BUILDER: ensambla la configuracion base paso a paso."""
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


def run_scenario_comparison():
    """
    Demuestra Prototype clonando la configuración base y comparando
    el impacto de distintos cálculos tarifarios (Bridge + Decorator).
    """
    base_config = default_configuration()
    calculos = {
        "Por kWh":            PerKWhCalculation(),
        "Tiempo de uso":      TimeOfUseCalculation(),
        "Cargo por demanda":  DemandChargeCalculation(charge_per_kw=5.0),
        "Penalización react": ReactivePenaltyCalculation(min_pf=0.90),
    }

    print("\n" + "=" * 78)
    print("DEMO FACADE + BRIDGE + DECORATOR: MISMA RED, DISTINTOS CÁLCULOS")
    print("=" * 78)

    resultados = []
    for nombre, calc in calculos.items():
        # Usamos el Facade para simplificar toda la orquestación
        facade = SmartGridFacade(calculation=calc, user_role="admin")
        billing, monitor = facade.run_simulation_cycle(
            base_config, verbose=False
        )
        resultados.append({
            "calculo": nombre,
            "costo": billing.total_cost(),
            "alertas": len(monitor.get_alerts()),
        })

    for r in resultados:
        print(
            f"{r['calculo']:22s} | Costo: ${r['costo']:8.2f} | "
            f"Alertas: {r['alertas']}"
        )
    print("=" * 78)


def run_adapter_demo():
    """Demuestra el Adapter: dos formatos externos → misma configuración interna."""
    print("\n" + "=" * 78)
    print("DEMO ADAPTER: DISTINTOS FORMATOS, MISMA GridConfiguration")
    print("=" * 78)
    for kind, path in [("json", "configs/utility_example.json"),
                       ("csv",  "configs/scada_example.csv")]:
        adapter = config_source_for(kind)
        cfg = adapter.load(path)
        print(f"[{kind.upper()}] {adapter.describe()}")
        print(f"   -> {cfg}")
        print(f"   -> fuentes: {cfg.sources_spec}")
    print("=" * 78)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Grid CLI")
    parser.add_argument("--config", choices=["base", "json", "csv"],
                        default="base",
                        help="Origen de la configuración (Adapter).")
    parser.add_argument("--calc", choices=["kwh", "tou", "demand", "reactive"],
                        default="kwh",
                        help="Método de cálculo tarifario (Bridge).")
    parser.add_argument("--flyweight", action="store_true",
                        help="Usar perfiles de consumo compartidos (Flyweight).")
    args = parser.parse_args()

    if args.config == "base":
        config = default_configuration()
    else:
        config = config_source_for(args.config).load(
            "configs/utility_example.json" if args.config == "json"
            else "configs/scada_example.csv"
        )

    calc = calculation_for(args.calc)
    
    # Usamos el Facade para ejecutar la simulación
    facade = SmartGridFacade(calculation=calc, user_role="admin")
    billing, monitor = facade.run_simulation_cycle(
        config, verbose=True, use_flyweight=args.flyweight
    )

    # Demos opcionales
    run_adapter_demo()
    run_scenario_comparison()