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
            if self.profile_type == "residencial":
                # Dos picos suaves: uno en la mañana (7:00) y otro en la noche (20:00)
                pico_manana = math.exp(-((hour - 7) ** 2) / 4.0)
                pico_noche = math.exp(-((hour - 20) ** 2) / 6.0)
                factor = 0.15 + 0.25 * pico_manana + 0.60 * pico_noche

            elif self.profile_type == "comercial":
                # Un pico ancho en horas de oficina (centro a las 13:00)
                pico_oficina = math.exp(-((hour - 13) ** 2) / 18.0)
                factor = 0.15 + 0.85 * pico_oficina

            else:  # industrial
                # Un pico muy ancho durante la producción (centro a las 12:00)
                pico_produccion = math.exp(-((hour - 12) ** 2) / 30.0)
                factor = 0.10 + 0.90 * pico_produccion

            curva = self.base_load + (self.peak_load - self.base_load) * factor
            curve[hour] = round(curva, 2)
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