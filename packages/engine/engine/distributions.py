from __future__ import annotations

import numpy as np

from .scenario import DistributionSpec, Hypothesis


def sample_distribution(
    spec: DistributionSpec,
    rng: np.random.Generator,
    size: int,
) -> np.ndarray:
    """Échantillonne une distribution validée en float64."""
    if spec.kind == "normal":
        assert spec.mean is not None and spec.std is not None
        values = rng.normal(loc=spec.mean, scale=spec.std, size=size)
    elif spec.kind == "lognormal":
        assert spec.mean is not None and spec.sigma is not None
        values = rng.lognormal(mean=spec.mean, sigma=spec.sigma, size=size)
    elif spec.kind == "triangular":
        assert spec.low is not None and spec.mode is not None and spec.high is not None
        values = rng.triangular(left=spec.low, mode=spec.mode, right=spec.high, size=size)
    elif spec.kind == "uniform":
        assert spec.low is not None and spec.high is not None
        values = rng.uniform(low=spec.low, high=spec.high, size=size)
    elif spec.kind == "poisson":
        assert spec.mean is not None
        values = rng.poisson(lam=spec.mean, size=size)
    elif spec.kind == "empirical":
        assert spec.values is not None
        values_array = np.asarray(spec.values, dtype=np.float64)
        probabilities = None
        if spec.weights is not None:
            weights = np.asarray(spec.weights, dtype=np.float64)
            probabilities = weights / weights.sum()
        values = rng.choice(values_array, size=size, p=probabilities)
    else:  # pragma: no cover - protégé par le Literal Pydantic
        raise ValueError(f"distribution inconnue: {spec.kind}")

    return np.ascontiguousarray(values, dtype=np.float64)


def sample_hypothesis(
    hypothesis: Hypothesis,
    rng: np.random.Generator,
    size: int,
    bounds: tuple[float, float | None] | None = None,
) -> np.ndarray:
    """Échantillonne une hypothèse puis applique ses bornes et celles du modèle."""
    if hypothesis.distribution is None:
        values = np.full(size, hypothesis.value, dtype=np.float64)
    else:
        values = sample_distribution(hypothesis.distribution, rng, size)

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


def default_rng(seed: int) -> np.random.Generator:
    """Générateur PCG64 reproductible, indépendant de l'état global de numpy."""
    return np.random.Generator(np.random.PCG64(seed))
