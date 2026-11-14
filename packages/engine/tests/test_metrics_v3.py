"""Tests des métriques cockpit V3 (phase 02).

Ces tests vérifient les définitions de l'ADR 0015 telles que le moteur les
applique : point mort en mois, trésorerie minimale, besoin de financement,
bandes mensuelles, CDF et histogrammes mensuels.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine import EngineError, SimulationConfig, SimulationResult, simulate
from engine.aggregation import build_min_cash_cdf, run_break_even_months

CDF_POINTS = 64
_V3_METRIC_FIELDS = (
    "cashNegativeProbability",
    "meanMinCash",
    "minCashP10",
    "minCashP50",
    "minCashP90",
    "financingNeedP50",
    "financingNeedP90",
    "breakEvenProbability",
    "medianBreakEvenMonth",
    "minCashCdf",
)
_V3_MONTHLY_FIELDS = (
    "profitP10",
    "profitP50",
    "profitP90",
    "cashP10",
    "cashP50",
    "cashP90",
    "breakEvenProbability",
    "profitHistogram",
    "cashHistogram",
)


def _assert_close(actual, expected, path: str = "root") -> None:
    """Compare deux structures JSON en tolérant les écarts flottants."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert actual.keys() == expected.keys(), path
        for key in expected:
            _assert_close(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), path
        assert len(actual) == len(expected), path
        for index, (actual_item, expected_item) in enumerate(
            zip(actual, expected, strict=True)
        ):
            _assert_close(actual_item, expected_item, f"{path}[{index}]")
    elif isinstance(expected, bool) or expected is None:
        assert actual == expected, path
    elif isinstance(expected, (int, float)):
        assert actual == pytest.approx(expected), path
    else:
        assert actual == expected, path


def test_break_even_month_detection() -> None:
    profit = np.array(
        [
            [-10.0, 10.0, 5.0],  # cumul -10, 0, 5 -> mois 2
            [5.0, -10.0, 5.0],  # cumul positif dès le mois 1
            [-10.0, -10.0, -10.0],  # jamais atteint -> sentinelle horizon + 1
        ]
    )

    assert run_break_even_months(profit).tolist() == [2, 1, 4]


def test_negative_cash_metrics_and_financing_need(scenario_factory) -> None:
    scenario = scenario_factory(
        horizonMonths=3,
        assumptions={
            "fixed_costs_monthly": {"value": 300},
            "demand_mean_monthly": {"value": 20},
        },
    )
    result = simulate(scenario, SimulationConfig(runs=20, seed=5))
    metrics = result.metrics

    assert metrics.min_cash_p10 == pytest.approx(-300)
    assert metrics.min_cash_p50 == pytest.approx(-300)
    assert metrics.min_cash_p90 == pytest.approx(-300)
    assert metrics.mean_min_cash == pytest.approx(-300)
    assert metrics.cash_negative_probability == 1.0
    assert metrics.financing_need_p50 == pytest.approx(300)
    assert metrics.financing_need_p90 == pytest.approx(300)
    assert metrics.break_even_probability == 0.0
    assert metrics.median_break_even_month is None
    assert [month.break_even_probability for month in result.monthly.values] == [0, 0, 0]

    assert metrics.min_cash_cdf is not None
    assert len(metrics.min_cash_cdf) == 1
    assert metrics.min_cash_cdf[0].value == pytest.approx(-300)
    assert metrics.min_cash_cdf[0].probability == pytest.approx(1.0)


def test_percentile_order_and_cdf_monotonicity(scenario_factory) -> None:
    scenario = scenario_factory(
        horizonMonths=8,
        assumptions={
            "demand_cv": {"value": 0.4},
            "initial_cash": {"value": 200},
            "fixed_costs_monthly": {"value": 80},
        },
    )
    result = simulate(scenario, SimulationConfig(runs=400, seed=13))
    metrics = result.metrics

    assert metrics.min_cash_p10 <= metrics.min_cash_p50 <= metrics.min_cash_p90
    assert 0.0 <= metrics.cash_negative_probability <= 1.0
    assert 0.0 <= metrics.break_even_probability <= 1.0
    assert metrics.financing_need_p50 == pytest.approx(
        max(0.0, -metrics.min_cash_p50)
    )
    assert metrics.financing_need_p90 == pytest.approx(
        max(0.0, -metrics.min_cash_p10)
    )

    assert metrics.min_cash_cdf is not None
    values = [point.value for point in metrics.min_cash_cdf]
    probabilities = [point.probability for point in metrics.min_cash_cdf]
    assert values == sorted(values)
    assert probabilities == sorted(probabilities)
    assert probabilities[-1] == pytest.approx(1.0)
    assert len(values) <= CDF_POINTS

    for month in result.monthly.values:
        assert month.profit_p10 <= month.profit_p50 <= month.profit_p90
        assert month.cash_p10 <= month.cash_p50 <= month.cash_p90


