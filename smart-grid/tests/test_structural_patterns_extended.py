"""
Pruebas unitarias para los patrones estructurales nuevos:
Composite, Decorator, Facade, Flyweight y Proxy.
Mismo estilo que tests/test_structural_patterns.py (asserts + prints OK).
"""
from core.grid_composite import GridNode, GridSector, SourceLeaf
from core.grid_monitor_proxy import GridMonitorProxy
from core.grid_monitor import GridMonitor
from core.smart_grid_facade import SmartGridFacade
from core.grid_builder import GridBuilder
from core.grid_configuration import GridConfiguration

from energy_sources.factory import EnergySourceFactory
from energy_sources.base import EnergySource, SourceCategory

from billing.tariff import PeakTariff, StandardTariff
from billing.calculation import PerKWhCalculation, TimeOfUseCalculation
from billing.tariff_decorators import (
    TariffDecorator, RenewableDiscountDecorator, PeakSurchargeDecorator,
)
from billing.billing_system import DynamicBillingSystem

from simulation.consumption_flyweight import (
    ConsumptionProfile, ConsumptionProfileFactory,
)
from simulation.data_simulator import simulate_daily_demand_flyweight


# ============================================================
# COMPOSITE
# ============================================================

def test_composite_leaf_returns_generation():
    """Una hoja devuelve la generación de su fuente."""
    solar = EnergySourceFactory.create_source("solar", "Panel Test", 50)
    leaf = SourceLeaf(solar)
    # A las 12h, el solar genera al máximo
    assert leaf.get_generation(12) > 0
    print("OK: SourceLeaf devuelve la generación de su fuente.")


def test_composite_sector_sums_children():
    """Un sector suma recursivamente la generación de sus hijos."""
    sector = GridSector("Sector Test")
    solar = EnergySourceFactory.create_source("solar", "Panel A", 50)
    eolica = EnergySourceFactory.create_source("eolica", "Turbina B", 30)
    sector.add(SourceLeaf(solar))
    sector.add(SourceLeaf(eolica))

    # get_generation suma ambos hijos
    total = sector.get_generation(12)
    assert total > 0
    print(f"OK: GridSector suma la generación de sus hijos ({total:.2f} kW).")


def test_composite_nested_sectors():
    """Un sector puede contener otros sectores (anidamiento)."""
    root = GridSector("Red Completa")
    sub1 = GridSector("Sector Renovables")
    sub2 = GridSector("Sector Convencional")

    # Usamos ThermalSource porque es determinista
    termica1 = EnergySourceFactory.create_source("termica", "Planta A", 50)
    termica2 = EnergySourceFactory.create_source("termica", "Planta B", 80)

    sub1.add(SourceLeaf(termica1))
    sub2.add(SourceLeaf(termica2))
    root.add(sub1)
    root.add(sub2)

    gen_root = root.get_generation(12)
    gen_sub1 = sub1.get_generation(12)
    gen_sub2 = sub2.get_generation(12)

    assert gen_root == gen_sub1 + gen_sub2
    print(f"OK: Composite anidado funciona ({gen_root:.2f} = {gen_sub1:.2f} + {gen_sub2:.2f}).")

def test_composite_renewable_generation_only_renewables():
    """get_renewable_generation solo cuenta fuentes renovables."""
    sector = GridSector("Sector Test")
    solar = EnergySourceFactory.create_source("solar", "Panel A", 50)
    termica = EnergySourceFactory.create_source("termica", "Planta B", 80)
    sector.add(SourceLeaf(solar))
    sector.add(SourceLeaf(termica))

    renovable = sector.get_renewable_generation(12)
    total = sector.get_generation(12)

    assert renovable < total  # la térmica no es renovable
    print(f"OK: get_renewable_generation filtra solo renovables ({renovable:.2f} de {total:.2f}).")


def test_composite_get_all_sources_flattens_tree():
    """get_all_sources devuelve una lista plana de todas las fuentes."""
    root = GridSector("Red Completa")
    sub = GridSector("Sector Test")
    solar = EnergySourceFactory.create_source("solar", "Panel A", 50)
    eolica = EnergySourceFactory.create_source("eolica", "Turbina B", 30)
    sub.add(SourceLeaf(solar))
    sub.add(SourceLeaf(eolica))
    root.add(sub)

    sources = root.get_all_sources()
    assert len(sources) == 2
    print("OK: get_all_sources aplana el árbol en una lista plana.")


# ============================================================
# DECORATOR
# ============================================================

