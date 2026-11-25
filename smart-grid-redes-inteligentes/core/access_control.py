import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional, Union


class Role(Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    GUEST = "guest"

    @classmethod
    def parse(cls, value: Union["Role", str]) -> "Role":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return cls.GUEST


class Permission(Enum):
    # Lectura
    READ = "leer"
    SUBSCRIBE = "suscribirse a eventos en vivo"
    EXPORT = "exportar reportes y datos"
    VIEW_OWN_AUDIT = "ver la propia auditoria"
    # Escritura operativa
    WRITE_READING = "registrar lecturas"
    WRITE_ALERT = "registrar alertas"
    REGISTER_SOURCE = "registrar fuentes"
    MANAGE_SOURCES = "activar/desactivar fuentes"
    CONFIGURE = "cambiar la configuracion"
    RUN_SIMULATION = "ejecutar simulaciones"
    # Puntos de restauracion
    SNAPSHOT_SAVE = "guardar puntos de restauracion"
    SNAPSHOT_RESTORE = "restaurar puntos de restauracion"
    # Administracion
    RESET = "resetear el monitor"
    VIEW_AUDIT = "ver la auditoria completa"


# Operador: todo lo operativo, incluido reset/restore/auditoria completa.
# No existe hoy "gestión de usuarios", así que OPERATOR == ADMIN en permisos.
# Se deja la distinción explícita para cuando se añada gestión de cuentas.
_OPERATOR_PERMISSIONS = frozenset(Permission) - frozenset({Permission.RESET}) | \
                        frozenset({Permission.RESET, Permission.SNAPSHOT_RESTORE,
                                   Permission.VIEW_AUDIT, Permission.RUN_SIMULATION})

_GUEST_PERMISSIONS = frozenset({
    Permission.READ,
    Permission.SUBSCRIBE,
    Permission.EXPORT,
    Permission.VIEW_OWN_AUDIT,
})

DEFAULT_ROLE_PERMISSIONS: Mapping[Role, frozenset] = MappingProxyType({
    Role.ADMIN: frozenset(Permission),
    Role.OPERATOR: _OPERATOR_PERMISSIONS,
    Role.GUEST: _GUEST_PERMISSIONS,
})


class AccessPolicy:
    def __init__(self, role_permissions: Optional[Mapping[Role, frozenset]] = None):
        self._role_permissions = role_permissions or DEFAULT_ROLE_PERMISSIONS

    def is_allowed(self, role: Role, permission: Permission) -> bool:
        return permission in self._role_permissions.get(role, frozenset())


@dataclass(frozen=True)
class AuditEntry:
    timestamp: str
    role: str
    action: str
    allowed: bool


class AuditLog:
    """Bitácora acotada, segura entre hilos, con vistas filtradas por rol."""

    def __init__(self, max_entries: int = 1000):
        self._entries = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def record(self, role: Role, action: str, allowed: bool) -> None:
        entry = AuditEntry(datetime.now().isoformat(timespec="seconds"),
                           role.value, action, allowed)
        with self._lock:
            self._entries.append(entry)

    def entries(self, role: Optional[Role] = None) -> tuple:
        """Si se pasa `role`, devuelve solo las entradas de ese rol."""
        with self._lock:
            snapshot = tuple(self._entries)
        if role is None:
            return snapshot
        return tuple(e for e in snapshot if e.role == role.value)
