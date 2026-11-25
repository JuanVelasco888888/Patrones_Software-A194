import math

from core.access_control import (
    AccessPolicy, AuditLog, Permission, Role,
)
from core.grid_monitor import GridMonitor
from core.source_view import ReadOnlySource
from energy_sources.base import EnergySource

MAX_ALERT_LENGTH = 500


class GridMonitorProxy:
    """
    Proxy de proteccion del GridMonitor (Singleton).

    Seguridad:
      - Rol inmutable y normalizado (fail-closed: rol desconocido = GUEST).
      - Politica de permisos por rol, inyectable (AccessPolicy).
      - Toda operacion (permitida o denegada) queda en un AuditLog.
      - Lecturas devuelven copias/vistas: no se filtra estado mutable.
      - Validacion y saneamiento de entradas (tipos, rangos, log injection).
    """

    __slots__ = ("_monitor", "_role", "_policy", "_audit", "_sealed")

    def __init__(self, user_role=Role.GUEST, policy: AccessPolicy = None,
                 audit_log: AuditLog = None, monitor: GridMonitor = None):
        object.__setattr__(self, "_monitor", monitor or GridMonitor.instance())
        object.__setattr__(self, "_role", Role.parse(user_role))
        object.__setattr__(self, "_policy", policy or AccessPolicy())
        object.__setattr__(self, "_audit", audit_log or AuditLog())
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name, value):
        if getattr(self, "_sealed", False):
            raise AttributeError("GridMonitorProxy es inmutable tras crearse.")
        object.__setattr__(self, name, value)

    @property
    def role(self) -> Role:
        return self._role

    @property
    def user_role(self) -> str:
        return self._role.value

    # ---------- control de acceso ----------
    def authorize(self, permission: Permission, action: str) -> None:
        allowed = self._policy.is_allowed(self._role, permission)
        self._audit.record(self._role, action, allowed)
        if not allowed:
            raise PermissionError(
                f"El rol '{self._role.value}' no tiene permiso para "
                f"{permission.value}."
            )
    # ---------- escritura ----------
    def register_source(self, source) -> None:
        self.authorize(Permission.REGISTER_SOURCE, "register_source")
        if not isinstance(source, EnergySource):
            raise TypeError("Solo se pueden registrar instancias de EnergySource.")
        self._monitor.register_source(source)

    def set_source_active(self, name: str, active: bool) -> bool:
        self.authorize(Permission.MANAGE_SOURCES, "set_source_active")
        return self._monitor.set_source_active(name, bool(active))

    def record_reading(self, hour: int, demand_kw: float, generation_kw: float,
                       voltage: float = None, current: float = None,
                       power_factor: float = None,
                       technical_loss_kw: float = None) -> dict:
        self.authorize(Permission.WRITE_READING, "record_reading")
        self._validate_reading(hour, demand_kw, generation_kw)
        reading = self._monitor.record_reading(
            hour, demand_kw, generation_kw, voltage=voltage, current=current,
            power_factor=power_factor, technical_loss_kw=technical_loss_kw,
        )
        return dict(reading)

    def register_alert(self, message) -> None:
        self.authorize(Permission.WRITE_ALERT, "register_alert")
        self._monitor.register_alert(self._sanitize(message))

    def reset(self) -> None:
        self.authorize(Permission.RESET, "reset")
        self._monitor.reset()

    # ---------- Memento ----------
    def create_memento(self):
        self.authorize(Permission.SNAPSHOT_SAVE, "create_memento")
        return self._monitor.create_memento()

    def restore_memento(self, memento) -> None:
        self.authorize(Permission.SNAPSHOT_RESTORE, "restore_memento")
        self._monitor.restore_memento(memento)

        # ---------- lectura ----------
    def get_history(self) -> list:
        self.authorize(Permission.READ, "get_history")
        return [dict(r) for r in self._monitor.get_history()]

    def get_alerts(self) -> list:
        self.authorize(Permission.READ, "get_alerts")
        return self._monitor.get_alerts()

    @property
    def sources(self) -> tuple:
        self.authorize(Permission.READ, "sources")
        return tuple(ReadOnlySource(s) for s in self._monitor.sources)

    # ---------- Observer ----------
    def subscribe(self, observer) -> None:
        self.authorize(Permission.SUBSCRIBE, "subscribe")
        self._monitor.subscribe(observer)

    def unsubscribe(self, observer) -> None:
        self.authorize(Permission.SUBSCRIBE, "unsubscribe")
        self._monitor.unsubscribe(observer)

    # ---------- exportación ----------
    def export_snapshot(self) -> dict:
        """Devuelve copia exportable (solo lectura) para descargar desde la UI."""
        self.authorize(Permission.EXPORT, "export_snapshot")
        return {
            "history": [dict(r) for r in self._monitor.get_history()],
            "alerts": self._monitor.get_alerts(),
            "sources": [
                {"name": s.name, "capacity_kw": s.capacity_kw,
                 "category": s.category.value, "is_active": s.is_active}
                for s in self._monitor.sources
            ],
        }

    # ---------- validacion ----------
    @staticmethod
    def _validate_reading(hour, demand_kw, generation_kw) -> None:
        if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
            raise ValueError("hour debe ser un entero entre 0 y 23.")
        for label, value in (("demand_kw", demand_kw), ("generation_kw", generation_kw)):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise ValueError(f"{label} debe ser un numero finito >= 0.")

    @staticmethod
    def _sanitize(message) -> str:
        """Elimina saltos de linea/caracteres de control (log injection) y acota la longitud."""
        clean = "".join(ch if ch.isprintable() else " " for ch in str(message))
        clean = " ".join(clean.split())
        if not clean:
            raise ValueError("La alerta no puede estar vacia.")
        return clean[:MAX_ALERT_LENGTH]
    # ---------- auditoría ----------
    def audit_trail(self) -> tuple:
        """Admin ve todo; el resto ve solo sus propias entradas."""
        if self._policy.is_allowed(self._role, Permission.VIEW_AUDIT):
            self._audit.record(self._role, "audit_trail", True)
            return self._audit.entries()
        self.authorize(Permission.VIEW_OWN_AUDIT, "audit_trail")
        return self._audit.entries(role=self._role)
