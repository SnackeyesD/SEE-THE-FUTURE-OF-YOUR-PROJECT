from __future__ import annotations

import pytest
from pydantic import ValidationError

from sidecar.protocol_models import (
    PROTOCOL_VERSION,
    JSONRPCRequest,
    Scenario,
    SimulationResult,
)


def test_protocol_version_matches_schema() -> None:
    assert PROTOCOL_VERSION == "1.15.0"


def test_request_accepts_valid_payload() -> None:
    request = JSONRPCRequest.model_validate(
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {"echo": "hi"}}
    )
    assert request.method == "ping"
    assert request.id == 1
    assert request.params == {"echo": "hi"}


def test_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        JSONRPCRequest.model_validate(
            {"jsonrpc": "2.0", "method": "ping", "unexpected": True}
        )


def test_request_requires_jsonrpc_2() -> None:
    with pytest.raises(ValidationError):
        JSONRPCRequest.model_validate({"jsonrpc": "1.0", "method": "ping"})


def test_old_simulation_result_without_v3_fields_is_still_valid() -> None:
    """Un run stocké en protocole 1.7.0 doit rester lisible après la phase 02."""
    payload = {
        "runId": "abc",
        "engineVersion": "0.1.0",
        "scenarioName": "Ancien run",
        "model": "retail_depot",
        "currency": "XOF",
        "horizonMonths": 1,
        "runs": 10,
        "seed": 42,
        "durationMs": 1.0,
        "metrics": {
            "meanProfit": 1.0,
            "medianProfit": 1.0,
            "stdProfit": 0.0,
            "minProfit": 1.0,
            "maxProfit": 1.0,
            "p10": 1.0,
            "p50": 1.0,
            "p90": 1.0,
            "lossProbability": 0.0,
            "profitPositiveProbability": 1.0,
            "meanRevenue": 2.0,
            "meanCosts": 1.0,
            "meanTax": 0.0,
            "meanCashEnd": 2.0,
            "meanUnitsSold": 1.0,
            "meanUnitsLost": 0.0,
            "meanStockoutMonths": 0.0,
            "meanEndStock": 0.0,
            "meanInventoryValue": 0.0,
            "meanProfitMargin": 0.5,
        },
        "histogram": {"bins": []},
        "monthly": {
            "values": [
                {
                    "index": 1,
                    "month": 1,
                    "meanRevenue": 2.0,
                    "meanProfit": 1.0,
                    "meanDemand": 1.0,
                    "meanUnitsSold": 1.0,
                    "meanStockEnd": 0.0,
                    "stockoutProbability": 0.0,
                }
            ]
        },
        "sensitivity": [],
        "breakEven": {
            "monthlyFixedCosts": 0.0,
            "unitMargin": 1.0,
            "breakEvenUnitsMonthly": 0.0,
            "breakEvenRevenueMonthly": 0.0,
        },
    }

    result = SimulationResult.model_validate(payload)

    assert result.runsRetained is None
    assert result.metrics.cashNegativeProbability is None
    assert result.metrics.minCashCdf is None
    assert result.monthly.values[0].profitP10 is None


def test_scenario_accepts_events_with_schema_version_1_1() -> None:
    scenario = Scenario.model_validate(
        {
            "schemaVersion": "1.1.0",
            "name": "Avec événement",
            "events": [
                {
                    "id": "ev1",
                    "type": "demand_peak",
                    "startMonth": 3,
                    "durationMonths": 2,
                    "target": "demand_mean_monthly",
                    "mode": "multiplicative",
                    "magnitude": {"kind": "uniform", "low": 1.1, "high": 1.4},
                    "probability": 0.5,
                }
            ],
        }
    )
    assert scenario.events is not None
    assert scenario.events[0].startMonth == 3
    assert scenario.events[0].magnitude.kind == "uniform"


def test_analysis_protocol_models_accept_camel_case_payloads() -> None:
    from sidecar.protocol_models import (
        AnalysisCancelled,
        AnalysisDone,
        AnalysisError,
        AnalysisJobAccepted,
        SimulationGoalSeekParams,
        SimulationSurfaceParams,
    )

    accepted = AnalysisJobAccepted.model_validate(
        {"jobId": "abc", "accepted": True, "replacedJobId": "def"}
    )
    assert accepted.replacedJobId == "def"

    surface = SimulationSurfaceParams.model_validate(
        {
            "projectId": "p1",
            "scenario": {"name": "Test"},
            "axisX": {"key": "unit_price", "minimum": 1, "maximum": 2},
            "axisY": {"key": "unit_cost", "minimum": 0, "maximum": 1},
            "grid": [2, 2],
            "runs": 10,
            "seed": 1,
            "metric": "profit_p50",
        }
    )
    assert surface.axisX.key == "unit_price"
    assert surface.grid == [2, 2]

    goal = SimulationGoalSeekParams.model_validate(
        {
            "projectId": "p1",
            "scenario": {"name": "Test"},
            "objective": {
                "metric": "profit_p50",
                "comparator": ">=",
                "target": 100,
            },
            "levers": [{"key": "unit_price", "minimum": 1, "maximum": 2}],
            "locked": [],
            "maxEvaluations": 20,
        }
    )
    assert goal.objective.target == 100
    assert goal.locked == []

    done = AnalysisDone.model_validate(
        {
            "jobId": "abc",
            "kind": "surface",
            "result": {
                "xValues": [1.0],
                "yValues": [2.0],
                "zP50": [[3.0]],
                "current": [1.0, 2.0],
                "metric": "profit_p50",
                "runs": 10,
                "seed": 1,
                "grid": [1, 1],
                "cost": 10,
                "durationMs": 1.0,
            },
        }
    )
    assert done.result.metric == "profit_p50"

    cancelled = AnalysisCancelled.model_validate(
        {"jobId": "abc", "kind": "goalseek", "reason": "analysis_cancelled"}
    )
    assert cancelled.reason == "analysis_cancelled"

    error = AnalysisError.model_validate(
        {
            "jobId": "abc",
            "kind": "surface",
            "code": "analysis_invalid",
            "message": "invalide",
            "retryable": False,
        }
    )
    assert error.code == "analysis_invalid"
