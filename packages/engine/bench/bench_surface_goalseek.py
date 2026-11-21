from __future__ import annotations

import json
import time

from engine import AxisSpec, Lever, Objective, Scenario, __version__, goal_seek, surface


def make_scenario() -> Scenario:
    return Scenario.model_validate(
        {
            "name": "Banc phase 11",
            "horizonMonths": 12,
            "assumptions": {
                "initial_stock": {"value": 10_000},
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
                "tax_rate": {"value": 0},
            },
        }
    )


def measure(iteration: int) -> dict[str, object]:
    scenario = make_scenario()
    started = time.perf_counter()
    grid = surface(
        scenario,
        axis_x=AxisSpec(key="unit_price", minimum=10, maximum=20),
        axis_y=AxisSpec(key="unit_cost", minimum=4, maximum=8),
        metric="profit_p50",
        grid=(15, 15),
        runs=200,
        seed=42,
    )
    surface_wall_ms = (time.perf_counter() - started) * 1_000

    started = time.perf_counter()
    goal = goal_seek(
        scenario,
        Objective(metric="profit_p50", comparator=">=", target=1_200),
        [Lever(key="unit_price", minimum=10, maximum=20)],
        seed=42,
        max_evaluations=80,
        runs=500,
        confirm_quality="final",
        confirm_runs=5_000,
    )
    goal_wall_ms = (time.perf_counter() - started) * 1_000

    return {
        "iteration": iteration,
        "engineVersion": __version__,
        "surface": {
            "grid": grid.grid,
            "runsPerPoint": grid.runs,
            "cost": grid.cost,
            "durationMs": grid.duration_ms,
            "wallMs": surface_wall_ms,
        },
        "goalSeek": {
            "budget": 80,
            "runsPerEvaluation": 500,
            "confirmationRuns": 5_000,
            "evaluations": goal.evaluations,
            "wallMs": goal_wall_ms,
            "feasible": goal.feasible,
            "budgetExhausted": goal.budget_exhausted,
            "achieved": goal.achieved,
            "best": goal.best,
            "quality": goal.quality,
        },
    }


for iteration in (1, 2):
    print(json.dumps(measure(iteration), ensure_ascii=False))
