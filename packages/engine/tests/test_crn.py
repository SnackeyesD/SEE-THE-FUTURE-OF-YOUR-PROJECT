from __future__ import annotations

import numpy as np

from engine import DrawBank, SimulationConfig, simulate
from engine.distributions import sample_distribution
from engine.scenario import DistributionSpec

_SIZES = (250, 256, 257, 500, 1_000)


def _scenario_with_draws(scenario_factory):
    return scenario_factory(
        horizonMonths=6,
        assumptions={
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            },
            "demand_cv": {
                "value": 0.25,
                "distribution": {"kind": "triangular", "low": 0.1, "mode": 0.25, "high": 0.4},
            },
            "loss_rate": {
                "value": 0.03,
                "distribution": {"kind": "uniform", "low": 0.01, "high": 0.06},
            },
        },
    )


def test_run_prefix_is_stable_for_all_sample_arrays(scenario_factory) -> None:
    scenario = _scenario_with_draws(scenario_factory)
    reference = simulate(scenario, SimulationConfig(runs=1_000, seed=42))
    assert reference.run_sample is not None

    for size in _SIZES:
        result = simulate(scenario, SimulationConfig(runs=size, seed=42))
        sample = result.run_sample
        assert sample is not None
        np.testing.assert_array_equal(
            sample.profit_monthly,
            reference.run_sample.profit_monthly[:size],
        )
        np.testing.assert_array_equal(
            sample.cash_monthly,
            reference.run_sample.cash_monthly[:size],
        )
        for key, values in sample.parameters.items():
            np.testing.assert_array_equal(
                values,
                reference.run_sample.parameters[key][:size],
            )


def test_prefix_is_stable_when_batch_size_changes(scenario_factory) -> None:
    scenario = _scenario_with_draws(scenario_factory)
    reference = simulate(
        scenario,
        SimulationConfig(runs=600, seed=9, batch_size=600),
    )
    chunked = simulate(
        scenario,
        SimulationConfig(runs=600, seed=9, batch_size=37),
    )

    assert reference.run_sample is not None and chunked.run_sample is not None
    np.testing.assert_array_equal(
        chunked.run_sample.profit_monthly,
        reference.run_sample.profit_monthly,
    )
    np.testing.assert_array_equal(
        chunked.run_sample.cash_monthly,
        reference.run_sample.cash_monthly,
    )


def test_parameter_change_does_not_change_base_draws() -> None:
    bank = DrawBank(seed=5, horizon=1)
    bank.register("hyp:unit_price")
    uniform, normal = bank.take("hyp:unit_price", 1_000)

    low = sample_distribution(
        DistributionSpec(kind="normal", mean=10, std=2), uniform, normal
    )
    high = sample_distribution(
        DistributionSpec(kind="normal", mean=12, std=3), uniform, normal
    )

    assert not np.allclose(low, high)
    np.testing.assert_allclose(high, 12 + 3 * normal)
    np.testing.assert_array_equal(
        bank.take("hyp:unit_price", 1_000)[1],
        normal,
    )


def test_family_change_keeps_the_same_base_draws() -> None:
    bank = DrawBank(seed=5, horizon=1)
    bank.register("hyp:unit_price")
    uniform, normal = bank.take("hyp:unit_price", 1_000)

    normal_values = sample_distribution(
        DistributionSpec(kind="normal", mean=10, std=2), uniform, normal
    )
    triangular_values = sample_distribution(
        DistributionSpec(kind="triangular", low=5, mode=10, high=15),
        uniform,
        normal,
    )

    assert not np.array_equal(normal_values, triangular_values)
    np.testing.assert_array_equal(
        bank.take("hyp:unit_price", 1_000)[0],
        uniform,
    )


def test_assumption_order_does_not_change_results(scenario_factory) -> None:
    forward = scenario_factory(
        assumptions={
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            },
            "demand_mean_monthly": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 1},
            },
        }
    )
    backward = scenario_factory(
        assumptions={
            "demand_mean_monthly": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 1},
            },
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            },
        }
    )

    first = simulate(forward, SimulationConfig(runs=300, seed=17))
    second = simulate(backward, SimulationConfig(runs=300, seed=17))

    assert first.run_sample is not None and second.run_sample is not None
    np.testing.assert_array_equal(
        first.run_sample.profit_monthly,
        second.run_sample.profit_monthly,
    )
    np.testing.assert_array_equal(
        first.run_sample.parameters["unit_price"],
        second.run_sample.parameters["unit_price"],
    )


def test_adding_a_hypothesis_does_not_change_existing_draws(scenario_factory) -> None:
    base = scenario_factory(
        assumptions={
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            }
        }
    )
    extended = scenario_factory(
        assumptions={
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            },
            "demand_mean_monthly": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 1},
            },
        }
    )

    first = simulate(base, SimulationConfig(runs=400, seed=23))
    second = simulate(extended, SimulationConfig(runs=400, seed=23))

    assert first.run_sample is not None and second.run_sample is not None
    for key in ("unit_price", "unit_cost", "fixed_costs_monthly"):
        np.testing.assert_array_equal(
            first.run_sample.parameters[key],
            second.run_sample.parameters[key],
        )


def test_poisson_approximation_is_reported(scenario_factory) -> None:
    scenario = scenario_factory(
        assumptions={
            "demand_mean_monthly": {
                "value": 50_001,
                "distribution": {"kind": "poisson", "mean": 50_001},
            }
        }
    )
    result = simulate(scenario, SimulationConfig(runs=50, seed=1))
    assert result.approximations == ["poisson_normal"]


def test_no_approximation_for_regular_distributions(scenario_factory) -> None:
    result = simulate(
        _scenario_with_draws(scenario_factory),
        SimulationConfig(runs=50, seed=1),
    )
    assert result.approximations is None
