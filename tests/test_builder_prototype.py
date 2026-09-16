from core.grid_builder import GridBuilder
from core.grid_configuration import GridConfiguration
from core.grid_monitor import GridMonitor


def test_builder_assembles_configuration_step_by_step():
    config = (
        GridBuilder()
        .add_source("solar", "Panel A", 40)
        .add_source("eolica", "Turbina A", 25)
        .set_peak_threshold(80)
        .set_demand_curve(base_load_kw=20, peak_load_kw=100)
        .set_seed(7)
        .build()
    )
    assert config.sources_spec == [("solar", "Panel A", 40), ("eolica", "Turbina A", 25)]
    assert config.peak_threshold_kw == 80
    assert config.base_load_kw == 20
    assert config.peak_load_kw == 100
    assert config.seed == 7
    print("OK: GridBuilder ensambla la configuracion paso a paso correctamente.")


def test_builder_returns_independent_configurations():
    builder = GridBuilder()
    config_a = builder.add_source("solar", "Panel A", 40).build()
    config_b = builder.add_source("eolica", "Turbina A", 25).build()
    # config_a no debe verse afectada por lo agregado despues de construirla
    assert config_a.sources_spec == [("solar", "Panel A", 40)]
    assert config_b.sources_spec == [("solar", "Panel A", 40), ("eolica", "Turbina A", 25)]
    print("OK: cada build() entrega una configuracion independiente (copia de la lista).")


def test_clone_creates_independent_copy():
    base = GridConfiguration(sources_spec=[("solar", "Panel A", 40)], peak_threshold_kw=70)
    clone = base.clone(peak_threshold_kw=90)

    assert clone is not base
    assert clone.peak_threshold_kw == 90
    assert base.peak_threshold_kw == 70  # el original no cambia
    print("OK: clone() crea una copia independiente y respeta los overrides.")


def test_clone_does_not_share_mutable_state_with_original():
    base = GridConfiguration(sources_spec=[("solar", "Panel A", 40)])
    clone = base.clone()
    clone.sources_spec.append(("eolica", "Turbina B", 25))

    assert len(base.sources_spec) == 1, "Modificar el clon no debe afectar al original"
    assert len(clone.sources_spec) == 2
    print("OK: clone() usa deepcopy, sources_spec no queda compartida por referencia.")


def test_clone_rejects_unknown_field():
    base = GridConfiguration()
    try:
        base.clone(campo_inexistente=123)
        raise AssertionError("Deberia haber lanzado AttributeError")
    except AttributeError:
        print("OK: clone() rechaza overrides de campos que no existen.")


def test_prototype_never_clones_the_singleton():
    """Verifica explicitamente que clonar una configuracion NO crea una
    segunda instancia de GridMonitor -- el Singleton permanece unico."""
    monitor_antes = GridMonitor.instance()

    base = GridConfiguration(sources_spec=[("solar", "Panel A", 40)])
    _ = base.clone(peak_threshold_kw=99)  # clonar la configuracion, no el monitor

    monitor_despues = GridMonitor.instance()
    assert monitor_antes is monitor_despues
    print("OK: clonar una GridConfiguration no afecta ni duplica el GridMonitor (Singleton).")


if __name__ == "__main__":
    test_builder_assembles_configuration_step_by_step()
    test_builder_returns_independent_configurations()
    test_clone_creates_independent_copy()
    test_clone_does_not_share_mutable_state_with_original()
    test_clone_rejects_unknown_field()
    test_prototype_never_clones_the_singleton()
    print("\nTodas las pruebas de Builder y Prototype pasaron correctamente.")
