from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from engine.distributions import default_rng, sample_distribution, sample_hypothesis
from engine.scenario import DistributionSpec, Hypothesis

finite_float = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)


def test_normal_sampling_is_reproducible() -> None:
    spec = DistributionSpec(kind="normal", mean=10, std=2)
    first = sample_distribution(spec, default_rng(123), 500)
    second = sample_distribution(spec, default_rng(123), 500)
    np.testing.assert_array_equal(first, second)
    assert first.dtype == np.float64


@given(
    mean=finite_float,
    std=st.floats(
        min_value=1e-6,
        max_value=1e6,
        allow_nan=False,
        allow_infinity=False,
    ),
    size=st.integers(min_value=1, max_value=200),
)
def test_normal_sampling_is_always_finite(mean: float, std: float, size: int) -> None:
    spec = DistributionSpec(kind="normal", mean=mean, std=std)
    values = sample_distribution(spec, default_rng(0), size)
    assert values.shape == (size,)
    assert np.all(np.isfinite(values))


def test_empirical_sampling_respects_weights() -> None:
    spec = DistributionSpec(kind="empirical", values=[1, 2], weights=[0.9, 0.1])
    values = sample_distribution(spec, default_rng(7), 20_000)
    share_of_one = float(np.mean(values == 1))
    assert share_of_one == pytest.approx(0.9, abs=0.02)


def test_poisson_sampling_returns_non_negative_integers() -> None:
    spec = DistributionSpec(kind="poisson", mean=4)
    values = sample_distribution(spec, default_rng(3), 2_000)
    assert np.all(values >= 0)
    assert np.all(values == np.rint(values))


def test_hypothesis_is_clipped_to_bounds() -> None:
    hypothesis = Hypothesis(
        value=0,
        distribution=DistributionSpec(kind="normal", mean=0, std=100),
        min=0,
        max=10,
    )
    values = sample_hypothesis(hypothesis, default_rng(5), 5_000, bounds=(-1, 20))
    assert values.min() >= 0
    assert values.max() <= 10


def test_model_bounds_are_combined_with_hypothesis_bounds() -> None:
    hypothesis = Hypothesis(
        value=0.5,
        distribution=DistributionSpec(kind="uniform", low=-10, high=10),
        min=-5,
    )
    values = sample_hypothesis(hypothesis, default_rng(11), 5_000, bounds=(0, 1))
    assert values.min() >= 0
    assert values.max() <= 1


def test_deterministic_hypothesis_returns_constant_array() -> None:
    hypothesis = Hypothesis(value=42)
    values = sample_hypothesis(hypothesis, default_rng(1), 10)
    np.testing.assert_array_equal(values, np.full(10, 42.0))


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "normal", "mean": 1},
        {"kind": "normal", "mean": 1, "std": 0},
        {"kind": "lognormal", "mean": 1},
        {"kind": "triangular", "low": 2, "mode": 1, "high": 3},
        {"kind": "uniform", "low": 1, "high": 1},
        {"kind": "poisson", "mean": 0},
        {"kind": "empirical", "values": []},
        {"kind": "empirical", "values": [1, 2], "weights": [1]},
        {"kind": "empirical", "values": [1, 2], "weights": [0, 0]},
    ],
)
def test_invalid_distributions_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DistributionSpec.model_validate(payload)