def test_decorator_renewable_discount():
    """RenewableDiscountDecorator aplica -10% si el ratio >= 0.7."""
    base = PeakTariff(PerKWhCalculation())
    decorated = RenewableDiscountDecorator(base, discount_rate=0.10)

    cost_base = base.compute_cost(50, 20, context={"renewable_ratio": 0.8})
    cost_dec = decorated.compute_cost(50, 20, context={"renewable_ratio": 0.8})

    assert cost_dec < cost_base
    print(f"OK: RenewableDiscount aplica descuento ({cost_dec:.2f} < {cost_base:.2f}).")


def test_decorator_peak_surcharge():
    """PeakSurchargeDecorator aplica +15% en horas pico (18-22)."""
    base = PeakTariff(PerKWhCalculation())
    decorated = PeakSurchargeDecorator(base, surcharge_rate=0.15)

    cost_base = base.compute_cost(50, 19, context={})
    cost_dec = decorated.compute_cost(50, 19, context={})

    assert cost_dec > cost_base
    print(f"OK: PeakSurcharge aplica recargo ({cost_dec:.2f} > {cost_base:.2f}).")


def test_decorator_does_not_apply_outside_conditions():
    """Los decoradores no aplican si las condiciones no se cumplen."""
    base = StandardTariff(PerKWhCalculation())
    decorated = RenewableDiscountDecorator(base, discount_rate=0.10)

    # Ratio renovable bajo → no aplica descuento
    cost_base = base.compute_cost(50, 12, context={"renewable_ratio": 0.3})
    cost_dec = decorated.compute_cost(50, 12, context={"renewable_ratio": 0.3})

    assert cost_dec == cost_base
    print("OK: Decorator no aplica si la condición no se cumple.")


def test_decorator_chains_multiple_layers():
    """Se pueden combinar varios decoradores (descuento + recargo)."""
    base = PeakTariff(PerKWhCalculation())
    decorated = PeakSurchargeDecorator(
        RenewableDiscountDecorator(base, discount_rate=0.10),
        surcharge_rate=0.15
    )

    # Hora pico Y ratio renovable alto → ambos aplican
    cost_base = base.compute_cost(50, 19, context={"renewable_ratio": 0.8})
    cost_dec = decorated.compute_cost(50, 19, context={"renewable_ratio": 0.8})

    assert cost_dec != cost_base
    print(f"OK: Combinación de decoradores ({cost_dec:.2f} vs {cost_base:.2f}).")


# ============================================================
# FACADE
# ============================================================

def test_facade_runs_full_simulation():
    """El Facade ejecuta un ciclo completo de simulación."""
    config = (
        GridBuilder()
        .add_source("solar", "Panel A", 40)
        .add_source("termica", "Planta B", 60)
        .set_peak_threshold(70)
        .build()
    )
    facade = SmartGridFacade(calculation=PerKWhCalculation(), user_role="admin")
    billing, monitor = facade.run_simulation_cycle(config, verbose=False)

    assert billing.total_cost() > 0
    assert len(monitor.get_history()) == 24
    print("OK: Facade ejecuta simulación completa (24h).")


def test_facade_exposes_composite_tree():
    """El Facade expone el árbol Composite para la UI."""
    config = (
        GridBuilder()
        .add_source("solar", "Panel A", 40)
        .add_source("termica", "Planta B", 60)
        .build()
    )
    facade = SmartGridFacade(user_role="admin")
    facade.run_simulation_cycle(config, verbose=False)

    assert facade.get_root_sector() is not None
    assert facade.get_sector_renovables() is not None
    assert facade.get_sector_convencional() is not None
    print("OK: Facade expone el árbol Composite.")


def test_facade_respects_proxy_role():
    """El Facade usa el Proxy y respeta el rol."""
    config = (
        GridBuilder()
        .add_source("solar", "Panel A", 40)
        .build()
    )
    # Invitado no puede registrar fuentes
    facade = SmartGridFacade(user_role="invitado")
    try:
        facade.run_simulation_cycle(config, verbose=False)
        raise AssertionError("Debería haber lanzado PermissionError")
    except PermissionError:
        print("OK: Facade respeta el rol del Proxy (invitado bloqueado).")


# ============================================================
# FLYWEIGHT
# ============================================================

def test_flyweight_returns_same_object():
    """Dos llamadas con el mismo perfil devuelven el mismo objeto."""
    p1 = ConsumptionProfileFactory.get_profile("comercial")
    p2 = ConsumptionProfileFactory.get_profile("comercial")
    assert p1 is p2
    print("OK: Flyweight devuelve el mismo objeto para el mismo perfil.")


def test_flyweight_different_profiles_are_different_objects():
    """Perfiles distintos devuelven objetos distintos."""
    p1 = ConsumptionProfileFactory.get_profile("residencial")
    p2 = ConsumptionProfileFactory.get_profile("industrial")
    assert p1 is not p2
    print("OK: Perfiles distintos son objetos distintos.")


