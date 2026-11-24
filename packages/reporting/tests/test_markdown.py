from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from see_reporting import (
    ReportInput,
    build_markdown,
    format_money,
    format_ratio,
)


def _metrics(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "meanProfit": 1_200_000.0,
        "medianProfit": 1_100_000.0,
        "stdProfit": 400_000.0,
        "minProfit": -300_000.0,
        "maxProfit": 2_400_000.0,
        "p10": -150_000.0,
        "p50": 1_100_000.0,
        "p90": 2_100_000.0,
        "lossProbability": 0.18,
        "profitPositiveProbability": 0.82,
        "meanRevenue": 14_000_000.0,
        "meanCosts": 12_800_000.0,
        "meanTax": 0.0,
        "meanCashEnd": 2_000_000.0,
        "meanUnitsSold": 520.0,
        "meanUnitsLost": 21.0,
        "meanStockoutMonths": 1.2,
        "meanEndStock": 80.0,
        "meanInventoryValue": 950_000.0,
        "meanProfitMargin": 0.086,
        "cashNegativeProbability": 0.31,
        "minCashP10": -450_000.0,
        "minCashP50": 120_000.0,
        "minCashP90": 700_000.0,
        "financingNeedP50": 0.0,
        "financingNeedP90": 450_000.0,
        "breakEvenProbability": 0.74,
        "medianBreakEvenMonth": 7,
    }
    base.update(overrides)
    return base


def _result(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "runId": "run-123",
        "engineVersion": "0.4.0",
        "scenarioName": "Dépôt de revente — Brazzaville",
        "model": "retail_depot",
        "currency": "XAF",
        "horizonMonths": 12,
        "runs": 5000,
        "runsRetained": 5000,
        "seed": 42,
        "durationMs": 900.0,
        "metrics": _metrics(),
        "histogram": {"bins": []},
        "monthly": {
            "values": [
                {
                    "index": 0,
                    "month": 1,
                    "meanRevenue": 1_000_000.0,
                    "meanProfit": 90_000.0,
                    "meanDemand": 220.0,
                    "meanUnitsSold": 210.0,
                    "meanStockEnd": 40.0,
                    "stockoutProbability": 0.05,
                    "profitP10": -20_000.0,
                    "profitP50": 90_000.0,
                    "profitP90": 200_000.0,
                    "cashP10": 1_000_000.0,
                    "cashP50": 1_200_000.0,
                    "cashP90": 1_400_000.0,
                    "breakEvenProbability": 0.4,
                }
            ]
        },
        "sensitivity": [
            {"hypothesis": "unit_price", "correlation": 0.81, "contribution": 0.42},
            {"hypothesis": "demand_mean_monthly", "correlation": 0.63, "contribution": 0.28},
        ],
        "breakEven": {
            "monthlyFixedCosts": 200_000.0,
            "unitMargin": 2_130.0,
            "breakEvenUnitsMonthly": 93.9,
            "breakEvenRevenueMonthly": 1_333_800.0,
        },
        "approximations": ["Pertes appliquées après les ventes."],
        "quality": "final",
        "convergence": {
            "converged": True,
            "stability": 0.97,
            "maxRelativeChange": 0.02,
            "stableBlocks": 4,
        },
    }
    base.update(overrides)
    return base


def _scenario() -> dict[str, Any]:
    return {
        "schemaVersion": "1.1.0",
        "name": "Dépôt de revente — Brazzaville",
        "model": "retail_depot",
        "currency": "XAF",
        "horizonMonths": 12,
        "assumptions": {
            "unit_price": {
                "value": 14200.0,
                "min": 12636.0,
                "max": 16883.0,
                "provenance": {
                    "kind": "benchmark",
                    "label": "Prix du panier WFP/HDX",
                    "reliability": "study",
                    "sourceDate": "2026-09-15",
                    "freshness": "fresh",
                    "packId": "cg-brazzaville-retail-2026.1",
                },
            },
            "demand_mean_monthly": {
                "value": 220.0,
                "min": 150.0,
                "max": 300.0,
                "source": "Enquête à remplacer",
            },
        },
        "events": [
            {
                "id": "rupture",
                "type": "supply_disruption",
                "startMonth": 4,
                "durationMonths": 1,
                "target": "reorder_lead_time_months",
                "mode": "multiplicative",
                "magnitude": {"kind": "uniform", "low": 1.5, "high": 2.5},
                "probability": 0.35,
                "enabled": True,
            }
        ],
    }


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "project": {
            "name": "Dépôt de revente",
            "currency": "XAF",
            "sector": "retail",
        },
        "scenario": _scenario(),
        "result": _result(),
        "branches": [
            {
                "scenarioId": "sc-1",
                "name": "Scénario de départ",
                "branchLabel": None,
                "parentId": None,
                "lastFinalRunId": "run-123",
                "seed": 42,
                "updatedAt": "2026-01-01T10:00:00+00:00",
            }
        ],
        "versions": [
            {
                "id": "v-1",
                "scenarioId": "sc-1",
                "label": "Scénario de départ",
                "seed": 42,
                "engineVersion": "0.4.0",
                "createdAt": "2026-01-01T10:00:00+00:00",
            }
        ],
        "generatedAt": "2026-11-23T12:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_markdown_is_deterministic() -> None:
    report = ReportInput.model_validate(_payload())
    first = build_markdown(report)
    second = build_markdown(report)
    assert first == second


