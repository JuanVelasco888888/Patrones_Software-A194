import csv

from core.config_source import ConfigSource
from core.grid_configuration import GridConfiguration


class CSVConfigAdapter(ConfigSource):
    """Adapter de objeto: envuelve un CSV legacy y expone ConfigSource."""

    def describe(self) -> str:
        return "CSV de SCADA legacy (columnas en español, potencia en W)"

    def load(self, path: str) -> GridConfiguration:
        sources_spec = []
        peak_threshold = 70.0
        base_load = 30.0
        peak_load = 90.0
        seed = 42

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                kind = row.get("tipo_fuente")
                if kind:  # fila de fuente de energía
                    cap_w = float(row["potencia_w"])
                    sources_spec.append((
                        kind.strip().lower(),
                        row["nombre"].strip(),
                        cap_w / 1000.0,  # W → kW
                    ))
                elif row.get("clave"):  # fila de parámetro
                    clave = row["clave"].strip().lower()
                    valor = row["valor"].strip()
                    if clave == "umbral_pico_kw":
                        peak_threshold = float(valor)
                    elif clave == "carga_base_kw":
                        base_load = float(valor)
                    elif clave == "carga_pico_kw":
                        peak_load = float(valor)
                    elif clave == "semilla":
                        seed = int(valor)

        return GridConfiguration(
            sources_spec=sources_spec,
            peak_threshold_kw=peak_threshold,
            base_load_kw=base_load,
            peak_load_kw=peak_load,
            seed=seed,
        )