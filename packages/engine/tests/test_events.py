from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from engine import SimulationConfig, simulate
from engine.draws import DrawBank
from engine.events import (
    EVENT_CATALOG,
    EVENT_TARGETS,
    EventModifiers,
    ScenarioEvent,
    build_event_modifiers,
    draw_events,
    magnitude_is_strictly_positive,
)
from engine.models.retail_depot import RetailDepotModel
from engine.scenario import Scenario


def _event(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "ev1",
        "type": "supplier_price_rise",
        "startMonth": 5,
        "durationMonths": 3,
        "target": "unit_cost",
        "mode": "multiplicative",
        "magnitude": {"kind": "empirical", "values": [1.5]},
        "probability": 1.0,
    }
    payload.update(overrides)
    return payload


def _catalog_event(event_id: str, name: str, *, probability: float = 0.5) -> dict[str, Any]:
    spec = EVENT_CATALOG[name]  # type: ignore[index]
    return {
        "id": event_id,
        "type": name,
        "startMonth": 6,
        "durationMonths": 3,
        "target": spec.target,
        "mode": spec.mode,
        "magnitude": spec.default_magnitude.model_dump(by_alias=True, exclude_none=True),
        "probability": probability,
    }


def _model_inputs() -> dict[str, np.ndarray]:
    return {
        "initial_cash": np.array([1_000.0]),
        "unit_price": np.array([10.0]),
        "unit_cost": np.array([5.0]),
        "fixed_costs_monthly": np.array([0.0]),
        "demand_mean_monthly": np.array([10.0]),
        "demand_cv": np.array([0.0]),
        "loss_rate": np.array([0.0]),
        "logistics_cost_per_unit": np.array([0.0]),
        "target_stock_months": np.array([0.0]),
        "reorder_lead_time_months": np.array([1.0]),
        "initial_stock": np.array([100.0]),
        "tax_rate": np.array([0.0]),
    }


def test_catalog_lists_seven_documented_types() -> None:
    assert len(EVENT_CATALOG) == 7
    for name, spec in EVENT_CATALOG.items():
        assert spec.target in spec.allowed_targets, name
        assert spec.allowed_targets <= set(EVENT_TARGETS), name
        assert spec.label and spec.description, name
        if spec.mode == "multiplicative":
            assert magnitude_is_strictly_positive(spec.default_magnitude), name
        payload = _catalog_event("ev0", name)
        event = ScenarioEvent.model_validate(payload)
        assert event.type == name


def test_builtin_distributions_are_rejected_for_multiplicative_effects() -> None:
    assert magnitude_is_strictly_positive(
        ScenarioEvent.model_validate(_event()).magnitude
    )
    for magnitude in (
        {"kind": "normal", "mean": 1.5, "std": 0.1},
        {"kind": "poisson", "mean": 2.0},
        {"kind": "uniform", "low": 0.0, "high": 2.0},
    ):
        with pytest.raises(ValidationError):
            ScenarioEvent.model_validate(_event(magnitude=magnitude))


def test_additive_effects_accept_signed_magnitudes() -> None:
    event = ScenarioEvent.model_validate(
        _event(
            type="power_outage",
            target="loss_rate",
            mode="additive",
            magnitude={"kind": "normal", "mean": -0.01, "std": 0.005},
        )
    )
    assert event.mode == "additive"


def test_schema_version_upgrades_when_events_exist(scenario_factory) -> None:
    plain = scenario_factory()
    assert plain.schema_version == "1.0.0"

    scenario = scenario_factory(events=[_event()])
    assert scenario.schema_version == "1.1.0"
    payload = scenario.model_dump(by_alias=True)
    assert payload["schemaVersion"] == "1.1.0"
    assert payload["events"][0]["startMonth"] == 5


def test_scenario_accepts_legacy_and_event_versions() -> None:
    legacy = Scenario.model_validate({"schemaVersion": "1.0.0", "name": "Legacy"})
    assert legacy.schema_version == "1.0.0"

    modern = Scenario.model_validate({"schemaVersion": "1.1.0", "name": "Moderne"})
    assert modern.schema_version == "1.1.0"

    with pytest.raises(ValidationError):
        Scenario.model_validate({"schemaVersion": "2.0.0", "name": "Futur"})


def test_duplicate_event_ids_are_rejected(scenario_factory) -> None:
    with pytest.raises(ValidationError, match="dupliqué"):
        scenario_factory(events=[_event(id="ev1"), _event(id="ev1", startMonth=1)])


