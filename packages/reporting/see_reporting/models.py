"""Contrat d'entrée du rapport.

Le contrat est versionné et tolère les champs inconnus : un producteur plus
récent peut enrichir le payload sans casser un constructeur plus ancien,
comme le recommandent les règles d'évolution de schéma de DDIA (chapitre 4).
Les champs strictement nécessaires restent validés par Pydantic.
"""

from __future__ import annotations

from typing import Any, Literal

from engine import Scenario, SimulationResult
from pydantic import BaseModel, ConfigDict, Field


def to_camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class ReportModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class ReportProject(ReportModel):
    name: str
    currency: str
    description: str | None = None
    sector: str | None = None


class ReportBranch(ReportModel):
    scenario_id: str
    name: str
    branch_label: str | None = None
    parent_id: str | None = None
    updated_at: str | None = None
    archived_at: str | None = None
    last_final_run_id: str | None = None
    seed: int | None = None


class ReportVersion(ReportModel):
    id: str
    scenario_id: str
    label: str
    seed: int | None = None
    engine_version: str | None = None
    created_at: str | None = None


class ReportInput(ReportModel):
    """Faits nécessaires au dossier, tous déjà produits ailleurs.

    ``result`` et ``scenario`` sont les objets validés du moteur : le rapport ne
    peut pas inventer une forme de résultat ni une hypothèse.
    """

    schema_version: Literal["1.0.0"] = "1.0.0"
    project: ReportProject
    scenario: Scenario | None = None
    result: SimulationResult
    branches: list[ReportBranch] = Field(default_factory=list)
    versions: list[ReportVersion] = Field(default_factory=list)
    generated_at: str
    narration: str | None = None


def parse_report_input(payload: dict[str, Any]) -> ReportInput:
    """Valide un payload brut, y compris les sous-objets du moteur."""

    return ReportInput.model_validate(payload)