def test_markdown_contains_required_sections() -> None:
    text = build_markdown(ReportInput.model_validate(_payload()))
    assert "simulation basée sur vos hypothèses" in text.lower()
    assert "Graine | 42" in text
    assert "Version du moteur | 0.4.0" in text
    assert "Profit cumulé P10" in text
    assert "Profit cumulé P90" in text
    assert "Point mort structurel" in text
    assert "Traçabilité" in text
    assert "`run-123`" in text


def test_absent_value_is_not_rendered_as_zero() -> None:
    payload = _payload(result=_result(metrics=_metrics(minCashP50=None)))
    text = build_markdown(ReportInput.model_validate(payload))
    assert "Trésorerie minimale P50 | non disponible" in text


def test_report_does_not_leak_secret_or_local_path() -> None:
    text = build_markdown(ReportInput.model_validate(_payload()))
    lowered = text.lower()
    assert "apikey" not in lowered
    assert "api_key" not in lowered
    assert "c:\\" not in lowered
    assert "/home/" not in lowered


def test_unknown_fields_are_tolerated_for_schema_evolution() -> None:
    payload = _payload()
    payload["project"]["futureField"] = "ignored"
    payload["futureTopLevel"] = {"anything": True}
    report = ReportInput.model_validate(payload)
    assert report.project.name == "Dépôt de revente"


def test_invalid_result_is_rejected() -> None:
    payload = _payload()
    del payload["result"]["metrics"]
    with pytest.raises(ValidationError):
        ReportInput.model_validate(payload)


def test_snapshot_stable_outside_date() -> None:
    first = build_markdown(ReportInput.model_validate(_payload()))
    other = _payload()
    other["generatedAt"] = "2026-11-24T08:00:00+00:00"
    second = build_markdown(ReportInput.model_validate(other))
    assert first.replace("23/11/2026", "24/11/2026") == second


def test_formatters_use_french_conventions() -> None:
    assert format_money(14200.0, "XAF") == "14 200 XAF"
    assert format_ratio(0.184) == "18,4 %"


def test_json_round_trip_keeps_numbers() -> None:
    payload = json.loads(json.dumps(_payload()))
    text = build_markdown(ReportInput.model_validate(payload))
    assert "14 200,00 XAF" in text
    assert "220,00 unités/mois" in text
    assert "220,00 XAF" not in text


def test_result_currency_wins_over_project_currency() -> None:
    payload = _payload()
    payload["project"]["currency"] = "XOF"
    text = build_markdown(ReportInput.model_validate(payload))
    assert "| Devise | XAF |" in text
    assert "| Devise | XOF |" not in text


def test_hypotheses_use_the_unit_declared_by_the_engine() -> None:
    payload = _payload()
    payload["scenario"]["assumptions"]["loss_rate"] = {
        "value": 0.04,
        "min": 0.02,
        "max": 0.08,
        "source": "Pertes observées",
    }
    payload["scenario"]["assumptions"]["reorder_lead_time_months"] = {
        "value": 1.0,
        "min": 0.5,
        "max": 2.0,
        "source": "Délai fournisseur",
    }
    text = build_markdown(ReportInput.model_validate(payload))
    assert "4,00 %" in text
    assert "1,00 mois" in text
    assert "220,00 unités/mois" in text
    assert "0,04 XAF" not in text