def test_event_window_must_fit_the_horizon() -> None:
    with pytest.raises(ValidationError, match="horizonMonths"):
        Scenario.model_validate(
            {
                "name": "Hors horizon",
                "horizonMonths": 12,
                "events": [_event(startMonth=11, durationMonths=3)],
            }
        )


def test_event_target_must_be_allowed_for_its_type() -> None:
    with pytest.raises(ValidationError, match="non autorisée"):
        ScenarioEvent.model_validate(
            _event(
                type="competitor_entry",
                target="unit_cost",
                magnitude={"kind": "empirical", "values": [0.9]},
            )
        )


def test_event_id_must_be_a_stable_slug() -> None:
    with pytest.raises(ValidationError):
        ScenarioEvent.model_validate(_event(id="Event 1"))


def test_disabled_event_is_bit_identical_to_no_events(scenario_factory) -> None:
    config = SimulationConfig(runs=200, seed=7)
    baseline = simulate(scenario_factory(), config)
    disabled = simulate(scenario_factory(events=[_event(enabled=False)]), config)

    np.testing.assert_array_equal(
        baseline.run_sample.profit_monthly, disabled.run_sample.profit_monthly
    )
    np.testing.assert_array_equal(
        baseline.run_sample.cash_monthly, disabled.run_sample.cash_monthly
    )
    assert baseline.metrics == disabled.metrics


def test_zero_probability_is_bit_identical_to_no_events(scenario_factory) -> None:
    config = SimulationConfig(runs=150, seed=11)
    baseline = simulate(scenario_factory(), config)
    impossible = simulate(scenario_factory(events=[_event(probability=0.0)]), config)

    np.testing.assert_array_equal(
        baseline.run_sample.profit_monthly, impossible.run_sample.profit_monthly
    )


def test_hypothesis_draws_are_stable_when_an_event_is_added(scenario_factory) -> None:
    config = SimulationConfig(runs=300, seed=5)
    assumptions = {
        "unit_cost": {
            "value": 5,
            "distribution": {"kind": "uniform", "low": 4, "high": 6},
        }
    }
    baseline = simulate(scenario_factory(assumptions=assumptions), config)
    with_event = simulate(
        scenario_factory(assumptions=assumptions, events=[_event(probability=0.4)]),
        config,
    )

    assert baseline.run_sample is not None
    assert with_event.run_sample is not None
    for key, values in baseline.run_sample.parameters.items():
        np.testing.assert_array_equal(values, with_event.run_sample.parameters[key])


def test_event_changes_only_its_window(scenario_factory) -> None:
    config = SimulationConfig(runs=64, seed=3)
    baseline = simulate(scenario_factory(), config)
    shocked = simulate(scenario_factory(events=[_event()]), config)

    for index, (before, after) in enumerate(
        zip(baseline.monthly.values, shocked.monthly.values, strict=True)
    ):
        if 4 <= index <= 6:
            assert after.mean_profit < before.mean_profit
        else:
            assert after.mean_profit == pytest.approx(before.mean_profit)
            assert after.mean_revenue == pytest.approx(before.mean_revenue)


def test_demand_peak_increases_sales_in_window(scenario_factory) -> None:
    config = SimulationConfig(runs=64, seed=9)
    baseline = simulate(scenario_factory(), config)
    peak = simulate(
        scenario_factory(
            events=[
                _event(
                    id="peak",
                    type="demand_peak",
                    target="demand_mean_monthly",
                    magnitude={"kind": "empirical", "values": [1.5]},
                )
            ]
        ),
        config,
    )

    for index, (before, after) in enumerate(
        zip(baseline.monthly.values, peak.monthly.values, strict=True)
    ):
        if 4 <= index <= 6:
            assert after.mean_demand > before.mean_demand
        else:
            assert after.mean_demand == pytest.approx(before.mean_demand)


def test_modifiers_are_built_per_window_and_per_run() -> None:
    bank = DrawBank(seed=1, horizon=12)
    event = ScenarioEvent.model_validate(_event())
    draws = draw_events([event], bank, 5)
    modifiers = build_event_modifiers(draws, 0, 5, 12)

    assert modifiers is not None
    factors = modifiers.factors["unit_cost"]
    assert factors.shape == (5, 12)
    np.testing.assert_array_equal(factors[:, :4], 1.0)
    np.testing.assert_array_equal(factors[:, 4:7], 1.5)
    np.testing.assert_array_equal(factors[:, 7:], 1.0)
    assert modifiers.offsets == {}


