from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_core import JOURNEY_STATES, BriefDraft, role_for_state
from engine import EngineError, Scenario, SimulationConfig, SimulationResult
from engine import simulate as run_simulation
from pydantic import ValidationError
from see_storage import (
    Brief,
    ProjectStore,
    ScenarioRecord,
    ScenarioVersion,
    SimulationRun,
    StorageValidationError,
)

MAX_ACTIVE_BRANCHES = 20
"""Plafond de branches actives par projet (phase 13)."""


def _required_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StorageValidationError(f"{key} doit être une chaîne non vide")
    return value.strip()


def _optional_seed(params: dict[str, Any], key: str = "seed") -> int | None:
    value = params.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise StorageValidationError(f"{key} doit être un entier ou null")
    return value


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
        "parentId": record.parent_id,
        "branchLabel": record.branch_label,
        "version": record.version,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
        "archivedAt": record.archived_at,
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
    payload = scenario.model_dump(by_alias=True, mode="json")
    raw_scenario_id = params.get("scenarioId")
    if raw_scenario_id is not None:
        if not isinstance(raw_scenario_id, str) or not raw_scenario_id.strip():
            raise StorageValidationError("scenarioId doit être une chaîne non vide")
        existing = _require_scenario(store, project_id, raw_scenario_id.strip())
        record = store.scenarios.update(
            existing.id,
            name=name.strip(),
            model=scenario.model,
            scenario=payload,
        )
        _advance(store, project_id, "hypotheses_set")
        return {"scenario": _scenario_payload(record)}
    record = store.scenarios.add(
        project_id,
        name.strip(),
        scenario.model,
        payload,
    )
    _advance(store, project_id, "hypotheses_set")
    return {"scenario": _scenario_payload(record)}


