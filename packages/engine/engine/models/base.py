from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ..scenario import Hypothesis, Scenario


@dataclass(frozen=True)
class InputSpec:
    key: str
    label: str
    unit: str
    minimum: float
    maximum: float | None = None
    default: float | None = None
    required: bool = True


@dataclass
class BatchResult:
    profit: np.ndarray
    revenue_monthly: np.ndarray
    profit_monthly: np.ndarray
    demand_monthly: np.ndarray
    sold_monthly: np.ndarray
    stock_end_monthly: np.ndarray
    stockout_monthly: np.ndarray
    lost_monthly: np.ndarray
    tax_monthly: np.ndarray
    costs_monthly: np.ndarray
    cash_end: np.ndarray
    inventory_value_end: np.ndarray
    units_sold: np.ndarray
    units_lost: np.ndarray


class SimulationModel(Protocol):
    name: str

    def resolve(self, scenario: Scenario) -> dict[str, Hypothesis]: ...

    def bounds(self, key: str) -> tuple[float, float | None]: ...

    def simulate_batch(
        self,
        inputs: dict[str, np.ndarray],
        noise: np.ndarray,
        seasonality: np.ndarray,
    ) -> BatchResult: ...
