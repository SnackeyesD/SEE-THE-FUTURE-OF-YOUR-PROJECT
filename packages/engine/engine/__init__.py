"""Moteur de simulation de See The Future.

Le moteur est le seul producteur de chiffres de simulation.
Il ne dépend ni de l'UI, ni du réseau, ni d'un fournisseur IA.
"""

__version__ = "0.2.0"

from .draws import DrawBank, DrawSlot
from .errors import EngineError, UnknownModelError
from .models import get_model
from .run_sample import RunSample
from .runner import simulate
from .scenario import (
    BreakEven,
    CashCdfPoint,
    DistributionSpec,
    Histogram,
    HistogramBin,
    Hypothesis,
    Metrics,
    MonthlyAverage,
    MonthlyAverages,
    Scenario,
    SensitivityEntry,
    SimulationConfig,
    SimulationResult,
    to_camel,
)

__all__ = [
    "BreakEven",
    "CashCdfPoint",
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
    "RunSample",
    "Scenario",
    "SensitivityEntry",
    "SimulationConfig",
    "SimulationResult",
    "UnknownModelError",
    "get_model",
    "simulate",
    "to_camel",
]
