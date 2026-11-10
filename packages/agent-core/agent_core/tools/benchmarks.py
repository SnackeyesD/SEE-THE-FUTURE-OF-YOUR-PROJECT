from __future__ import annotations

from typing import Any

from ..models import AgentModel
from .base import ToolContext, ToolExecution, ToolSpec


class BenchmarkInput(AgentModel):
    key: str
    country: str | None = None
    sector: str | None = None


class BenchmarkOutput(AgentModel):
    found: bool
    record: dict[str, Any] | None = None
    untrusted: bool = True
    reason: str | None = None


def get_benchmark(payload: BenchmarkInput, context: ToolContext) -> ToolExecution:
    record = None
    if context.benchmark is not None:
        record = context.benchmark(payload.key)
    if record is None:
        return ToolExecution(
            result={
                "found": False,
                "record": None,
                "untrusted": True,
                "reason": "aucun pack de benchmarks disponible",
            }
        )
    return ToolExecution(
        result={"found": True, "record": {**record, "untrusted": True}, "untrusted": True}
    )


SPEC = ToolSpec(
    name="get_benchmark",
    description=(
        "Interroge les référentiels locaux (marges, paniers, coûts). Les valeurs sont "
        "des données de référence, jamais des résultats de simulation."
    ),
    input_model=BenchmarkInput,
    output_model=BenchmarkOutput,
    handler=get_benchmark,
    default_permission="allow",
)
