from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from see_benchmarks import (
    BenchmarkPackLoader,
    BenchmarkQuery,
    PackRoot,
    PublicKey,
    freshness_for,
    generate_keypair,
    load_catalog,
    sign_file,
    write_private_key,
    write_public_key_set,
)


def _pack_payload(
    *,
    pack_id: str = "cg-brazzaville-retail-test",
    version: str = "2026.1",
    published_at: str = "2026-01-10",
    source_date: str = "2026-01-05",
    country: str = "CG",
    region: str | None = "Brazzaville",
    value: float = 1250.0,
    reliability: str = "official",
    indicator: str = "unit_price",
) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "id": pack_id,
        "name": "Test Brazzaville",
        "version": version,
        "publishedAt": published_at,
        "country": country,
        "region": region,
        "regionGroup": "CEMAC",
        "currency": "XAF",
        "sector": "retail",
        "subsector": "alimentation_generale",
        "publisher": "See The Future",
        "license": "CC-BY-4.0",
        "referenceBasket": {
            "label": "Panier test",
            "unit": "panier",
            "components": [
                {"item": "Riz", "quantity": 1, "unit": "kg"},
            ],
        },
        "notes": "Fixture de test.",
        "values": [
            {
                "indicator": indicator,
                "value": value,
                "unit": "XAF/panier",
                "currency": "XAF",
                "country": country,
                "region": region,
                "regionGroup": "CEMAC",
                "sector": "retail",
                "subsector": "alimentation_generale",
                "source": "Source de test",
                "sourceUrl": "https://example.test/prices",
                "sourceDate": source_date,
                "reliability": reliability,
                "min": value * 0.9,
                "max": value * 1.1,
                "notes": "Valeur de test.",
            }
        ],
    }


def _write_pack(root: Path, payload: dict, private_key: Path) -> Path:
    packs = root / "packs"
    packs.mkdir(parents=True, exist_ok=True)
    path = packs / f"{payload['id']}-{payload['version']}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    sign_file(path, private_key)
    return path


@pytest.fixture
def signed_root(tmp_path: Path) -> tuple[Path, Path]:
    private_payload, public_key = generate_keypair("test-2026", created_at=date(2026, 1, 1))
    private_key = tmp_path / "private.json"
    write_private_key(private_key, private_payload)
    keys = tmp_path / "keys" / "public.json"
    write_public_key_set(keys, [public_key])
    root = tmp_path / "pack-root"
    _write_pack(root, _pack_payload(), private_key)
    return root, keys


def test_loads_and_verifies_signed_pack(signed_root: tuple[Path, Path]) -> None:
    root, keys = signed_root
    catalog = load_catalog([PackRoot(root)], key_set_path=keys)
    assert catalog.errors == ()
    assert catalog.verified_count == 1
    loaded = catalog.packs[0]
    assert loaded.pack.id == "cg-brazzaville-retail-test"
    assert loaded.key_id == "test-2026"
    assert len(loaded.checksum) == 64


def test_rejects_tampered_pack(signed_root: tuple[Path, Path]) -> None:
    root, keys = signed_root
    pack_path = next((root / "packs").glob("*.json"))
    pack_path.write_text(
        pack_path.read_text(encoding="utf-8").replace("1250.0", "9999.0"),
        encoding="utf-8",
    )
    catalog = load_catalog([PackRoot(root)], key_set_path=keys)
    assert catalog.verified_count == 0
    assert any("signature" in error.lower() for error in catalog.errors)


def test_rejects_missing_signature(signed_root: tuple[Path, Path]) -> None:
    root, keys = signed_root
    pack_path = next((root / "packs").glob("*.json"))
    Path(str(pack_path) + ".sig").unlink()
    catalog = load_catalog([PackRoot(root)], key_set_path=keys)
    assert catalog.verified_count == 0
    assert any("signature" in error.lower() for error in catalog.errors)


