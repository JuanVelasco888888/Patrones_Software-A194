"""
tests/test_patterns.py
Pruebas simples (sin pytest, solo asserts) que demuestran que los dos
patrones de diseño exigidos funcionan como se espera.

Ejecutar con:  python3 -m tests.test_patterns
"""
from core.grid_monitor import GridMonitor
from energy_sources.factory import EnergySourceFactory
from energy_sources.sources import SolarSource, WindSource


def test_singleton_returns_same_instance():
    a = GridMonitor()
    b = GridMonitor()
    c = GridMonitor.instance()
    assert a is b is c, "GridMonitor debería ser siempre la misma instancia"
    print("OK: GridMonitor es Singleton (misma instancia siempre).")


def test_singleton_shares_state_across_references():
    monitor = GridMonitor.instance()
    monitor.reset()
    monitor.register_alert("prueba")

    otra_referencia = GridMonitor()
    assert otra_referencia.alerts == ["prueba"], \
        "El estado debe compartirse entre cualquier referencia al Singleton"
    print("OK: el estado del Singleton se comparte entre referencias.")


def test_factory_creates_correct_types():
    solar = EnergySourceFactory.create_source("solar", "Panel A", 10)
    eolica = EnergySourceFactory.create_source("eolica", "Turbina A", 10)

    assert isinstance(solar, SolarSource)
    assert isinstance(eolica, WindSource)
    print("OK: la fábrica crea el tipo de fuente correcto según el parámetro.")


def test_factory_rejects_unknown_type():
    try:
        EnergySourceFactory.create_source("nuclear", "Reactor X", 100)
        raise AssertionError("Debería haber lanzado ValueError para un tipo desconocido")
    except ValueError:
        print("OK: la fábrica rechaza tipos de fuente no registrados.")


def test_factory_can_be_extended_without_modifying_existing_code():
    from energy_sources.base import EnergySource, SourceCategory

    class GeothermalSource(EnergySource):
        def __init__(self, name, capacity_kw):
            super().__init__(name, capacity_kw, SourceCategory.RENOVABLE)

        def generate_output(self, hour):
            return self.capacity_kw * 0.85

    EnergySourceFactory.register_source_type("geotermica", GeothermalSource)
    nueva = EnergySourceFactory.create_source("geotermica", "Pozo 1", 15)

    assert isinstance(nueva, GeothermalSource)
    print("OK: la fábrica se puede extender con nuevos tipos sin tocar su código.")


if __name__ == "__main__":
    test_singleton_returns_same_instance()
    test_singleton_shares_state_across_references()
    test_factory_creates_correct_types()
    test_factory_rejects_unknown_type()
    test_factory_can_be_extended_without_modifying_existing_code()
    print("\nTodas las pruebas de patrones pasaron correctamente.")
