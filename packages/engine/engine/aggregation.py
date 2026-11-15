from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .models.base import BatchResult
from .progressive import PartialAggregates
from .run_sample import RunSample
from .scenario import (
    BreakEven,
    CashCdfPoint,
    ConvergenceState,
    Histogram,
    HistogramBin,
    Metrics,
    MonthlyAverage,
    MonthlyAverages,
    SimulationConfig,
)

_MONTHLY_FIELDS = (
    "revenue_monthly",
    "profit_monthly",
    "demand_monthly",
    "sold_monthly",
    "stock_end_monthly",
    "stockout_monthly",
    "lost_monthly",
    "tax_monthly",
    "costs_monthly",
)

CDF_POINTS = 64
"""Nombre cible de points de la CDF du minimum de trésorerie."""

BAND_SAMPLE_LIMIT = 2_000
"""Nombre de runs utilisé pour les bandes mensuelles du résultat final.

Un sous-échantillon régulier du préfixe retenu suffit pour P10/P50/P90 et
garde le calcul sous la cible de 5 ms. L'échantillon complet (jusqu'à 20 000
runs) reste disponible pour les trajectoires de la phase 12.
"""

PARTIAL_BAND_SAMPLE_LIMIT = 1_000
"""Nombre de runs utilisé pour les bandes d'un partiel.

Le partiel est un objet d'affichage transitoire : 1 000 runs suffisent pour un
éventail lisible et divisent par deux le coût des percentiles mensuels.
"""

_MONTHLY_DIGITS = 5
"""Chiffres significatifs conservés pour les bornes d'histogramme mensuel.

Les histogrammes sont des objets d'affichage : cinq chiffres significatifs
suffisent et gardent le payload final sous la cible de 100 Kio.
"""

PARTIAL_SAMPLE_LIMIT = 5_000
"""Runs utilisés au maximum pour calculer les métriques d'un partiel.

Un sous-échantillon régulier du préfixe garde chaque partiel sous la cible de
10 ms. Les moyennes mensuelles restent exactes : elles viennent de l'état
d'agrégation complet.
"""

CONVERGENCE_SAMPLE_LIMIT = 2_000
"""Runs utilisés au maximum pour le vecteur de convergence de chaque bloc.

La convergence est recalculée à chaque bloc, mais sur un échantillon borné :
son coût ne dépend pas du nombre total de runs.
"""

HISTOGRAM_PADDING = 0.02
"""Marge relative appliquée aux bornes stables d'un histogramme partiel."""


@dataclass
class HistogramRange:
    """Bornes stables d'histogramme, élargies symétriquement si nécessaire.

    Le centre est fixé au premier bloc. Quand une valeur sort de la plage, la
    demi-largeur augmente des deux côtés de la même quantité, avec une petite
    marge pour éviter un élargissement à chaque bloc. Un histogramme partiel ne
    change donc pas de bornes sans raison visible.
    """

    center: float
    half_width: float
    bins: int

    @classmethod
    def from_values(
        cls,
        values: np.ndarray,
        bins: int,
        *,
        padding: float = HISTOGRAM_PADDING,
    ) -> HistogramRange:
        if values.size == 0:
            raise ValueError("impossible de dériver des bornes d'un tableau vide")
        lower = float(values.min())
        upper = float(values.max())
        if lower == upper:
            return cls(center=lower, half_width=0.5, bins=bins)
        center = (lower + upper) / 2.0
        half_width = max(upper - center, center - lower) * (1.0 + padding)
        return cls(center=center, half_width=half_width, bins=bins)

    @property
    def lower(self) -> float:
        return self.center - self.half_width

    @property
    def upper(self) -> float:
        return self.center + self.half_width

    @property
    def edges(self) -> np.ndarray:
        return np.linspace(self.lower, self.upper, self.bins + 1)

    def expand(self, values: np.ndarray) -> bool:
        """Élargit symétriquement la plage si ``values`` en sort.

        Retourne ``True`` si les bornes ont changé.
        """

        if values.size == 0:
            return False
        needed = max(
            self.center - float(values.min()),
            float(values.max()) - self.center,
        )
        if needed > self.half_width:
            self.half_width = needed * (1.0 + HISTOGRAM_PADDING)
            return True
        return False