def test_rejects_retired_key(signed_root: tuple[Path, Path]) -> None:
    root, keys = signed_root
    private_payload, public_key = generate_keypair("old-2025", created_at=date(2025, 1, 1))
    write_public_key_set(
        keys,
        [
            PublicKey(
                key_id=public_key.key_id,
                public_key=public_key.public_key,
                status="retired",
                created_at=public_key.created_at,
            )
        ],
    )
    private_key = root.parent / "old-private.json"
    write_private_key(private_key, private_payload)
    _write_pack(root, _pack_payload(pack_id="cg-old-pack"), private_key)
    catalog = load_catalog([PackRoot(root)], key_set_path=keys)
    assert any("retirée" in error for error in catalog.errors)


def test_lookup_exact_and_fallback(signed_root: tuple[Path, Path]) -> None:
    root, keys = signed_root
    catalog = load_catalog([PackRoot(root)], key_set_path=keys)
    exact = catalog.lookup(
        BenchmarkQuery(
            indicator="unit_price",
            country="CG",
            region="Brazzaville",
            sector="retail",
            subsector="alimentation_generale",
            as_of=date(2026, 2, 1),
        )
    )
    assert exact.found
    assert exact.record is not None
    assert exact.record.fallback == "none"
    assert exact.record.freshness == "fresh"

    other_city = catalog.lookup(
        BenchmarkQuery(
            indicator="unit_price",
            country="CG",
            region="Pointe-Noire",
            sector="retail",
            subsector="alimentation_generale",
            as_of=date(2026, 2, 1),
        )
    )
    assert not other_city.found

    _write_pack(
        root / "country",
        _pack_payload(
            pack_id="cg-country-retail-test",
            region=None,
            value=1200.0,
        ),
        root.parent / "private.json",
    )
    catalog = load_catalog([PackRoot(root / "country"), PackRoot(root)], key_set_path=keys)
    fallback = catalog.lookup(
        BenchmarkQuery(
            indicator="unit_price",
            country="CG",
            region="Pointe-Noire",
            sector="retail",
            subsector="alimentation_generale",
            as_of=date(2026, 2, 1),
        )
    )
    assert fallback.found
    assert fallback.record is not None
    assert fallback.record.fallback == "country"


def test_lookup_prefers_recent_pack(signed_root: tuple[Path, Path]) -> None:
    root, keys = signed_root
    private_payload, public_key = generate_keypair("test-2026", created_at=date(2026, 1, 1))
    write_private_key(root.parent / "private-2.json", private_payload)
    write_public_key_set(keys, [public_key])
    original_pack = next((root / "packs").glob("*.json"))
    sign_file(original_pack, root.parent / "private-2.json")
    _write_pack(
        root / "second",
        _pack_payload(
            pack_id="cg-brazzaville-retail-new",
            published_at="2026-03-01",
            source_date="2026-02-20",
            value=1400.0,
        ),
        root.parent / "private-2.json",
    )
    catalog = load_catalog(
        [PackRoot(root / "second"), PackRoot(root)],
        key_set_path=keys,
    )
    result = catalog.lookup(
        BenchmarkQuery(
            indicator="unit_price",
            country="CG",
            region="Brazzaville",
            sector="retail",
            subsector="alimentation_generale",
            as_of=date(2026, 4, 1),
        )
    )
    assert result.found
    assert result.record is not None
    assert result.record.pack_id == "cg-brazzaville-retail-new"
    assert result.record.conflicts == 1


def test_freshness_thresholds() -> None:
    assert freshness_for(date(2025, 11, 1), date(2026, 1, 1)) == "fresh"
    assert freshness_for(date(2024, 1, 1), date(2026, 1, 1)) == "aging"
    assert freshness_for(date(2021, 1, 1), date(2026, 1, 1)) == "stale"


def test_requires_signature_by_default(signed_root: tuple[Path, Path]) -> None:
    root, _keys = signed_root
    catalog = BenchmarkPackLoader([PackRoot(root)], key_set_path=None).load()
    assert catalog.verified_count == 0
    assert any("clés" in error for error in catalog.errors)
