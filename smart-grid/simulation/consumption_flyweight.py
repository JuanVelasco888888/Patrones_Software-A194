import math
import random

class ConsumptionProfile:
    """Flyweight: Estado intrínseco compartido (curva de consumo base)."""
    def __init__(self, profile_type: str, base_load: float, peak_load: float):
        self.profile_type = profile_type
        self.base_load = base_load
        self.peak_load = peak_load
        # Pre-calculamos la curva de 24h para ahorrar CPU
        self.curve = self._generate_curve()

    def _generate_curve(self):
        curve = {}
        for hour in range(24):
            curva = (
                self.base_load
                + (self.peak_load - self.base_load) * max(0, math.sin(math.pi * (hour - 6) / 12))
                + 15 * max(0, math.sin(math.pi * (hour - 18) / 6))
            )
            curve[hour] = max(self.base_load * 0.5, curva)
        return curve

    def get_demand(self, hour: int, seed: int = 42) -> float:
        """El estado extrínseco (seed, hora) se pasa como parámetro."""
        random.seed(seed + hour)
        ruido = random.uniform(-3, 3)
        return round(self.curve[hour] + ruido, 2)


class ConsumptionProfileFactory:
    """Flyweight Factory: Cachea y reutiliza perfiles."""
    _profiles = {}
    _created_count = 0
    _reused_count = 0

    @classmethod
    def get_profile(cls, profile_type: str) -> ConsumptionProfile:
        if profile_type not in cls._profiles:
            if profile_type == "residencial":
                cls._profiles[profile_type] = ConsumptionProfile(
                    "residencial", 10, 30
                )
            elif profile_type == "comercial":
                cls._profiles[profile_type] = ConsumptionProfile(
                    "comercial", 30, 90
                )
            elif profile_type == "industrial":
                cls._profiles[profile_type] = ConsumptionProfile(
                    "industrial", 100, 300
                )
            else:
                raise ValueError(f"Perfil desconocido: {profile_type}")
            cls._created_count += 1
        else:
            cls._reused_count += 1

        return cls._profiles[profile_type]

    @classmethod
    def stats(cls) -> dict:
        """Devuelve las estadísticas requeridas por la interfaz de Streamlit."""
        return {
            "perfiles_creados": cls._created_count,
            "perfiles_reutilizados": cls._reused_count,
            "total_objetos_unicos": len(cls._profiles),
            "perfiles_en_cache": list(cls._profiles.keys()),
        }

    @classmethod
    def reset_stats(cls):
        """Reinicia la caché de perfiles Flyweight y sus contadores."""
        cls._profiles.clear()
        cls._created_count = 0
        cls._reused_count = 0