def sample_prefix_indices(count: int, limit: int) -> np.ndarray | None:
    """Indices régulièrement espacés dans ``[0, count)``, ou ``None`` si inutile."""

    if count <= limit:
        return None
    return np.linspace(0, count - 1, limit).round().astype(np.int64)


@dataclass
class AggregationState:
    horizon: int
    monthly_sums: dict[str, np.ndarray] = field(init=False)
    units_sold: float = 0.0
    units_lost: float = 0.0
    cash_end: float = 0.0
    inventory_value: float = 0.0
    stockout_months: float = 0.0

    def __post_init__(self) -> None:
        self.monthly_sums = {
            name: np.zeros(self.horizon, dtype=np.float64) for name in _MONTHLY_FIELDS
        }

    def add(self, batch: BatchResult) -> None:
        for name in _MONTHLY_FIELDS:
            self.monthly_sums[name] += getattr(batch, name).sum(axis=0)
        self.units_sold += float(batch.units_sold.sum())
        self.units_lost += float(batch.units_lost.sum())
        self.cash_end += float(batch.cash_end.sum())
        self.inventory_value += float(batch.inventory_value_end.sum())
        self.stockout_months += float(batch.stockout_monthly.sum())


def run_min_cash(cash_monthly: np.ndarray) -> np.ndarray:
    """Minimum de trésorerie mensuelle par run."""
    return cash_monthly.min(axis=1)


def run_break_even_months(profit_monthly: np.ndarray) -> np.ndarray:
    """Premier mois où le profit net cumulé est >= 0, par run.

    Le sentinelle ``horizon + 1`` signifie « non atteint sur l'horizon ».
    """
    cumulative = np.cumsum(profit_monthly, axis=1)
    reached = cumulative >= 0.0
    months = np.argmax(reached, axis=1) + 1
    horizon = profit_monthly.shape[1]
    return np.where(reached.any(axis=1), months, horizon + 1).astype(np.int64)


def _sorted_quantile(sorted_values: np.ndarray, q: float) -> float:
    """Quantile linéaire d'un tableau déjà trié (méthode de numpy)."""
    count = sorted_values.size
    position = q * (count - 1)
    lower = int(position)
    upper = min(lower + 1, count - 1)
    fraction = position - lower
    return float(
        sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction
    )


def _band_matrix(
    monthly: np.ndarray,
    limit: int = BAND_SAMPLE_LIMIT,
) -> np.ndarray:
    """Transpose un sous-échantillon régulier pour des percentiles par mois."""
    count = monthly.shape[0]
    if count > limit:
        indices = np.linspace(0, count - 1, limit).round().astype(np.int64)
        monthly = monthly[indices]
    return np.ascontiguousarray(monthly.T)


def build_metrics(
    profit: np.ndarray,
    state: AggregationState,
    runs: int,
    min_cash: np.ndarray,
    break_even_month: np.ndarray,
) -> Metrics:
    p10, p50, p90 = (float(value) for value in np.percentile(profit, [10.0, 50.0, 90.0]))
    mean_profit = float(profit.mean())
    mean_revenue = float(state.monthly_sums["revenue_monthly"].sum() / runs)
    mean_costs = float(state.monthly_sums["costs_monthly"].sum() / runs)
    mean_tax = float(state.monthly_sums["tax_monthly"].sum() / runs)

    sorted_min_cash = np.sort(min_cash)
    min_cash_p10 = _sorted_quantile(sorted_min_cash, 0.10)
    min_cash_p50 = _sorted_quantile(sorted_min_cash, 0.50)
    min_cash_p90 = _sorted_quantile(sorted_min_cash, 0.90)
    financing_p50 = max(0.0, -min_cash_p50)
    financing_p90 = max(0.0, -min_cash_p10)
    reached = break_even_month <= state.horizon
    break_even_probability = float(np.mean(reached))
    if np.any(reached):
        median_break_even_month: int | None = int(
            round(float(np.median(break_even_month[reached])))
        )
    else:
        median_break_even_month = None

    return Metrics(
        mean_profit=mean_profit,
        median_profit=float(np.median(profit)),
        std_profit=float(profit.std(ddof=0)),
        min_profit=float(profit.min()),
        max_profit=float(profit.max()),
        p10=p10,
        p50=p50,
        p90=p90,
        loss_probability=float(np.mean(profit < 0)),
        profit_positive_probability=float(np.mean(profit > 0)),
        mean_revenue=mean_revenue,
        mean_costs=mean_costs,
        mean_tax=mean_tax,
        mean_cash_end=float(state.cash_end / runs),
        mean_units_sold=float(state.units_sold / runs),
        mean_units_lost=float(state.units_lost / runs),
        mean_stockout_months=float(state.stockout_months / runs),
        mean_end_stock=float(state.monthly_sums["stock_end_monthly"][-1] / runs),
        mean_inventory_value=float(state.inventory_value / runs),
        mean_profit_margin=float(mean_profit / mean_revenue) if mean_revenue > 0 else 0.0,
        cash_negative_probability=float(np.mean(min_cash < 0)),
        mean_min_cash=float(min_cash.mean()),
        min_cash_p10=min_cash_p10,
        min_cash_p50=min_cash_p50,
        min_cash_p90=min_cash_p90,
        financing_need_p50=financing_p50,
        financing_need_p90=financing_p90,
        break_even_probability=break_even_probability,
        median_break_even_month=median_break_even_month,
        min_cash_cdf=build_min_cash_cdf(min_cash),
    )


