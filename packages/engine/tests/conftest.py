from __future__ import annotations

from typing import Any

import pytest

from engine import Scenario

BASE_ASSUMPTIONS: dict[str, dict[str, Any]] = {
    "initial_cash": {"value": 0},
    "unit_price": {"value": 10},
    "unit_cost": {"value": 5},
    "fixed_costs_monthly": {"value": 0},
    "demand_mean_monthly": {"value": 10},
    "demand_cv": {"value": 0},
    "loss_rate": {"value": 0},
    "logistics_cost_per_unit": {"value": 0},
    "target_stock_months": {"value": 0},
    "reorder_lead_time_months": {"value": 1},
    "initial_stock": {"value": 100},
    "tax_rate": {"value": 0},
}


def make_scenario(
    *,
    assumptions: dict[str, dict[str, Any]] | None = None,
    omit: tuple[str, ...] = (),
    **overrides: Any,
) -> Scenario:
    merged = {**BASE_ASSUMPTIONS, **(assumptions or {})}
    for key in omit:
        merged.pop(key, None)
    payload: dict[str, Any] = {
        "name": "Scénario de test",
        "horizonMonths": 12,
        "assumptions": merged,
        **overrides,
    }
    return Scenario.model_validate(payload)


@pytest.fixture
def scenario_factory():
    return make_scenario
