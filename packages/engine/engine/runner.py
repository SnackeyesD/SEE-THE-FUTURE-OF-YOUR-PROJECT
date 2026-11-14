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
    run_break_even_months,
    run_min_cash,
)
from .distributions import (
    distribution_approximation,
    distribution_streams,
    sample_hypothesis,
)
from .draws import DrawBank
from .errors import EngineError
from .models import get_model
from .models.retail_depot import DEFAULT_SEASONALITY
from .run_sample import SAMPLE_LIMIT, RunSample
from .scenario import Scenario, SimulationConfig, SimulationResult
from .sensitivity import build_sensitivity

ProgressCallback = Callable[[float], None]

_SAMPLE_ARRAYS = ("profit_monthly", "cash_monthly", "revenue_monthly")


def _concat(parts: list[np.ndarray]) -> np.ndarray:
    return parts[0] if len(parts) == 1 else np.concatenate(parts)


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
    if config.histogram_month is not None and config.histogram_month > scenario.horizon_months:
        raise EngineError(
            "histogramMonth doit être inférieur ou égal à horizonMonths "
            f"({config.histogram_month} > {scenario.horizon_months})"
        )
    model = get_model(scenario.model)
    started = time.perf_counter()

    assumptions = model.resolve(scenario)
    bank = DrawBank(config.seed, scenario.horizon_months)
    for key in sorted(assumptions):
        bank.register(f"hyp:{key}")
    bank.register("noise", width=scenario.horizon_months, squeeze=False)

    approximations: set[str] = set()
    samples: dict[str, np.ndarray] = {}
    for key in sorted(assumptions):
        hypothesis = assumptions[key]
        slot = f"hyp:{key}"
        if hypothesis.distribution is None:
            samples[key] = sample_hypothesis(
                hypothesis,
                None,
                None,
                model.bounds(key),
                size=config.runs,
            )
        else:
            needs_uniform, needs_normal = distribution_streams(
                hypothesis.distribution
            )
            uniform, normal = bank.take(
                slot,
                config.runs,
                uniform=needs_uniform,
                normal=needs_normal,
            )
            samples[key] = sample_hypothesis(
                hypothesis,
                uniform,
                normal,
                model.bounds(key),
            )
            approximation = distribution_approximation(hypothesis.distribution)
            if approximation is not None:
                approximations.add(approximation)

    seasonality = (
        np.asarray(scenario.seasonality, dtype=np.float64)
        if scenario.seasonality is not None
        else DEFAULT_SEASONALITY
    )

    if progress is not None:
        progress(0.0)

    state = AggregationState(horizon=scenario.horizon_months)
    profit_batches: list[np.ndarray] = []
    min_cash_batches: list[np.ndarray] = []
    break_even_batches: list[np.ndarray] = []
    sample_indices: list[np.ndarray] = []
    sample_arrays: dict[str, list[np.ndarray]] = {name: [] for name in _SAMPLE_ARRAYS}
    sample_parameters: dict[str, list[np.ndarray]] = {}
    sample_remaining = min(config.runs, SAMPLE_LIMIT)
    batch_size = min(config.batch_size, config.runs)

    for start in range(0, config.runs, batch_size):
        end = min(start + batch_size, config.runs)
        batch_inputs = {key: values[start:end] for key, values in samples.items()}
        batch_noise = bank.take_range(
            "noise",
            start,
            end,
            uniform=False,
        )[1]
        batch = model.simulate_batch(batch_inputs, batch_noise, seasonality)
        state.add(batch)
        profit_batches.append(batch.profit)
        min_cash_batches.append(run_min_cash(batch.cash_monthly))
        break_even_batches.append(run_break_even_months(batch.profit_monthly))

        if sample_remaining > 0:
            take = min(sample_remaining, end - start)
            full_run_set = start == 0 and end == config.runs and take == end - start
            sample_indices.append(np.arange(start, start + take, dtype=np.int64))
            for name in _SAMPLE_ARRAYS:
                array = getattr(batch, name)
                sample_arrays[name].append(
                    array if full_run_set else np.array(array[:take], copy=True)
                )
            for key, values in batch_inputs.items():
                sample_parameters.setdefault(key, []).append(
                    values if full_run_set else np.array(values[:take], copy=True)
                )
            sample_remaining -= take

        if progress is not None:
            progress(end / config.runs)

    profit = np.concatenate(profit_batches)
    min_cash = np.concatenate(min_cash_batches)
    break_even_month = np.concatenate(break_even_batches)
    sample = RunSample(
        indices=_concat(sample_indices),
        profit_monthly=_concat(sample_arrays["profit_monthly"]),
        cash_monthly=_concat(sample_arrays["cash_monthly"]),
        revenue_monthly=_concat(sample_arrays["revenue_monthly"]),
        parameters={
            key: _concat(parts) for key, parts in sample_parameters.items()
        },
    )
    duration_ms = (time.perf_counter() - started) * 1000.0

    result = SimulationResult(
        run_id=uuid.uuid4().hex,
        engine_version=__version__,
        scenario_name=scenario.name,
        model=scenario.model,
        currency=scenario.currency,
        horizon_months=scenario.horizon_months,
        runs=config.runs,
        runs_retained=int(sample.indices.size),
        seed=config.seed,
        duration_ms=duration_ms,
        metrics=build_metrics(profit, state, config.runs, min_cash, break_even_month),
        histogram=build_histogram(profit, config),
        monthly=build_monthly(
            state,
            config.runs,
            sample,
            break_even_month,
            config,
        ),
        sensitivity=build_sensitivity(samples, profit),
        break_even=build_break_even(samples),
        approximations=sorted(approximations) or None,
    )
    result.attach_sample(sample)
    return result
