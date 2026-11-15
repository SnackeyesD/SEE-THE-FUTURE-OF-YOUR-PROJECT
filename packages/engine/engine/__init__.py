"""Moteur de simulation de See The Future.

Le moteur est le seul producteur de chiffres de simulation.
Il ne dépend ni de l'UI, ni du réseau, ni d'un fournisseur IA.
"""

__version__ = "0.3.0"

from .draws import DrawBank, DrawSlot
from .errors import EngineError, SimulationCancelled, UnknownModelError
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
    "EngineError",
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
    "SensitivityEntry",
    "SimulationCancelled",
    "SimulationConfig",
    "SimulationResult",
    "UnknownModelError",
    "get_model",
    "resolve_execution",
    "simulate",
    "to_camel",
]
