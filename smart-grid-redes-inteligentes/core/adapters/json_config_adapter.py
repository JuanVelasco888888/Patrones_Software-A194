import json

from core.config_source import (
    ConfigFileError, ConfigSource, check_source_type, read_text_file,
    to_positive_number,
)
from core.grid_configuration import GridConfiguration


class JSONConfigAdapter(ConfigSource):
    """Adapter de objeto: envuelve el JSON externo y expone ConfigSource."""

    def describe(self) -> str:
        return "JSON de utility (formato estándar exportado por SCADA)"

    def load(self, path: str) -> GridConfiguration:
        return self.load_from_text(read_text_file(path))

    def load_from_text(self, text: str) -> GridConfiguration:
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise ConfigFileError(
                f"El archivo no es un JSON valido (linea {e.lineno}, columna {e.colno}): {e.msg}."
            ) from None
        if not isinstance(raw, dict):
            raise ConfigFileError("El JSON debe ser un objeto { ... } con 'generators', 'thresholds' y 'demand'.")

        generators = raw.get("generators")
        if not isinstance(generators, list) or not generators:
            raise ConfigFileError("Falta la lista 'generators' (o esta vacia): debe tener al menos una fuente.")

        # Traducción de nombres de campo: el JSON externo usa 'generators',
        # 'label', 'cap_kw', mientras el interno espera 'sources_spec' con
        # tuplas (type, name, capacity_kw).
        sources_spec = []
        for i, g in enumerate(generators, start=1):
            where = f"generators[{i}]"
            if not isinstance(g, dict):
                raise ConfigFileError(f"{where}: cada fuente debe ser un objeto con type, label y cap_kw.")
            missing = [k for k in ("type", "label", "cap_kw") if k not in g]
            if missing:
                raise ConfigFileError(f"{where}: faltan los campos {', '.join(missing)}.")
            sources_spec.append((
                check_source_type(g["type"], where),
                str(g["label"]).strip(),
                to_positive_number(g["cap_kw"], f"{where}.cap_kw"),
            ))

        names = [n for _, n, _ in sources_spec]
        duplicated = sorted({n for n in names if names.count(n) > 1})
        if duplicated:
            raise ConfigFileError(f"Hay fuentes con el mismo nombre: {', '.join(duplicated)}. Cada 'label' debe ser unico.")

        def section(name, key):
            block = raw.get(name)
            if not isinstance(block, dict) or key not in block:
                raise ConfigFileError(f"Falta '{name}.{key}'.")
            return to_positive_number(block[key], f"{name}.{key}")

        try:
            seed = int(raw.get("random_seed", 42))
        except (TypeError, ValueError):
            raise ConfigFileError("'random_seed' debe ser un numero entero.") from None

        return GridConfiguration(
            sources_spec=sources_spec,
            peak_threshold_kw=section("thresholds", "peak_kw"),
            base_load_kw=section("demand", "off_peak_kw"),
            peak_load_kw=section("demand", "on_peak_kw"),
            seed=seed,
        )
