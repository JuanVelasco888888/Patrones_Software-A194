from abc import ABC, abstractmethod


class GridVisitor(ABC):
    """Visitor: nuevas operaciones sobre el árbol de la red sin modificar sus clases.

    Por qué aquí: la red es un árbol de sectores y fuentes. Resúmenes como capacidad
    renovable instalada, fuentes fuera de servicio o salud de los equipos son operaciones
    distintas que recorren ese mismo árbol; cada una vive en su propio visitante y las
    clases de la red no cambian cuando aparece una nueva.
    """

    @abstractmethod
    def visit_sector(self, sector) -> None:
        raise NotImplementedError

    @abstractmethod
    def visit_source(self, leaf) -> None:
        raise NotImplementedError


class CapacityVisitor(GridVisitor):
    """Calcula la capacidad instalada total y renovable (integracion de renovables)."""

    def __init__(self):
        self.sector_count = 0
        self.total_kw = 0.0
        self.renewable_kw = 0.0
        self.storage_kw = 0.0

    def visit_sector(self, sector) -> None:
        self.sector_count += 1

    def visit_source(self, leaf) -> None:
        source = leaf.source
        if source.is_storage:
            self.storage_kw += source.capacity_kw
            return
        self.total_kw += source.capacity_kw
        if source.category.value == "renovable":
            self.renewable_kw += source.capacity_kw

    @property
    def renewable_share(self) -> float:
        return round(self.renewable_kw / self.total_kw, 4) if self.total_kw else 0.0


class InactiveSourcesVisitor(GridVisitor):
    """Lista las fuentes fuera de servicio (apoyo al balanceo de carga)."""

    def __init__(self):
        self.inactive = []

    def visit_sector(self, sector) -> None:
        pass

    def visit_source(self, leaf) -> None:
        if not leaf.source.is_active and not leaf.source.failed:
            self.inactive.append(leaf.source.name)


class EquipmentHealthVisitor(GridVisitor):
    """Revisa el estado de cada equipo: fallas y desgaste por sobrecarga (prevención de fallas)."""

    def __init__(self):
        self.rows = []

    def visit_sector(self, sector) -> None:
        pass

    def visit_source(self, leaf) -> None:
        s = leaf.source
        self.rows.append({
            "name": s.name, "capacity_kw": s.capacity_kw,
            "effective_kw": s.effective_capacity_kw, "wear": s.degradation,
            "status": s.status_label, "reason": s.failure_reason,
            "is_storage": s.is_storage,
            "charge_level": getattr(s, "charge_level", None),
        })

    @property
    def failed(self) -> list:
        return [r["name"] for r in self.rows if r["status"] == "falla"]

    @property
    def worst_wear(self) -> float:
        return max((r["wear"] for r in self.rows), default=0.0)
