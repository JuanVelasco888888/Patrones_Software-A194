from abc import ABC, abstractmethod

from core.grid_configuration import GridConfiguration


class ConfigSource(ABC):
    """Target: interfaz que el cliente (main.py / streamlit_app.py) espera."""

    @abstractmethod
    def load(self, path: str) -> GridConfiguration:
        """Carga una configuración desde un origen externo y la traduce
        al formato interno GridConfiguration."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> str:
        """Devuelve una etiqueta legible del formato soportado."""
        raise NotImplementedError