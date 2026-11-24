"""Projets d'exemple importables.

Un modèle est une **donnée** versionnée, pas du code : le service le valide
entièrement avant de créer quoi que ce soit, puis n'effectue que des appels au
stockage existant. L'import génère toujours de nouveaux identifiants, si bien
qu'importer deux fois le même modèle produit deux projets indépendants.
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from engine import Scenario
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from see_storage import ProjectStore, StorageValidationError
from see_storage.utils import utc_now

from . import project_service

TEMPLATE_FILENAME = "template.json"
_TEMPLATE_ID = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


def _to_camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class _TemplateModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class BranchDefinition(_TemplateModel):
    label: str = Field(min_length=1, max_length=120)
    notes: str | None = None
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)


class Template(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    schema_version: Literal["1.0.0"] = "1.0.0"
    id: str
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    currency: str = Field(min_length=1, max_length=8)
    sector: str | None = None
    seed: int = Field(ge=0)
    initial_version_label: str = Field(default="Scénario de départ", max_length=120)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    brief: dict[str, Any]
    scenario: Scenario
    branches: list[BranchDefinition] = Field(default_factory=list)


def bundled_template_dir() -> Path:
    override = os.environ.get("SEE_EXAMPLES_DIR")
    if override:
        return Path(override).expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "data" / "examples"


class TemplateService:
    def __init__(self, *, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or bundled_template_dir()).resolve()

    def _template_path(self, template_id: str) -> Path:
        if not _TEMPLATE_ID.match(template_id):
            raise StorageValidationError("identifiant de modèle invalide")
        candidate = (self.base_dir / template_id / TEMPLATE_FILENAME).resolve()
        try:
            candidate.relative_to(self.base_dir)
        except ValueError as error:
            raise StorageValidationError("modèle hors du dossier autorisé") from error
        if not candidate.is_file():
            raise StorageValidationError(f"modèle introuvable: {template_id}")
        return candidate

    def load(self, template_id: str) -> Template:
        path = self._template_path(template_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise StorageValidationError(f"modèle illisible: {error}") from error
        try:
            template = Template.model_validate(payload)
        except ValidationError as error:
            raise StorageValidationError(
                "modèle invalide: "
                + "; ".join(
                    f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                    for item in error.errors(include_url=False)
                )
            ) from error
        if template.id != template_id:
            raise StorageValidationError("l'identifiant du fichier ne correspond pas au dossier")
        return template

    def list(self) -> dict[str, Any]:
        templates: list[dict[str, Any]] = []
        errors: list[str] = []
        if self.base_dir.is_dir():
            for entry in sorted(self.base_dir.iterdir()):
                if not entry.is_dir() or not (entry / TEMPLATE_FILENAME).is_file():
                    continue
                try:
                    template = self.load(entry.name)
                except StorageValidationError as error:
                    errors.append(f"{entry.name}: {error}")
                    continue
                templates.append(_summary(template))
        return {"templates": templates, "errors": errors}

    def create_project(self, store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
        template_id = _required_text(params, "templateId")
        template = self.load(template_id)
        name = _optional_text(params, "name") or template.name
        currency = _optional_text(params, "currency") or template.currency

        brief = copy.deepcopy(template.brief)
        scenario_payload = template.scenario.model_dump(by_alias=True, mode="json")
        branches = [
            (branch.label, _branch_scenario(scenario_payload, branch))
            for branch in template.branches
        ]

        project = store.create_project(
            name,
            description=template.description,
            currency=currency,
            sector=template.sector,
            metadata={
                "templateId": template.id,
                "templateVersion": template.schema_version,
                "templateSources": template.sources,
            },
        )
        try:
            project_service.save_brief(
                store,
                {
                    "projectId": project.id,
                    "content": brief,
                    "status": "validated",
                },
            )
            saved = project_service.save_scenario(
                store,
                {
                    "projectId": project.id,
                    "name": template.scenario.name,
                    "scenario": scenario_payload,
                },
            )["scenario"]
            version = project_service.create_version(
                store,
                {
                    "projectId": project.id,
                    "scenarioId": saved["id"],
                    "label": template.initial_version_label,
                    "seed": template.seed,
                },
            )["version"]
            created_branches = [
                project_service.branch_scenario(
                    store,
                    {
                        "projectId": project.id,
                        "scenarioId": saved["id"],
                        "label": label,
                        "scenario": branch_payload,
                    },
                )["scenario"]
                for label, branch_payload in branches
            ]
        except Exception:
            store.delete_project(project.id)
            raise

        return {
            "project": store.projects.require(project.id).to_dict(),
            "scenario": saved,
            "branches": created_branches,
            "seed": template.seed,
            "version": version,
            "templateId": template.id,
            "importedAt": utc_now(),
        }


def get_service(base_dir: Path | None = None) -> TemplateService:
    return TemplateService(base_dir=base_dir)


def _summary(template: Template) -> dict[str, Any]:
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "currency": template.currency,
        "sector": template.sector,
        "horizonMonths": template.scenario.horizon_months,
        "seed": template.seed,
        "sources": template.sources,
        "branchCount": len(template.branches),
    }


def _branch_scenario(base: dict[str, Any], branch: BranchDefinition) -> dict[str, Any]:
    payload = copy.deepcopy(base)
    assumptions = payload.setdefault("assumptions", {})
    for key, hypothesis in branch.overrides.items():
        assumptions[key] = copy.deepcopy(hypothesis)
    payload["name"] = f"{base.get('name', 'Scénario')} — {branch.label}"
    if branch.notes:
        payload["notes"] = branch.notes
    try:
        return Scenario.model_validate(payload).model_dump(by_alias=True, mode="json")
    except ValidationError as error:
        raise StorageValidationError(
            f"branche {branch.label!r} invalide: "
            + "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                for item in error.errors(include_url=False)
            )
        ) from error


def _required_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StorageValidationError(f"{key} doit être une chaîne non vide")
    return value.strip()


def _optional_text(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise StorageValidationError(f"{key} doit être une chaîne")
    cleaned = value.strip()
    return cleaned or None
