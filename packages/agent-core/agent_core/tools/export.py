from __future__ import annotations

import json
from typing import Literal

from ..guardrails import scrub_secrets
from ..models import AgentModel
from .base import ToolContext, ToolExecution, ToolSpec


class ExportReportInput(AgentModel):
    format: Literal["markdown"] = "markdown"


class ExportReportOutput(AgentModel):
    format: str
    content: str
    path: str | None = None


def export_report(payload: ExportReportInput, context: ToolContext) -> ToolExecution:
    lines = ["# Rapport de simulation", ""]
    if context.brief:
        lines.extend(["## Brief", "", "```json", _json(context.brief), "```", ""])
    if context.scenario:
        lines.extend(
            ["## Hypothèses", "", "```json", _json(context.scenario), "```", ""]
        )
    if context.latest_result:
        metrics = context.latest_result.get("metrics", {})
        lines.extend(
            [
                "## Résultats du moteur",
                "",
                "```json",
                _json(metrics),
                "```",
                "",
                "Tous les chiffres ci-dessus proviennent du moteur de simulation.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Résultats",
                "",
                "Aucun résultat de simulation n'est encore disponible.",
                "",
            ]
        )
    content = scrub_secrets("\n".join(lines))
    path = context.export_path
    if context.export is not None and path is not None:
        context.export(path, content)
    return ToolExecution(result={"format": payload.format, "content": content, "path": path})


def _json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


SPEC = ToolSpec(
    name="export_report",
    description=(
        "Prépare un rapport Markdown à partir du brief, des hypothèses et du dernier "
        "résultat du moteur. Ne publie rien sans autorisation."
    ),
    input_model=ExportReportInput,
    output_model=ExportReportOutput,
    handler=export_report,
    default_permission="ask",
)
