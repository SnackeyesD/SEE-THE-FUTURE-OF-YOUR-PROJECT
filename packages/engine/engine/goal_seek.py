"""Recherche d'objectif par évaluations moteur (phase 11).

L'objectif porte sur une métrique produite par le moteur. Aucune valeur n'est
estimée dans l'UI : la recherche évalue des scénarios complets avec la même
graine et retourne le meilleur point trouvé, sa faisabilité et son écart.

Les probabilités et les mois de point mort forment des plateaux : la recherche
utilise un balayage + dichotomie pour un levier, et une recherche par
coordonnées (compass search) à pas décroissant pour plusieurs leviers. Pas de
Nelder-Mead.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import Field, model_validator

from .errors import EngineError, SimulationCancelled
from .models import get_model
from .progressive import CancelToken
from .runner import simulate
from .scenario import Hypothesis, Quality, Scenario, SimulationConfig
from .schema import CamelModel
from .surface import SurfaceMetric, _linspace, metric_value

Comparator = Literal[">=", "<="]


class Objective(CamelModel):
    metric: SurfaceMetric
    comparator: Comparator
    target: float
    tolerance: float = Field(default=0.02, ge=0.0)


class Lever(CamelModel):
    key: str = Field(min_length=1, max_length=80)
    minimum: float
    maximum: float

    @model_validator(mode="after")
    def _check_range(self) -> Lever:
        if not self.minimum < self.maximum:
            raise ValueError("un levier doit avoir minimum < maximum")
        return self


class GoalTraceEntry(CamelModel):
    point: dict[str, float]
    value: float
    feasible: bool


class GoalSeekResult(CamelModel):
    feasible: bool
    best: dict[str, float]
    achieved: float
    target: float
    gap: float
    evaluations: int
    trace: list[GoalTraceEntry]
    budget_exhausted: bool
    message: str
    metric: SurfaceMetric
    comparator: Comparator
    quality: Quality | None = None


class _BudgetExhausted(Exception):
    pass


def _signed_gap(comparator: Comparator, achieved: float, target: float) -> float:
    """Écart signé : positif tant que la cible n'est pas atteinte."""

    return target - achieved if comparator == ">=" else achieved - target


def _is_feasible(objective: Objective, value: float) -> bool:
    return _signed_gap(objective.comparator, value, objective.target) <= objective.tolerance


def _score(objective: Objective, value: float) -> float:
    """Score à minimiser : 0 dès que la cible est dans la tolérance."""

    return max(0.0, _signed_gap(objective.comparator, value, objective.target))


def _bounds_for(
    scenario: Scenario,
    levers: list[Lever],
    locked: Iterable[str],
) -> dict[str, tuple[float, float]]:
    locked_set = set(locked)
    resolved = get_model(scenario.model).resolve(scenario)
    bounds: dict[str, tuple[float, float]] = {}
    for lever in levers:
        if lever.key in locked_set:
            raise EngineError(f"le levier {lever.key!r} est verrouillé")
        if lever.key not in resolved:
            raise EngineError(
                f"levier inconnu pour le modèle {scenario.model!r}: {lever.key}"
            )
        model = get_model(scenario.model)
        model_lower, model_upper = model.bounds(lever.key)
        hypothesis = resolved[lever.key]
        lower = max(lever.minimum, model_lower)
        upper = lever.maximum
        if hypothesis.min is not None:
            lower = max(lower, hypothesis.min)
        if hypothesis.max is not None:
            upper = min(upper, hypothesis.max)
        if model_upper is not None:
            upper = min(upper, model_upper)
        if lower >= upper:
            raise EngineError(
                f"levier {lever.key!r}: bornes effectives invalides "
                f"({lower} ≥ {upper}) après contraintes du modèle"
            )
        bounds[lever.key] = (float(lower), float(upper))
    return bounds


def _scenario_with(scenario: Scenario, point: dict[str, float]) -> Scenario:
    assumptions = dict(scenario.assumptions)
    for key, value in point.items():
        assumptions[key] = Hypothesis(value=value)
    return scenario.model_copy(update={"assumptions": assumptions})


