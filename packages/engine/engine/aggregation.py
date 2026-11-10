from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .models.base import BatchResult
from .scenario import (
    BreakEven,
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


def build_metrics(
    profit: np.ndarray,
    state: AggregationState,
    runs: int,
) -> Metrics:
    p10, p50, p90 = (float(value) for value in np.percentile(profit, [10.0, 50.0, 90.0]))
    mean_profit = float(profit.mean())
    mean_revenue = float(state.monthly_sums["revenue_monthly"].sum() / runs)
    mean_costs = float(state.monthly_sums["costs_monthly"].sum() / runs)
    mean_tax = float(state.monthly_sums["tax_monthly"].sum() / runs)

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
    )


def build_histogram(profit: np.ndarray, config: SimulationConfig) -> Histogram:
    lower = float(profit.min())
    upper = float(profit.max())
    if lower == upper:
        lower -= 0.5
        upper += 0.5
    counts, edges = np.histogram(profit, bins=config.histogram_bins, range=(lower, upper))
    total = float(counts.sum())
    bins = [
        HistogramBin(
            lower=float(edges[index]),
            upper=float(edges[index + 1]),
            count=int(counts[index]),
            probability=float(counts[index] / total) if total else 0.0,
        )
        for index in range(len(counts))
    ]
    return Histogram(bins=bins)


def build_monthly(state: AggregationState, runs: int) -> MonthlyAverages:
    values = []
    for index in range(state.horizon):
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
            )
        )
    return MonthlyAverages(values=values)


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
