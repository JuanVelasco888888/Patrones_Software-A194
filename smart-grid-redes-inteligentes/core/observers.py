from core.events import EventKind, GridEvent, GridObserver


class DeficitObserver(GridObserver):
    """Observer del monitoreo en tiempo real: acumula las horas con generación < demanda.

    Por qué aquí: el monitor publica cada lectura y cada alerta apenas ocurren; quien
    necesite seguirlas (contadores del panel, reportes) se suscribe sin que el monitor
    sepa quiénes son. Así la detección temprana no depende de consultar el historial.
    """

    def __init__(self):
        self.deficit_hours = []
        self.total_deficit_kw = 0.0

    def update(self, event: GridEvent) -> None:
        if event.kind is EventKind.RESET:
            self.deficit_hours.clear()
            self.total_deficit_kw = 0.0
        elif event.kind is EventKind.READING and event.payload["balance_kw"] < 0:
            self.deficit_hours.append(event.payload["hour"])
            self.total_deficit_kw = round(
                self.total_deficit_kw - event.payload["balance_kw"], 2
            )


class AlertCountObserver(GridObserver):
    """Cuenta las alertas emitidas durante la simulacion."""

    def __init__(self):
        self.count = 0

    def update(self, event: GridEvent) -> None:
        if event.kind is EventKind.RESET:
            self.count = 0
        elif event.kind is EventKind.ALERT:
            self.count += 1
