class ReadOnlySource:
    """Vista de solo lectura de una fuente: quien solo puede mirar no puede apagarla ni repararla."""

    __slots__ = ("_source",)

    def __init__(self, source):
        object.__setattr__(self, "_source", source)

    def __setattr__(self, name, value):
        raise AttributeError("ReadOnlySource es de solo lectura.")

    name = property(lambda self: self._source.name)
    capacity_kw = property(lambda self: self._source.capacity_kw)
    effective_capacity_kw = property(lambda self: self._source.effective_capacity_kw)
    category = property(lambda self: self._source.category)
    stability = property(lambda self: self._source.stability)
    is_active = property(lambda self: self._source.is_active)
    failed = property(lambda self: self._source.failed)
    failure_reason = property(lambda self: self._source.failure_reason)
    degradation = property(lambda self: self._source.degradation)
    is_storage = property(lambda self: self._source.is_storage)
    status_label = property(lambda self: self._source.status_label)

    @property
    def charge_level(self):
        return getattr(self._source, "charge_level", None)

    def generate_output(self, hour: int) -> float:
        return self._source.generate_output(hour)

    def __repr__(self) -> str:
        return f"<ReadOnlySource '{self.name}' cap={self.capacity_kw}kW>"
