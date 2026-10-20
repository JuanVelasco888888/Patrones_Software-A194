import json

from core.config_source import ConfigSource
from core.grid_configuration import GridConfiguration


class JSONConfigAdapter(ConfigSource):
    """Adapter de objeto: envuelve el JSON externo y expone ConfigSource."""

    def describe(self) -> str:
        return "JSON de utility (formato estándar exportado por SCADA)"

    def load(self, path: str) -> GridConfiguration:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Traducción de nombres de campo: el JSON externo usa 'generators',
        # 'label', 'cap_kw', mientras el interno espera 'sources_spec' con
        # tuplas (type, name, capacity_kw).
        sources_spec = [
            (g["type"], g["label"], float(g["cap_kw"]))
            for g in raw["generators"]
        ]

        return GridConfiguration(
            sources_spec=sources_spec,
            peak_threshold_kw=float(raw["thresholds"]["peak_kw"]),
            base_load_kw=float(raw["demand"]["off_peak_kw"]),
            peak_load_kw=float(raw["demand"]["on_peak_kw"]),
            seed=int(raw.get("random_seed", 42)),
        )