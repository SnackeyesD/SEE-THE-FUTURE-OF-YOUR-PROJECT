from __future__ import annotations

import pytest
from pydantic import ValidationError

from engine.scenario import Hypothesis, Scenario, SimulationConfig


def test_scenario_accepts_camel_case_and_round_trips() -> None:
    scenario = Scenario.model_validate(
        {
            "schemaVersion": "1.0.0",
            "name": "Test",
            "model": "retail_depot",
            "currency": "XOF",
            "horizonMonths": 6,
            "assumptions": {"unit_price": {"value": 10}},
        }
    )
    payload = scenario.model_dump(by_alias=True)
    assert payload["horizonMonths"] == 6
    assert payload["schemaVersion"] == "1.0.0"
    assert payload["assumptions"]["unit_price"]["value"] == 10


def test_scenario_accepts_snake_case_too() -> None:
    scenario = Scenario.model_validate(
        {"name": "Test", "horizon_months": 3, "assumptions": {"unit_price": {"value": 1}}}
    )
    assert scenario.horizon_months == 3


def test_scenario_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Scenario.model_validate({"name": "Test", "unexpected": True})


def test_seasonality_requires_twelve_positive_factors() -> None:
    with pytest.raises(ValidationError):
        Scenario.model_validate({"name": "Test", "seasonality": [1.0] * 11})
    with pytest.raises(ValidationError):
        Scenario.model_validate({"name": "Test", "seasonality": [0.0] * 12})
    scenario = Scenario.model_validate({"name": "Test", "seasonality": [1.0] * 12})
    assert scenario.seasonality == [1.0] * 12


def test_assumption_keys_must_be_identifiers() -> None:
    with pytest.raises(ValidationError):
        Scenario.model_validate({"name": "Test", "assumptions": {"Unit Price": {"value": 1}}})


def test_hypothesis_rejects_incoherent_bounds() -> None:
    with pytest.raises(ValidationError):
        Hypothesis.model_validate({"value": 5, "min": 10, "max": 1})


def test_hypothesis_keeps_benchmark_provenance() -> None:
    scenario = Scenario.model_validate(
        {
            "name": "Test",
            "assumptions": {
                "unit_price": {
                    "value": 10,
                    "provenance": {
                        "kind": "benchmark",
                        "label": "Pack signé",
                        "packId": "cg-brazzaville-retail-2026.1",
                        "reliability": "study",
                        "freshness": "fresh",
                    },
                }
            },
        }
    )
    payload = scenario.model_dump(by_alias=True, mode="json")
    provenance = payload["assumptions"]["unit_price"]["provenance"]
    assert provenance["packId"] == "cg-brazzaville-retail-2026.1"
    assert provenance["freshness"] == "fresh"


def test_config_defaults_and_bounds() -> None:
    config = SimulationConfig()
    assert config.runs == 10_000
    assert config.seed == 42
    assert config.batch_size == 50_000

    with pytest.raises(ValidationError):
        SimulationConfig(runs=0)
    with pytest.raises(ValidationError):
        SimulationConfig(runs=1_000_001)
    with pytest.raises(ValidationError):
        SimulationConfig(histogram_bins=0)
