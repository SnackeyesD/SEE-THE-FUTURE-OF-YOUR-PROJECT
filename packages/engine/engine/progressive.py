"""Calcul progressif, annulation coopérative et convergence.

Ce module ne dépend pas de la boucle de simulation : il fournit les objets
publics que le runner, puis le sidecar (phase 06), manipulent.

Invariants :

- un ``CancelToken`` est vérifié **entre deux blocs**, jamais au milieu ;
- un partiel ne contient ni trajectoire ni paramètre par run ;
- la convergence décrit une stabilité observée, pas une précision garantie.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .scenario import (
    ConvergenceState,
    Histogram,
    Metrics,
    MonthlyAverages,
    Quality,
    SimulationConfig,
)

CONVERGENCE_THRESHOLD = 0.02
"""Variation relative maximale pour considérer un bloc comme stable (2 %)."""

EPSILON = 1e-9
"""Dénominateur minimal de la variation relative (valeurs proches de zéro)."""

MAX_PARTIALS = 64
"""Nombre maximal de partiels produits pour un calcul.

Au-delà, les partiels sont espacés régulièrement dans la boucle de blocs. La
vérification d'annulation, elle, reste faite à chaque bloc.
"""

MAX_BLOCK_SIZE = 2_048
"""Bloc maximal quand la taille de bloc vient du profil.

Un bloc de 2 048 runs × 36 mois reste sous le budget d'annulation de 100 ms sur
la machine de référence. Au-delà, on préfère plusieurs blocs plutôt qu'un bloc
trop long à interrompre.
"""


@dataclass(frozen=True)
class QualityProfile:
    """Profil de qualité effectif du moteur."""

    runs: int
    block_size: int
    convergence_min_runs: int
    convergence_stable_transitions: int


QUALITY_PROFILES: dict[Quality, QualityProfile] = {
    "draft": QualityProfile(
        runs=500,
        block_size=256,
        convergence_min_runs=500,
        convergence_stable_transitions=1,
    ),
    "final": QualityProfile(
        runs=5_000,
        block_size=256,
        convergence_min_runs=2_000,
        convergence_stable_transitions=2,
    ),
}
"""Profils de la V3.

``draft`` sert au glissement (aperçu rapide) et ``final`` au relâchement, avec
persistance. Les deux partagent les mêmes tirages : le draft est un préfixe
exact du final.
"""


@dataclass(frozen=True)
class ExecutionPlan:
    """Runs et taille de bloc effectivement utilisés."""

    quality: Quality
    runs: int
    block_size: int


def resolve_execution(
    config: SimulationConfig | None,
    quality: Quality,
) -> ExecutionPlan:
    """Applique la précédence configuration explicite > profil de qualité.

    ``SimulationConfig`` conserve ses valeurs par défaut (10 000 runs,
    ``batch_size`` 50 000) pour les appelants historiques. En revanche, seuls
    les champs réellement fournis (``model_fields_set``) écrasent le profil.

    Quand la taille de bloc vient du profil, elle est élargie pour les très
    grands calculs afin de garder au plus ``MAX_PARTIALS`` blocs : le coût par
    bloc du modèle dépend peu du nombre de runs, et 100 000 runs en blocs de
    256 seraient inutilement lents. Le plafond ``MAX_BLOCK_SIZE`` préserve le
    budget d'annulation.
    """

    if quality not in QUALITY_PROFILES:
        raise ValueError(f"qualité inconnue: {quality!r}")
    profile = QUALITY_PROFILES[quality]
    resolved = config or SimulationConfig()
    fields_set = resolved.model_fields_set
    runs = resolved.runs if "runs" in fields_set else profile.runs
    if "batch_size" in fields_set:
        block_size = resolved.batch_size
    else:
        block_size = max(
            profile.block_size,
            min(MAX_BLOCK_SIZE, math.ceil(runs / MAX_PARTIALS)),
        )
    return ExecutionPlan(
        quality=quality,
        runs=runs,
        block_size=max(1, min(block_size, runs)),
    )


class CancelToken:
    """Jeton d'annulation coopératif, réutilisable par le sidecar.

    ``threading.Event`` rend ``cancel()`` et ``is_cancelled()`` sûrs entre
    threads. Le moteur ne teste le jeton qu'entre deux blocs.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def reset(self) -> None:
        """Réarme le jeton pour un nouveau run (usage avancé)."""
        self._event.clear()


