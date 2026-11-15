"""Tests de la phase 04 : calcul progressif, annulation et convergence."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pytest

from engine import (
    CancelToken,
    EngineError,
    Scenario,
    SimulationCancelled,
    SimulationConfig,
    resolve_execution,
    simulate,
)

EXAMPLE = Path(__file__).parents[1] / "examples" / "retail_depot.json"


def _stochastic_scenario_factory(scenario_factory):
    return scenario_factory(
        horizonMonths=36,
        assumptions={
            "unit_price": {
                "value": 10,
                "distribution": {"kind": "normal", "mean": 10, "std": 2},
            },
            "demand_cv": {
                "value": 0.25,
                "distribution": {
                    "kind": "triangular",
                    "low": 0.1,
                    "mode": 0.25,
                    "high": 0.4,
                },
            },
            "loss_rate": {
                "value": 0.03,
                "distribution": {"kind": "uniform", "low": 0.01, "high": 0.06},
            },
        },
    )


def _example_scenario() -> Scenario:
    scenario = Scenario.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))
    return scenario.model_copy(update={"horizon_months": 36})


def test_quality_profiles_precede_defaults_but_not_explicit_config() -> None:
    plan = resolve_execution(SimulationConfig(seed=1), "draft")
    assert (plan.runs, plan.block_size) == (500, 256)

    plan = resolve_execution(SimulationConfig(seed=1), "final")
    assert (plan.runs, plan.block_size) == (5_000, 256)

    plan = resolve_execution(SimulationConfig(runs=1_234, seed=1), "draft")
    assert (plan.runs, plan.block_size) == (1_234, 256)

    plan = resolve_execution(
        SimulationConfig(runs=1_234, batch_size=64, seed=1),
        "draft",
    )
    assert (plan.runs, plan.block_size) == (1_234, 64)

    # Les très grands calculs élargissent le bloc du profil pour éviter des
    # centaines d'appels de modèle, sans dépasser le budget d'annulation.
    plan = resolve_execution(SimulationConfig(runs=100_000, seed=1), "final")
    assert plan.runs == 100_000
    assert plan.block_size == math.ceil(100_000 / 64)
    plan = resolve_execution(SimulationConfig(runs=1_000_000, seed=1), "final")
    assert plan.block_size == 2_048


def test_draft_is_an_exact_prefix_of_final() -> None:
    scenario = _example_scenario()
    draft = simulate(scenario, SimulationConfig(seed=42), quality="draft")
    final = simulate(scenario, SimulationConfig(seed=42), quality="final")

    assert draft.runs == 500
    assert final.runs == 5_000
    assert draft.run_sample is not None
    assert final.run_sample is not None
    assert np.array_equal(
        draft.run_sample.profit_monthly,
        final.run_sample.profit_monthly[: draft.runs],
    )
    assert np.array_equal(
        draft.run_sample.cash_monthly,
        final.run_sample.cash_monthly[: draft.runs],
    )
    assert np.array_equal(
        draft.run_sample.revenue_monthly,
        final.run_sample.revenue_monthly[: draft.runs],
    )
    for key, values in draft.run_sample.parameters.items():
        assert np.array_equal(values, final.run_sample.parameters[key][: draft.runs])


def test_progress_is_monotonic_and_reaches_one(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=6)
    fractions: list[float] = []

    result = simulate(
        scenario,
        SimulationConfig(seed=3),
        on_progress=fractions.append,
    )

    assert result.runs == 5_000
    assert fractions[0] == 0.0
    assert fractions[-1] == 1.0
    assert fractions == sorted(fractions)
    assert len(fractions) > 2


def test_legacy_progress_argument_still_works(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=4)
    fractions: list[float] = []

    result = simulate(
        scenario,
        SimulationConfig(runs=300, seed=4),
        progress=fractions.append,
    )

    assert result.runs == 300
    assert fractions[-1] == 1.0


def test_cancel_raises_and_publishes_nothing_after_cancellation(
    scenario_factory,
) -> None:
    scenario = scenario_factory(horizonMonths=6)
    token = CancelToken()
    partials: list[int] = []
    fractions: list[float] = []

    def on_partial(partial) -> None:
        partials.append(partial.completed_runs)
        if len(partials) == 2:
            token.cancel()

    with pytest.raises(SimulationCancelled) as excinfo:
        simulate(
            scenario,
            SimulationConfig(seed=8),
            on_partial=on_partial,
            on_progress=fractions.append,
            cancel=token,
        )

    assert isinstance(excinfo.value, EngineError)
    assert partials == [256, 512]
    assert excinfo.value.completed_runs == 512
    # Progression initiale + un seul bloc publié : rien après l'annulation.
    assert fractions == [0.0, pytest.approx(256 / 5_000)]


def test_cancel_latency_is_below_budget(scenario_factory) -> None:
    scenario = _stochastic_scenario_factory(scenario_factory)
    token = CancelToken()
    cancelled_at: float | None = None
    partials: list[int] = []

    def on_partial(partial) -> None:
        nonlocal cancelled_at
        partials.append(partial.completed_runs)
        if len(partials) == 2:
            cancelled_at = time.perf_counter()
            token.cancel()

    with pytest.raises(SimulationCancelled):
        simulate(
            scenario,
            SimulationConfig(seed=12),
            on_partial=on_partial,
            cancel=token,
        )

    assert cancelled_at is not None
    latency_ms = (time.perf_counter() - cancelled_at) * 1_000.0
    assert latency_ms < 100.0, f"latence d'annulation: {latency_ms:.1f} ms"


def test_partial_histogram_bounds_are_stable_and_never_shrink(
    scenario_factory,
) -> None:
    scenario = _stochastic_scenario_factory(scenario_factory)
    partials = []

    simulate(
        scenario,
        SimulationConfig(seed=21),
        on_partial=partials.append,
    )

    first = partials[0].histogram.bins
    last = partials[-1].histogram.bins
    first_center = (first[0].lower + first[-1].upper) / 2.0
    assert len(first) == 40
    assert len(last) == 40
    for previous, current in zip(partials, partials[1:], strict=False):
        previous_bins = previous.histogram.bins
        current_bins = current.histogram.bins
        assert current_bins[0].lower <= previous_bins[0].lower
        assert current_bins[-1].upper >= previous_bins[-1].upper
        assert (current_bins[0].lower + current_bins[-1].upper) / 2.0 == pytest.approx(
            first_center
        )
        assert sum(bin.count for bin in current_bins) == current.completed_runs


def test_convergence_flag_on_deterministic_scenario(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=6)

    final = simulate(scenario, SimulationConfig(seed=7), quality="final")
    draft = simulate(scenario, SimulationConfig(seed=7), quality="draft")
    short = simulate(scenario, SimulationConfig(runs=256, seed=7))

    assert final.convergence is not None
    assert final.convergence.converged is True
    assert final.convergence.stability == pytest.approx(1.0)
    assert final.convergence.max_relative_change == 0.0
    assert final.convergence.stable_blocks >= 2

    assert draft.convergence is not None
    assert draft.convergence.converged is True

    assert short.convergence is not None
    assert short.convergence.converged is False
    assert short.convergence.stable_blocks == 0


def test_partial_payload_stays_under_budget() -> None:
    scenario = _example_scenario()
    partials = []

    simulate(
        scenario,
        SimulationConfig(seed=42),
        on_partial=partials.append,
    )

    assert partials
    sizes = [
        len(
            json.dumps(
                partial.to_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        )
        for partial in partials
    ]
    assert max(sizes) < 50 * 1024
    payload = partials[-1].to_dict()
    assert payload["completedRuns"] == 5_000
    assert payload["totalRuns"] == 5_000
    assert "runSample" not in json.dumps(payload)
    assert all(
        month["profitHistogram"] is None and month["cashHistogram"] is None
        for month in payload["monthly"]["values"]
    )


def test_result_exposes_effective_quality(scenario_factory) -> None:
    scenario = scenario_factory(horizonMonths=3)

    draft = simulate(scenario, SimulationConfig(seed=5), quality="draft")
    final = simulate(scenario, SimulationConfig(runs=300, seed=5), quality="final")

    assert draft.quality == "draft"
    assert final.quality == "final"
    assert final.runs == 300
