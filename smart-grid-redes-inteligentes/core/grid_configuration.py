import copy


class GridConfiguration:
    def __init__(self, sources_spec=None, peak_threshold_kw: float = 70.0,
                 base_load_kw: float = 30.0, peak_load_kw: float = 90.0,
                 seed: int = 42):
        self.sources_spec = sources_spec if sources_spec is not None else []
        self.peak_threshold_kw = peak_threshold_kw
        self.base_load_kw = base_load_kw
        self.peak_load_kw = peak_load_kw
        self.seed = seed

    def clone(self, **overrides) -> "GridConfiguration":

        cloned = copy.deepcopy(self)
        for field, value in overrides.items():
            if not hasattr(cloned, field):
                raise AttributeError(
                    f"GridConfiguration no tiene el campo '{field}'"
                )
            setattr(cloned, field, value)
        return cloned

    def __repr__(self) -> str:
        return (f"<GridConfiguration fuentes={len(self.sources_spec)} "
                f"peak_threshold_kw={self.peak_threshold_kw} "
                f"base_load_kw={self.base_load_kw} "
                f"peak_load_kw={self.peak_load_kw} seed={self.seed}>")
