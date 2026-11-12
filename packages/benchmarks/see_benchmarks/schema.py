from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PACK_SCHEMA_VERSION = "1.0.0"
DEFAULT_FRESH_DAYS = 365
DEFAULT_AGING_DAYS = 365 * 3

Reliability = Literal["official", "study", "field", "estimate"]
Freshness = Literal["fresh", "aging", "stale"]
Fallback = Literal["none", "country", "regional", "global"]

RELIABILITY_RANK: dict[str, int] = {
    "official": 4,
    "study": 3,
    "field": 2,
    "estimate": 1,
}

RELIABILITY_CONFIDENCE: dict[str, float] = {
    "official": 0.9,
    "study": 0.8,
    "field": 0.7,
    "estimate": 0.45,
}

COUNTRY_PATTERN = re.compile(r"^(?:[A-Z]{2}|GLOBAL)$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
INDICATOR_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,80}$")
PACK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,100}$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+$")
KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,80}$")


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


def _finite(value: float, field: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{field} doit être fini")
    return value


class ReferenceBasketComponent(CamelModel):
    item: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("quantity")
    @classmethod
    def quantity_is_finite(cls, value: float) -> float:
        return _finite(value, "quantity")


class ReferenceBasket(CamelModel):
    label: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=80)
    components: list[ReferenceBasketComponent] = Field(min_length=1)


