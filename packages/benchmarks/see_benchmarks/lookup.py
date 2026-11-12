from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .schema import (
    RELIABILITY_RANK,
    BenchmarkLookupResult,
    BenchmarkQuery,
    BenchmarkRecord,
    BenchmarkValue,
    Fallback,
    freshness_for,
)

if TYPE_CHECKING:
    from .loader import LoadedPack


@dataclass(frozen=True, slots=True)
class Candidate:
    loaded: LoadedPack
    value: BenchmarkValue
    geography: int
    fallback: Fallback


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _matches_geography(
    query: BenchmarkQuery,
    value: BenchmarkValue,
) -> tuple[int, Fallback] | None:
    if value.country == "GLOBAL":
        if not query.allow_fallback:
            return None
        return 0, "global"
    if query.country is not None and value.country != query.country:
        return None
    if query.region is not None:
        if value.region == query.region:
            return 4, "none"
        if value.region is None:
            if not query.allow_fallback:
                return None
            return 2, "country"
        return None
    return 2, "none"


def _matches_sector(query: BenchmarkQuery, value: BenchmarkValue) -> bool:
    if query.sector is not None and value.sector != query.sector:
        return False
    if query.subsector is not None:
        if value.subsector is None:
            return bool(query.allow_fallback)
        return value.subsector == query.subsector
    return True


def _matches_dates(query: BenchmarkQuery, value: BenchmarkValue) -> bool:
    if query.from_date is not None and value.source_date < query.from_date:
        return False
    if query.to_date is not None and value.source_date > query.to_date:
        return False
    return True


def lookup_packs(
    packs: tuple[LoadedPack, ...],
    query: BenchmarkQuery,
) -> BenchmarkLookupResult:
    if not packs:
        return BenchmarkLookupResult(
            found=False,
            reason="aucun pack de benchmarks signé n'est disponible",
        )

    candidates: list[Candidate] = []
    indicator_present = False
    for loaded in packs:
        for value in loaded.pack.values:
            if value.indicator != query.indicator:
                continue
            indicator_present = True
            geography = _matches_geography(query, value)
            if geography is None:
                continue
            if not _matches_sector(query, value):
                continue
            if not _matches_dates(query, value):
                continue
            rank, fallback = geography
            candidates.append(
                Candidate(
                    loaded=loaded,
                    value=value,
                    geography=rank,
                    fallback=fallback,
                )
            )

    if not candidates:
        if not indicator_present:
            return BenchmarkLookupResult(
                found=False,
                reason=f"indicateur absent des packs signés: {query.indicator}",
            )
        return BenchmarkLookupResult(
            found=False,
            reason="aucune valeur ne correspond au pays, secteur ou à la période demandés",
        )

    candidates.sort(
        key=lambda candidate: (
            -candidate.loaded.pack.published_at.toordinal(),
            -RELIABILITY_RANK[candidate.value.reliability],
            -candidate.geography,
            -candidate.value.source_date.toordinal(),
            tuple(-part for part in _version_key(candidate.loaded.pack.version)),
            candidate.loaded.pack.id,
            candidate.value.indicator,
        )
    )
    best = candidates[0]
    value = best.value
    record = BenchmarkRecord(
        indicator=value.indicator,
        value=value.value,
        unit=value.unit,
        currency=value.currency,
        country=value.country,
        region=value.region,
        region_group=value.region_group,
        sector=value.sector,
        subsector=value.subsector,
        source=value.source,
        source_url=value.source_url,
        source_date=value.source_date,
        reliability=value.reliability,
        freshness=freshness_for(value.source_date, query.as_of),
        min=value.min,
        max=value.max,
        notes=value.notes,
        pack_id=best.loaded.pack.id,
        pack_version=best.loaded.pack.version,
        pack_published_at=best.loaded.pack.published_at,
        key_id=best.loaded.key_id,
        checksum=best.loaded.checksum,
        fallback=best.fallback,
        conflicts=max(0, len(candidates) - 1),
    )
    return BenchmarkLookupResult(found=True, record=record)
