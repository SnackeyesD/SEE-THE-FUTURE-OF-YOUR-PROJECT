"""Moteur de simulation de See The Future.

Le moteur est le seul producteur de chiffres de simulation.
Il ne dépend ni de l'UI, ni du réseau, ni d'un fournisseur IA.
"""

__version__ = "0.4.0"

from .draws import DrawBank, DrawSlot
from .errors import EngineError, SimulationCancelled, UnknownModelError
from .events import (
    EVENT_CATALOG,
    EVENT_TARGETS,
    EventDraws,
    EventModifiers,
    EventSpec,
    EventTarget,
    EventType,
    ScenarioEvent,
    build_event_modifiers,
    draw_events,
    register_event_slots,
)
from .goal_seek import (
    GoalSeekProgress,
    GoalSeekResult,
    GoalTraceEntry,
    Lever,
    Objective,
    goal_seek,
)
from .models import get_model
from .progressive import (
    QUALITY_PROFILES,
    CancelToken,
    ConvergenceTracker,
    PartialAggregates,
    QualityProfile,
    resolve_execution,
)
from .provenance import (
    ROUNDING_TOLERANCE,
    allowed_numbers,
    build_provenance,
    deterministic_explanation,
    extract_numbers,
    number_is_allowed,
    scenario_hash,
    validate_explanation,
)
from .run_sample import SAMPLE_LIMIT, RunSample
from .runner import PartialCallback, ProgressCallback, simulate
from .scenario import (
    BreakEven,
    CashCdfPoint,
    ConvergenceState,
    DistributionSpec,
    Histogram,
    HistogramBin,
    Hypothesis,
    Metrics,
    MonthlyAverage,
    MonthlyAverages,
    Quality,
    Scenario,
    SensitivityEntry,
    SimulationConfig,
    SimulationResult,
    to_camel,
)
from .surface import AxisSpec, SurfaceResult, SurfaceRowCallback, surface

__all__ = [
    "AxisSpec",
    "BreakEven",
    "CancelToken",
    "CashCdfPoint",
    "ConvergenceState",
    "ConvergenceTracker",
    "DistributionSpec",
    "DrawBank",
    "DrawSlot",
    "EVENT_CATALOG",
    "EVENT_TARGETS",
    "EngineError",
    "EventDraws",
    "EventModifiers",
    "EventSpec",
    "EventTarget",
    "EventType",
    "GoalSeekProgress",
    "GoalSeekResult",
    "GoalTraceEntry",
    "Histogram",
    "HistogramBin",
    "Hypothesis",
    "Lever",
    "Metrics",
    "MonthlyAverage",
    "MonthlyAverages",
    "Objective",
    "PartialAggregates",
    "PartialCallback",
    "ProgressCallback",
    "QUALITY_PROFILES",
    "Quality",
    "QualityProfile",
    "ROUNDING_TOLERANCE",
    "SAMPLE_LIMIT",
    "RunSample",
    "Scenario",
    "ScenarioEvent",
    "SensitivityEntry",
    "SimulationCancelled",
    "SimulationConfig",
    "SimulationResult",
    "SurfaceResult",
    "SurfaceRowCallback",
    "UnknownModelError",
    "allowed_numbers",
    "build_event_modifiers",
    "build_provenance",
    "deterministic_explanation",
    "draw_events",
    "extract_numbers",
    "get_model",
    "goal_seek",
    "number_is_allowed",
    "register_event_slots",
    "resolve_execution",
    "scenario_hash",
    "simulate",
    "surface",
    "to_camel",
    "validate_explanation",
]
