from abc import ABC, abstractmethod
from energy_sources.base import EnergySource

class GridNode(ABC):
    """Component: Interfaz común para hojas (fuentes) y composites (sectores)."""
    @abstractmethod
    def get_demand(self, hour: int) -> float:
        pass

    @abstractmethod
    def get_generation(self, hour: int) -> float:
        pass

    @abstractmethod
    def get_renewable_generation(self, hour: int) -> float:
        pass

    @abstractmethod
    def get_all_sources(self) -> list:
        """Devuelve una lista plana de todas las fuentes (útil para el LoadBalancer)."""
        pass

class GridSector(GridNode):
    """Composite: Representa un sector de la red (ej. 'Sector Norte', 'Red Completa')."""
    def __init__(self, name: str):
        self.name = name
        self.children = []

    def add(self, node: GridNode):
        self.children.append(node)

    def remove(self, node: GridNode):
        self.children.remove(node)

    def get_demand(self, hour: int) -> float:
        # La demanda no se calcula en el árbol, se inyecta desde el simulador,
        # pero podemos devolver 0 o la suma de demandas si tuviéramos medidores.
        return 0.0 

    def get_generation(self, hour: int) -> float:
        """Suma recursiva de la generación de todos los hijos."""
        return sum(child.get_generation(hour) for child in self.children)

    def get_renewable_generation(self, hour: int) -> float:
        """Suma recursiva de la generación renovable de todos los hijos."""
        return sum(child.get_renewable_generation(hour) for child in self.children)

    def get_all_sources(self) -> list:
        """Recorre el árbol y devuelve una lista plana de todas las fuentes."""
        sources = []
        for child in self.children:
            if isinstance(child, GridSector):
                sources.extend(child.get_all_sources())
            else:
                sources.append(child)
        return sources


class SourceLeaf(GridNode):
    """Leaf: Envuelve una EnergySource para que cumpla con GridNode."""
    def __init__(self, source: EnergySource):
        self.source = source

    def get_demand(self, hour: int) -> float:
        return 0.0

    def get_generation(self, hour: int) -> float:
        return self.source.generate_output(hour)

    def get_renewable_generation(self, hour: int) -> float:
        if self.source.category.value == "renovable":
            return self.source.generate_output(hour)
        return 0.0

    def get_all_sources(self) -> list:
        return [self.source]