def test_flyweight_stats_accumulate():
    """Los contadores hits/misses acumulan correctamente."""
    ConsumptionProfileFactory.reset_stats()
    ConsumptionProfileFactory.get_profile("comercial")   # miss
    ConsumptionProfileFactory.get_profile("comercial")   # hit
    ConsumptionProfileFactory.get_profile("comercial")   # hit

    stats = ConsumptionProfileFactory.stats()
    assert stats["perfiles_creados"] == 1
    assert stats["perfiles_reutilizados"] == 2
    print("OK: Stats acumulan hits y misses correctamente.")


def test_flyweight_extrinsic_state_varies():
    """El estado extrínseco (hora, seed) produce resultados distintos."""
    profile = ConsumptionProfileFactory.get_profile("comercial")
    d1 = profile.get_demand(12, seed=1)
    d2 = profile.get_demand(12, seed=2)
    assert d1 != d2
    print("OK: Estado extrínseco varía el resultado sin crear objetos nuevos.")


def test_flyweight_simulation_uses_cache():
    """La simulación Flyweight reutiliza el perfil entre llamadas."""
    ConsumptionProfileFactory.reset_stats()
    simulate_daily_demand_flyweight("comercial", seed=42)
    simulate_daily_demand_flyweight("comercial", seed=42)

    stats = ConsumptionProfileFactory.stats()
    assert stats["perfiles_creados"] == 1
    assert stats["perfiles_reutilizados"] >= 1
    print("OK: Simulación Flyweight reutiliza el perfil entre llamadas.")


# ============================================================
# PROXY
# ============================================================

def test_proxy_admin_can_register_sources():
    """Admin puede registrar fuentes."""
    proxy = GridMonitorProxy(user_role="admin")
    proxy.reset()  # admin puede resetear
    source = EnergySourceFactory.create_source("solar", "Panel Test", 40)
    proxy.register_source(source)
    assert len(proxy.sources) >= 1
    print("OK: Admin puede registrar fuentes.")


def test_proxy_operator_can_register_but_not_reset():
    """Operator puede registrar fuentes pero no resetear."""
    proxy = GridMonitorProxy(user_role="operator")
    source = EnergySourceFactory.create_source("solar", "Panel Test", 40)
    proxy.register_source(source)  # OK

    try:
        proxy.reset()
        raise AssertionError("Operator no debería poder resetear")
    except PermissionError:
        print("OK: Operator puede registrar pero no resetear.")


def test_proxy_invitado_cannot_register():
    """Invitado no puede registrar fuentes."""
    proxy = GridMonitorProxy(user_role="invitado")
    source = EnergySourceFactory.create_source("solar", "Panel Test", 40)

    try:
        proxy.register_source(source)
        raise AssertionError("Invitado no debería poder registrar")
    except PermissionError:
        print("OK: Invitado bloqueado al registrar fuentes.")


def test_proxy_invitado_can_read():
    """Invitado puede leer el historial y las alertas."""
    proxy = GridMonitorProxy(user_role="invitado")
    history = proxy.get_history()
    alerts = proxy.get_alerts()
    assert isinstance(history, list)
    assert isinstance(alerts, list)
    print("OK: Invitado puede leer historial y alertas.")


def test_proxy_all_roles_can_record_reading():
    """Todos los roles pueden registrar lecturas."""
    for role in ["admin", "operator", "invitado"]:
        proxy = GridMonitorProxy(user_role=role)
        reading = proxy.record_reading(10, 50, 45)
        assert reading["hour"] == 10
    print("OK: Todos los roles pueden registrar lecturas.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Composite
    test_composite_leaf_returns_generation()
    test_composite_sector_sums_children()
    test_composite_nested_sectors()
    test_composite_renewable_generation_only_renewables()
    test_composite_get_all_sources_flattens_tree()

    # Decorator
    test_decorator_renewable_discount()
    test_decorator_peak_surcharge()
    test_decorator_does_not_apply_outside_conditions()
    test_decorator_chains_multiple_layers()

    # Facade
    test_facade_runs_full_simulation()
    test_facade_exposes_composite_tree()
    test_facade_respects_proxy_role()

    # Flyweight
    test_flyweight_returns_same_object()
    test_flyweight_different_profiles_are_different_objects()
    test_flyweight_stats_accumulate()
    test_flyweight_extrinsic_state_varies()
    test_flyweight_simulation_uses_cache()

    # Proxy
    test_proxy_admin_can_register_sources()
    test_proxy_operator_can_register_but_not_reset()
    test_proxy_invitado_cannot_register()
    test_proxy_invitado_can_read()
    test_proxy_all_roles_can_record_reading()

    print("\nTodas las pruebas de los patrones estructurales nuevos pasaron correctamente.")