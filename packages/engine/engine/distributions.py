"""Transformations déterministes des tirages ``U`` et ``Z``.

Aucune fonction de ce module ne consomme d'aléa supplémentaire : les valeurs
sont obtenues par inversion de CDF ou transformation fermée à partir des
tableaux fournis par :class:`engine.draws.DrawBank`. Changer les paramètres
d'une loi ne modifie donc jamais les tirages de base.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .schema import DistributionSpec, Hypothesis

POISSON_EXACT_MAX = 50_000
"""Au-delà de ce ``lambda``, la table de CDF exacte serait trop volumineuse.

L'approximation normale est alors utilisée et signalée dans le résultat.
"""

_POISSON_TAIL_SIGMAS = 10.0


@lru_cache(maxsize=32)
def _poisson_table(lam: float) -> np.ndarray:
    """Table cumulative ``P(X ≤ k)`` pour un lambda scalaire.

    Construite en espace logarithmique pour éviter le sous-dépassement de
    ``exp(−λ)`` quand λ est grand. La borne supérieure couvre la queue à
    ``10√λ`` écarts-types, très en dessous de la tolérance de 1e-12. La table
    est mise en cache : elle ne dépend que de λ.
    """
    upper = int(np.ceil(lam + _POISSON_TAIL_SIGMAS * np.sqrt(lam) + 30.0))
    upper = min(max(upper, 8), POISSON_EXACT_MAX + 1_000)
    k = np.arange(upper + 1, dtype=np.float64)
    log_factorial = np.concatenate(
        ([0.0], np.cumsum(np.log(np.arange(1, upper + 1, dtype=np.float64))))
    )
    log_probability = -lam + k * np.log(lam) - log_factorial
    cumulative = np.cumsum(np.exp(log_probability))
    cumulative = np.minimum(cumulative, 1.0)
    cumulative[-1] = 1.0
    return cumulative


def poisson_uses_normal_approximation(lam: float) -> bool:
    """Indique si la loi de Poisson sera approchée par une normale."""
    return lam > POISSON_EXACT_MAX


def distribution_approximation(spec: DistributionSpec) -> str | None:
    """Retourne l'identifiant d'approximation d'une loi, ou ``None``."""
    if (
        spec.kind == "poisson"
        and spec.mean is not None
        and poisson_uses_normal_approximation(spec.mean)
    ):
        return "poisson_normal"
    return None


def _triangular(
    uniform: np.ndarray,
    low: float,
    mode: float,
    high: float,
) -> np.ndarray:
    """Inversion de la CDF triangulaire, sans division par zéro.

    Les cas ``low == mode`` et ``mode == high`` sont couverts par les deux
    branches de la formule ; la branche non prise reste finie.
    """
    span = high - low
    threshold = (mode - low) / span
    left = low + np.sqrt(uniform * span * (mode - low))
    right = high - np.sqrt((1.0 - uniform) * span * (high - mode))
    return np.where(uniform < threshold, left, right)


def _empirical(spec: DistributionSpec, uniform: np.ndarray) -> np.ndarray:
    assert spec.values is not None
    values = np.asarray(spec.values, dtype=np.float64)
    if spec.weights is None:
        weights = np.full(values.size, 1.0 / values.size, dtype=np.float64)
    else:
        raw = np.asarray(spec.weights, dtype=np.float64)
        weights = raw / raw.sum()
    cumulative = np.cumsum(weights)
    cumulative[-1] = 1.0
    indices = np.searchsorted(cumulative, uniform, side="right")
    return values[np.minimum(indices, values.size - 1)]


def distribution_streams(spec: DistributionSpec) -> tuple[bool, bool]:
    """Indique quels flux de base une loi consomme : ``(U, Z)``.

    Le runner ne génère que les flux utiles. Cette fonction est l'unique
    endroit qui connaît le mapping loi → flux, ce qui évite qu'une
    optimisation locale ne désynchronise les tirages.
    """
    if spec.kind in ("normal", "lognormal"):
        return False, True
    if spec.kind == "poisson" and spec.mean is not None:
        if poisson_uses_normal_approximation(spec.mean):
            return False, True
        return True, False
    return True, False


def sample_distribution(
    spec: DistributionSpec,
    uniform: np.ndarray | None,
    normal: np.ndarray | None,
) -> np.ndarray:
    """Transforme les tirages de base en valeurs de la loi demandée.

    Seul le flux attendu par la loi est requis ; l'autre peut valoir ``None``.
    """
    if uniform is not None and normal is not None and uniform.shape != normal.shape:
        raise ValueError("les tirages U et Z doivent avoir la même forme")

    if spec.kind == "normal":
        assert spec.mean is not None and spec.std is not None and normal is not None
        values = spec.mean + spec.std * normal
    elif spec.kind == "lognormal":
        assert spec.mean is not None and spec.sigma is not None and normal is not None
        values = np.exp(spec.mean + spec.sigma * normal)
    elif spec.kind == "triangular":
        assert (
            spec.low is not None
            and spec.mode is not None
            and spec.high is not None
            and uniform is not None
        )
        values = _triangular(uniform, spec.low, spec.mode, spec.high)
    elif spec.kind == "uniform":
        assert spec.low is not None and spec.high is not None and uniform is not None
        values = spec.low + uniform * (spec.high - spec.low)
    elif spec.kind == "poisson":
        assert spec.mean is not None
        if poisson_uses_normal_approximation(spec.mean):
            assert normal is not None
            values = np.rint(spec.mean + np.sqrt(spec.mean) * normal)
            values = np.maximum(values, 0.0)
        else:
            assert uniform is not None
            table = _poisson_table(float(spec.mean))
            indices = np.searchsorted(table, uniform, side="right")
            values = np.minimum(indices, table.size - 1).astype(np.float64)
    elif spec.kind == "empirical":
        assert uniform is not None
        values = _empirical(spec, uniform)
    else:  # pragma: no cover - protégé par le Literal Pydantic
        raise ValueError(f"distribution inconnue: {spec.kind}")

    return np.ascontiguousarray(values, dtype=np.float64)


def sample_hypothesis(
    hypothesis: Hypothesis,
    uniform: np.ndarray | None,
    normal: np.ndarray | None,
    bounds: tuple[float, float | None] | None = None,
    *,
    size: int | None = None,
) -> np.ndarray:
    """Transforme une hypothèse puis applique ses bornes et celles du modèle."""
    if hypothesis.distribution is None:
        if size is None:
            reference = uniform if uniform is not None else normal
            assert reference is not None
            size = reference.shape[0]
        values = np.full(size, hypothesis.value, dtype=np.float64)
    else:
        values = sample_distribution(hypothesis.distribution, uniform, normal)

    lower = hypothesis.min
    upper = hypothesis.max
    if bounds is not None:
        model_lower, model_upper = bounds
        lower = model_lower if lower is None else max(lower, model_lower)
        if model_upper is not None:
            upper = model_upper if upper is None else min(upper, model_upper)

    if lower is not None:
        values = np.maximum(values, lower)
    if upper is not None:
        values = np.minimum(values, upper)

    return np.ascontiguousarray(values, dtype=np.float64)
