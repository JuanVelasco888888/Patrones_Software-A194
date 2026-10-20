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
        """
        Crea una copia independiente de esta configuración. Usa deepcopy
        para que sources_spec (una lista) no quede compartida por
        referencia entre el original y el clon -- modificar el clon nunca
        debe afectar al original.

        overrides permite sobreescribir campos puntuales del clon sin
        tener que reconstruir toda la configuración desde cero, por
        ejemplo: base.clone(peak_threshold_kw=90).
        """
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
