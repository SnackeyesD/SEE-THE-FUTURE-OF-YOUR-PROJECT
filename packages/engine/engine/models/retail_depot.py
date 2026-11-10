from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..errors import EngineError
from ..scenario import Hypothesis, Scenario
from .base import BatchResult, InputSpec

INPUT_SPECS: tuple[InputSpec, ...] = (
    InputSpec("initial_cash", "Trésorerie initiale", "FCFA", minimum=0.0),
    InputSpec("unit_price", "Prix de vente unitaire", "FCFA/unité", minimum=0.0),
    InputSpec("unit_cost", "Coût d'achat unitaire", "FCFA/unité", minimum=0.0),
    InputSpec("fixed_costs_monthly", "Coûts fixes mensuels", "FCFA/mois", minimum=0.0),
    InputSpec("demand_mean_monthly", "Demande moyenne mensuelle", "unités/mois", minimum=0.0),
    InputSpec(
        "demand_cv",
        "Coefficient de variation de la demande",
        "sans unité",
        minimum=0.0,
        maximum=5.0,
        default=0.2,
        required=False,
    ),
    InputSpec(
        "loss_rate",
        "Taux de perte mensuel du stock",
        "fraction",
        minimum=0.0,
        maximum=1.0,
        default=0.02,
        required=False,
    ),
    InputSpec(
        "logistics_cost_per_unit",
        "Coût logistique unitaire",
        "FCFA/unité",
        minimum=0.0,
        default=0.0,
        required=False,
    ),
    InputSpec(
        "target_stock_months",
        "Stock cible",
        "mois de demande",
        minimum=0.0,
        maximum=24.0,
        default=1.0,
        required=False,
    ),
    InputSpec(
        "reorder_lead_time_months",
        "Délai de réapprovisionnement",
        "mois",
        minimum=0.0,
        maximum=24.0,
        default=1.0,
        required=False,
    ),
    InputSpec(
        "initial_stock",
        "Stock initial",
        "unités",
        minimum=0.0,
        default=0.0,
        required=False,
    ),
    InputSpec(
        "tax_rate",
        "Taux d'imposition sur le bénéfice",
        "fraction",
        minimum=0.0,
        maximum=1.0,
        default=0.0,
        required=False,
    ),
)

INPUTS: dict[str, InputSpec] = {spec.key: spec for spec in INPUT_SPECS}

DEFAULT_SEASONALITY = np.ones(12, dtype=np.float64)