def test_probability_is_drawn_once_per_run() -> None:
    runs = 20_000
    bank = DrawBank(seed=11, horizon=3)
    event = ScenarioEvent.model_validate(
        _event(probability=0.3, startMonth=1, durationMonths=1)
    )
    draws = draw_events([event], bank, runs)
    modifiers = build_event_modifiers(draws, 0, runs, 3)
    assert modifiers is not None
    active = modifiers.factors["unit_cost"][:, 0] != 1.0
    assert 0.28 <= float(active.mean()) <= 0.32


def test_events_do_not_contaminate_each_other() -> None:
    bank = DrawBank(seed=21, horizon=12)
    first = ScenarioEvent.model_validate(_event(id="ev_a", probability=0.4))
    second = ScenarioEvent.model_validate(
        _event(
            id="ev_b",
            type="demand_peak",
            target="demand_mean_monthly",
            magnitude={"kind": "empirical", "values": [1.3]},
            probability=0.7,
        )
    )

    together = build_event_modifiers(
        draw_events([first, second], bank, 500), 0, 500, 12
    )
    alone = build_event_modifiers(draw_events([first], bank, 500), 0, 500, 12)

    assert together is not None and alone is not None
    np.testing.assert_array_equal(
        together.factors["unit_cost"], alone.factors["unit_cost"]
    )
    np.testing.assert_array_equal(
        together.factors["demand_mean_monthly"],
        build_event_modifiers(
            draw_events([second], bank, 500), 0, 500, 12
        ).factors["demand_mean_monthly"],
    )


def test_additive_offsets_are_clipped_to_the_target_domain() -> None:
    bank = DrawBank(seed=2, horizon=6)
    event = ScenarioEvent.model_validate(
        _event(
            type="power_outage",
            target="loss_rate",
            mode="additive",
            magnitude={"kind": "empirical", "values": [5.0]},
            startMonth=1,
            durationMonths=2,
        )
    )
    modifiers = build_event_modifiers(draw_events([event], bank, 3), 0, 3, 6)

    assert modifiers is not None
    offsets = modifiers.offsets["loss_rate"]
    assert offsets.max() == pytest.approx(1.0)
    np.testing.assert_array_equal(offsets[:, 2:], 0.0)


def test_model_applies_exact_multiplier_and_offset() -> None:
    model = RetailDepotModel()
    inputs = _model_inputs()
    noise = np.zeros((1, 4), dtype=np.float64)
    seasonality = np.ones(12, dtype=np.float64)

    baseline = model.simulate_batch(inputs, noise, seasonality)
    assert baseline.costs_monthly[0, 0] == pytest.approx(10 * 5)
    assert baseline.inventory_value_end[0] == pytest.approx(60 * 5)

    modifiers = EventModifiers(
        factors={"unit_cost": np.full((1, 4), 2.0)},
        offsets={"unit_cost": np.full((1, 4), 1.0)},
    )
    shocked = model.simulate_batch(inputs, noise, seasonality, modifiers)

    assert shocked.costs_monthly[0, 0] == pytest.approx(10 * (5 * 2.0 + 1.0))
    assert shocked.inventory_value_end[0] == pytest.approx(60 * 11.0)
    np.testing.assert_array_equal(shocked.demand_monthly, baseline.demand_monthly)


def test_draft_is_an_exact_prefix_of_final_with_events(scenario_factory) -> None:
    events = [_event(probability=0.5), _catalog_event("ev2", "demand_peak")]
    scenario = scenario_factory(events=events)

    draft = simulate(scenario, SimulationConfig(seed=4), quality="draft")
    final = simulate(scenario, SimulationConfig(seed=4), quality="final")

    assert draft.run_sample is not None and final.run_sample is not None
    count = draft.runs
    np.testing.assert_array_equal(
        draft.run_sample.profit_monthly,
        final.run_sample.profit_monthly[:count],
    )
    for key, values in draft.run_sample.parameters.items():
        np.testing.assert_array_equal(values, final.run_sample.parameters[key][:count])


@pytest.mark.slow
def test_seven_events_add_less_than_fifteen_percent(scenario_factory) -> None:
    plain = scenario_factory()
    shocked = scenario_factory(
        events=[
            _catalog_event(f"ev{index}", name)
            for index, name in enumerate(EVENT_CATALOG)
        ]
    )
    config = SimulationConfig(runs=5_000, seed=42)

    baseline_durations: list[float] = []
    shocked_durations: list[float] = []
    for _ in range(3):
        baseline_durations.append(simulate(plain, config).duration_ms)
        shocked_durations.append(simulate(shocked, config).duration_ms)

    baseline = min(baseline_durations)
    with_events = min(shocked_durations)
    assert with_events < baseline * 1.15 + 25.0, (baseline, with_events)