def build_min_cash_cdf(min_cash: np.ndarray, points: int = CDF_POINTS) -> list[CashCdfPoint]:
    """CDF empirique ``P(min_cash <= value)``, au plus ``points`` points.

    Les valeurs sont uniques et triées ; la probabilité est cumulée à droite.
    Pour un minimum constant, un seul point suffit et la probabilité vaut 1.
    """
    values, counts = np.unique(min_cash, return_counts=True)
    cumulative = np.cumsum(counts) / float(min_cash.size)
    if values.size > points:
        indices = np.unique(
            np.linspace(0, values.size - 1, points).round().astype(np.int64)
        )
        values = values[indices]
        cumulative = cumulative[indices]
    return [
        CashCdfPoint(value=float(value), probability=float(probability))
        for value, probability in zip(values, cumulative, strict=True)
    ]


def _round_significant(value: float, digits: int = _MONTHLY_DIGITS) -> float:
    if value == 0.0 or not np.isfinite(value):
        return float(value)
    return float(f"{value:.{digits}g}")


def _histogram_bins(
    values: np.ndarray,
    bins: int,
    *,
    compact: bool = False,
    value_range: HistogramRange | None = None,
) -> list[HistogramBin]:
    if value_range is not None:
        value_range.expand(values)
        edges = value_range.edges
    else:
        lower = float(values.min())
        upper = float(values.max())
        if lower == upper:
            lower -= 0.5
            upper += 0.5
        edges = np.linspace(lower, upper, bins + 1)
    counts, edges = np.histogram(values, bins=edges)
    total = float(counts.sum())
    result: list[HistogramBin] = []
    for index in range(len(counts)):
        bin_lower = float(edges[index])
        bin_upper = float(edges[index + 1])
        probability = float(counts[index] / total) if total else 0.0
        if compact:
            rounded_lower = _round_significant(bin_lower)
            rounded_upper = _round_significant(bin_upper)
            if rounded_upper > rounded_lower:
                bin_lower = rounded_lower
                bin_upper = rounded_upper
            probability = round(probability, 5)
        result.append(
            HistogramBin(
                lower=bin_lower,
                upper=bin_upper,
                count=int(counts[index]),
                probability=probability,
            )
        )
    return result


def build_histogram(
    profit: np.ndarray,
    config: SimulationConfig,
    value_range: HistogramRange | None = None,
) -> Histogram:
    return Histogram(
        bins=_histogram_bins(
            profit,
            config.histogram_bins,
            value_range=value_range,
        )
    )