class RetailDepotModel:
    """Modèle d'un dépôt de revente avec stock, pertes et réapprovisionnement."""

    name = "retail_depot"

    def resolve(self, scenario: Scenario) -> dict[str, Hypothesis]:
        unknown = sorted(set(scenario.assumptions) - set(INPUTS))
        if unknown:
            raise EngineError(
                "hypothèses inconnues pour le modèle retail_depot: " + ", ".join(unknown)
            )

        resolved: dict[str, Hypothesis] = {}
        for spec in INPUT_SPECS:
            hypothesis = scenario.assumptions.get(spec.key)
            if hypothesis is None:
                if spec.required:
                    raise EngineError(f"hypothèse requise manquante: {spec.key}")
                assert spec.default is not None
                hypothesis = Hypothesis(value=spec.default)

            self._check_value(spec, hypothesis)
            resolved[spec.key] = hypothesis

        return resolved

    @staticmethod
    def _check_value(spec: InputSpec, hypothesis: Hypothesis) -> None:
        value = hypothesis.value
        if value < spec.minimum:
            raise EngineError(f"{spec.key}: la valeur {value} est inférieure à {spec.minimum}")
        if spec.maximum is not None and value > spec.maximum:
            raise EngineError(f"{spec.key}: la valeur {value} est supérieure à {spec.maximum}")
        if hypothesis.min is not None and value < hypothesis.min:
            raise EngineError(f"{spec.key}: la valeur {value} est inférieure à min")
        if hypothesis.max is not None and value > hypothesis.max:
            raise EngineError(f"{spec.key}: la valeur {value} est supérieure à max")

    def bounds(self, key: str) -> tuple[float, float | None]:
        spec = INPUTS[key]
        return spec.minimum, spec.maximum

    def simulate_batch(
        self,
        inputs: Mapping[str, np.ndarray],
        noise: np.ndarray,
        seasonality: np.ndarray,
    ) -> BatchResult:
        run_count, horizon = noise.shape
        if run_count == 0:
            raise ValueError("un lot de simulation ne peut pas être vide")

        price = inputs["unit_price"]
        cost = inputs["unit_cost"]
        fixed = inputs["fixed_costs_monthly"]
        demand_mean = inputs["demand_mean_monthly"]
        demand_cv = inputs["demand_cv"]
        loss_rate = inputs["loss_rate"]
        logistics_cost = inputs["logistics_cost_per_unit"]
        target_stock_months = inputs["target_stock_months"]
        lead_time = inputs["reorder_lead_time_months"]
        tax_rate = inputs["tax_rate"]

        sigma = np.sqrt(np.log1p(demand_cv**2))
        seasonal_series = seasonality[np.arange(horizon) % seasonality.shape[0]]

        max_lead = max(1, int(np.rint(lead_time).max(initial=1.0)))
        pipeline = np.zeros((run_count, max_lead + 1), dtype=np.float64)
        run_indices = np.arange(run_count)

        stock = np.array(inputs["initial_stock"], dtype=np.float64, copy=True)
        cash = np.array(inputs["initial_cash"], dtype=np.float64, copy=True)

        revenue_monthly = np.empty((run_count, horizon), dtype=np.float64)
        profit_monthly = np.empty((run_count, horizon), dtype=np.float64)
        demand_monthly = np.empty((run_count, horizon), dtype=np.float64)
        sold_monthly = np.empty((run_count, horizon), dtype=np.float64)
        stock_end_monthly = np.empty((run_count, horizon), dtype=np.float64)
        stockout_monthly = np.empty((run_count, horizon), dtype=np.float64)
        lost_monthly = np.empty((run_count, horizon), dtype=np.float64)
        tax_monthly = np.empty((run_count, horizon), dtype=np.float64)
        costs_monthly = np.empty((run_count, horizon), dtype=np.float64)

        for month in range(horizon):
            pipeline[:, :-1] = pipeline[:, 1:].copy()
            pipeline[:, -1] = 0.0
            arrivals = pipeline[:, 0].copy()

            stock = stock + arrivals
            lost = stock * loss_rate
            available = stock - lost
            stock = available

            seasonal = seasonal_series[month]
            demand = demand_mean * seasonal * np.exp(
                sigma * noise[:, month] - 0.5 * sigma**2
            )
            demand = np.maximum(demand, 0.0)
            sold = np.minimum(demand, available)
            stockout = demand > available
            stock_end = available - sold

            revenue = sold * price
            cogs = sold * cost
            logistics = sold * logistics_cost
            loss_cost = lost * cost
            taxable = revenue - cogs - logistics - fixed - loss_cost
            tax = np.maximum(taxable, 0.0) * tax_rate
            net = taxable - tax

            cash = cash + revenue - arrivals * cost - logistics - fixed - tax
            stock = stock_end

            revenue_monthly[:, month] = revenue
            profit_monthly[:, month] = net
            demand_monthly[:, month] = demand
            sold_monthly[:, month] = sold
            stock_end_monthly[:, month] = stock_end
            stockout_monthly[:, month] = stockout.astype(np.float64)
            lost_monthly[:, month] = lost
            tax_monthly[:, month] = tax
            costs_monthly[:, month] = cogs + logistics + fixed + loss_cost + tax

            target = demand_mean * seasonal * target_stock_months
            order_quantity = np.maximum(target - stock_end, 0.0)
            delay = np.clip(np.rint(lead_time).astype(np.int64), 1, max_lead)
            np.add.at(pipeline, (run_indices, delay), order_quantity)

        profit = profit_monthly.sum(axis=1)

        return BatchResult(
            profit=profit,
            revenue_monthly=revenue_monthly,
            profit_monthly=profit_monthly,
            demand_monthly=demand_monthly,
            sold_monthly=sold_monthly,
            stock_end_monthly=stock_end_monthly,
            stockout_monthly=stockout_monthly,
            lost_monthly=lost_monthly,
            tax_monthly=tax_monthly,
            costs_monthly=costs_monthly,
            cash_end=cash,
            inventory_value_end=stock_end_monthly[:, -1] * cost,
            units_sold=sold_monthly.sum(axis=1),
            units_lost=lost_monthly.sum(axis=1),
        )
