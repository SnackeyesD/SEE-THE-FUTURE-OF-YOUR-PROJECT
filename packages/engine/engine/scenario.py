from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
DistributionKind = Literal["normal", "lognormal", "triangular", "uniform", "poisson", "empirical"]
ModelName = Literal["retail_depot"]

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def to_camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class DistributionSpec(CamelModel):
    kind: DistributionKind
    mean: FiniteFloat | None = None
    std: FiniteFloat | None = None
    sigma: FiniteFloat | None = None
    low: FiniteFloat | None = None
    mode: FiniteFloat | None = None
    high: FiniteFloat | None = None
    values: list[FiniteFloat] | None = None
    weights: list[FiniteFloat] | None = None

    @model_validator(mode="after")
    def _check_parameters(self) -> DistributionSpec:
        kind = self.kind
        if kind == "normal":
            if self.mean is None or self.std is None:
                raise ValueError("distribution normale: 'mean' et 'std' sont requis")
            if self.std <= 0:
                raise ValueError("distribution normale: 'std' doit être strictement positif")
        elif kind == "lognormal":
            if self.mean is None or self.sigma is None:
                raise ValueError("distribution lognormale: 'mean' et 'sigma' sont requis")
            if self.sigma <= 0:
                raise ValueError("distribution lognormale: 'sigma' doit être strictement positif")
        elif kind == "triangular":
            if self.low is None or self.mode is None or self.high is None:
                raise ValueError("distribution triangulaire: 'low', 'mode' et 'high' sont requis")
            if not self.low <= self.mode <= self.high:
                raise ValueError("distribution triangulaire: low <= mode <= high est requis")
            if self.low == self.high:
                raise ValueError("distribution triangulaire: low et high doivent différer")
        elif kind == "uniform":
            if self.low is None or self.high is None:
                raise ValueError("distribution uniforme: 'low' et 'high' sont requis")
            if self.low >= self.high:
                raise ValueError(
                    "distribution uniforme: low doit être strictement inférieur à high"
                )
        elif kind == "poisson":
            if self.mean is None:
                raise ValueError("distribution de Poisson: 'mean' est requis")
            if self.mean <= 0:
                raise ValueError("distribution de Poisson: 'mean' doit être strictement positif")
        elif kind == "empirical":
            if not self.values:
                raise ValueError("distribution empirique: 'values' doit être non vide")
            if self.weights is not None:
                if len(self.weights) != len(self.values):
                    raise ValueError("distribution empirique: 'weights' doit avoir la même taille")
                if any(weight < 0 for weight in self.weights):
                    raise ValueError("distribution empirique: les poids doivent être positifs")
                if sum(self.weights) <= 0:
                    raise ValueError(
                        "distribution empirique: la somme des poids doit être positive"
                    )
        return self


class BenchmarkProvenance(CamelModel):
    kind: Literal["benchmark", "user"] = "user"
    label: str = Field(min_length=1, max_length=300)
    indicator: str | None = None
    source: str | None = None
    source_url: str | None = None
    source_date: str | None = None
    reliability: Literal["official", "study", "field", "estimate"] | None = None
    freshness: Literal["fresh", "aging", "stale"] | None = None
    pack_id: str | None = None
    pack_version: str | None = None
    pack_published_at: str | None = None
    key_id: str | None = None
    checksum: str | None = None
    fallback: Literal["none", "country", "regional", "global"] | None = None
    conflicts: int | None = Field(default=None, ge=0)


class Hypothesis(CamelModel):
    value: FiniteFloat
    distribution: DistributionSpec | None = None
    source: str | None = None
    confidence: FiniteFloat | None = Field(default=None, ge=0, le=1)
    min: FiniteFloat | None = None
    max: FiniteFloat | None = None
    description: str | None = None
    provenance: BenchmarkProvenance | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> Hypothesis:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("hypothèse: 'min' doit être inférieur ou égal à 'max'")
        return self


class Scenario(CamelModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    name: str = Field(min_length=1, max_length=200)
    model: ModelName = "retail_depot"
    currency: str = Field(default="XOF", min_length=1, max_length=8)
    horizon_months: int = Field(default=12, ge=1, le=120)
    assumptions: dict[str, Hypothesis] = Field(default_factory=dict)
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


class SimulationConfig(CamelModel):
    runs: int = Field(default=10_000, ge=1, le=1_000_000)
    seed: int = Field(default=42, ge=0, le=2**63 - 1)
    batch_size: int = Field(default=50_000, ge=1, le=1_000_000)
    histogram_bins: int = Field(default=40, ge=1, le=200)


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


class MonthlyAverages(CamelModel):
    values: list[MonthlyAverage]


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
    seed: int
    duration_ms: float
    metrics: Metrics
    histogram: Histogram
    monthly: MonthlyAverages
    sensitivity: list[SensitivityEntry]
    break_even: BreakEven

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)
