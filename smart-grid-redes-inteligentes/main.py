"""Ejecuta la simulación desde la terminal (la interfaz gráfica está en streamlit_app.py).

Ejemplos:
    python main.py
    python main.py --config json --cobro horario --reportes
"""
import argparse

from billing.methods import BILLING_METHODS
from core.adapters import CSVConfigAdapter, JSONConfigAdapter
from core.grid_builder import GridBuilder
from core.smart_grid_facade import SmartGridFacade

COBROS = {"simple": "Precio simple", "horario": "Según el horario",
          "demanda": "Con cargo por el pico del día", "eficiencia": "Con recargo por mala eficiencia"}


def cargar_configuracion(origen: str):
    if origen == "json":
        return JSONConfigAdapter().load("configs/utility_example.json")
    if origen == "csv":
        return CSVConfigAdapter().load("configs/scada_example.csv")
    return GridBuilder.default_template()


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de red eléctrica inteligente")
    parser.add_argument("--config", choices=["base", "json", "csv"], default="base", help="origen de los datos de la red")
    parser.add_argument("--cobro", choices=list(COBROS), default="simple", help="forma de cobro")
    parser.add_argument("--perfil", choices=["residencial", "comercial", "industrial"], help="tipo de demanda")
    parser.add_argument("--flexible", type=float, default=0, help="%% de consumo que se mueve fuera del pico")
    parser.add_argument("--reportes", action="store_true", help="imprimir los reportes del día")
    args = parser.parse_args()

    calculo = BILLING_METHODS[COBROS[args.cobro]][0]()
    facade = SmartGridFacade(calculation=calculo, user_role="admin")
    billing, _ = facade.run_simulation_cycle(
        cargar_configuracion(args.config), verbose=True, use_flyweight=bool(args.perfil),
        profile_type=args.perfil or "comercial", flexible_load_pct=args.flexible)
    if args.reportes:
        for texto in facade.generate_reports(billing).values():
            print("\n" + texto)


if __name__ == "__main__":
    main()
