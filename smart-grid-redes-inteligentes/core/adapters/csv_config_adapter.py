import csv
import io

from core.config_source import (
    ConfigFileError, ConfigSource, check_source_type, read_text_file,
    to_positive_number,
)
from core.grid_configuration import GridConfiguration


class CSVConfigAdapter(ConfigSource):
    """Adapter de objeto: envuelve un CSV legacy y expone ConfigSource."""

    def describe(self) -> str:
        return "CSV de SCADA legacy (columnas en español, potencia en W)"

    def load(self, path: str) -> GridConfiguration:
        return self.load_from_text(read_text_file(path))

    def load_from_text(self, text: str) -> GridConfiguration:
        sources_spec = []
        peak_threshold = 70.0
        base_load = 30.0
        peak_load = 90.0
        seed = 42

        lines = text.splitlines()
        if not lines or not lines[0].strip():
            raise ConfigFileError("El archivo CSV esta vacio.")
        # Excel en español guarda con ';'; otros programas usan ','.
        delimiter = ";" if lines[0].count(";") >= lines[0].count(",") else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        headers = {h.strip() for h in (reader.fieldnames or []) if h}
        if "tipo_fuente" not in headers or "nombre" not in headers or "potencia_w" not in headers:
            raise ConfigFileError(
                "La primera fila debe tener las columnas: tipo_fila;tipo_fuente;nombre;potencia_w;clave;valor "
                f"(se encontro: {', '.join(sorted(headers)) or 'nada'})."
            )

        for n, row in enumerate(reader, start=2):  # fila 1 = encabezado
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            where = f"Fila {n}"
            if row.get("tipo_fuente"):  # fila de fuente de energía
                if not row.get("nombre"):
                    raise ConfigFileError(f"{where}: falta el 'nombre' de la fuente.")
                cap_w = to_positive_number(row.get("potencia_w"), f"{where}, potencia_w")
                sources_spec.append((
                    check_source_type(row["tipo_fuente"], where),
                    row["nombre"],
                    cap_w / 1000.0,  # W → kW
                ))
            elif row.get("clave"):  # fila de parámetro
                clave = row["clave"].lower()
                valor = row.get("valor", "")
                if clave == "umbral_pico_kw":
                    peak_threshold = to_positive_number(valor, f"{where}, umbral_pico_kw")
                elif clave == "carga_base_kw":
                    base_load = to_positive_number(valor, f"{where}, carga_base_kw")
                elif clave == "carga_pico_kw":
                    peak_load = to_positive_number(valor, f"{where}, carga_pico_kw")
                elif clave == "semilla":
                    try:
                        seed = int(valor)
                    except ValueError:
                        raise ConfigFileError(f"{where}, semilla: '{valor}' no es un numero entero.") from None
                else:
                    raise ConfigFileError(
                        f"{where}: parametro desconocido '{row['clave']}'. "
                        "Validos: umbral_pico_kw, carga_base_kw, carga_pico_kw, semilla."
                    )

        if not sources_spec:
            raise ConfigFileError("El CSV no tiene ninguna fuente de energia (filas con tipo_fuente).")
        names = [n for _, n, _ in sources_spec]
        duplicated = sorted({n for n in names if names.count(n) > 1})
        if duplicated:
            raise ConfigFileError(f"Hay fuentes con el mismo nombre: {', '.join(duplicated)}.")

        return GridConfiguration(
            sources_spec=sources_spec,
            peak_threshold_kw=peak_threshold,
            base_load_kw=base_load,
            peak_load_kw=peak_load,
            seed=seed,
        )
