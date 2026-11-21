"""Surface de résultat 2D et exploration conditionnelle (phase 11).

La surface est une grille de scénarios **conditionnels** : deux hypothèses
varient, toutes les autres restent identiques. La même graine est réutilisée
pour chaque point, ce qui garantit des tirages communs (CRN) et rend les
écarts entre cellules imputables aux axes, pas au hasard.

Aucun chiffre n'est calculé dans l'UI : ce module est le seul producteur de la
matrice affichée par la heatmap.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal

from pydantic import Field, model_validator

from .errors import EngineError, SimulationCancelled
from .models import get_model
from .progressive import CancelToken
from .runner import simulate
from .scenario import Hypothesis, Quality, Scenario, SimulationConfig
from .schema import CamelModel

SurfaceMetric = Literal[
    "profit_p50",
    "profit_p10",
    "profit_p90",
    "break_even_months_p50",
    "financing_need_p90",
    "loss_probability",
]

SurfaceProgress = Callable[[float], None]


class AxisSpec(CamelModel):
    """Hypothèse variant sur un axe de la surface."""

    key: str = Field(min_length=1, max_length=80)
    minimum: float
    maximum: float
    scale: Literal["linear"] = "linear"

    @model_validator(mode="after")
    def _check_range(self) -> AxisSpec:
        if not self.minimum < self.maximum:
            raise ValueError("un axe doit avoir minimum < maximum")
        return self


class SurfaceResult(CamelModel):
    """Résultat d'une surface, orienté ``z[ligne_y][colonne_x]``."""

    x_values: list[float]
    y_values: list[float]
    z_p50: list[list[float]]
    z_p10: list[list[float]] | None = None
    z_p90: list[list[float]] | None = None
    current: tuple[float, float]
    metric: SurfaceMetric
    runs: int
    seed: int
    grid: tuple[int, int]
    cost: int
    duration_ms: float


_PROFIT_METRICS: frozenset[str] = frozenset({"profit_p50", "profit_p10", "profit_p90"})


def metric_value(result, metric: SurfaceMetric, horizon: int) -> float:
    """Extrait une métrique d'un résultat, sans recalcul côté appelant."""

    metrics = result.metrics
    if metric == "profit_p50":
        return float(metrics.p50)
    if metric == "profit_p10":
        return float(metrics.p10)
    if metric == "profit_p90":
        return float(metrics.p90)
    if metric == "break_even_months_p50":
        # ``None`` signifie « jamais atteint » : on utilise la sentinelle
        # historique du moteur (horizon + 1) plutôt qu'une valeur inventée.
        month = metrics.median_break_even_month
        return float(horizon + 1 if month is None else month)
    if metric == "financing_need_p90":
        value = metrics.financing_need_p90
        return float(0.0 if value is None else value)
    if metric == "loss_probability":
        return float(metrics.loss_probability)
    raise EngineError(f"métrique de surface inconnue: {metric!r}")


def _validate_axis(scenario: Scenario, axis: AxisSpec, name: str) -> None:
    model = get_model(scenario.model)
    resolved = model.resolve(scenario)
    if axis.key not in resolved:
        raise EngineError(
            f"axe {name}: hypothèse inconnue pour le modèle {scenario.model!r}: {axis.key}"
        )
    lower, upper = model.bounds(axis.key)
    hypothesis = resolved[axis.key]
    if hypothesis.min is not None:
        lower = max(lower, hypothesis.min)
    if hypothesis.max is not None:
        upper = hypothesis.max if upper is None else min(upper, hypothesis.max)
    if axis.minimum < lower:
        raise EngineError(
            f"axe {name}: minimum {axis.minimum} inférieur à la borne {lower} pour {axis.key}"
        )
    if upper is not None and axis.maximum > upper:
        raise EngineError(
            f"axe {name}: maximum {axis.maximum} supérieur à la borne {upper} pour {axis.key}"
        )


def _with_value(scenario: Scenario, key: str, value: float) -> Scenario:
    assumptions = dict(scenario.assumptions)
    assumptions[key] = Hypothesis(value=value)
    return scenario.model_copy(update={"assumptions": assumptions})


