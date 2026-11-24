"""Tests de la phase 15 : modèle importable et dossier déterministe."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from see_storage import ProjectStore, StorageValidationError

from sidecar import report_service, template_service

TEMPLATE_ID = "retail-depot-brazzaville"


@pytest.fixture
def store(tmp_path: Path):
    project_store = ProjectStore(tmp_path / "data")
    try:
        yield project_store
    finally:
        project_store.close()


@pytest.fixture
def service() -> template_service.TemplateService:
    return template_service.TemplateService()


def _import(store: ProjectStore, service: template_service.TemplateService) -> dict[str, Any]:
    return service.create_project(store, {"templateId": TEMPLATE_ID})


def test_template_list_contains_example(service: template_service.TemplateService) -> None:
    result = service.list()
    ids = {template["id"] for template in result["templates"]}
    assert TEMPLATE_ID in ids
    assert result["errors"] == []


def test_template_rejects_traversal(service: template_service.TemplateService) -> None:
    with pytest.raises(StorageValidationError):
        service.load("../secret")
    with pytest.raises(StorageValidationError):
        service.load("retail-depot-brazzaville/../../etc")


def test_import_creates_brief_scenario_version_and_branch(
    store: ProjectStore, service: template_service.TemplateService
) -> None:
    imported = _import(store, service)
    project = imported["project"]
    assert project["currency"] == "XAF"
    assert project["metadata"]["templateId"] == TEMPLATE_ID

    data = store.projects.require(project["id"])
    assert data.sector == "retail"

    brief = store.briefs.latest(project["id"])
    assert brief is not None
    assert brief.status == "validated"

    scenarios = store.scenarios.list(project["id"], limit=10)
    assert len(scenarios) == 2
    base = next(item for item in scenarios if item.branch_label is None)
    branch = next(item for item in scenarios if item.branch_label == "Prix -10 %")
    assert base.scenario["horizonMonths"] == 36
    assert base.scenario["currency"] == "XAF"
    assert branch.parent_id == base.id
    assert branch.scenario["assumptions"]["unit_price"]["value"] == 12465

    versions = store.versions.list(project["id"])
    assert [version.label for version in versions] == ["Scénario de départ"]
    assert versions[0].seed == 42


def test_templates_are_never_shared_between_projects(
    store: ProjectStore, service: template_service.TemplateService
) -> None:
    first = _import(store, service)
    second = _import(store, service)
    assert first["project"]["id"] != second["project"]["id"]
    assert first["scenario"]["id"] != second["scenario"]["id"]


def test_import_rolls_back_when_a_step_fails(
    store: ProjectStore,
    service: template_service.TemplateService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise StorageValidationError("panne simulée")

    monkeypatch.setattr(template_service.project_service, "create_version", boom)
    with pytest.raises(StorageValidationError):
        _import(store, service)
    assert store.projects.list() == []


def test_import_rolls_back_when_a_branch_is_invalid(
    store: ProjectStore, tmp_path: Path
) -> None:
    source = template_service.bundled_template_dir() / TEMPLATE_ID
    examples = tmp_path / "examples"
    target = examples / "broken"
    shutil.copytree(source, target)
    payload = json.loads((target / template_service.TEMPLATE_FILENAME).read_text("utf-8"))
    payload["id"] = "broken"
    payload["branches"][0]["overrides"]["unit_price"]["confidence"] = 2
    (target / template_service.TEMPLATE_FILENAME).write_text(
        json.dumps(payload), encoding="utf-8"
    )

    service = template_service.TemplateService(base_dir=examples)
    with pytest.raises(StorageValidationError):
        service.create_project(store, {"templateId": "broken"})

    assert store.projects.list() == []


def _final_run(store: ProjectStore, service: template_service.TemplateService):
    imported = _import(store, service)
    project_id = imported["project"]["id"]
    scenario_record = imported["scenario"]
    from engine import Scenario, SimulationConfig, simulate

    scenario = Scenario.model_validate(scenario_record["scenario"])
    result = simulate(scenario, SimulationConfig(runs=40, seed=42))
    payload = result.model_dump(by_alias=True, mode="json")
    run = store.save_run(
        project_id,
        result.engine_version,
        result.runs,
        {"p50": result.metrics.p50},
        result=payload,
        max_inline_bytes=0,
        scenario_id=scenario_record["id"],
        seed=42,
        quality="final",
    )
    return project_id, run, payload


def test_report_is_deterministic_and_traceable(
    store: ProjectStore, service: template_service.TemplateService
) -> None:
    project_id, run, _payload = _final_run(store, service)
    params = {
        "projectId": project_id,
        "runId": run.id,
        "generatedAt": "2026-11-23T12:00:00+00:00",
    }
    first = report_service.build(store, params)
    second = report_service.build(store, params)
    assert first == second
    assert first["format"] == "markdown"
    assert first["runId"] == run.id
    assert first["seed"] == 42
    assert first["filename"].endswith("-dossier-20261123.md")
    assert "Simulation basée sur vos hypothèses" in first["content"]
    assert "| Graine | 42 |" in first["content"]
    assert "Point mort structurel" in first["content"]
    assert "Traçabilité" in first["content"]
    assert "Prix -10 %" in first["content"]
    assert "Scénario de départ" in first["content"]


def test_draft_runs_are_never_persisted(
    store: ProjectStore, service: template_service.TemplateService
) -> None:
    project_id, run, _payload = _final_run(store, service)
    with pytest.raises(StorageValidationError):
        store.runs.add(
            project_id,
            run.engine_version,
            run.runs,
            {"p50": 0},
            scenario_id=run.scenario_id,
            seed=42,
            quality="draft",
        )


def test_report_rejects_a_cancelled_run(
    store: ProjectStore, service: template_service.TemplateService
) -> None:
    project_id, run, _payload = _final_run(store, service)
    cancelled = store.runs.add(
        project_id,
        run.engine_version,
        run.runs,
        {"p50": 0},
        scenario_id=run.scenario_id,
        seed=42,
        quality="final",
        status="cancelled",
    )
    with pytest.raises(StorageValidationError):
        report_service.build(
            store, {"projectId": project_id, "runId": cancelled.id}
        )


def test_report_requires_an_existing_run(
    store: ProjectStore, service: template_service.TemplateService
) -> None:
    imported = _import(store, service)
    with pytest.raises(StorageValidationError):
        report_service.build(store, {"projectId": imported["project"]["id"]})


def test_report_does_not_leak_paths_or_keys(
    store: ProjectStore, service: template_service.TemplateService
) -> None:
    project_id, run, _payload = _final_run(store, service)
    content = report_service.build(
        store,
        {
            "projectId": project_id,
            "runId": run.id,
            "generatedAt": "2026-11-23T12:00:00+00:00",
        },
    )["content"]
    lowered = content.lower()
    assert "apikey" not in lowered
    assert "c:\\" not in lowered
    assert "/home/" not in lowered


def test_pdf_report_is_deterministic_and_valid(
    store: ProjectStore, service: template_service.TemplateService
) -> None:
    import base64

    project_id, run, _payload = _final_run(store, service)
    params = {
        "projectId": project_id,
        "runId": run.id,
        "generatedAt": "2026-11-23T12:00:00+00:00",
    }
    first = report_service.build_pdf(store, params)
    second = report_service.build_pdf(store, params)
    assert first == second
    assert first["format"] == "pdf"
    assert first["filename"].endswith("-dossier-20261123.pdf")
    assert first["filename"] != report_service.build(store, params)["filename"]
    content = base64.b64decode(first["contentBase64"])
    assert content.startswith(b"%PDF-1.4")
    assert content.rstrip().endswith(b"%%EOF")
    assert len(content) == first["byteLength"]
    assert "Traçabilité".encode("cp1252") in content
    assert b"C:\\" not in content


def test_pdf_report_rejects_a_draft_or_missing_run(
    store: ProjectStore, service: template_service.TemplateService
) -> None:
    imported = _import(store, service)
    with pytest.raises(StorageValidationError):
        report_service.build_pdf(store, {"projectId": imported["project"]["id"]})