def test_min_cash_cdf_constant_and_bounded() -> None:
    constant = build_min_cash_cdf(np.full(100, 42.0))
    assert len(constant) == 1
    assert constant[0].value == pytest.approx(42.0)
    assert constant[0].probability == pytest.approx(1.0)

    rng = np.random.default_rng(0)
    sampled = build_min_cash_cdf(rng.normal(size=5_000), points=CDF_POINTS)
    assert 0 < len(sampled) <= CDF_POINTS
    assert [point.value for point in sampled] == sorted(
        point.value for point in sampled
    )
    assert [point.probability for point in sampled] == sorted(
        point.probability for point in sampled
    )
    assert sampled[-1].probability == pytest.approx(1.0)


def test_only_selected_month_gets_histograms(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=4)
    result = simulate(
        scenario,
        SimulationConfig(
            runs=200,
            seed=1,
            histogram_month=2,
            monthly_histogram_bins=12,
        ),
    )

    for month in result.monthly.values:
        if month.index == 2:
            assert month.profit_histogram is not None
            assert month.cash_histogram is not None
            assert len(month.profit_histogram) == 12
            assert len(month.cash_histogram) == 12
            assert sum(bin.count for bin in month.profit_histogram) == 200
            assert sum(bin.probability for bin in month.profit_histogram) == pytest.approx(
                1.0
            )
            assert sum(bin.count for bin in month.cash_histogram) == 200
            for bin in month.profit_histogram + month.cash_histogram:
                assert bin.lower < bin.upper
        else:
            assert month.profit_histogram is None
            assert month.cash_histogram is None


def test_histograms_can_be_disabled(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=3)
    result = simulate(
        scenario,
        SimulationConfig(runs=50, seed=2, histogram_month=None),
    )

    assert all(month.profit_histogram is None for month in result.monthly.values)
    assert all(month.cash_histogram is None for month in result.monthly.values)


def test_histogram_month_outside_horizon_is_rejected(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=3)
    with pytest.raises(EngineError, match="histogramMonth"):
        simulate(scenario, SimulationConfig(runs=10, seed=2, histogram_month=4))


def test_sample_is_capped_and_is_a_prefix(scenario_factory, monkeypatch) -> None:
    from engine import runner

    monkeypatch.setattr(runner, "SAMPLE_LIMIT", 50)
    scenario = scenario_factory(horizonMonths=3)
    result = simulate(
        scenario,
        SimulationConfig(runs=120, seed=3, batch_size=37),
    )

    assert result.runs == 120
    assert result.runs_retained == 50
    sample = result.run_sample
    assert sample is not None
    assert sample.indices.tolist() == list(range(50))
    assert sample.profit_monthly.shape == (50, 3)
    assert sample.cash_monthly.shape == (50, 3)
    assert "runSample" not in result.model_dump(by_alias=True)


def test_batch_size_does_not_change_results(scenario_factory) -> None:
    scenario = scenario_factory(
        horizonMonths=6,
        assumptions={"demand_cv": {"value": 0.3}},
    )
    small = simulate(scenario, SimulationConfig(runs=300, seed=7, batch_size=64))
    full = simulate(scenario, SimulationConfig(runs=300, seed=7, batch_size=300))

    _assert_close(
        small.metrics.model_dump(by_alias=True),
        full.metrics.model_dump(by_alias=True),
        "metrics",
    )
    _assert_close(
        [month.model_dump(by_alias=True) for month in small.monthly.values],
        [month.model_dump(by_alias=True) for month in full.monthly.values],
        "monthly",
    )
    _assert_close(
        small.histogram.model_dump(by_alias=True),
        full.histogram.model_dump(by_alias=True),
        "histogram",
    )


def test_old_payload_without_v3_fields_is_still_valid(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=3)
    result = simulate(scenario, SimulationConfig(runs=40, seed=11))
    payload = result.model_dump(by_alias=True, mode="json")

    payload.pop("runsRetained")
    for field in _V3_METRIC_FIELDS:
        payload["metrics"].pop(field)
    for month in payload["monthly"]["values"]:
        for field in _V3_MONTHLY_FIELDS:
            month.pop(field)

    restored = SimulationResult.model_validate(payload)
    assert restored.runs_retained is None
    assert restored.metrics.cash_negative_probability is None
    assert restored.metrics.min_cash_cdf is None
    assert restored.metrics.median_break_even_month is None
    assert restored.monthly.values[0].profit_p10 is None
    assert restored.monthly.values[0].cash_histogram is None


def test_v3_fields_are_serialized_for_new_runs(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=2)
    result = simulate(
        scenario,
        SimulationConfig(runs=40, seed=11, histogram_month=1),
    )
    payload = result.model_dump(by_alias=True)

    assert payload["runsRetained"] == 40
    assert payload["metrics"]["minCashCdf"]
    assert payload["metrics"]["breakEvenProbability"] is not None
    assert payload["monthly"]["values"][0]["profitHistogram"]
    assert payload["monthly"]["values"][0]["profitP50"] is not None
