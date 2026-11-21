"""Tests unitaires du service de surface et de recherche d'objectif."""

from __future__ import annotations

import time
from typing import Any

import pytest

from sidecar.analysis_service import AnalysisService, AnalysisServiceError

SCENARIO: dict[str, Any] = {
    "name": "Analyse",
    "horizonMonths": 12,
    "assumptions": {
        "initial_cash": {"value": 0},
        "unit_price": {"value": 10},
        "unit_cost": {"value": 5},
        "fixed_costs_monthly": {"value": 0},
        "demand_mean_monthly": {"value": 10},
        "demand_cv": {"value": 0},
        "loss_rate": {"value": 0},
        "target_stock_months": {"value": 0},
        "reorder_lead_time_months": {"value": 1},
        "initial_stock": {"value": 10_000},
        "tax_rate": {"value": 0},
    },
}


def _surface_params(**overrides: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "projectId": "project-1",
        "scenario": SCENARIO,
        "axisX": {"key": "unit_price", "minimum": 10, "maximum": 20},
        "axisY": {"key": "unit_cost", "minimum": 5, "maximum": 7},
        "grid": [2, 2],
        "runs": 10,
        "seed": 3,
        "metric": "profit_p50",
        "quality": "draft",
    }
    params.update(overrides)
    return params


def _goal_params(**overrides: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "projectId": "project-1",
        "scenario": SCENARIO,
        "objective": {
            "metric": "profit_p50",
            "comparator": ">=",
            "target": 1_200,
        },
        "levers": [{"key": "unit_price", "minimum": 10, "maximum": 20}],
        "locked": [],
        "maxEvaluations": 20,
        "runs": 10,
        "seed": 4,
        "confirmQuality": None,
    }
    params.update(overrides)
    return params


@pytest.fixture
def service() -> AnalysisService:
    instance = AnalysisService(throttle_seconds=0.0)
    try:
        yield instance
    finally:
        instance.shutdown()


