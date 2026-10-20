"""
Pruebas de los patrones estructurales Adapter y Bridge aplicados a Smart Grid.
Mismo estilo que tests/test_patterns.py (asserts + prints OK).
"""
from core.config_source import ConfigSource
from core.adapters.json_config_adapter import JSONConfigAdapter
from core.adapters.csv_config_adapter import CSVConfigAdapter
from core.grid_configuration import GridConfiguration

from billing.calculation import (
    PerKWhCalculation, TimeOfUseCalculation,
    DemandChargeCalculation, ReactivePenaltyCalculation,
)
from billing.tariff import (
    PeakTariff, RenewableIncentiveTariff, StandardTariff,
)
from billing.tariff_factory import TariffFactory
from billing.billing_system import DynamicBillingSystem


# ---------- ADAPTER ----------

def test_json_adapter_returns_grid_configuration():
    adapter = JSONConfigAdapter()
    assert isinstance(adapter, ConfigSource)
    cfg = adapter.load("configs/utility_example.json")
    assert isinstance(cfg, GridConfiguration)
    assert len(cfg.sources_spec) == 4
    assert cfg.peak_threshold_kw == 85
    print("OK: JSONConfigAdapter traduce JSON externo a GridConfiguration.")


def test_csv_adapter_returns_grid_configuration():
    adapter = CSVConfigAdapter()
    cfg = adapter.load("configs/scada_example.csv")
    assert isinstance(cfg, GridConfiguration)
    assert len(cfg.sources_spec) == 4
    # 50000 W → 50 kW
    assert cfg.sources_spec[0][2] == 50.0
    assert cfg.peak_threshold_kw == 75
    print("OK: CSVConfigAdapter traduce CSV legacy (W → kW) a GridConfiguration.")


def test_adapters_are_interchangeable_under_same_interface():
    adapters = [JSONConfigAdapter(), CSVConfigAdapter()]
    for a in adapters:
        assert isinstance(a, ConfigSource)
        assert isinstance(a.describe(), str)
    print("OK: JSON y CSV son intercambiables bajo ConfigSource (Target).")


def test_adapter_preserves_internal_contract():
    """Los dos adapters producen el MISMO tipo, aunque vengan de formatos distintos."""
    json_cfg = JSONConfigAdapter().load("configs/utility_example.json")
    csv_cfg = CSVConfigAdapter().load("configs/scada_example.csv")
    for cfg in (json_cfg, csv_cfg):
        assert hasattr(cfg, "sources_spec")
        assert hasattr(cfg, "peak_threshold_kw")
        assert hasattr(cfg, "clone")  # Prototype sigue disponible
    print("OK: ambos Adapters respetan el contrato interno de GridConfiguration.")


# ---------- BRIDGE ----------

def test_any_tariff_combines_with_any_calculation():
    """El Bridge permite combinar 4 tarifas × 4 cálculos sin 16 clases."""
    tarifas = [PeakTariff, StandardTariff, RenewableIncentiveTariff]
    calculos = [PerKWhCalculation, TimeOfUseCalculation,
                DemandChargeCalculation, ReactivePenaltyCalculation]

    combinaciones = 0
    for t_cls in tarifas:
        for c in calculos:
            t = t_cls(c)
            assert t.calculation is c
            combinaciones += 1

    assert combinaciones == 12
    print(f"OK: 3 tarifas × 4 cálculos = {combinaciones} combinaciones, "
          f"resueltas con {len(tarifas) + len(calculos)} clases.")


def test_bridge_avoids_combinatorial_explosion():
    """Cuantifica la diferencia: herencia pura vs Bridge."""
    TARIFAS = 4
    CALCULOS = 4
    herencia_pura = TARIFAS * CALCULOS  # 16
    bridge = TARIFAS + CALCULOS          # 8
    assert bridge < herencia_pura
    print(f"OK: herencia pura = {herencia_pura} clases vs Bridge = {bridge} clases.")


def test_different_calculations_give_different_costs():
    """La misma tarifa con distintos cálculos produce montos distintos."""
    t_kwh = PeakTariff(PerKWhCalculation())
    t_tou = PeakTariff(TimeOfUseCalculation())
    t_dem = PeakTariff(DemandChargeCalculation(charge_per_kw=10.0))

    # hora punta (18) → TOU aplica factor 1.3
    cost_kwh = t_kwh.compute_cost(demand_kw=50.0, hour=18)
    cost_tou = t_tou.compute_cost(demand_kw=50.0, hour=18)
    cost_dem = t_dem.compute_cost(demand_kw=50.0, hour=23)  # se liquida al cierre

    assert cost_kwh != cost_tou
    assert cost_dem > cost_kwh  # incluye cargo por demanda
    print("OK: distintos cálculos sobre la misma tarifa dan costos distintos.")


def test_reactive_penalty_applies_only_when_pf_is_low():
    calc = ReactivePenaltyCalculation(min_pf=0.90, penalty_ratio=0.15)
    tariff = PeakTariff(calc)

    cost_ok = tariff.compute_cost(50.0, 20, context={"power_factor": 0.95})
    cost_bad = tariff.compute_cost(50.0, 20, context={"power_factor": 0.80})
    assert cost_bad > cost_ok
    print("OK: ReactivePenaltyCalculation solo penaliza si el FP está bajo.")


def test_billing_system_uses_bridge_end_to_end():
    """Integración: DynamicBillingSystem + TariffFactory + Bridge."""
    billing = DynamicBillingSystem(calculation=TimeOfUseCalculation())
    item = billing.bill_reading(
        hour=19, demand_kw=60.0, generation_kw=65.0, renewable_kw=50.0
    )
    assert item["calculation"] == "Tiempo de uso"
    assert item["tariff"] == "Incentivo renovable"  # renewable_ratio >= 0.7
    assert item["cost"] > 0

    # El resumen por cálculo expone el Bridge
    resumen = billing.summary_by_calculation()
    assert "Tiempo de uso" in resumen
    print("OK: DynamicBillingSystem aplica el Bridge de punta a punta.")


def test_billing_system_default_calculation_still_works():
    """Retrocompatibilidad: sin pasar calculation, usa PerKWhCalculation."""
    billing = DynamicBillingSystem()
    item = billing.bill_reading(10, 40.0, 45.0, 20.0)
    assert item["calculation"] == "Por kWh"
    print("OK: DynamicBillingSystem mantiene compatibilidad (cálculo por defecto).")


if __name__ == "__main__":
    # Adapter
    test_json_adapter_returns_grid_configuration()
    test_csv_adapter_returns_grid_configuration()
    test_adapters_are_interchangeable_under_same_interface()
    test_adapter_preserves_internal_contract()
    # Bridge
    test_any_tariff_combines_with_any_calculation()
    test_bridge_avoids_combinatorial_explosion()
    test_different_calculations_give_different_costs()
    test_reactive_penalty_applies_only_when_pf_is_low()
    test_billing_system_uses_bridge_end_to_end()
    test_billing_system_default_calculation_still_works()
    print("\nTodas las pruebas de Adapter y Bridge pasaron correctamente.")