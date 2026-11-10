from __future__ import annotations

import time
import uuid
from collections.abc import Callable

import numpy as np

from . import __version__
from .aggregation import (
    AggregationState,
    build_break_even,
    build_histogram,
    build_metrics,
    build_monthly,
)
from .distributions import default_rng, sample_hypothesis
from .models import get_model
from .models.retail_depot import DEFAULT_SEASONALITY
from .scenario import Scenario, SimulationConfig, SimulationResult
from .sensitivity import build_sensitivity

ProgressCallback = Callable[[float], None]


def simulate(
    scenario: Scenario,
    config: SimulationConfig | None = None,
    progress: ProgressCallback | None = None,
) -> SimulationResult:
    """Exécute une simulation Monte Carlo reproductible.

    La même configuration (scénario, graine, taille de lot) produit les mêmes
    agrégats, indépendamment de l'état global de numpy.
    """
    config = config or SimulationConfig()
    model = get_model(scenario.model)
    started = time.perf_counter()

    assumptions = model.resolve(scenario)
    assumption_rng = default_rng(config.seed)
    samples: dict[str, np.ndarray] = {}
    for key in sorted(assumptions):
        samples[key] = sample_hypothesis(
            assumptions[key],
            assumption_rng,
            config.runs,
            model.bounds(key),
        )

    noise_rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([config.seed, 0x5EED]))
    )
    noise = noise_rng.standard_normal((config.runs, scenario.horizon_months))

    seasonality = (
        np.asarray(scenario.seasonality, dtype=np.float64)
        if scenario.seasonality is not None
        else DEFAULT_SEASONALITY
    )

    if progress is not None:
        progress(0.0)

    state = AggregationState(horizon=scenario.horizon_months)
    profit_batches: list[np.ndarray] = []
    batch_size = min(config.batch_size, config.runs)
    for start in range(0, config.runs, batch_size):
        end = min(start + batch_size, config.runs)
        batch_inputs = {key: values[start:end] for key, values in samples.items()}
        batch = model.simulate_batch(batch_inputs, noise[start:end], seasonality)
        state.add(batch)
        profit_batches.append(batch.profit)
        if progress is not None:
            progress(end / config.runs)

    profit = np.concatenate(profit_batches)
    duration_ms = (time.perf_counter() - started) * 1000.0

    return SimulationResult(
        run_id=uuid.uuid4().hex,
        engine_version=__version__,
        scenario_name=scenario.name,
        model=scenario.model,
        currency=scenario.currency,
        horizon_months=scenario.horizon_months,
        runs=config.runs,
        seed=config.seed,
        duration_ms=duration_ms,
        metrics=build_metrics(profit, state, config.runs),
        histogram=build_histogram(profit, config),
        monthly=build_monthly(state, config.runs),
        sensitivity=build_sensitivity(samples, profit),
        break_even=build_break_even(samples),
    )