def build_monthly(
    state: AggregationState,
    runs: int,
    sample: RunSample,
    break_even_month: np.ndarray,
    config: SimulationConfig,
    *,
    include_monthly_histograms: bool = True,
    band_sample_limit: int = BAND_SAMPLE_LIMIT,
) -> MonthlyAverages:
    selected_month = config.histogram_month if include_monthly_histograms else None
    profit_bands = np.percentile(
        _band_matrix(sample.profit_monthly, band_sample_limit),
        [10.0, 50.0, 90.0],
        axis=1,
    )
    cash_bands = np.percentile(
        _band_matrix(sample.cash_monthly, band_sample_limit),
        [10.0, 50.0, 90.0],
        axis=1,
    )
    values = []
    for index in range(state.horizon):
        include_histograms = selected_month == index + 1
        values.append(
            MonthlyAverage(
                index=index + 1,
                month=index % 12 + 1,
                mean_revenue=float(state.monthly_sums["revenue_monthly"][index] / runs),
                mean_profit=float(state.monthly_sums["profit_monthly"][index] / runs),
                mean_demand=float(state.monthly_sums["demand_monthly"][index] / runs),
                mean_units_sold=float(state.monthly_sums["sold_monthly"][index] / runs),
                mean_stock_end=float(state.monthly_sums["stock_end_monthly"][index] / runs),
                stockout_probability=float(
                    state.monthly_sums["stockout_monthly"][index] / runs
                ),
                profit_p10=float(profit_bands[0, index]),
                profit_p50=float(profit_bands[1, index]),
                profit_p90=float(profit_bands[2, index]),
                cash_p10=float(cash_bands[0, index]),
                cash_p50=float(cash_bands[1, index]),
                cash_p90=float(cash_bands[2, index]),
                break_even_probability=float(
                    np.mean(break_even_month <= index + 1)
                ),
                profit_histogram=(
                    _histogram_bins(
                        sample.profit_monthly[:, index],
                        config.monthly_histogram_bins,
                        compact=True,
                    )
                    if include_histograms
                    else None
                ),
                cash_histogram=(
                    _histogram_bins(
                        sample.cash_monthly[:, index],
                        config.monthly_histogram_bins,
                        compact=True,
                    )
                    if include_histograms
                    else None
                ),
            )
        )
    return MonthlyAverages(values=values)


def build_partial_aggregates(
    *,
    profit: np.ndarray,
    min_cash: np.ndarray,
    break_even_month: np.ndarray,
    state: AggregationState,
    completed_runs: int,
    total_runs: int,
    sample: RunSample,
    config: SimulationConfig,
    convergence: ConvergenceState,
    histogram_range: HistogramRange,
) -> PartialAggregates:
    """Construit un partiel borné en coût et en taille.

    Les métriques probabilistes utilisent au plus ``PARTIAL_SAMPLE_LIMIT``
    runs ; les moyennes mensuelles restent exactes car elles viennent de
    l'état d'agrégation complet. Les histogrammes mensuels sont omis : ils
    gonfleraient le payload sans apport pour l'éventail en cours de geste.
    """

    indices = sample_prefix_indices(completed_runs, PARTIAL_SAMPLE_LIMIT)
    if indices is None:
        sampled_profit = profit[:completed_runs]
        sampled_min_cash = min_cash[:completed_runs]
        sampled_break_even = break_even_month[:completed_runs]
    else:
        sampled_profit = profit[indices]
        sampled_min_cash = min_cash[indices]
        sampled_break_even = break_even_month[indices]

    return PartialAggregates(
        completed_runs=completed_runs,
        total_runs=total_runs,
        metrics=build_metrics(
            sampled_profit,
            state,
            completed_runs,
            sampled_min_cash,
            sampled_break_even,
        ),
        histogram=build_histogram(
            profit[:completed_runs],
            config,
            histogram_range,
        ),
        monthly=build_monthly(
            state,
            completed_runs,
            sample,
            break_even_month[:completed_runs],
            config,
            include_monthly_histograms=False,
            band_sample_limit=PARTIAL_BAND_SAMPLE_LIMIT,
        ),
        convergence=convergence,
    )


def build_break_even(samples: dict[str, np.ndarray]) -> BreakEven:
    mean_price = float(samples["unit_price"].mean())
    mean_cost = float(samples["unit_cost"].mean())
    mean_logistics = float(samples["logistics_cost_per_unit"].mean())
    mean_fixed = float(samples["fixed_costs_monthly"].mean())
    unit_margin = mean_price - mean_cost - mean_logistics

    if unit_margin > 0:
        break_even_units = mean_fixed / unit_margin
        break_even_revenue: float | None = break_even_units * mean_price
    else:
        break_even_units = None
        break_even_revenue = None

    return BreakEven(
        monthly_fixed_costs=mean_fixed,
        unit_margin=unit_margin,
        break_even_units_monthly=(
            float(break_even_units) if break_even_units is not None else None
        ),
        break_even_revenue_monthly=break_even_revenue,
    )
