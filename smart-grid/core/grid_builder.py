from core.grid_configuration import GridConfiguration


class GridBuilder:
    def __init__(self):
        self._sources_spec = []
        self._peak_threshold_kw = 70.0
        self._base_load_kw = 30.0
        self._peak_load_kw = 90.0
        self._seed = 42

    def add_source(self, source_type: str, name: str, capacity_kw: float) -> "GridBuilder":
        self._sources_spec.append((source_type, name, capacity_kw))
        return self

    def set_peak_threshold(self, kw: float) -> "GridBuilder":
        self._peak_threshold_kw = kw
        return self

    def set_demand_curve(self, base_load_kw: float, peak_load_kw: float) -> "GridBuilder":
        self._base_load_kw = base_load_kw
        self._peak_load_kw = peak_load_kw
        return self

    def set_seed(self, seed: int) -> "GridBuilder":
        self._seed = seed
        return self

    def build(self) -> GridConfiguration:
        return GridConfiguration(
            sources_spec=list(self._sources_spec),
            peak_threshold_kw=self._peak_threshold_kw,
            base_load_kw=self._base_load_kw,
            peak_load_kw=self._peak_load_kw,
            seed=self._seed,
        )
