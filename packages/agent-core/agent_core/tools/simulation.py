from __future__ import annotations

from typing import Any

from engine import (
    EngineError,
    Scenario,
    SimulationConfig,
    SimulationResult,
    simulate,
)

from ..errors import ToolError
from ..models import AgentModel
from .base import ToolContext, ToolExecution, ToolSpec

_SIMULATION_STATES = frozenset({"hypotheses_set", "simulating", "results_ready"})


class RunSimulationInput(AgentModel):
    scenario: Scenario | None = None
    seed: int = 42
    runs: int = 10_000
    histogram_bins: int = 40


class CompareScenariosInput(AgentModel):
    scenario_a: Scenario
    scenario_b: Scenario
    seed: int = 42
    runs: int = 10_000


class CompareScenariosOutput(AgentModel):
    first: dict[str, Any]
    second: dict[str, Any]
    delta: dict[str, float]


def _resolve_scenario(payload: RunSimulationInput, context: ToolContext) -> Scenario:
    if payload.scenario is not None:
        return payload.scenario
    if context.scenario is None:
        raise ToolError(
            "aucune hypothèse enregistrée pour ce projet",
            code="hypotheses_required",
        )
    return Scenario.model_validate(context.scenario)


def _run(
    scenario: Scenario,
    *,
    seed: int,
    runs: int,
    histogram_bins: int,
) -> SimulationResult:
    try:
        return simulate(
            scenario,
            SimulationConfig(seed=seed, runs=runs, histogram_bins=histogram_bins),
        )
    except (EngineError, ValueError) as error:
        raise ToolError(
            f"simulation impossible: {error}",
            code="simulation_failed",
        ) from error


def run_simulation(payload: RunSimulationInput, context: ToolContext) -> ToolExecution:
    if context.state not in _SIMULATION_STATES:
        raise ToolError(
            "les hypothèses doivent être validées avant de simuler",
            code="hypotheses_required",
            details={"state": context.state},
        )
    scenario = _resolve_scenario(payload, context)
    if not scenario.assumptions:
        raise ToolError("le scénario ne contient aucune hypothèse", code="hypotheses_required")
    result = _run(
        scenario,
        seed=payload.seed,
        runs=payload.runs,
        histogram_bins=payload.histogram_bins,
    )
    if context.save_run is not None:
        context.save_run(result, context.scenario_id)
    return ToolExecution(
        result=result,
        state_path=("simulating", "results_ready"),
    )


def compare_scenarios(
    payload: CompareScenariosInput, context: ToolContext
) -> ToolExecution:
    if context.state not in _SIMULATION_STATES:
        raise ToolError(
            "les hypothèses doivent être validées avant de comparer",
            code="hypotheses_required",
        )
    first = _run(
        payload.scenario_a,
        seed=payload.seed,
        runs=payload.runs,
        histogram_bins=40,
    )
    second = _run(
        payload.scenario_b,
        seed=payload.seed,
        runs=payload.runs,
        histogram_bins=40,
    )
    if context.save_run is not None:
        context.save_run(first, None)
        context.save_run(second, None)
    delta = {
        "meanProfit": second.metrics.mean_profit - first.metrics.mean_profit,
        "p10": second.metrics.p10 - first.metrics.p10,
        "p50": second.metrics.p50 - first.metrics.p50,
        "p90": second.metrics.p90 - first.metrics.p90,
        "lossProbability": (
            second.metrics.loss_probability - first.metrics.loss_probability
        ),
    }
    return ToolExecution(
        result={
            "first": first.model_dump(by_alias=True, mode="json"),
            "second": second.model_dump(by_alias=True, mode="json"),
            "delta": delta,
        },
        state_path=("results_ready",),
    )


RUN_SPEC = ToolSpec(
    name="run_simulation",
    description=(
        "Lance le moteur Monte Carlo sur le scénario courant ou fourni. Tous les "
        "chiffres renvoyés proviennent exclusivement du moteur."
    ),
    input_model=RunSimulationInput,
    output_model=SimulationResult,
    handler=run_simulation,
    default_permission="allow",
)

COMPARE_SPEC = ToolSpec(
    name="compare_scenarios",
    description=(
        "Exécute deux scénarios avec la même graine et renvoie leurs métriques et "
        "écarts calculés par le moteur."
    ),
    input_model=CompareScenariosInput,
    output_model=CompareScenariosOutput,
    handler=compare_scenarios,
    default_permission="allow",
)
