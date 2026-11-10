from __future__ import annotations

from typing import Any

from engine import Scenario

from ..errors import ToolError
from ..models import AgentModel
from .base import ToolContext, ToolExecution, ToolSpec


class HypothesesOutput(AgentModel):
    scenario: dict[str, Any]
    assumption_count: int


def set_hypotheses(payload: Scenario, context: ToolContext) -> ToolExecution:
    if not context.brief:
        raise ToolError(
            "le brief doit être enregistré avant les hypothèses",
            code="brief_required",
        )
    if not payload.assumptions:
        raise ToolError(
            "au moins une hypothèse est requise",
            code="hypotheses_required",
        )
    scenario = payload.model_dump(by_alias=True, mode="json")
    if context.save_scenario is not None:
        context.save_scenario(scenario)
    return ToolExecution(
        result={"scenario": scenario, "assumptionCount": len(payload.assumptions)},
        state_path=("hypotheses_set",),
    )


SPEC = ToolSpec(
    name="set_hypotheses",
    description=(
        "Définit les hypothèses du scénario (valeur, distribution, source, confiance, "
        "bornes) et les enregistre. Utilise uniquement des hypothèses explicites."
    ),
    input_model=Scenario,
    output_model=HypothesesOutput,
    handler=set_hypotheses,
    default_permission="allow",
)
