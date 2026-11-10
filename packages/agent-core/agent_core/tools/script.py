from __future__ import annotations

from typing import Any, Literal

from pydantic import Field
from see_sandbox import analyze_code, code_hash

from ..models import AgentModel
from .base import ToolContext, ToolExecution, ToolSpec


class CustomScriptInput(AgentModel):
    code: str = Field(min_length=1, max_length=32_768)
    language: Literal["python"] = "python"
    purpose: str = Field(default="", max_length=2_000)


class CustomScriptOutput(AgentModel):
    executed: bool
    requires_review: bool
    approved: bool
    reason: str
    code: str
    code_hash: str
    purpose: str
    analysis: dict[str, Any]


def run_custom_script(payload: CustomScriptInput, _context: ToolContext) -> ToolExecution:
    analysis = analyze_code(payload.code)
    digest = analysis.codeHash or code_hash(payload.code)
    if analysis.ok:
        reason = (
            "analyse statique validée ; le script reste inactif jusqu'à l'approbation "
            "humaine dans la sandbox"
        )
    else:
        details = "; ".join(issue.message for issue in analysis.issues[:4])
        reason = f"script refusé par l'analyse statique : {details}"
    return ToolExecution(
        result={
            "executed": False,
            "requiresReview": True,
            "approved": analysis.ok,
            "reason": reason,
            "code": payload.code,
            "codeHash": digest,
            "purpose": payload.purpose,
            "analysis": analysis.to_dict(),
        },
        requires_review=True,
    )


SPEC = ToolSpec(
    name="run_custom_script",
    description=(
        "Propose un script Python qui définit main(data) et renvoie un résultat structuré "
        "(summary, metrics, series, tables). Le script est analysé puis doit être approuvé "
        "dans la sandbox ; il ne s'exécute jamais directement."
    ),
    input_model=CustomScriptInput,
    output_model=CustomScriptOutput,
    handler=run_custom_script,
    default_permission="ask",
    always_ask=True,
)
