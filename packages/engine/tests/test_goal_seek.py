"""Tests de la phase 11 : recherche d'objectif."""

from __future__ import annotations

import pytest

from engine import (
    CancelToken,
    EngineError,
    Lever,
    Objective,
    Scenario,
    SimulationCancelled,
    goal_seek,
    simulate,
)


def _deterministic_scenario(scenario_factory) -> Scenario:
    """Profit annuel = 120 × (prix − coût), sans aléa."""

    return scenario_factory(
        horizonMonths=12,
        assumptions={
            "initial_stock": {"value": 10_000},
            "initial_cash": {"value": 0},
            "unit_price": {"value": 10},
            "unit_cost": {"value": 5},
            "demand_mean_monthly": {"value": 10},
            "demand_cv": {"value": 0},
            "loss_rate": {"value": 0},
            "fixed_costs_monthly": {"value": 0},
            "logistics_cost_per_unit": {"value": 0},
            "target_stock_months": {"value": 0},
        },
    )


def test_goal_seek_single_lever_reaches_target(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = goal_seek(
        scenario,
        Objective(metric="profit_p50", comparator=">=", target=1_200),
        [Lever(key="unit_price", minimum=10, maximum=20)],
        runs=20,
        seed=5,
        confirm_quality=None,
    )

    assert result.feasible is True
    assert result.achieved == pytest.approx(1_200)
    assert result.best["unit_price"] == pytest.approx(15)
    assert result.budget_exhausted is False
    assert result.metric == "profit_p50"
    assert result.comparator == ">="
    assert result.quality == "draft"
    assert "Objectif atteint" in result.message


def test_goal_seek_single_lever_refines_the_threshold(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = goal_seek(
        scenario,
        Objective(metric="profit_p50", comparator=">=", target=1_000),
        [Lever(key="unit_price", minimum=10, maximum=20)],
        runs=20,
        confirm_quality=None,
    )

    assert result.feasible is True
    # Le premier point faisable est 15 (1 200) : le raffinement doit s'en
    # approcher sans jamais franchir la cible.
    assert result.best["unit_price"] == pytest.approx(13.333, abs=0.02)
    assert result.achieved >= 1_000


def test_goal_seek_unreachable_target_is_reported_honestly(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = goal_seek(
        scenario,
        Objective(metric="profit_p50", comparator=">=", target=5_000),
        [Lever(key="unit_price", minimum=10, maximum=20)],
        runs=20,
        confirm_quality=None,
    )

    assert result.feasible is False
    assert result.best["unit_price"] == pytest.approx(20)
    assert result.achieved == pytest.approx(1_800)
    assert result.gap > 0
    assert result.budget_exhausted is False
    assert "non atteignable" in result.message
    assert "Objectif atteint" not in result.message


def test_goal_seek_budget_exhaustion_is_distinct_from_infeasibility(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = goal_seek(
        scenario,
        Objective(metric="profit_p50", comparator=">=", target=1_300),
        [
            Lever(key="unit_price", minimum=10, maximum=20),
            Lever(key="demand_mean_monthly", minimum=5, maximum=15),
        ],
        runs=10,
        max_evaluations=2,
        confirm_quality=None,
    )

    assert result.evaluations == 2
    assert result.feasible is False
    assert result.budget_exhausted is True
    assert "Budget" in result.message
    assert "non atteignable" not in result.message


def test_goal_seek_compass_search_with_two_levers(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = goal_seek(
        scenario,
        Objective(metric="profit_p50", comparator=">=", target=1_200),
        [
            Lever(key="unit_price", minimum=10, maximum=20),
            Lever(key="demand_mean_monthly", minimum=5, maximum=15),
        ],
        runs=20,
        confirm_quality=None,
    )

    assert result.feasible is True
    assert result.achieved >= 1_200
    assert set(result.best) == {"unit_price", "demand_mean_monthly"}
    assert result.evaluations <= 80


def test_goal_seek_handles_less_or_equal_comparator(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = goal_seek(
        scenario,
        Objective(metric="break_even_months_p50", comparator="<=", target=6),
        [Lever(key="unit_price", minimum=10, maximum=20)],
        runs=20,
        confirm_quality=None,
    )

    assert result.feasible is True
    assert result.achieved <= 6
    assert result.gap <= 0


def test_goal_seek_confirmation_overrides_the_draft_value(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = goal_seek(
        scenario,
        Objective(metric="profit_p50", comparator=">=", target=1_200),
        [Lever(key="unit_price", minimum=10, maximum=20)],
        runs=20,
        confirm_quality="final",
        confirm_runs=50,
    )

    assert result.quality == "final"
    assert result.achieved == pytest.approx(1_200)


def test_goal_seek_is_deterministic(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    objective = Objective(metric="profit_p50", comparator=">=", target=1_000)
    levers = [Lever(key="unit_price", minimum=10, maximum=20)]

    first = goal_seek(scenario, objective, levers, runs=20, seed=77, confirm_quality=None)
    second = goal_seek(scenario, objective, levers, runs=20, seed=77, confirm_quality=None)

    assert first.best == second.best
    assert first.achieved == second.achieved
    assert [entry.value for entry in first.trace] == [
        entry.value for entry in second.trace
    ]


def test_goal_seek_progress_stays_within_the_budget(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    progress: list[tuple[int, int]] = []
    result = goal_seek(
        scenario,
        Objective(metric="profit_p50", comparator=">=", target=1_200),
        [Lever(key="unit_price", minimum=10, maximum=20)],
        runs=20,
        max_evaluations=40,
        on_progress=lambda done, total: progress.append((done, total)),
        confirm_quality=None,
    )

    assert progress[0] == (0, 40)
    assert progress[-1][0] == result.evaluations
    assert [done for done, _ in progress] == sorted(done for done, _ in progress)
    assert all(done <= total == 40 for done, total in progress)


def test_goal_seek_cancellation(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    cancel = CancelToken()
    cancel.cancel()
    with pytest.raises(SimulationCancelled):
        goal_seek(
            scenario,
            Objective(metric="profit_p50", comparator=">=", target=1_000),
            [Lever(key="unit_price", minimum=10, maximum=20)],
            cancel=cancel,
            confirm_quality=None,
        )


def test_goal_seek_rejects_locked_or_unknown_levers(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    objective = Objective(metric="profit_p50", comparator=">=", target=1_000)

    with pytest.raises(EngineError):
        goal_seek(
            scenario,
            objective,
            [Lever(key="unit_price", minimum=10, maximum=20)],
            locked=["unit_price"],
            confirm_quality=None,
        )
    with pytest.raises(EngineError):
        goal_seek(
            scenario,
            objective,
            [Lever(key="unknown", minimum=1, maximum=2)],
            confirm_quality=None,
        )
    with pytest.raises(EngineError):
        goal_seek(scenario, objective, [], confirm_quality=None)
    with pytest.raises(EngineError):
        goal_seek(
            scenario,
            objective,
            [Lever(key="demand_cv", minimum=6, maximum=8)],
            confirm_quality=None,
        )


def test_goal_seek_metric_extraction_matches_simulate(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = goal_seek(
        scenario,
        Objective(metric="profit_p50", comparator=">=", target=0),
        [Lever(key="unit_price", minimum=10, maximum=10.1)],
        runs=20,
        confirm_quality=None,
    )
    reference = simulate(scenario, quality="draft")
    assert result.trace[0].value == pytest.approx(reference.metrics.p50)
    # La comparaison ``>=`` avec une cible nulle est déjà satisfaite.
    assert result.feasible is True


def test_objective_and_lever_validation():
    with pytest.raises(ValueError):
        Objective(metric="profit_p50", comparator=">=", target=1, tolerance=-1)
    with pytest.raises(ValueError):
        Lever(key="unit_price", minimum=20, maximum=20)
