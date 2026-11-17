from __future__ import annotations

import math
import time
import uuid
from collections.abc import Callable

import numpy as np

from . import __version__
from .aggregation import (
    CONVERGENCE_SAMPLE_LIMIT,
    AggregationState,
    HistogramRange,
    build_break_even,
    build_histogram,
    build_metrics,
    build_monthly,
    build_partial_aggregates,
    run_break_even_months,
    run_min_cash,
    sample_prefix_indices,
)
from .distributions import (
    distribution_approximation,
    distribution_streams,
    sample_hypothesis,
)
from .draws import DrawBank
from .errors import EngineError, SimulationCancelled
from .events import build_event_modifiers, draw_events
from .models import get_model
from .models.retail_depot import DEFAULT_SEASONALITY
from .progressive import (
    MAX_PARTIALS,
    CancelToken,
    ConvergenceTracker,
    PartialAggregates,
    convergence_vector,
    resolve_execution,
)
from .run_sample import SAMPLE_LIMIT, RunSample
from .scenario import Quality, Scenario, SimulationConfig, SimulationResult
from .sensitivity import build_sensitivity

ProgressCallback = Callable[[float], None]
PartialCallback = Callable[[PartialAggregates], None]

_SAMPLE_ARRAYS = ("profit_monthly", "cash_monthly", "revenue_monthly")


