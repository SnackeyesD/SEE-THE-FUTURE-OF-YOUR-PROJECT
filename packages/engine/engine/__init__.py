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
from .models import get_model
from .progressive import (
    QUALITY_PROFILES,
    CancelToken,
    ConvergenceTracker,
    PartialAggregates,
    QualityProfile,
    resolve_execution,
)
from .run_sample import RunSample
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

__all__ = [
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
    "Histogram",
    "HistogramBin",
    "Hypothesis",
    "Metrics",
    "MonthlyAverage",
    "MonthlyAverages",
    "PartialAggregates",
    "PartialCallback",
    "ProgressCallback",
    "QUALITY_PROFILES",
    "Quality",
    "QualityProfile",
    "RunSample",
    "Scenario",
    "ScenarioEvent",
    "SensitivityEntry",
    "SimulationCancelled",
    "SimulationConfig",
    "SimulationResult",
    "UnknownModelError",
    "build_event_modifiers",
    "draw_events",
    "get_model",
    "register_event_slots",
    "resolve_execution",
    "simulate",
    "to_camel",
]
