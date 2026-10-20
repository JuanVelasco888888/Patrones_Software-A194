from core.grid_monitor import GridMonitor

class GridMonitorProxy:
    """Proxy: Controla el acceso al GridMonitor (Singleton)."""
    
    def __init__(self, user_role: str = "operator"):
        self._real_monitor = GridMonitor.instance()
        self.user_role = user_role

    def register_source(self, source):
        if self.user_role not in ["admin", "operator"]:
            raise PermissionError("Solo admin/operator pueden registrar fuentes.")
        self._real_monitor.register_source(source)

    def record_reading(self, *args, **kwargs):
        # Lectura permitida para todos
        return self._real_monitor.record_reading(*args, **kwargs)

    def reset(self):
        if self.user_role != "admin":
            raise PermissionError("Solo admin puede resetear el monitor.")
        self._real_monitor.reset()

    def register_alert(self, message):
        # Las alertas se pueden registrar automáticamente
        self._real_monitor.register_alert(message)

    def get_history(self):
        return self._real_monitor.get_history()

    def get_alerts(self):
        return self._real_monitor.alerts

    @property
    def sources(self):
        return self._real_monitor.sources