def surface(
    scenario: Scenario,
    config: SimulationConfig | None = None,
    axis_x: AxisSpec | None = None,
    axis_y: AxisSpec | None = None,
    metric: SurfaceMetric = "profit_p50",
    grid: tuple[int, int] = (15, 15),
    runs: int = 200,
    seed: int | None = None,
    on_progress: SurfaceProgress | None = None,
    cancel: CancelToken | None = None,
    *,
    quality: Quality = "draft",
) -> SurfaceResult:
    """Calcule une grille 2D avec des tirages communs.

    ``axis_x`` varie les colonnes, ``axis_y`` les lignes. Les valeurs sont
    celles du moteur, sans lissage. La fonction est annulable entre deux
    points ; la progression est un nombre de points, pas un pourcentage de
    précision.
    """

    if axis_x is None or axis_y is None:
        raise EngineError("une surface exige deux axes")
    if axis_x.key == axis_y.key:
        raise EngineError("les deux axes doivent porter sur des hypothèses différentes")
    columns, rows = (int(grid[0]), int(grid[1]))
    if columns < 2 or rows < 2 or columns > 60 or rows > 60:
        raise EngineError("la grille doit être comprise entre 2×2 et 60×60")
    if runs < 1:
        raise EngineError("le nombre de runs doit être positif")

    _validate_axis(scenario, axis_x, "X")
    _validate_axis(scenario, axis_y, "Y")

    resolved_seed = int(seed if seed is not None else (config.seed if config else 42))
    base_config = (config or SimulationConfig()).model_copy(
        update={"seed": resolved_seed, "runs": runs}
    )

    x_values = [float(value) for value in _linspace(axis_x.minimum, axis_x.maximum, columns)]
    y_values = [float(value) for value in _linspace(axis_y.minimum, axis_y.maximum, rows)]

    current_x = float(scenario.assumptions.get(axis_x.key, Hypothesis(value=x_values[0])).value)
    current_y = float(scenario.assumptions.get(axis_y.key, Hypothesis(value=y_values[0])).value)

    z_p50 = [[0.0 for _ in range(columns)] for _ in range(rows)]
    z_p10: list[list[float]] | None = (
        [[0.0 for _ in range(columns)] for _ in range(rows)]
        if metric in _PROFIT_METRICS
        else None
    )
    z_p90: list[list[float]] | None = (
        [[0.0 for _ in range(columns)] for _ in range(rows)]
        if metric in _PROFIT_METRICS
        else None
    )

    total = columns * rows
    done = 0
    started = time.perf_counter()
    if on_progress is not None:
        on_progress(0.0)

    for row_index, y_value in enumerate(y_values):
        for column_index, x_value in enumerate(x_values):
            if cancel is not None and cancel.is_cancelled():
                raise SimulationCancelled(done, total)
            point_scenario = _with_value(scenario, axis_x.key, x_value)
            point_scenario = _with_value(point_scenario, axis_y.key, y_value)
            result = simulate(
                point_scenario,
                base_config,
                quality=quality,
                cancel=cancel,
            )
            z_p50[row_index][column_index] = metric_value(
                result, metric, scenario.horizon_months
            )
            if z_p10 is not None and z_p90 is not None:
                z_p10[row_index][column_index] = float(result.metrics.p10)
                z_p90[row_index][column_index] = float(result.metrics.p90)
            done += 1
            if on_progress is not None:
                on_progress(done / total)

    return SurfaceResult(
        x_values=x_values,
        y_values=y_values,
        z_p50=z_p50,
        z_p10=z_p10,
        z_p90=z_p90,
        current=(current_x, current_y),
        metric=metric,
        runs=runs,
        seed=resolved_seed,
        grid=(columns, rows),
        cost=total * runs,
        duration_ms=(time.perf_counter() - started) * 1_000.0,
    )


def _linspace(minimum: float, maximum: float, count: int) -> list[float]:
    """``numpy.linspace`` sans dépendre d'un tableau NumPy exposé."""

    if count == 1:
        return [float(minimum)]
    step = (maximum - minimum) / (count - 1)
    return [float(minimum + step * index) for index in range(count)]


__all__ = [
    "AxisSpec",
    "SurfaceMetric",
    "SurfaceProgress",
    "SurfaceResult",
    "metric_value",
    "surface",
]
