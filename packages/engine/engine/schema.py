"""Primitives de schéma partagées par le scénario et les événements.

Ce module ne dépend que de Pydantic. Il isole les objets communs au scénario,
aux événements et aux transformations de tirages, afin que ``scenario`` puisse
importer ``events`` sans créer de cycle d'import.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
DistributionKind = Literal[
    "normal", "lognormal", "triangular", "uniform", "poisson", "empirical"
]


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