def branch_scenario(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    """Crée une branche depuis un scénario existant.

    Le parent reste intact : la branche porte ses propres hypothèses, son
    libellé et un lien ``parentId``. Aucune simulation n'est lancée ici ; le
    calcul final est demandé séparément par l'UI avec la même graine.
    """

    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    scenario_id = _required_text(params, "scenarioId")
    label = _required_text(params, "label")
    parent = store.scenarios.get(scenario_id)
    if parent is None or parent.project_id != project_id:
        raise StorageValidationError(f"scénario introuvable: {scenario_id}")

    raw = params.get("scenario")
    if raw is None:
        payload = parent.scenario
        model = parent.model
        name = parent.name
    elif isinstance(raw, dict):
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
        payload = scenario.model_dump(by_alias=True, mode="json")
        model = scenario.model
        name = scenario.name
    else:
        raise StorageValidationError("scenario doit être un objet")

    requested_name = params.get("name")
    if isinstance(requested_name, str) and requested_name.strip():
        name = requested_name.strip()

    active = store.scenarios.list(project_id, limit=MAX_ACTIVE_BRANCHES + 1)
    if len(active) >= MAX_ACTIVE_BRANCHES:
        raise StorageValidationError(
            f"limite de {MAX_ACTIVE_BRANCHES} branches actives atteinte; "
            "archivez une branche avant d'en créer une nouvelle"
        )

    record = store.scenarios.add(
        project_id,
        name,
        model,
        payload,
        parent_id=parent.id,
        branch_label=label,
    )
    _advance(store, project_id, "hypotheses_set")
    return {"scenario": _scenario_payload(record)}


def _require_scenario(
    store: ProjectStore, project_id: str, scenario_id: str
) -> ScenarioRecord:
    record = store.scenarios.get(scenario_id)
    if record is None or record.project_id != project_id:
        raise StorageValidationError(f"scénario introuvable: {scenario_id}")
    return record


def _branch_ref(record: ScenarioRecord, run: SimulationRun | None) -> dict[str, Any]:
    return {
        "scenarioId": record.id,
        "name": record.name,
        "branchLabel": record.branch_label,
        "parentId": record.parent_id,
        "updatedAt": record.updated_at,
        "archivedAt": record.archived_at,
        "lastFinalRunId": run.id if run is not None else None,
        "seed": run.seed if run is not None else None,
    }


def _run_ref(run: SimulationRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "scenarioId": run.scenario_id,
        "seed": run.seed,
        "engineVersion": run.engine_version,
        "runs": run.runs,
        "pinned": run.pinned,
        "createdAt": run.created_at,
        "summary": run.summary,
    }


def _version_ref(version: ScenarioVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "projectId": version.project_id,
        "scenarioId": version.scenario_id,
        "label": version.label,
        "seed": version.seed,
        "engineVersion": version.engine_version,
        "createdAt": version.created_at,
    }


def _latest_runs_by_scenario(
    store: ProjectStore, project_id: str
) -> dict[str, SimulationRun]:
    latest: dict[str, SimulationRun] = {}
    for run in store.runs.list(project_id, limit=1000):
        if run.scenario_id is not None and run.scenario_id not in latest:
            latest[run.scenario_id] = run
    return latest


def list_branches(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    """Liste plate des branches, triée par date de création décroissante."""

    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    include_archived = params.get("includeArchived") is True
    records = store.scenarios.list(
        project_id, limit=1000, include_archived=include_archived
    )
    latest = _latest_runs_by_scenario(store, project_id)
    return {"branches": [_branch_ref(record, latest.get(record.id)) for record in records]}


def get_scenario(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    scenario_id = _required_text(params, "scenarioId")
    return {"scenario": _scenario_payload(_require_scenario(store, project_id, scenario_id))}


def rename_scenario(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    scenario_id = _required_text(params, "scenarioId")
    name = _required_text(params, "name")
    _require_scenario(store, project_id, scenario_id)
    fields: dict[str, Any] = {"name": name}
    if "branchLabel" in params:
        label = params.get("branchLabel")
        if label is not None and not isinstance(label, str):
            raise StorageValidationError("branchLabel doit être une chaîne ou null")
        fields["branch_label"] = label.strip() if isinstance(label, str) else None
    record = store.scenarios.update(scenario_id, **fields)
    return {"scenario": _scenario_payload(record)}


def archive_scenario(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    scenario_id = _required_text(params, "scenarioId")
    record = _require_scenario(store, project_id, scenario_id)
    pinned = [
        run
        for run in store.runs.list(project_id, limit=1000)
        if run.scenario_id == record.id and run.pinned
    ]
    if pinned and params.get("confirmPinned") is not True:
        raise StorageValidationError(
            f"{len(pinned)} run(s) épinglé(s) référencent cette branche; "
            "confirmez l'archivage (confirmPinned)"
        )
    archived = store.scenarios.archive(scenario_id, archived=True)
    return {
        "scenario": _scenario_payload(archived),
        "archived": True,
        "pinnedRuns": len(pinned),
    }


def unarchive_scenario(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    scenario_id = _required_text(params, "scenarioId")
    _require_scenario(store, project_id, scenario_id)
    record = store.scenarios.archive(scenario_id, archived=False)
    return {"scenario": _scenario_payload(record)}


def list_runs(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    scenario_id = params.get("scenarioId")
    if scenario_id is not None and not isinstance(scenario_id, str):
        raise StorageValidationError("scenarioId doit être une chaîne")
    seed = _optional_seed(params)
    limit = params.get("limit", 50)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise StorageValidationError("limit doit être un entier entre 1 et 500")
    runs = store.runs.list(project_id, limit=1000)
    selected = [
        run
        for run in runs
        if (scenario_id is None or run.scenario_id == scenario_id)
        and (seed is None or run.seed == seed)
    ][:limit]
    return {"runs": [_run_ref(run) for run in selected]}


def pin_run(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    run_id = _required_text(params, "runId")
    pinned = params.get("pinned")
    if not isinstance(pinned, bool):
        raise StorageValidationError("pinned doit être un booléen")
    run = store.runs.get(run_id)
    if run is None or run.project_id != project_id:
        raise StorageValidationError(f"run introuvable: {run_id}")
    updated = store.runs.set_pinned(run_id, pinned)
    return {"run": _run_ref(updated)}


def compare_runs(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    run_ids = params.get("runIds")
    if (
        not isinstance(run_ids, list)
        or len(run_ids) != 2
        or not all(isinstance(item, str) and item.strip() for item in run_ids)
        or run_ids[0] == run_ids[1]
    ):
        raise StorageValidationError("runIds doit contenir deux identifiants distincts")
    compiled: list[dict[str, Any]] = []
    for run_id in run_ids:
        run = store.runs.get(run_id.strip())
        if run is None or run.project_id != project_id:
            raise StorageValidationError(f"run introuvable: {run_id}")
        result = run.result
        if result is None and run.result_path is not None:
            try:
                result = store.load_run_detail(project_id, run.id)
            except Exception as exc:  # noqa: BLE001 - message métier explicite
                raise StorageValidationError(
                    f"résultat du run indisponible: {run.id}"
                ) from exc
        if result is None:
            raise StorageValidationError(f"résultat du run indisponible: {run.id}")
        compiled.append(
            {
                "id": run.id,
                "scenarioId": run.scenario_id,
                "seed": run.seed,
                "engineVersion": run.engine_version,
                "result": result,
            }
        )
    first, second = compiled
    return {
        "runs": compiled,
        "sameSeed": first["seed"] == second["seed"],
        "sameEngineVersion": first["engineVersion"] == second["engineVersion"],
    }


def create_version(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    label = _required_text(params, "label")
    seed = _optional_seed(params)
    scenario_id = params.get("scenarioId")
    if scenario_id is not None:
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise StorageValidationError("scenarioId doit être une chaîne non vide")
        record = _require_scenario(store, project_id, scenario_id.strip())
    else:
        records = store.scenarios.list(project_id, limit=1)
        if not records:
            raise StorageValidationError(
                "aucun scénario enregistré: impossible de créer une version"
            )
        record = records[0]
    latest = _latest_runs_by_scenario(store, project_id).get(record.id)
    version = store.versions.create(
        project_id,
        record.id,
        label,
        record.scenario,
        seed=seed,
        engine_version=latest.engine_version if latest is not None else None,
    )
    return {"version": _version_ref(version)}


def list_versions(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    return {
        "versions": [_version_ref(item) for item in store.versions.list(project_id)]
    }


def restore_version(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    version_id = _required_text(params, "versionId")
    version = store.versions.get(version_id)
    if version is None or version.project_id != project_id:
        raise StorageValidationError(f"version introuvable: {version_id}")
    label = params.get("label")
    if label is not None and (not isinstance(label, str) or not label.strip()):
        raise StorageValidationError("label doit être une chaîne non vide")
    active = store.scenarios.list(project_id, limit=MAX_ACTIVE_BRANCHES + 1)
    if len(active) >= MAX_ACTIVE_BRANCHES:
        raise StorageValidationError(
            f"limite de {MAX_ACTIVE_BRANCHES} branches actives atteinte; "
            "archivez une branche avant de restaurer une version"
        )
    record = store.versions.restore(
        version_id, label=label.strip() if isinstance(label, str) else None
    )
    _advance(store, project_id, "hypotheses_set")
    return {"scenario": _scenario_payload(record)}


def delete_version(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    version_id = _required_text(params, "versionId")
    version = store.versions.get(version_id)
    if version is None or version.project_id != project_id:
        raise StorageValidationError(f"version introuvable: {version_id}")
    return {"deleted": store.versions.delete(version_id)}


def simulate(
    store: ProjectStore,
    params: dict[str, Any],
    progress: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    raw_scenario = params.get("scenario")
    raw_scenario_id = params.get("scenarioId")
    scenario_id: str | None = None
    if raw_scenario_id is not None:
        if not isinstance(raw_scenario_id, str) or not raw_scenario_id.strip():
            raise StorageValidationError("scenarioId doit être une chaîne non vide")
        scenario_id = raw_scenario_id.strip()
        _require_scenario(store, project_id, scenario_id)
    if raw_scenario is None:
        if scenario_id is not None:
            scenario_payload = _require_scenario(store, project_id, scenario_id).scenario
        else:
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

    run, record = _persist_result(
        store,
        project_id,
        scenario,
        result,
        create_scenario=True if raw_scenario is not None else None,
        scenario_id=scenario_id,
    )
    return {
        "run": _run_payload(store, run),
        "scenario": _scenario_payload(record),
        "result": result.to_dict(),
    }


def persist_result(
    store: ProjectStore,
    project_id: str,
    scenario: Scenario,
    result: SimulationResult,
    *,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """Persiste un résultat déjà calculé, sur le thread principal.

    Utilisé par ``simulation.start`` en qualité ``final`` : le worker calcule,
    puis le thread principal écrit une seule fois le run en base. Le scénario
    existant est réutilisé s'il est identique ; sinon une nouvelle version est
    enregistrée. ``scenario_id`` rattache explicitement le run à une branche.
    """

    run, record = _persist_result(
        store,
        project_id,
        scenario,
        result,
        create_scenario=None,
        scenario_id=scenario_id,
    )
    return {
        "run": _run_payload(store, run),
        "scenario": _scenario_payload(record),
    }


def _persist_result(
    store: ProjectStore,
    project_id: str,
    scenario: Scenario,
    result: SimulationResult,
    *,
    create_scenario: bool | None,
    scenario_id: str | None = None,
) -> tuple[Any, Any]:
    store.projects.require(project_id)
    scenario_payload = scenario.model_dump(by_alias=True, mode="json")
    if scenario_id is not None:
        record = _require_scenario(store, project_id, scenario_id)
        if record.scenario != scenario_payload:
            record = store.scenarios.update(
                record.id,
                name=scenario.name,
                model=scenario.model,
                scenario=scenario_payload,
            )
    else:
        scenarios = store.scenarios.list(project_id, limit=1)
        record = scenarios[0] if scenarios else None
        if (
            record is None
            or create_scenario is True
            or (create_scenario is None and record.scenario != scenario_payload)
        ):
            record = store.scenarios.add(
                project_id,
                scenario.name,
                scenario.model,
                scenario_payload,
            )
    run = store.save_run(
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
    return run, record


__all__ = [
    "MAX_ACTIVE_BRANCHES",
    "archive_scenario",
    "branch_scenario",
    "compare_runs",
    "create_version",
    "data",
    "delete_version",
    "get_scenario",
    "list_branches",
    "list_runs",
    "list_versions",
    "persist_result",
    "pin_run",
    "rename_scenario",
    "restore_version",
    "save_brief",
    "save_scenario",
    "simulate",
    "unarchive_scenario",
]