def _start_point(
    scenario: Scenario,
    bounds: dict[str, tuple[float, float]],
) -> dict[str, float]:
    start: dict[str, float] = {}
    for key, (lower, upper) in bounds.items():
        hypothesis = scenario.assumptions.get(key)
        value = hypothesis.value if hypothesis is not None else (lower + upper) / 2.0
        start[key] = float(min(max(value, lower), upper))
    return start


def goal_seek(
    scenario: Scenario,
    objective: Objective,
    levers: list[Lever],
    *,
    locked: Iterable[str] = (),
    seed: int = 42,
    max_evaluations: int = 80,
    runs: int = 500,
    config: SimulationConfig | None = None,
    cancel: CancelToken | None = None,
    confirm_quality: Quality | None = "final",
    confirm_runs: int = 5_000,
) -> GoalSeekResult:
    """Cherche des valeurs de leviers qui atteignent ``objective``.

    ``max_evaluations`` compte les évaluations uniques en qualité ``draft``
    (ou ``runs`` explicitement demandé). La confirmation finale, si activée,
    n'entre pas dans ce budget : elle vérifie le meilleur point avec le profil
    ``final`` et remplace la valeur retournée.
    """

    if not levers:
        raise EngineError("la recherche d'objectif exige au moins un levier")
    if max_evaluations < 1:
        raise EngineError("le budget d'évaluations doit être positif")
    if runs < 1:
        raise EngineError("le nombre de runs doit être positif")

    bounds = _bounds_for(scenario, levers, locked)
    base_config = (config or SimulationConfig()).model_copy(
        update={"seed": int(seed), "runs": int(runs)}
    )

    trace: list[GoalTraceEntry] = []
    cache: dict[tuple[tuple[str, float], ...], float] = {}
    evaluations = 0
    best_point = _start_point(scenario, bounds)
    best_value = 0.0
    best_score = float("inf")
    best_distance = float("inf")
    start_point = dict(best_point)

    def evaluate(point: dict[str, float]) -> float:
        nonlocal evaluations
        key = tuple(sorted((name, round(value, 12)) for name, value in point.items()))
        if key in cache:
            return cache[key]
        if evaluations >= max_evaluations:
            raise _BudgetExhausted
        if cancel is not None and cancel.is_cancelled():
            raise SimulationCancelled(evaluations, max_evaluations)
        result = simulate(
            _scenario_with(scenario, point),
            base_config,
            quality="draft",
            cancel=cancel,
        )
        value = metric_value(result, objective.metric, scenario.horizon_months)
        cache[key] = value
        evaluations += 1
        trace.append(
            GoalTraceEntry(
                point=dict(point),
                value=value,
                feasible=_is_feasible(objective, value),
            )
        )
        return value

    def consider(point: dict[str, float], value: float) -> None:
        nonlocal best_point, best_value, best_score, best_distance
        score = _score(objective, value)
        distance = sum(
            abs(setting - start_point.get(key, setting))
            for key, setting in point.items()
        )
        if (score, distance) < (best_score, best_distance):
            best_point = dict(point)
            best_value = value
            best_score = score
            best_distance = distance

    budget_exhausted = False
    try:
        if len(levers) == 1:
            _search_single(
                objective,
                bounds,
                levers[0].key,
                evaluate,
                consider,
                max_evaluations,
            )
        else:
            _search_compass(
                objective,
                bounds,
                start_point,
                evaluate,
                consider,
            )
    except _BudgetExhausted:
        budget_exhausted = True

    feasible = _is_feasible(objective, best_value)
    gap = _signed_gap(objective.comparator, best_value, objective.target)
    quality: Quality | None = "draft"

    if confirm_quality is not None and best_point:
        confirmation_config = base_config.model_copy(
            update={"runs": max(1, int(confirm_runs))}
        )
        confirmation = simulate(
            _scenario_with(scenario, best_point),
            confirmation_config,
            quality=confirm_quality,
            cancel=cancel,
        )
        best_value = metric_value(
            confirmation, objective.metric, scenario.horizon_months
        )
        feasible = _is_feasible(objective, best_value)
        gap = _signed_gap(objective.comparator, best_value, objective.target)
        quality = confirm_quality

    if feasible:
        message = (
            f"Objectif atteint : {objective.metric} = {best_value:.4g} "
            f"(cible {objective.target:.4g}, tolérance {objective.tolerance:.4g})."
        )
    elif budget_exhausted:
        message = (
            f"Budget de {max_evaluations} évaluations épuisé sans atteindre la cible. "
            f"Meilleur écart : {gap:.4g}."
        )
    else:
        message = (
            f"Cible non atteignable dans les bornes des leviers. "
            f"Meilleur écart : {gap:.4g}."
        )

    return GoalSeekResult(
        feasible=feasible,
        best=best_point,
        achieved=best_value,
        target=objective.target,
        gap=gap,
        evaluations=evaluations,
        trace=trace,
        budget_exhausted=budget_exhausted,
        message=message,
        metric=objective.metric,
        comparator=objective.comparator,
        quality=quality,
    )


