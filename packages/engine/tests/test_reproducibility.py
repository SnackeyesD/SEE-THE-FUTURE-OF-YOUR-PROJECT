from __future__ import annotations

from engine import SimulationConfig, simulate


def _aggregates(result):  # type: ignore[no-untyped-def]
    payload = result.model_dump(by_alias=True)
    payload.pop("runId")
    payload.pop("durationMs")
    return payload


def test_same_seed_produces_identical_aggregates(scenario_factory) -> None:
    scenario = scenario_factory(
        assumptions={
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            },
            "demand_mean_monthly": {
                "value": 10,
                "distribution": {"kind": "lognormal", "mean": 2.2, "sigma": 0.2},
            },
        }
    )
    config = SimulationConfig(runs=500, seed=1234)
    first = simulate(scenario, config)
    second = simulate(scenario, config)
    assert _aggregates(first) == _aggregates(second)


def test_different_seeds_change_the_distribution(scenario_factory) -> None:
    scenario = scenario_factory(
        assumptions={
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            }
        }
    )
    first = simulate(scenario, SimulationConfig(runs=500, seed=1))
    second = simulate(scenario, SimulationConfig(runs=500, seed=2))
    assert first.metrics.mean_profit != second.metrics.mean_profit


def test_run_id_is_unique_but_aggregates_are_stable(scenario_factory) -> None:
    scenario = scenario_factory()
    first = simulate(scenario, SimulationConfig(runs=50, seed=7))
    second = simulate(scenario, SimulationConfig(runs=50, seed=7))
    assert first.run_id != second.run_id
    assert first.metrics == second.metrics
