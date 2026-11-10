from __future__ import annotations

import numpy as np
import pytest

from engine import EngineError, SimulationConfig, simulate
from engine.models import get_model
from engine.models.retail_depot import INPUTS, RetailDepotModel


def test_required_assumptions_are_enforced(scenario_factory) -> None:
    scenario = scenario_factory(omit=("unit_price",))
    with pytest.raises(EngineError, match="unit_price"):
        RetailDepotModel().resolve(scenario)


def test_unknown_assumptions_are_rejected(scenario_factory) -> None:
    scenario = scenario_factory(assumptions={"mystery_parameter": {"value": 1}})
    with pytest.raises(EngineError, match="mystery_parameter"):
        RetailDepotModel().resolve(scenario)


def test_optional_assumptions_use_prudent_defaults(scenario_factory) -> None:
    scenario = scenario_factory(
        omit=("demand_cv", "loss_rate", "target_stock_months", "tax_rate")
    )
    resolved = get_model("retail_depot").resolve(scenario)
    assert resolved["demand_cv"].value == INPUTS["demand_cv"].default
    assert resolved["loss_rate"].value == INPUTS["loss_rate"].default
    assert resolved["target_stock_months"].value == INPUTS["target_stock_months"].default
    assert resolved["tax_rate"].value == INPUTS["tax_rate"].default


def test_values_outside_model_bounds_are_rejected(scenario_factory) -> None:
    scenario = scenario_factory(assumptions={"loss_rate": {"value": 1.5}})
    with pytest.raises(EngineError, match="loss_rate"):
        RetailDepotModel().resolve(scenario)


def test_one_month_deterministic_result_is_exact(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=1)
    result = simulate(scenario, SimulationConfig(runs=10, seed=1))

    assert result.metrics.mean_profit == pytest.approx(50.0)
    assert result.metrics.mean_revenue == pytest.approx(100.0)
    assert result.metrics.mean_costs == pytest.approx(50.0)
    assert result.metrics.mean_cash_end == pytest.approx(100.0)
    assert result.metrics.mean_units_sold == pytest.approx(10.0)
    assert result.metrics.loss_probability == 0.0
    assert result.metrics.mean_end_stock == pytest.approx(90.0)


def test_zero_stock_produces_stockouts_and_no_sales(scenario_factory) -> None:
    scenario = scenario_factory(
        horizonMonths=1,
        assumptions={"initial_stock": {"value": 0}, "target_stock_months": {"value": 0}},
    )
    result = simulate(scenario, SimulationConfig(runs=10, seed=1))

    assert result.metrics.mean_units_sold == pytest.approx(0.0)
    assert result.metrics.mean_profit == pytest.approx(0.0)
    assert result.metrics.mean_stockout_months == pytest.approx(1.0)


def test_full_loss_rate_destroys_inventory(scenario_factory) -> None:
    scenario = scenario_factory(
        horizonMonths=1,
        assumptions={"loss_rate": {"value": 1.0}},
    )
    result = simulate(scenario, SimulationConfig(runs=10, seed=1))

    assert result.metrics.mean_revenue == pytest.approx(0.0)
    assert result.metrics.mean_units_lost == pytest.approx(100.0)
    assert result.metrics.mean_profit == pytest.approx(-500.0)


def test_seasonality_changes_monthly_demand(scenario_factory) -> None:
    scenario = scenario_factory(
        horizonMonths=12,
        seasonality=[0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0],
    )
    result = simulate(scenario, SimulationConfig(runs=50, seed=3))
    demand = [month.mean_demand for month in result.monthly.values]
    assert demand[0] == pytest.approx(5.0)
    assert demand[-1] == pytest.approx(20.0)


def test_inventory_pipeline_can_run_out(scenario_factory) -> None:
    scenario = scenario_factory(
        horizonMonths=2,
        assumptions={
            "initial_stock": {"value": 0},
            "target_stock_months": {"value": 2},
            "demand_mean_monthly": {"value": 10},
            "reorder_lead_time_months": {"value": 1},
        },
    )
    result = simulate(scenario, SimulationConfig(runs=10, seed=1))
    assert result.monthly.values[0].mean_units_sold == pytest.approx(0.0)
    assert result.monthly.values[1].mean_units_sold == pytest.approx(10.0)
    assert result.metrics.mean_stockout_months == pytest.approx(1.0)


def test_batch_result_shapes_are_consistent(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=6)
    model = RetailDepotModel()
    inputs = {
        key: np.full(7, hypothesis.value)
        for key, hypothesis in model.resolve(scenario).items()
    }
    batch = model.simulate_batch(inputs, np.zeros((7, 6)), np.ones(12))
    assert batch.profit.shape == (7,)
    assert batch.revenue_monthly.shape == (7, 6)
    assert batch.cash_end.shape == (7,)
