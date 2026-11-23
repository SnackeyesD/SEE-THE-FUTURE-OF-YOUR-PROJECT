from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import ConfigDict, Field, PrivateAttr, field_validator, model_validator

from .events import ScenarioEvent
from .run_sample import RunSample
from .schema import BenchmarkProvenance as BenchmarkProvenance
from .schema import CamelModel, FiniteFloat, Hypothesis, to_camel
from .schema import DistributionSpec as DistributionSpec

ModelName = Literal["retail_depot"]
Quality = Literal["draft", "final"]

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class Scenario(CamelModel):
    schema_version: Literal["1.0.0", "1.1.0"] = "1.0.0"
    name: str = Field(min_length=1, max_length=200)
    model: ModelName = "retail_depot"
    currency: str = Field(default="XOF", min_length=1, max_length=8)
    horizon_months: int = Field(default=12, ge=1, le=120)
    assumptions: dict[str, Hypothesis] = Field(default_factory=dict)
    events: list[ScenarioEvent] = Field(default_factory=list)
    seasonality: list[FiniteFloat] | None = None
    notes: str | None = None

    @field_validator("assumptions")
    @classmethod
    def _check_assumption_keys(cls, value: dict[str, Hypothesis]) -> dict[str, Hypothesis]:
        for key in value:
            if not _KEY_PATTERN.match(key):
                raise ValueError(f"clé d'hypothèse invalide: {key!r}")
        return value

    @model_validator(mode="after")
    def _check_seasonality(self) -> Scenario:
        if self.seasonality is None:
            return self
        if len(self.seasonality) != 12:
            raise ValueError("'seasonality' doit contenir exactement 12 valeurs mensuelles")
        if any(factor <= 0 for factor in self.seasonality):
            raise ValueError("'seasonality' doit contenir des facteurs strictement positifs")
        return self

    @model_validator(mode="after")
    def _check_events(self) -> Scenario:
        """Valide l'unicité et la fenêtre des événements, puis versionne.

        Un scénario sans événement reste en ``1.0.0`` ; dès qu'il en contient,
        le schéma émis passe en ``1.1.0`` sans rétrograder un scénario déjà
        versionné en ``1.1.0``.
        """

        if not self.events:
            return self
        seen: set[str] = set()
        for event in self.events:
            if event.id in seen:
                raise ValueError(f"id d'événement dupliqué: {event.id!r}")
            seen.add(event.id)
            last_month = event.start_month + event.duration_months - 1
            if last_month > self.horizon_months:
                raise ValueError(
                    f"événement {event.id!r}: la fenêtre se termine au mois "
                    f"{last_month}, au-delà de horizonMonths={self.horizon_months}"
                )
        if self.schema_version == "1.0.0":
            self.schema_version = "1.1.0"
        return self


class SimulationConfig(CamelModel):
    runs: int = Field(default=10_000, ge=1, le=1_000_000)
    seed: int = Field(default=42, ge=0, le=2**63 - 1)
    batch_size: int = Field(default=50_000, ge=1, le=1_000_000)
    histogram_bins: int = Field(default=40, ge=1, le=200)
    monthly_histogram_bins: int = Field(default=20, ge=10, le=30)
    histogram_month: int | None = Field(default=1, ge=1, le=120)
    include_monthly_histograms: bool = False


class CashCdfPoint(CamelModel):
    value: float
    probability: float


class Metrics(CamelModel):
    mean_profit: float
    median_profit: float
    std_profit: float
    min_profit: float
    max_profit: float
    p10: float
    p50: float
    p90: float
    loss_probability: float
    profit_positive_probability: float
    mean_revenue: float
    mean_costs: float
    mean_tax: float
    mean_cash_end: float
    mean_units_sold: float
    mean_units_lost: float
    mean_stockout_months: float
    mean_end_stock: float
    mean_inventory_value: float
    mean_profit_margin: float
    cash_negative_probability: float | None = None
    mean_min_cash: float | None = None
    min_cash_p10: float | None = None
    min_cash_p50: float | None = None
    min_cash_p90: float | None = None
    financing_need_p50: float | None = None
    financing_need_p90: float | None = None
    break_even_probability: float | None = None
    median_break_even_month: int | None = None
    min_cash_cdf: list[CashCdfPoint] | None = None


class HistogramBin(CamelModel):
    lower: float
    upper: float
    count: int
    probability: float


class Histogram(CamelModel):
    bins: list[HistogramBin]


class MonthlyAverage(CamelModel):
    index: int
    month: int
    mean_revenue: float
    mean_profit: float
    mean_demand: float
    mean_units_sold: float
    mean_stock_end: float
    stockout_probability: float
    profit_p10: float | None = None
    profit_p50: float | None = None
    profit_p90: float | None = None
    cash_p10: float | None = None
    cash_p50: float | None = None
    cash_p90: float | None = None
    break_even_probability: float | None = None
    profit_histogram: list[HistogramBin] | None = None
    cash_histogram: list[HistogramBin] | None = None


class MonthlyAverages(CamelModel):
    values: list[MonthlyAverage]


class ConvergenceState(CamelModel):
    """Stabilité observée du calcul, jamais une garantie de précision.

    ``stable_blocks`` compte les transitions de bloc consécutives dont la
    variation relative est restée sous le seuil. ``stability`` est une valeur
    d'affichage entre 0 (instable) et 1 (parfaitement stable sur le dernier
    bloc) ; elle ne doit pas être présentée comme un pourcentage de précision.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    converged: bool
    stability: float = Field(ge=0.0, le=1.0)
    max_relative_change: float = Field(ge=0.0)
    stable_blocks: int = Field(ge=0)


class SensitivityEntry(CamelModel):
    hypothesis: str
    correlation: float
    contribution: float


class BreakEven(CamelModel):
    monthly_fixed_costs: float
    unit_margin: float
    break_even_units_monthly: float | None
    break_even_revenue_monthly: float | None


class SimulationResult(CamelModel):
    run_id: str
    engine_version: str
    scenario_name: str
    model: str
    currency: str
    horizon_months: int
    runs: int
    runs_retained: int | None = None
    seed: int
    duration_ms: float
    metrics: Metrics
    histogram: Histogram
    monthly: MonthlyAverages
    sensitivity: list[SensitivityEntry]
    break_even: BreakEven
    approximations: list[str] | None = None
    quality: Quality | None = None
    convergence: ConvergenceState | None = None

    _run_sample: RunSample | None = PrivateAttr(default=None)

    @property
    def run_sample(self) -> RunSample | None:
        """Échantillon interne (non sérialisé) des premiers runs."""
        return self._run_sample

    def attach_sample(self, sample: RunSample) -> None:
        self._run_sample = sample

    def detach_sample(self) -> None:
        """Libère l'échantillon tout en conservant les agrégats du résultat."""
        self._run_sample = None

    def __repr_args__(self):  # type: ignore[no-untyped-def]
        for name, value in super().__repr_args__():
            if name != "run_sample":
                yield name, value

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)
