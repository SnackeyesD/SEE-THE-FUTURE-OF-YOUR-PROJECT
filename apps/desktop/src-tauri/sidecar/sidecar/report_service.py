"""Construction du dossier de pitch à partir des faits persistés.

Le service ne simule rien. Il rassemble un run **final** déjà enregistré, son
scénario, les branches et les versions, puis délègue la mise en forme à
``see_reporting``. Le rapport reste donc une donnée dérivée reconstructible
(DDIA, chapitres 11–12) : supprimer le fichier exporté ne perd aucune source.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import ValidationError
from see_reporting import ReportInput, build_markdown
from see_storage import (
    ProjectStore,
    ScenarioRecord,
    SimulationRun,
    StorageValidationError,
)
from see_storage.utils import utc_now

from . import project_service


class ReportServiceError(StorageValidationError):
    """Erreur de construction du dossier, exposée en ``invalid params``."""


def build(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    project = store.projects.require(project_id)
    run = _select_run(store, project_id, params.get("runId"))
    if run.quality != "final":
        raise ReportServiceError(
            "seul un run final peut produire un dossier; lancez un calcul final"
        )
    if run.status != "complete":
        raise ReportServiceError(
            "seul un run final terminé peut produire un dossier"
        )
    if not run.result_path:
        raise ReportServiceError("ce run ne contient pas de résultat détaillé")
    try:
        result = store.load_run_detail(project_id, run.id)
    except StorageValidationError as error:
        raise ReportServiceError(str(error)) from error

    scenario = _scenario_for_run(store, project_id, run.scenario_id)
    generated_at = _optional_text(params, "generatedAt") or utc_now()
    branches = project_service.list_branches(store, {"projectId": project_id})["branches"]
    versions = project_service.list_versions(store, {"projectId": project_id})["versions"]

    payload = {
        "project": {
            "name": project.name,
            "currency": project.currency,
            "description": project.description,
            "sector": project.sector,
        },
        "scenario": scenario.scenario if scenario is not None else None,
        "result": result,
        "branches": branches,
        "versions": versions,
        "generatedAt": generated_at,
    }
    try:
        report = ReportInput.model_validate(payload)
    except ValidationError as error:
        raise ReportServiceError(f"run final illisible pour le rapport: {error}") from error

    content = build_markdown(report)
    return {
        "format": "markdown",
        "content": content,
        "filename": _filename(project.name, generated_at),
        "generatedAt": generated_at,
        "runId": run.id,
        "seed": run.seed,
        "engineVersion": run.engine_version,
    }


def _select_run(store: ProjectStore, project_id: str, run_id: Any) -> SimulationRun:
    if run_id is not None:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ReportServiceError("runId doit être une chaîne non vide")
        run = store.runs.get(run_id.strip())
        if run is None or run.project_id != project_id:
            raise ReportServiceError(f"run introuvable: {run_id}")
        return run
    runs = store.runs.list(project_id, limit=50)
    for candidate in runs:
        if (
            candidate.quality == "final"
            and candidate.status == "complete"
            and candidate.result_path
        ):
            return candidate
    raise ReportServiceError(
        "aucun run final terminé avec résultat détaillé pour ce projet"
    )


def _scenario_for_run(
    store: ProjectStore, project_id: str, scenario_id: str | None
) -> ScenarioRecord | None:
    if scenario_id:
        record = store.scenarios.get(scenario_id)
        if record is not None and record.project_id == project_id:
            return record
    records = store.scenarios.list(project_id, limit=1)
    return records[0] if records else None


def _filename(project_name: str, generated_at: str) -> str:
    normalized = unicodedata.normalize("NFKD", project_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    words = [word for word in re.split(r"[^a-z0-9]+", ascii_name) if word]
    slug = "-".join(words) or "projet"
    date_part = generated_at[:10].replace("-", "") or "date"
    return f"{slug}-dossier-{date_part}.md"


def _required_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReportServiceError(f"{key} doit être une chaîne non vide")
    return value.strip()


def _optional_text(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReportServiceError(f"{key} doit être une chaîne")
    cleaned = value.strip()
    return cleaned or None