class BenchmarkValue(CamelModel):
    indicator: str
    value: float
    unit: str = Field(min_length=1, max_length=80)
    currency: str
    country: str
    region: str | None = Field(default=None, max_length=120)
    region_group: str | None = Field(default=None, max_length=120)
    sector: str = Field(min_length=1, max_length=80)
    subsector: str | None = Field(default=None, max_length=80)
    source: str = Field(min_length=1, max_length=300)
    source_url: str = Field(min_length=1, max_length=1000)
    source_date: date
    reliability: Reliability
    min: float | None = None
    max: float | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("indicator")
    @classmethod
    def indicator_is_canonical(cls, value: str) -> str:
        cleaned = value.strip()
        if not INDICATOR_PATTERN.match(cleaned):
            raise ValueError("indicator doit être en snake_case minuscule")
        return cleaned

    @field_validator("country")
    @classmethod
    def country_is_canonical(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not COUNTRY_PATTERN.match(cleaned):
            raise ValueError("country doit être un code ISO 3166-1 alpha-2 ou GLOBAL")
        return cleaned

    @field_validator("currency")
    @classmethod
    def currency_is_canonical(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not CURRENCY_PATTERN.match(cleaned):
            raise ValueError("currency doit être un code ISO 4217")
        return cleaned

    @field_validator("sector", "subsector")
    @classmethod
    def sector_is_canonical(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()

    @field_validator("source_url")
    @classmethod
    def source_url_is_http(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith(("https://", "http://")):
            raise ValueError("sourceUrl doit commencer par http:// ou https://")
        return cleaned

    @field_validator("value", "min", "max")
    @classmethod
    def numbers_are_finite(cls, value: float | None) -> float | None:
        return None if value is None else _finite(value, "valeur")

    @model_validator(mode="after")
    def interval_is_consistent(self) -> BenchmarkValue:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min doit être inférieur ou égal à max")
        if self.min is not None and self.value < self.min:
            raise ValueError("value doit être supérieur ou égal à min")
        if self.max is not None and self.value > self.max:
            raise ValueError("value doit être inférieur ou égal à max")
        return self


class BenchmarkPack(CamelModel):
    schema_version: Literal["1.0.0"] = PACK_SCHEMA_VERSION
    id: str
    name: str = Field(min_length=1, max_length=200)
    version: str
    published_at: date
    country: str
    region: str | None = Field(default=None, max_length=120)
    region_group: str | None = Field(default=None, max_length=120)
    currency: str
    sector: str = Field(min_length=1, max_length=80)
    subsector: str | None = Field(default=None, max_length=80)
    publisher: str = Field(min_length=1, max_length=200)
    license: str = Field(min_length=1, max_length=120)
    reference_basket: ReferenceBasket | None = None
    notes: str | None = Field(default=None, max_length=4000)
    values: list[BenchmarkValue] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def id_is_canonical(cls, value: str) -> str:
        cleaned = value.strip()
        if not PACK_ID_PATTERN.match(cleaned):
            raise ValueError("id de pack invalide")
        return cleaned

    @field_validator("version")
    @classmethod
    def version_is_canonical(cls, value: str) -> str:
        cleaned = value.strip()
        if not VERSION_PATTERN.match(cleaned):
            raise ValueError("version doit ressembler à 2026.1")
        return cleaned

    @field_validator("country")
    @classmethod
    def country_is_canonical(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not COUNTRY_PATTERN.match(cleaned):
            raise ValueError("country doit être un code ISO 3166-1 alpha-2 ou GLOBAL")
        return cleaned

    @field_validator("currency")
    @classmethod
    def currency_is_canonical(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not CURRENCY_PATTERN.match(cleaned):
            raise ValueError("currency doit être un code ISO 4217")
        return cleaned

    @field_validator("sector", "subsector")
    @classmethod
    def sector_is_canonical(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()

    @model_validator(mode="after")
    def values_are_unique(self) -> BenchmarkPack:
        seen: set[tuple[str, str, str | None, str, str | None]] = set()
        for value in self.values:
            key = (
                value.indicator,
                value.country,
                value.region,
                value.sector,
                value.subsector,
            )
            if key in seen:
                raise ValueError(f"indicateur dupliqué dans le pack: {value.indicator}")
            seen.add(key)
        return self


class PublicKey(CamelModel):
    key_id: str
    algorithm: Literal["ed25519"] = "ed25519"
    public_key: str = Field(min_length=1, max_length=200)
    status: Literal["active", "retired"] = "active"
    created_at: date

    @field_validator("key_id")
    @classmethod
    def key_id_is_canonical(cls, value: str) -> str:
        cleaned = value.strip()
        if not KEY_ID_PATTERN.match(cleaned):
            raise ValueError("keyId invalide")
        return cleaned


class PublicKeySet(CamelModel):
    schema_version: Literal["1.0.0"] = PACK_SCHEMA_VERSION
    keys: list[PublicKey] = Field(min_length=1)

    @model_validator(mode="after")
    def key_ids_are_unique(self) -> PublicKeySet:
        seen: set[str] = set()
        for key in self.keys:
            if key.key_id in seen:
                raise ValueError(f"clé dupliquée: {key.key_id}")
            seen.add(key.key_id)
        return self


class SignatureEnvelope(CamelModel):
    schema_version: Literal["1.0.0"] = PACK_SCHEMA_VERSION
    algorithm: Literal["ed25519"] = "ed25519"
    key_id: str
    value: str = Field(min_length=1, max_length=200)


class BenchmarkQuery(CamelModel):
    indicator: str
    country: str | None = None
    region: str | None = Field(default=None, max_length=120)
    sector: str | None = Field(default=None, max_length=80)
    subsector: str | None = Field(default=None, max_length=80)
    as_of: date | None = None
    from_date: date | None = None
    to_date: date | None = None
    allow_fallback: bool = True

    @field_validator("indicator")
    @classmethod
    def indicator_is_canonical(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not INDICATOR_PATTERN.match(cleaned):
            raise ValueError("indicator doit être en snake_case minuscule")
        return cleaned

    @field_validator("country")
    @classmethod
    def country_is_optional_canonical(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if not COUNTRY_PATTERN.match(cleaned):
            raise ValueError("country doit être un code ISO 3166-1 alpha-2 ou GLOBAL")
        return cleaned

    @field_validator("sector", "subsector")
    @classmethod
    def sector_is_optional_canonical(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()


class BenchmarkRecord(CamelModel):
    indicator: str
    value: float
    unit: str
    currency: str
    country: str
    region: str | None = None
    region_group: str | None = None
    sector: str
    subsector: str | None = None
    source: str
    source_url: str
    source_date: date
    reliability: Reliability
    freshness: Freshness
    min: float | None = None
    max: float | None = None
    notes: str | None = None
    pack_id: str
    pack_version: str
    pack_published_at: date
    key_id: str
    checksum: str
    fallback: Fallback = "none"
    conflicts: int = 0


class BenchmarkLookupResult(CamelModel):
    found: bool
    record: BenchmarkRecord | None = None
    reason: str | None = None


class BenchmarkPackInfo(CamelModel):
    pack_id: str
    name: str
    version: str
    published_at: date
    country: str
    region: str | None = None
    currency: str
    sector: str
    subsector: str | None = None
    value_count: int
    checksum: str
    key_id: str
    status: Literal["verified", "invalid", "unverified"]
    source: Literal["bundled", "user", "imported"]
    path: str | None = None
    error: str | None = None


class BenchmarkPackListResult(CamelModel):
    packs: list[BenchmarkPackInfo]
    errors: list[str] = Field(default_factory=list)


class BenchmarkPackImportParams(CamelModel):
    path: str = Field(min_length=1, max_length=2000)


class BenchmarkPackImportResult(CamelModel):
    pack: BenchmarkPackInfo
    replaced: bool = False


def freshness_for(source_date: date, as_of: date | None = None) -> Freshness:
    reference = as_of or date.today()
    age_days = (reference - source_date).days
    if age_days <= DEFAULT_FRESH_DAYS:
        return "fresh"
    if age_days <= DEFAULT_AGING_DAYS:
        return "aging"
    return "stale"


def confidence_for(reliability: Reliability) -> float:
    return RELIABILITY_CONFIDENCE[reliability]


def pack_to_dict(pack: BenchmarkPack) -> dict[str, Any]:
    return pack.model_dump(by_alias=True, mode="json")