def simulate(
    scenario: Scenario,
    config: SimulationConfig | None = None,
    progress: ProgressCallback | None = None,
    *,
    quality: Quality = "final",
    on_progress: ProgressCallback | None = None,
    on_partial: PartialCallback | None = None,
    cancel: CancelToken | None = None,
) -> SimulationResult:
    """Exécute une simulation Monte Carlo reproductible, par blocs.

    La signature reste rétrocompatible : ``simulate(scenario, config,
    progress=callback)`` continue de fonctionner. ``progress`` est un alias
    historique de ``on_progress`` ; si les deux callbacks sont fournis, les
    deux sont appelés.

    Le profil de qualité ne s'applique qu'aux champs **non explicitement
    fournis** dans ``SimulationConfig`` : un ``runs`` ou un ``batch_size``
    présent dans la configuration gagne toujours. Le calcul est annulable
    entre deux blocs via :class:`CancelToken`.
    """

    config = config or SimulationConfig()
    if config.histogram_month is not None and config.histogram_month > scenario.horizon_months:
        raise EngineError(
            "histogramMonth doit être inférieur ou égal à horizonMonths "
            f"({config.histogram_month} > {scenario.horizon_months})"
        )

    plan = resolve_execution(config, quality)
    runs = plan.runs
    block_size = plan.block_size
    quality = plan.quality

    model = get_model(scenario.model)
    started = time.perf_counter()

    assumptions = model.resolve(scenario)
    bank = DrawBank(config.seed, scenario.horizon_months)
    for key in sorted(assumptions):
        bank.register(f"hyp:{key}")
    bank.register("noise", width=scenario.horizon_months, squeeze=False)
    event_draws = draw_events(scenario.events, bank, runs)

    approximations: set[str] = set()
    for key in sorted(assumptions):
        hypothesis = assumptions[key]
        if hypothesis.distribution is not None:
            approximation = distribution_approximation(hypothesis.distribution)
            if approximation is not None:
                approximations.add(approximation)
    for event in scenario.events:
        if not event.enabled:
            continue
        approximation = distribution_approximation(event.magnitude)
        if approximation is not None:
            approximations.add(approximation)

    seasonality = (
        np.asarray(scenario.seasonality, dtype=np.float64)
        if scenario.seasonality is not None
        else DEFAULT_SEASONALITY
    )

    progress_callbacks: list[ProgressCallback] = []
    if progress is not None:
        progress_callbacks.append(progress)
    if on_progress is not None and on_progress is not progress:
        progress_callbacks.append(on_progress)

    def notify_progress(fraction: float) -> None:
        for callback in progress_callbacks:
            callback(fraction)

    def check_cancelled(completed_runs: int) -> None:
        if cancel is not None and cancel.is_cancelled():
            raise SimulationCancelled(completed_runs, runs)

    check_cancelled(0)

    total_blocks = math.ceil(runs / block_size)
    if total_blocks <= MAX_PARTIALS:
        partial_blocks = set(range(total_blocks))
    else:
        partial_blocks = set(
            np.linspace(0, total_blocks - 1, MAX_PARTIALS)
            .round()
            .astype(np.int64)
            .tolist()
        )

    state = AggregationState(horizon=scenario.horizon_months)
    profit = np.empty(runs, dtype=np.float64)
    min_cash = np.empty(runs, dtype=np.float64)
    break_even_month = np.empty(runs, dtype=np.int64)

    sample_limit = min(runs, SAMPLE_LIMIT)
    sample_profit_monthly = np.empty(
        (sample_limit, scenario.horizon_months), dtype=np.float64
    )
    sample_cash_monthly = np.empty_like(sample_profit_monthly)
    sample_revenue_monthly = np.empty_like(sample_profit_monthly)
    sample_parameters = {
        key: np.empty(sample_limit, dtype=np.float64) for key in assumptions
    }
    sample_arrays = {
        "profit_monthly": sample_profit_monthly,
        "cash_monthly": sample_cash_monthly,
        "revenue_monthly": sample_revenue_monthly,
    }
    sample_filled = 0

    # Les hypothèses complètes restent nécessaires à la sensibilité et au
    # point mort, mais elles sont tirées bloc par bloc pour rester annulables.
    samples = {key: np.empty(runs, dtype=np.float64) for key in assumptions}

    tracker = ConvergenceTracker(quality)
    histogram_range: HistogramRange | None = None

    def sample_view() -> RunSample:
        return RunSample(
            indices=np.arange(sample_filled, dtype=np.int64),
            profit_monthly=sample_profit_monthly[:sample_filled],
            cash_monthly=sample_cash_monthly[:sample_filled],
            revenue_monthly=sample_revenue_monthly[:sample_filled],
            parameters={
                key: values[:sample_filled]
                for key, values in sample_parameters.items()
            },
        )

    notify_progress(0.0)

    for block_index, start in enumerate(range(0, runs, block_size)):
        check_cancelled(start)
        end = min(start + block_size, runs)
        count = end - start

        batch_inputs: dict[str, np.ndarray] = {}
        for key in sorted(assumptions):
            hypothesis = assumptions[key]
            slot = f"hyp:{key}"
            if hypothesis.distribution is None:
                values = sample_hypothesis(
                    hypothesis,
                    None,
                    None,
                    model.bounds(key),
                    size=count,
                )
            else:
                needs_uniform, needs_normal = distribution_streams(
                    hypothesis.distribution
                )
                uniform, normal = bank.take_range(
                    slot,
                    start,
                    end,
                    uniform=needs_uniform,
                    normal=needs_normal,
                )
                values = sample_hypothesis(
                    hypothesis,
                    uniform,
                    normal,
                    model.bounds(key),
                )
            batch_inputs[key] = values
            samples[key][start:end] = values

        batch_noise = bank.take_range(
            "noise",
            start,
            end,
            uniform=False,
        )[1]
        modifiers = build_event_modifiers(
            event_draws,
            start,
            end,
            scenario.horizon_months,
        )
        batch = model.simulate_batch(batch_inputs, batch_noise, seasonality, modifiers)

        state.add(batch)
        profit[start:end] = batch.profit
        min_cash[start:end] = run_min_cash(batch.cash_monthly)
        break_even_month[start:end] = run_break_even_months(batch.profit_monthly)

        remaining = sample_limit - sample_filled
        if remaining > 0:
            take = min(remaining, count)
            destination = slice(sample_filled, sample_filled + take)
            source = slice(0, take)
            for name in _SAMPLE_ARRAYS:
                sample_arrays[name][destination] = getattr(batch, name)[source]
            for key in assumptions:
                sample_parameters[key][destination] = batch_inputs[key][source]
            sample_filled += take

        # Le bloc en cours est terminé ; on ne publie plus rien s'il a été
        # annulé pendant son calcul.
        check_cancelled(end)

        if histogram_range is None:
            histogram_range = HistogramRange.from_values(
                profit[:end], config.histogram_bins
            )
        else:
            histogram_range.expand(profit[start:end])

        index = sample_prefix_indices(end, CONVERGENCE_SAMPLE_LIMIT)
        if index is None:
            convergence = tracker.update(
                convergence_vector(
                    profit[:end],
                    min_cash[:end],
                    break_even_month[:end],
                    scenario.horizon_months,
                ),
                end,
            )
        else:
            convergence = tracker.update(
                convergence_vector(
                    profit[index],
                    min_cash[index],
                    break_even_month[index],
                    scenario.horizon_months,
                ),
                end,
            )

        should_emit_partial = on_partial is not None and block_index in partial_blocks
        if should_emit_partial:
            partial = build_partial_aggregates(
                profit=profit,
                min_cash=min_cash,
                break_even_month=break_even_month,
                state=state,
                completed_runs=end,
                total_runs=runs,
                sample=sample_view(),
                config=config,
                convergence=convergence,
                histogram_range=histogram_range,
            )
            # Une annulation peut arriver pendant la construction du partiel :
            # on ne publie rien après elle.
            check_cancelled(end)
            on_partial(partial)

        # Couvre aussi une annulation demandée depuis le callback partiel.
        check_cancelled(end)
        notify_progress(end / runs)

    duration_ms = (time.perf_counter() - started) * 1000.0
    sample = sample_view()

    result = SimulationResult(
        run_id=uuid.uuid4().hex,
        engine_version=__version__,
        scenario_name=scenario.name,
        model=scenario.model,
        currency=scenario.currency,
        horizon_months=scenario.horizon_months,
        runs=runs,
        runs_retained=int(sample.indices.size),
        seed=config.seed,
        duration_ms=duration_ms,
        metrics=build_metrics(profit, state, runs, min_cash, break_even_month),
        histogram=build_histogram(profit, config),
        monthly=build_monthly(
            state,
            runs,
            sample,
            break_even_month,
            config,
        ),
        sensitivity=build_sensitivity(samples, profit),
        break_even=build_break_even(samples),
        approximations=sorted(approximations) or None,
        quality=quality,
        convergence=tracker.state,
    )
    result.attach_sample(sample)
    return result
