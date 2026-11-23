"""Tests de la phase 12 : provenance et validation numérique."""

from __future__ import annotations

import json

import pytest

from engine import (
    SimulationConfig,
    build_provenance,
    deterministic_explanation,
    extract_numbers,
    number_is_allowed,
    scenario_hash,
    simulate,
    validate_explanation,
)


def _scenario(scenario_factory):
    return scenario_factory(
        horizonMonths=12,
        assumptions={
            "initial_stock": {"value": 10_000},
            "initial_cash": {"value": 0},
            "unit_price": {
                "value": 15,
                "confidence": 0.8,
                "min": 10,
                "max": 20,
                "distribution": {"kind": "normal", "mean": 15, "std": 1},
            },
            "unit_cost": {"value": 5},
            "demand_mean_monthly": {"value": 10},
            "demand_cv": {"value": 0},
            "loss_rate": {"value": 0},
            "fixed_costs_monthly": {"value": 0},
            "logistics_cost_per_unit": {"value": 0},
            "target_stock_months": {"value": 0},
        },
    )


@pytest.fixture
def scenario(scenario_factory):
    return _scenario(scenario_factory)


@pytest.fixture
def result(scenario):
    return simulate(scenario, SimulationConfig(runs=50, seed=9))


def test_provenance_aggregate_contains_real_engine_values(scenario, result):
    provenance = build_provenance(result, scenario, "profit_p50")

    assert provenance["runId"] == result.run_id
    assert provenance["metric"] == "profit_p50"
    assert provenance["point"] is None
    assert provenance["value"] == pytest.approx(result.metrics.p50)
    assert provenance["range"] == pytest.approx([result.metrics.p10, result.metrics.p90])
    assert provenance["seed"] == 9
    assert provenance["runs"] == 50
    assert provenance["engineVersion"] == result.engine_version
    assert provenance["unit"] == scenario.currency
    assert len(provenance["scenariosHash"]) == 64

    inputs = {item["key"]: item for item in provenance["inputs"]}
    assert inputs["unit_price"]["value"] == 15
    assert inputs["unit_price"]["confidence"] == pytest.approx(0.8)
    assert inputs["unit_price"]["source"] == "user"
    contributions = sum(item["contribution"] for item in provenance["inputs"])
    assert contributions == pytest.approx(1.0)


def test_provenance_monthly_uses_the_month_distribution(scenario, result):
    month = result.monthly.values[5]
    provenance = build_provenance(result, scenario, "profit_p50", point=month.index)

    assert provenance["point"] == month.index
    assert provenance["value"] == pytest.approx(month.profit_p50)
    assert provenance["range"] == pytest.approx([month.profit_p10, month.profit_p90])


def test_provenance_has_no_secret_or_project_identity(scenario, result):
    provenance = build_provenance(result, scenario, "profit_p50")
    encoded = json.dumps(provenance, ensure_ascii=False)

    assert scenario.name not in encoded
    assert "apiKey" not in encoded
    assert "keychain" not in encoded.lower()
    assert "/home/" not in encoded
    assert "notes" not in provenance


def test_scenario_hash_ignores_volatile_metadata(scenario, result):
    renamed = scenario.model_copy(update={"name": "Autre nom", "notes": "note volatile"})
    changed = scenario.model_copy(
        update={
            "assumptions": {
                **scenario.assumptions,
                "unit_price": scenario.assumptions["unit_price"].model_copy(
                    update={"value": 16}
                ),
            }
        }
    )

    assert scenario_hash(scenario) == scenario_hash(renamed)
    assert scenario_hash(scenario) != scenario_hash(changed)


def test_extract_numbers_handles_french_formats():
    assert extract_numbers("12 500 FCFA")[0] == (12_500.0, False)
    assert extract_numbers("12,5 %")[0] == (12.5, True)
    assert extract_numbers("P10–P90") == []
    assert extract_numbers("1\u202f234")[0] == (1_234.0, False)


def test_validator_accepts_payload_numbers_and_rejects_invented_ones(scenario, result):
    provenance = build_provenance(result, scenario, "profit_p50")
    provenance["value"] = 12_500.0
    provenance["inputs"][0]["confidence"] = 0.125
    provenance["seed"] = 42
    provenance["runs"] = 5
    provenance["range"] = [1_000.0, 2_000.0]

    valid = {
        "summary": "Le profit P50 atteint 12 500 FCFA avec la graine 42 et 5 runs.",
        "points": [
            {
                "text": (
                    "La confiance de l'entrée est de 12,5 % ; la fourchette "
                    "P10–P90 va de 1 000 à 2 000."
                ),
                "references": ["p50", "seed"],
            }
        ],
        "caveats": ["Une valeur de 12 500 n'est pas une garantie."],
    }
    assert validate_explanation(valid, provenance) == []

    invented = {
        "summary": "Le profit atteint 1 234 FCFA.",
        "points": [],
        "caveats": [],
    }
    assert validate_explanation(invented, provenance) == ["1 234"]

    rounded = {
        "summary": "Le profit atteint 12 300 FCFA.",
        "points": [],
        "caveats": [],
    }
    assert validate_explanation(rounded, provenance) == ["12 300"]


def test_validator_tolerance_is_relative():
    allowed = {12_500.0}
    assert number_is_allowed(12_500.0, is_percent=False, allowed=allowed)
    assert number_is_allowed(12_512.5, is_percent=False, allowed=allowed)
    assert not number_is_allowed(12_513.0, is_percent=False, allowed=allowed)


def test_deterministic_explanation_is_valid_and_mentions_seed(scenario, result):
    provenance = build_provenance(result, scenario, "profit_p50")
    explanation = deterministic_explanation(provenance)

    assert "graine 9" in explanation["summary"]
    assert explanation["points"]
    assert validate_explanation(explanation, provenance) == []


def test_detach_sample_keeps_aggregates(result):
    sample = result.run_sample
    assert sample is not None

    result.detach_sample()

    assert result.run_sample is None
    assert result.metrics.p50 == pytest.approx(result.metrics.p50)