def _wait(predicate: Any, *, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("événement attendu non reçu")
        time.sleep(0.01)


def _terminal(messages: list[tuple[str, dict[str, Any]]]) -> list[Any]:
    return [
        (method, params)
        for method, params in messages
        if method in {"simulation.done", "simulation.cancelled", "simulation.error"}
    ]


def test_surface_job_emits_rows_progress_and_done(service: AnalysisService) -> None:
    messages: list[tuple[str, dict[str, Any]]] = []
    accepted = service.start_surface(
        _surface_params(),
        lambda method, params: messages.append((method, params)),
    )
    service.activate()
    _wait(lambda: _terminal(messages))

    assert accepted["accepted"] is True
    job_id = accepted["jobId"]
    terminal = _terminal(messages)
    assert len(terminal) == 1
    method, payload = terminal[0]
    assert method == "simulation.done"
    assert payload["jobId"] == job_id
    assert payload["kind"] == "surface"

    result = payload["result"]
    assert result["grid"] == [2, 2]
    assert result["cost"] == 4 * 10
    assert result["seed"] == 3
    assert len(result["xValues"]) == 2
    assert len(result["yValues"]) == 2
    assert len(result["zP50"]) == 2
    assert result["zP50"][0][0] == pytest.approx(600.0)
    assert result["zP50"][0][1] == pytest.approx(1_800.0)

    partials = [
        params
        for method, params in messages
        if method == "simulation.surface.partial"
    ]
    assert [partial["rowIndex"] for partial in partials] == [0, 1]
    assert [partial["seq"] for partial in partials] == [1, 2]
    assert all(len(partial["values"]) == 2 for partial in partials)
    assert partials[-1]["completedPoints"] == 4

    progress = [
        params
        for method, params in messages
        if method == "simulation.progress"
    ]
    assert progress[0]["fraction"] == 0.0
    assert progress[-1]["fraction"] == 1.0
    assert all(0.0 <= item["fraction"] <= 1.0 for item in progress)


def test_goal_seek_job_returns_the_best_point(service: AnalysisService) -> None:
    messages: list[tuple[str, dict[str, Any]]] = []
    accepted = service.start_goal_seek(
        _goal_params(), lambda method, params: messages.append((method, params))
    )
    service.activate()
    _wait(lambda: _terminal(messages))

    method, payload = _terminal(messages)[0]
    assert method == "simulation.done"
    assert payload["jobId"] == accepted["jobId"]
    assert payload["kind"] == "goalseek"
    result = payload["result"]
    assert result["feasible"] is True
    assert result["best"]["unit_price"] == pytest.approx(15)
    assert result["achieved"] == pytest.approx(1_200)
    assert result["evaluations"] <= 20
    assert result["budgetExhausted"] is False

    progress = [
        params
        for method, params in messages
        if method == "simulation.progress"
    ]
    assert progress[0]["completed"] == 0
    assert all(item["total"] == 20 for item in progress)


def test_cancel_before_activation_prevents_execution(service: AnalysisService) -> None:
    messages: list[tuple[str, dict[str, Any]]] = []
    accepted = service.start_surface(
        _surface_params(), lambda method, params: messages.append((method, params))
    )
    assert service.cancel(accepted["jobId"]) == {"cancelled": True}
    service.activate()
    time.sleep(0.2)

    terminal = _terminal(messages)
    assert terminal[0][0] == "simulation.cancelled"
    assert terminal[0][1]["reason"] == "analysis_cancelled"
    assert all(method != "simulation.done" for method, _ in messages)


def test_new_job_replaces_the_active_job_of_the_same_project(
    service: AnalysisService,
) -> None:
    messages: list[tuple[str, dict[str, Any]]] = []
    notify = lambda method, params: messages.append((method, params))  # noqa: E731
    first = service.start_surface(_surface_params(), notify)
    second = service.start_surface(_surface_params(seed=4), notify)

    assert second["replacedJobId"] == first["jobId"]
    cancelled = [
        params
        for method, params in messages
        if method == "simulation.cancelled"
    ]
    assert cancelled == [
        {"jobId": first["jobId"], "kind": "surface", "reason": "analysis_superseded"}
    ]

    other = service.start_surface(_surface_params(projectId="project-2", seed=5), notify)
    assert "replacedJobId" not in other
    service.cancel(second["jobId"])
    service.cancel(other["jobId"])


def test_engine_errors_are_reported_as_analysis_invalid(
    service: AnalysisService,
) -> None:
    messages: list[tuple[str, dict[str, Any]]] = []
    service.start_surface(
        _surface_params(
            axisX={"key": "loss_rate", "minimum": 0, "maximum": 2}
        ),
        lambda method, params: messages.append((method, params)),
    )
    service.activate()
    _wait(lambda: _terminal(messages))

    method, payload = _terminal(messages)[0]
    assert method == "simulation.error"
    assert payload["code"] == "analysis_invalid"
    assert payload["retryable"] is False


def test_invalid_params_are_rejected_before_any_job(service: AnalysisService) -> None:
    notify = lambda method, params: None  # noqa: E731

    with pytest.raises(AnalysisServiceError):
        service.start_surface(_surface_params(projectId=""), notify)
    with pytest.raises(AnalysisServiceError):
        service.start_surface(_surface_params(grid=[1, 2]), notify)
    with pytest.raises(AnalysisServiceError):
        service.start_surface(_surface_params(metric="unknown"), notify)
    with pytest.raises(AnalysisServiceError):
        service.start_surface(
            _surface_params(axisX={"key": "unit_price", "minimum": 20, "maximum": 10}),
            notify,
        )
    with pytest.raises(AnalysisServiceError):
        service.start_surface(
            _surface_params(axisY={"key": "unit_price", "minimum": 10, "maximum": 20}),
            notify,
        )
    with pytest.raises(AnalysisServiceError):
        service.start_goal_seek(_goal_params(levers=[]), notify)
    with pytest.raises(AnalysisServiceError):
        service.start_goal_seek(
            _goal_params(
                levers=[
                    {"key": "unit_price", "minimum": 10, "maximum": 20},
                    {"key": "unit_price", "minimum": 10, "maximum": 20},
                ]
            ),
            notify,
        )
    with pytest.raises(AnalysisServiceError):
        service.start_goal_seek(
            _goal_params(maxEvaluations=0), notify
        )
    with pytest.raises(AnalysisServiceError):
        service.start_goal_seek(
            _goal_params(confirmQuality="ultra"), notify
        )
