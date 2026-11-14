from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from engine.distributions import (
    POISSON_EXACT_MAX,
    distribution_approximation,
    distribution_streams,
    sample_distribution,
    sample_hypothesis,
)
from engine.draws import DrawBank
from engine.scenario import DistributionSpec, Hypothesis

finite_float = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)


def _draws(size: int, *, seed: int = 0, slot: str = "test") -> tuple[np.ndarray, np.ndarray]:
    bank = DrawBank(seed=seed, horizon=1)
    bank.register(slot)
    return bank.take(slot, size)


def _poisson_reference_cdf(lam: float, limit: int = 500) -> np.ndarray:
    probabilities = [math.exp(-lam)]
    cumulative = [probabilities[0]]
    for k in range(1, limit):
        probabilities.append(probabilities[-1] * lam / k)
        cumulative.append(cumulative[-1] + probabilities[-1])
        if cumulative[-1] >= 1.0 - 1e-14:
            break
    return np.asarray(cumulative)


def test_normal_sampling_is_reproducible() -> None:
    spec = DistributionSpec(kind="normal", mean=10, std=2)
    first = sample_distribution(spec, *_draws(500, seed=123))
    second = sample_distribution(spec, *_draws(500, seed=123))
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
    values = sample_distribution(spec, *_draws(size))
    assert values.shape == (size,)
    assert np.all(np.isfinite(values))


def test_uniform_uses_the_uniform_draw_directly() -> None:
    spec = DistributionSpec(kind="uniform", low=-2, high=6)
    uniform = np.array([0.0, 0.25, 0.5, 0.75])
    normal = np.zeros_like(uniform)
    values = sample_distribution(spec, uniform, normal)
    np.testing.assert_allclose(values, [-2.0, 0.0, 2.0, 4.0])


def test_triangular_handles_degenerate_modes() -> None:
    uniform = np.array([0.0, 0.25, 0.5, 0.75, 0.999999])
    normal = np.zeros_like(uniform)

    left_mode = DistributionSpec(kind="triangular", low=1, mode=1, high=3)
    right_mode = DistributionSpec(kind="triangular", low=1, mode=3, high=3)
    middle = DistributionSpec(kind="triangular", low=1, mode=2, high=3)

    for spec, expected_bounds in (
        (left_mode, (1.0, 3.0)),
        (right_mode, (1.0, 3.0)),
        (middle, (1.0, 3.0)),
    ):
        values = sample_distribution(spec, uniform, normal)
        assert np.all(np.isfinite(values))
        assert values.min() >= expected_bounds[0] - 1e-12
        assert values.max() <= expected_bounds[1] + 1e-12


def test_lognormal_is_exp_of_mean_plus_sigma_z() -> None:
    spec = DistributionSpec(kind="lognormal", mean=2.0, sigma=0.5)
    uniform = np.array([0.1, 0.5, 0.9])
    normal = np.array([-1.0, 0.0, 2.0])
    values = sample_distribution(spec, uniform, normal)
    np.testing.assert_allclose(values, np.exp(2.0 + 0.5 * normal))


def test_empirical_sampling_respects_weights() -> None:
    spec = DistributionSpec(kind="empirical", values=[1, 2], weights=[0.9, 0.1])
    values = sample_distribution(spec, *_draws(20_000, seed=7))
    share_of_one = float(np.mean(values == 1))
    assert share_of_one == pytest.approx(0.9, abs=0.02)


def test_poisson_sampling_returns_non_negative_integers() -> None:
    spec = DistributionSpec(kind="poisson", mean=4)
    values = sample_distribution(spec, *_draws(2_000, seed=3))
    assert np.all(values >= 0)
    assert np.all(values == np.rint(values))


@pytest.mark.parametrize("lam", [1.0, 5.0, 30.0])
def test_poisson_inversion_matches_reference_cdf(lam: float) -> None:
    reference = _poisson_reference_cdf(lam)
    uniform = np.array([0.0001, 0.1, 0.5, 0.9, 0.9999])
    normal = np.zeros_like(uniform)
    values = sample_distribution(
        DistributionSpec(kind="poisson", mean=lam), uniform, normal
    )
    expected = np.minimum(
        np.searchsorted(reference, uniform, side="right"), reference.size - 1
    )
    np.testing.assert_array_equal(values, expected.astype(np.float64))


def test_poisson_large_lambda_is_signalled_as_approximation() -> None:
    exact = DistributionSpec(kind="poisson", mean=float(POISSON_EXACT_MAX))
    approximate = DistributionSpec(kind="poisson", mean=float(POISSON_EXACT_MAX + 1))

    assert distribution_approximation(exact) is None
    assert distribution_approximation(approximate) == "poisson_normal"

    values = sample_distribution(approximate, *_draws(500, seed=1))
    assert np.all(values >= 0)
    assert np.all(values == np.rint(values))
    assert abs(float(values.mean()) - approximate.mean) < 50


def test_hypothesis_is_clipped_to_bounds() -> None:
    hypothesis = Hypothesis(
        value=0,
        distribution=DistributionSpec(kind="normal", mean=0, std=100),
        min=0,
        max=10,
    )
    values = sample_hypothesis(hypothesis, *_draws(5_000, seed=5), bounds=(-1, 20))
    assert values.min() >= 0
    assert values.max() <= 10


def test_model_bounds_are_combined_with_hypothesis_bounds() -> None:
    hypothesis = Hypothesis(
        value=0.5,
        distribution=DistributionSpec(kind="uniform", low=-10, high=10),
        min=-5,
    )
    values = sample_hypothesis(hypothesis, *_draws(5_000, seed=11), bounds=(0, 1))
    assert values.min() >= 0
    assert values.max() <= 1


def test_deterministic_hypothesis_returns_constant_array() -> None:
    hypothesis = Hypothesis(value=42)
    values = sample_hypothesis(hypothesis, None, None, size=10)
    np.testing.assert_array_equal(values, np.full(10, 42.0))


def test_distribution_streams_match_the_transformation() -> None:
    assert distribution_streams(DistributionSpec(kind="normal", mean=1, std=1)) == (
        False,
        True,
    )
    assert distribution_streams(
        DistributionSpec(kind="lognormal", mean=1, sigma=0.1)
    ) == (False, True)
    assert distribution_streams(
        DistributionSpec(kind="triangular", low=0, mode=1, high=2)
    ) == (True, False)
    assert distribution_streams(
        DistributionSpec(kind="poisson", mean=10)
    ) == (True, False)
    assert distribution_streams(
        DistributionSpec(kind="poisson", mean=POISSON_EXACT_MAX + 1)
    ) == (False, True)


def test_only_the_requested_stream_is_required() -> None:
    uniform, _ = _draws(20, slot="u")
    _, normal = _draws(20, slot="z")

    normal_values = sample_distribution(
        DistributionSpec(kind="normal", mean=0, std=1), None, normal
    )
    np.testing.assert_array_equal(normal_values, normal)

    uniform_values = sample_distribution(
        DistributionSpec(kind="uniform", low=0, high=1), uniform, None
    )
    np.testing.assert_array_equal(uniform_values, uniform)


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