class ConvergenceTracker:
    """Suit la stabilité des percentiles et du point mort d'un bloc à l'autre."""

    def __init__(
        self,
        quality: Quality = "final",
        *,
        threshold: float = CONVERGENCE_THRESHOLD,
    ) -> None:
        if quality not in QUALITY_PROFILES:
            raise ValueError(f"qualité inconnue: {quality!r}")
        if threshold <= 0:
            raise ValueError("le seuil de convergence doit être strictement positif")
        self.quality = quality
        self.threshold = threshold
        self._profile = QUALITY_PROFILES[quality]
        self._previous: np.ndarray | None = None
        self._blocks = 0
        self._stable_transitions = 0
        self._state = ConvergenceState(
            converged=False,
            stability=0.0,
            max_relative_change=0.0,
            stable_blocks=0,
        )

    @property
    def state(self) -> ConvergenceState:
        return self._state

    def update(
        self,
        vector: Sequence[float],
        completed_runs: int,
    ) -> ConvergenceState:
        """Met à jour l'état après un bloc complet.

        ``vector`` doit rester stable dans son ordre :
        ``[p10, p50, p90, P(point mort), P50(trésorerie minimale)]``.
        """

        current = np.asarray(vector, dtype=np.float64)
        if current.ndim != 1 or current.size == 0:
            raise ValueError("le vecteur de convergence doit être non vide et 1D")

        self._blocks += 1
        if self._previous is None:
            max_change = 0.0
        else:
            denominator = np.maximum(np.abs(self._previous), EPSILON)
            changes = np.abs(current - self._previous) / denominator
            max_change = float(np.max(changes))
            if max_change < self.threshold:
                self._stable_transitions += 1
            else:
                self._stable_transitions = 0
        self._previous = current

        converged = (
            self._blocks >= 2
            and self._stable_transitions
            >= self._profile.convergence_stable_transitions
            and completed_runs >= self._profile.convergence_min_runs
        )
        if self._blocks < 2:
            stability = 0.0
        else:
            stability = max(
                0.0,
                1.0 - min(max_change / self.threshold, 1.0),
            )

        self._state = ConvergenceState(
            converged=converged,
            stability=float(stability),
            max_relative_change=max_change,
            stable_blocks=self._stable_transitions,
        )
        return self._state


def convergence_vector(
    profit: np.ndarray,
    min_cash: np.ndarray,
    break_even_month: np.ndarray,
    horizon: int,
) -> np.ndarray:
    """Vecteur stable utilisé par le tracker.

    Les tableaux peuvent être un sous-échantillon du préfixe : le runner
    plafonne leur taille pour garder un coût constant par bloc.
    """

    p10, p50, p90 = np.percentile(profit, [10.0, 50.0, 90.0])
    break_even_probability = float(np.mean(break_even_month <= horizon))
    min_cash_p50 = float(np.percentile(min_cash, 50.0))
    return np.array(
        [p10, p50, p90, break_even_probability, min_cash_p50],
        dtype=np.float64,
    )


@dataclass(frozen=True)
class PartialAggregates:
    """Instantané d'agrégats publiable pendant le calcul.

    Les champs sont volontairement limités aux objets d'affichage : pas de
    trajectoire, pas de paramètre par run, pas d'échantillon complet.
    """

    completed_runs: int
    total_runs: int
    metrics: Metrics
    histogram: Histogram
    monthly: MonthlyAverages
    convergence: ConvergenceState

    def to_dict(self) -> dict[str, Any]:
        """Sérialise en camelCase, prêt pour une notification JSON-RPC."""

        return {
            "completedRuns": self.completed_runs,
            "totalRuns": self.total_runs,
            "metrics": self.metrics.model_dump(by_alias=True, mode="json"),
            "histogram": self.histogram.model_dump(by_alias=True, mode="json"),
            "monthly": self.monthly.model_dump(by_alias=True, mode="json"),
            "convergence": self.convergence.model_dump(by_alias=True, mode="json"),
        }
