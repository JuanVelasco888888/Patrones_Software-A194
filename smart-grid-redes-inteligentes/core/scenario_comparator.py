from dataclasses import dataclass

from core.grid_configuration import GridConfiguration
from core.reports import BillingReport


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    config: GridConfiguration
    total_cost: float
    report: str
    delta_vs_base: float = 0.0


class ScenarioComparator:
    """
    Clona una configuración base (Prototype) y compara el costo de cada
    variante contra la base. No imprime: devuelve resultados estructurados
    para que CLI y Streamlit los presenten como prefieran.
    """

    def __init__(self, runner):
        # runner(config, verbose=False) -> (billing, monitor)
        self._runner = runner

    def compare(self, base_config: GridConfiguration,
                variants: dict) -> list:
        results = []
        billing_base, _ = self._runner(base_config)
        base = ScenarioResult(
            name="base",
            config=base_config,
            total_cost=billing_base.total_cost(),
            report=BillingReport(billing_base).generate(),
        )
        results.append(base)

        for name, overrides in variants.items():
            cfg = base_config.clone(**overrides)   # Prototype
            billing, _ = self._runner(cfg)
            results.append(ScenarioResult(
                name=name,
                config=cfg,
                total_cost=billing.total_cost(),
                report=BillingReport(billing).generate(),
                delta_vs_base=round(billing.total_cost() - base.total_cost, 2),
            ))
        return results
