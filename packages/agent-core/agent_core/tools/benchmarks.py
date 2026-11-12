from __future__ import annotations

from datetime import date
from typing import Any

from ..models import AgentModel
from .base import ToolContext, ToolExecution, ToolSpec


class BenchmarkInput(AgentModel):
    indicator: str
    country: str | None = None
    region: str | None = None
    sector: str | None = None
    subsector: str | None = None
    as_of: date | None = None
    allow_fallback: bool = True


class BenchmarkOutput(AgentModel):
    found: bool
    record: dict[str, Any] | None = None
    untrusted: bool = False
    reason: str | None = None


def get_benchmark(payload: BenchmarkInput, context: ToolContext) -> ToolExecution:
    if context.benchmark is None:
        return ToolExecution(
            result={
                "found": False,
                "record": None,
                "untrusted": False,
                "reason": "aucun pack de benchmarks disponible",
            }
        )
    query = payload.model_dump(by_alias=True, exclude_none=True)
    result = context.benchmark(query)
    if not result.get("found"):
        return ToolExecution(
            result={
                "found": False,
                "record": None,
                "untrusted": False,
                "reason": result.get("reason")
                or "aucune valeur de référence ne correspond à la demande",
            }
        )
    return ToolExecution(
        result={
            "found": True,
            "record": result.get("record"),
            "untrusted": False,
        }
    )


SPEC = ToolSpec(
    name="get_benchmark",
    description=(
        "Interroge les référentiels locaux signés (prix, marges, coûts, loyers, "
        "demande). Retourne une valeur sourcée et datée avec son pack, sa fiabilité, "
        "sa fraîcheur et un éventuel fallback géographique. Ces valeurs sont des "
        "références de marché, jamais des résultats de simulation."
    ),
    input_model=BenchmarkInput,
    output_model=BenchmarkOutput,
    handler=get_benchmark,
    default_permission="allow",
)