def _search_single(
    objective: Objective,
    bounds: dict[str, tuple[float, float]],
    key: str,
    evaluate,
    consider,
    max_evaluations: int,
) -> None:
    lower, upper = bounds[key]
    samples = max(2, min(max_evaluations, 11))
    points = _linspace(lower, upper, samples)

    evaluated: list[tuple[float, float]] = []
    for value in points:
        point = {key: value}
        metric = evaluate(point)
        consider(point, metric)
        evaluated.append((value, metric))

    feasible = [
        (value, metric) for value, metric in evaluated if _is_feasible(objective, metric)
    ]
    if not feasible:
        return

    def target_distance(item: tuple[float, float]) -> tuple[float, float]:
        return abs(item[1] - objective.target), item[0]

    best_x, best_metric = min(feasible, key=target_distance)
    index = next(
        position
        for position, (value, _) in enumerate(evaluated)
        if value == best_x
    )
    neighbours: list[tuple[float, float]] = []
    if index > 0:
        neighbours.append(evaluated[index - 1])
    if index + 1 < len(evaluated):
        neighbours.append(evaluated[index + 1])

    # Pour chaque voisin qui n'atteint pas la cible, resserre l'intervalle
    # jusqu'à obtenir une valeur proche du seuil, sans dépasser le budget.
    for neighbour_x, neighbour_metric in neighbours:
        if _is_feasible(objective, neighbour_metric):
            continue
        feasible_x = best_x
        infeasible_x = neighbour_x
        for _ in range(32):
            if abs(infeasible_x - feasible_x) <= (upper - lower) / 1_000.0:
                break
            midpoint = (feasible_x + infeasible_x) / 2.0
            point = {key: midpoint}
            metric = evaluate(point)
            consider(point, metric)
            if _is_feasible(objective, metric):
                feasible_x = midpoint
                if abs(metric - objective.target) < abs(
                    best_metric - objective.target
                ):
                    best_x, best_metric = midpoint, metric
            else:
                infeasible_x = midpoint


def _search_compass(
    objective: Objective,
    bounds: dict[str, tuple[float, float]],
    start: dict[str, float],
    evaluate,
    consider,
) -> None:
    point = dict(start)
    value = evaluate(point)
    consider(point, value)

    steps = {key: (high - low) / 2.0 for key, (low, high) in bounds.items()}
    minimum_step = {
        key: (high - low) / 1_024.0 for key, (low, high) in bounds.items()
    }

    while any(steps[key] > minimum_step[key] for key in bounds):
        improved = False
        for key, (low, high) in bounds.items():
            if steps[key] <= minimum_step[key]:
                continue
            for direction in (1.0, -1.0):
                candidate = dict(point)
                candidate[key] = min(
                    max(candidate[key] + direction * steps[key], low), high
                )
                if candidate[key] == point[key]:
                    continue
                candidate_value = evaluate(candidate)
                consider(candidate, candidate_value)
                if _is_feasible(objective, candidate_value):
                    return
                if _score(objective, candidate_value) < _score(objective, value):
                    point, value = candidate, candidate_value
                    improved = True
        if not improved:
            for key in steps:
                steps[key] /= 2.0


__all__ = [
    "Comparator",
    "GoalSeekResult",
    "GoalTraceEntry",
    "Lever",
    "Objective",
    "goal_seek",
]
