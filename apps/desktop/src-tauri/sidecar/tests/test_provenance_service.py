"""Tests de la phase 12 : trajectoires, provenance et explication vérifiée."""

from __future__ import annotations

from typing import Any

import pytest
from engine import (
    CancelToken,
    Scenario,
    SimulationConfig,
    deterministic_explanation,
    simulate,
    validate_explanation,
)
from see_storage import ProjectStore

from sidecar.explain_service import ExplainService
from sidecar.provenance_service import ProvenanceServiceError, build
from sidecar.simulation_service import (
    MAX_RETAINED_SAMPLES,
    Job,
    SimulationService,
    SimulationServiceError,
)

SCENARIO: dict[str, Any] = {
    "name": "Provenance",
    "horizonMonths": 4,
    "assumptions": {
        "initial_cash": {"value": 100_000},
        "unit_price": {
            "value": 20,
            "min": 15,
            "max": 25,
            "confidence": 0.7,
            "distribution": {"kind": "normal", "mean": 20, "std": 2},
        },
        "unit_cost": {"value": 8},
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


@pytest.fixture
def scenario() -> Scenario:
    return Scenario.model_validate(SCENARIO)


@pytest.fixture
def service(scenario: Scenario):
    instance = SimulationService()
    config = SimulationConfig(runs=20, seed=5)
    result = simulate(scenario, config)
    result.run_id = "run-test"
    job = Job(
        run_id="run-test",
        project_id="project-1",
        quality="draft",
        cancel=CancelToken(),
        notify=lambda _method, _params: None,
        scenario=scenario,
        config=config,
        seed=5,
        created_at=0.0,
        updated_at=0.0,
        status="done",
        result=result,
    )
    instance._runs[job.run_id] = job
    try:
        yield instance, job
    finally:
        instance.shutdown()


@pytest.fixture
def store(tmp_path):
    project_store = ProjectStore(tmp_path / "data")
    try:
        yield project_store
    finally:
        project_store.close()


def test_trajectories_are_bounded_and_carry_engine_metadata(service) -> None:
    instance, job = service
    result = instance.trajectories({"runId": "run-test", "count": 5})

    assert result["runId"] == "run-test"
    assert result["seed"] == 5
    assert result["runs"] == 20
    assert result["runsRetained"] == 20
    assert result["horizonMonths"] == 4
    assert len(result["trajectories"]) == 5
    first = result["trajectories"][0]
    assert first["index"] == 0
    assert len(first["profitMonthly"]) == 4

    capped = instance.trajectories({"runId": "run-test", "count": 200})
    assert len(capped["trajectories"]) == 20
    assert capped["truncated"] is True


def test_trajectories_reject_unknown_index(service) -> None:
    instance, _job = service
    with pytest.raises(SimulationServiceError) as caught:
        instance.trajectories({"runId": "run-test", "indices": [0, 99]})
    assert caught.value.code == "trajectory_invalid"


def test_evicted_sample_is_explicit(service) -> None:
    instance, job = service
    assert job.result is not None
    job.result.detach_sample()

    with pytest.raises(SimulationServiceError) as caught:
        instance.trajectories({"runId": "run-test"})
    assert caught.value.code == "run_sample_unavailable"

    with pytest.raises(SimulationServiceError) as caught:
        instance.run_params({"runId": "run-test", "index": 0})
    assert caught.value.code == "run_sample_unavailable"


def test_run_params_expose_drawn_values_and_hash(service) -> None:
    instance, job = service
    assert job.result is not None
    sample = job.result.run_sample
    assert sample is not None

    result = instance.run_params({"runId": "run-test", "index": 3})

    assert result["scenariosHash"]
    assert set(result["parameters"]) == set(sample.parameters)
    assert result["parameters"]["unit_price"] == pytest.approx(
        float(sample.parameters["unit_price"][3])
    )


def test_only_recent_samples_are_retained(scenario: Scenario) -> None:
    instance = SimulationService()
    config = SimulationConfig(runs=5, seed=1)
    try:
        jobs: list[Job] = []
        for index in range(MAX_RETAINED_SAMPLES + 2):
            result = simulate(scenario, config)
            result.run_id = f"run-{index}"
            job = Job(
                run_id=result.run_id,
                project_id="project-1",
                quality="draft",
                cancel=CancelToken(),
                notify=lambda _method, _params: None,
                scenario=scenario,
                config=config,
                seed=1,
                created_at=0.0,
                updated_at=float(index),
                status="done",
                result=result,
            )
            instance._runs[job.run_id] = job
            jobs.append(job)

        instance._trim_samples_locked()

        retained = [job for job in jobs if job.result and job.result.run_sample]
        assert len(retained) == MAX_RETAINED_SAMPLES
        assert {job.run_id for job in retained} == {
            f"run-{index}" for index in range(MAX_RETAINED_SAMPLES + 2)
        } - {"run-0", "run-1"}
    finally:
        instance.shutdown()


def test_provenance_uses_engine_values_without_project_identity(service) -> None:
    instance, job = service
    assert job.result is not None

    payload = build(instance, {"runId": "run-test", "metric": "profit_p50"})
    provenance = payload["provenance"]

    assert provenance["value"] == pytest.approx(job.result.metrics.p50)
    assert provenance["seed"] == 5
    assert provenance["runs"] == 20
    assert provenance["unit"] == "XOF"
    inputs = {item["key"]: item for item in provenance["inputs"]}
    assert inputs["unit_price"]["confidence"] == pytest.approx(0.7)
    assert sum(item["contribution"] for item in provenance["inputs"]) == pytest.approx(1.0)
    encoded = str(provenance)
    assert "Provenance" not in encoded
    assert "project-1" not in encoded


def test_provenance_rejects_unknown_metric(service) -> None:
    instance, _job = service
    with pytest.raises(ProvenanceServiceError) as caught:
        build(instance, {"runId": "run-test", "metric": "profit_magic"})
    assert caught.value.code == "provenance_invalid"


def _attach_project(store, job, name: str = "Projet") -> str:
    project = store.create_project(name)
    job.project_id = project.id
    return project.id


def test_explain_without_provider_returns_valid_fallback(service, store) -> None:
    instance, job = service
    project_id = _attach_project(store, job)
    explain = ExplainService()

    result = explain.explain(
        store, instance, {"projectId": project_id, "runId": "run-test", "metric": "profit_p50"}
    )

    assert result["source"] == "fallback"
    assert result["reason"] == "no_provider"
    assert result["cached"] is False
    assert validate_explanation(result["explanation"], result["provenance"]) == []
    assert result["explanation"] == deterministic_explanation(result["provenance"])


def test_explain_rejects_run_from_another_project(service, store) -> None:
    instance, job = service
    _attach_project(store, job)
    other = store.create_project("Autre projet")
    explain = ExplainService()

    with pytest.raises(ProvenanceServiceError) as caught:
        explain.explain(
            store,
            instance,
            {"projectId": other.id, "runId": "run-test", "metric": "profit_p50"},
        )
    assert caught.value.code == "explanation_invalid"


def test_explain_caches_successful_answers_per_project(service, store) -> None:
    instance, job = service
    project_id = _attach_project(store, job)
    explain = ExplainService()
    calls: list[int] = []

    async def fake_provider(*_args: Any):
        calls.append(1)
        return (
            {"summary": "Ce chiffre provient du calcul.", "points": [], "caveats": []},
            False,
        )

    explain._ask_provider = fake_provider  # type: ignore[method-assign]
    profile = {
        "id": "profile-1",
        "projectId": project_id,
        "provider": "openai",
        "model": "gpt-test",
    }
    params = {
        "projectId": project_id,
        "runId": "run-test",
        "metric": "profit_p50",
        "profile": profile,
    }

    first = explain.explain(store, instance, params)
    second = explain.explain(store, instance, params)

    assert first["source"] == "llm"
    assert first["cached"] is False
    assert second["cached"] is True
    assert len(calls) == 1
    assert project_id in explain._cache
    assert len(explain._cache[project_id]) == 1


def test_explain_repairs_invented_numbers(service, store) -> None:
    instance, job = service
    project_id = _attach_project(store, job)
    explain = ExplainService()
    answers = [
        '{"summary": "Le profit atteint 999 999 FCFA.", "points": [], "caveats": []}',
        '{"summary": "Ce chiffre provient du calcul.", "points": [], "caveats": []}',
    ]

    async def fake_chat(*_args: Any):
        return answers.pop(0)

    explain._chat = fake_chat  # type: ignore[method-assign]
    profile = {
        "id": "profile-1",
        "projectId": project_id,
        "provider": "openai",
        "model": "gpt-test",
    }

    result = explain.explain(
        store,
        instance,
        {
            "projectId": project_id,
            "runId": "run-test",
            "metric": "profit_p50",
            "profile": profile,
        },
    )

    assert result["source"] == "llm"
    assert result["repaired"] is True
    assert validate_explanation(result["explanation"], result["provenance"]) == []


def test_explain_falls_back_after_two_repairs(service, store) -> None:
    instance, job = service
    project_id = _attach_project(store, job)
    explain = ExplainService()
    calls: list[int] = []

    async def fake_chat(*_args: Any):
        calls.append(1)
        return '{"summary": "Un chiffre inventé: 777 777.", "points": [], "caveats": []}'

    explain._chat = fake_chat  # type: ignore[method-assign]
    profile = {
        "id": "profile-1",
        "projectId": project_id,
        "provider": "openai",
        "model": "gpt-test",
    }

    result = explain.explain(
        store,
        instance,
        {
            "projectId": project_id,
            "runId": "run-test",
            "metric": "profit_p50",
            "profile": profile,
        },
    )

    assert len(calls) == 3
    assert result["source"] == "fallback"
    assert result["reason"] == "unverified_numbers"
