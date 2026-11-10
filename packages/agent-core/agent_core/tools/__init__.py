from __future__ import annotations

from .base import ToolContext, ToolExecution, ToolOutcome, ToolRegistry, ToolSpec
from .benchmarks import SPEC as BENCHMARK_SPEC
from .brief import SPEC as BRIEF_SPEC
from .export import SPEC as EXPORT_SPEC
from .hypotheses import SPEC as HYPOTHESES_SPEC
from .script import SPEC as SCRIPT_SPEC
from .simulation import COMPARE_SPEC, RUN_SPEC
from .web import SPEC as WEB_SPEC


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for spec in (
        BRIEF_SPEC,
        HYPOTHESES_SPEC,
        RUN_SPEC,
        COMPARE_SPEC,
        BENCHMARK_SPEC,
        WEB_SPEC,
        EXPORT_SPEC,
        SCRIPT_SPEC,
    ):
        registry.register(spec)
    return registry


__all__ = [
    "ToolContext",
    "ToolExecution",
    "ToolOutcome",
    "ToolRegistry",
    "ToolSpec",
    "default_registry",
]
