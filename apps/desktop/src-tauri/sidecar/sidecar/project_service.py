from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_core import JOURNEY_STATES, BriefDraft, role_for_state
from engine import EngineError, Scenario, SimulationConfig
from engine import simulate as run_simulation
from pydantic import ValidationError
from see_storage import (
    Brief,
    ProjectStore,
    ScenarioRecord,
    SimulationRun,
    StorageValidationError,
)


def _required_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StorageValidationError(f"{key} doit être une chaîne non vide")
    return value.strip()


def _brief_payload(brief: Brief | None) -> dict[str, Any] | None:
    if brief is None:
        return None
    return {
        "id": brief.id,
        "projectId": brief.project_id,
        "version": brief.version,
        "content": brief.content,
        "status": brief.status,
        "createdAt": brief.created_at,
        "updatedAt": brief.updated_at,
    }


def _scenario_payload(record: ScenarioRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "id": record.id,
        "projectId": record.project_id,
        "name": record.name,
        "model": record.model,
        "scenario": record.scenario,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def _run_payload(store: ProjectStore, run: SimulationRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    result = run.result
    if result is None and run.result_path is not None:
        try:
            result = store.load_run_detail(run.project_id, run.id)
        except Exception:
            result = None
    return {
        "id": run.id,
        "projectId": run.project_id,
        "scenarioId": run.scenario_id,
        "engineVersion": run.engine_version,
        "seed": run.seed,
        "runs": run.runs,
        "durationMs": run.duration_ms,
        "summary": run.summary,
        "result": result,
        "createdAt": run.created_at,
    }


def _advance(store: ProjectStore, project_id: str, target: str) -> None:
    session = store.agent_sessions.get(project_id)
    current = session.state if session is not None else "idea"
    if JOURNEY_STATES.index(current) >= JOURNEY_STATES.index(target):
        return
    store.agent_sessions.upsert(
        project_id,
        target,
        role_for_state(target),
        list(session.thread) if session is not None else [],
    )


def data(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    scenarios = store.scenarios.list(project_id, limit=1)
    runs = store.runs.list(project_id, limit=1)
    return {
        "projectId": project_id,
        "brief": _brief_payload(store.briefs.latest(project_id)),
        "scenario": _scenario_payload(scenarios[0] if scenarios else None),
        "run": _run_payload(store, runs[0] if runs else None),
    }


def save_brief(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    raw = params.get("content")
    if not isinstance(raw, dict):
        raise StorageValidationError("content doit être un objet")
    try:
        draft = BriefDraft.model_validate(raw)
    except ValidationError as exc:
        raise StorageValidationError(
            "brief invalide: "
            + "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_url=False)
            )
        ) from exc
    requested = params.get("status", "validated")
    missing = draft.missing_fields()
    if requested == "validated":
        if missing:
            raise StorageValidationError(
                "champs requis manquants: " + ", ".join(missing)
            )
        status = "validated"
    elif requested == "draft":
        status = "draft"
    else:
        raise StorageValidationError("statut de brief invalide")
    content = draft.model_dump(by_alias=True, exclude_none=True)
    brief = store.briefs.add_version(project_id, content, status=status)
    if status == "validated":
        _advance(store, project_id, "brief_validated")
    else:
        _advance(store, project_id, "brief_draft")
    return {"brief": _brief_payload(brief)}


def save_scenario(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    raw = params.get("scenario")
    if not isinstance(raw, dict):
        raise StorageValidationError("scenario doit être un objet")
    try:
        scenario = Scenario.model_validate(raw)
    except ValidationError as exc:
        raise StorageValidationError(
            "scénario invalide: "
            + "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_url=False)
            )
        ) from exc
    if not scenario.assumptions:
        raise StorageValidationError("au moins une hypothèse est requise")
    name = params.get("name")
    if not isinstance(name, str) or not name.strip():
        name = scenario.name
    record = store.scenarios.add(
        project_id,
        name.strip(),
        scenario.model,
        scenario.model_dump(by_alias=True, mode="json"),
    )
    _advance(store, project_id, "hypotheses_set")
    return {"scenario": _scenario_payload(record)}


def simulate(
    store: ProjectStore,
    params: dict[str, Any],
    progress: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    raw_scenario = params.get("scenario")
    if raw_scenario is None:
        existing = store.scenarios.list(project_id, limit=1)
        if not existing:
            raise StorageValidationError(
                "aucun scénario enregistré: définissez les hypothèses avant de simuler"
            )
        scenario_payload = existing[0].scenario
    elif isinstance(raw_scenario, dict):
        scenario_payload = raw_scenario
    else:
        raise StorageValidationError("scenario doit être un objet")
    try:
        scenario = Scenario.model_validate(scenario_payload)
        config = SimulationConfig.model_validate(params.get("config") or {})
    except ValidationError as exc:
        raise StorageValidationError(
            "paramètres de simulation invalides: "
            + "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_url=False)
            )
        ) from exc
    try:
        result = run_simulation(scenario, config, progress=progress)
    except (EngineError, ValueError) as exc:
        raise StorageValidationError(f"simulation impossible: {exc}") from exc

    scenarios = store.scenarios.list(project_id, limit=1)
    record = scenarios[0] if scenarios else None
    if raw_scenario is not None or record is None:
        record = store.scenarios.add(
            project_id,
            scenario.name,
            scenario.model,
            scenario.model_dump(by_alias=True, mode="json"),
        )
    run = store.runs.add(
        project_id,
        result.engine_version,
        result.runs,
        result.metrics.model_dump(by_alias=True, mode="json"),
        scenario_id=record.id,
        seed=result.seed,
        duration_ms=result.duration_ms,
        result=result.to_dict(),
        run_id=result.run_id,
    )
    _advance(store, project_id, "results_ready")
    return {
        "run": _run_payload(store, run),
        "scenario": _scenario_payload(record),
        "result": result.to_dict(),
    }


__all__ = ["data", "save_brief", "save_scenario", "simulate"]
