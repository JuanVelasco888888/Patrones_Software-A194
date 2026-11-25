from collections.abc import Iterator
from typing import Callable, Iterable, Optional


class GridTreeIterator(Iterator):
    """Iterator: recorre las fuentes de la red en profundidad sin exponer cómo está organizada.

    Por qué aquí: el balanceador, los reportes y el panel necesitan "todas las fuentes" o
    "todas las lecturas con faltante" sin conocer si están en sectores anidados o en listas.
    """

    def __init__(self, root, leaves_only: bool = True):
        self._stack = [root]
        self._leaves_only = leaves_only

    def __next__(self):
        while self._stack:
            node = self._stack.pop()
            self._stack.extend(reversed(tuple(node.children)))
            if not self._leaves_only or node.is_leaf:
                return node
        raise StopIteration


class ReadingIterator(Iterator):
    """Iterator: recorre lecturas del monitor, opcionalmente filtradas."""

    def __init__(self, readings: Iterable[dict],
                 predicate: Optional[Callable[[dict], bool]] = None):
        self._readings = iter(tuple(readings))
        self._predicate = predicate or (lambda reading: True)

    def __next__(self):
        for reading in self._readings:
            if self._predicate(reading):
                return reading
        raise StopIteration


def deficit_readings(readings: Iterable[dict]) -> ReadingIterator:
    return ReadingIterator(readings, lambda r: r["balance_kw"] < 0)
