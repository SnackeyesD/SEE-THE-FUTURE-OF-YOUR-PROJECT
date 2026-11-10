from __future__ import annotations

import pytest

from engine import SimulationConfig, simulate


def _result_payload(result):  # type: ignore[no-untyped-def]
    payload = result.model_dump(by_alias=True)
    payload.pop("runId")
    payload.pop("durationMs")
    return payload


def test_histogram_is_consistent(scenario_factory) -> None:
    scenario = scenario_factory(
        assumptions={
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            }
        }
    )
    result = simulate(scenario, SimulationConfig(runs=500, seed=9))
    counts = sum(bin.count for bin in result.histogram.bins)
    probabilities = sum(bin.probability for bin in result.histogram.bins)
    assert counts == 500
    assert probabilities == pytest.approx(1.0)
    assert len(result.histogram.bins) == 40


def test_monthly_averages_match_horizon(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=7)
    result = simulate(scenario, SimulationConfig(runs=100, seed=2))
    assert len(result.monthly.values) == 7
    assert [month.index for month in result.monthly.values] == list(range(1, 8))
    assert [month.month for month in result.monthly.values] == list(range(1, 8))


def test_sensitivity_contributions_sum_to_one(scenario_factory) -> None:
    scenario = scenario_factory(
        assumptions={
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            },
            "demand_mean_monthly": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            },
        }
    )
    result = simulate(scenario, SimulationConfig(runs=1_000, seed=11))
    total = sum(entry.contribution for entry in result.sensitivity)
    assert total == pytest.approx(1.0)
    assert all(-1.0 <= entry.correlation <= 1.0 for entry in result.sensitivity)


def test_sensitivity_is_zero_when_profit_is_constant(scenario_factory) -> None:
    scenario = scenario_factory()
    result = simulate(scenario, SimulationConfig(runs=100, seed=1))
    assert all(entry.correlation == 0.0 for entry in result.sensitivity)
    assert all(entry.contribution == 0.0 for entry in result.sensitivity)


def test_batch_size_has_no_material_effect_on_aggregates(scenario_factory) -> None:
    scenario = scenario_factory(
        assumptions={
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 1.5},
            }
        }
    )
    small = simulate(scenario, SimulationConfig(runs=250, seed=5, batch_size=7))
    large = simulate(scenario, SimulationConfig(runs=250, seed=5, batch_size=1_000))
    assert small.metrics.mean_profit == pytest.approx(large.metrics.mean_profit, rel=1e-12)
    assert small.metrics.p50 == pytest.approx(large.metrics.p50, rel=1e-12)
    assert small.monthly.values[0].mean_revenue == pytest.approx(
        large.monthly.values[0].mean_revenue, rel=1e-12
    )


def test_progress_is_monotonic_and_completes(scenario_factory) -> None:
    scenario = scenario_factory()
    seen: list[float] = []
    simulate(
        scenario,
        SimulationConfig(runs=100, seed=1, batch_size=10),
        progress=seen.append,
    )
    assert seen[0] == 0.0
    assert seen[-1] == 1.0
    assert seen == sorted(seen)
    assert len(seen) == 11


def test_break_even_uses_mean_margins(scenario_factory) -> None:
    scenario = scenario_factory(
        assumptions={
            "unit_price": {"value": 20},
            "unit_cost": {"value": 8},
            "logistics_cost_per_unit": {"value": 1},
            "fixed_costs_monthly": {"value": 100},
        }
    )
    result = simulate(scenario, SimulationConfig(runs=10, seed=1))
    assert result.break_even.unit_margin == pytest.approx(11.0)
    assert result.break_even.break_even_units_monthly == pytest.approx(100 / 11)
    assert result.break_even.break_even_revenue_monthly == pytest.approx(2000 / 11)


def test_negative_margin_has_no_break_even(scenario_factory) -> None:
    scenario = scenario_factory(
        assumptions={
            "unit_price": {"value": 5},
            "unit_cost": {"value": 10},
            "fixed_costs_monthly": {"value": 100},
        }
    )
    result = simulate(scenario, SimulationConfig(runs=10, seed=1))
    assert result.break_even.unit_margin < 0
    assert result.break_even.break_even_units_monthly is None
    assert result.break_even.break_even_revenue_monthly is None
