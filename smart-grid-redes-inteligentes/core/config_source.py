from abc import ABC, abstractmethod
import math

from core.grid_configuration import GridConfiguration


class ConfigFileError(ValueError):
    """El archivo de configuracion tiene un problema que el usuario puede corregir."""


def decode_text(data: bytes) -> str:
    """Decodifica bytes subidos desde la UI (UTF-8, con o sin BOM; si no, latin-1 de Excel)."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def read_text_file(path: str) -> str:
    with open(path, "rb") as f:
        return decode_text(f.read())


def to_positive_number(value, label: str) -> float:
    try:
        number = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        raise ConfigFileError(f"{label}: '{value}' no es un numero.") from None
    if not math.isfinite(number) or number <= 0:
        raise ConfigFileError(f"{label}: debe ser un numero mayor que 0 (se recibio '{value}').")
    return number


def check_source_type(kind, where: str) -> str:
    from energy_sources.factory import EnergySourceFactory
    key = str(kind).strip().lower()
    valid = EnergySourceFactory.available_types()
    if key not in valid:
        raise ConfigFileError(
            f"{where}: el tipo de fuente '{kind}' no existe. Use uno de: {', '.join(valid)}."
        )
    return key


class ConfigSource(ABC):
    """Target: interfaz que el cliente (main.py / streamlit_app.py) espera."""

    @abstractmethod
    def load(self, path: str) -> GridConfiguration:
        """Carga una configuración desde un archivo y la traduce
        al formato interno GridConfiguration."""
        raise NotImplementedError

    def load_from_text(self, text: str) -> GridConfiguration:
        """Igual que load(), pero con el contenido ya leido (p. ej. archivo subido)."""
        raise NotImplementedError

    def load_from_bytes(self, data: bytes) -> GridConfiguration:
        return self.load_from_text(decode_text(data))

    @abstractmethod
    def describe(self) -> str:
        """Devuelve una etiqueta legible del formato soportado."""
        raise NotImplementedError
