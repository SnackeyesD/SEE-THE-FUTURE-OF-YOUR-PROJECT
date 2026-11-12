from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from see_storage import ProjectStore, StorageValidationError

from sidecar.benchmark_service import BenchmarkService, bundled_benchmark_dir


def _pack(name: str) -> Path:
    return bundled_benchmark_dir() / "packs" / name


def test_lookup_reads_a_signed_bundled_pack(tmp_path: Path) -> None:
    service = BenchmarkService(user_dir=tmp_path / "user")
    result = service.lookup(
        {
            "indicator": "unit_price",
            "country": "CG",
            "region": "Brazzaville",
            "sector": "retail",
            "subsector": "alimentation_generale",
        }
    )
    assert result["found"] is True
    record = result["record"]
    assert record["value"] == pytest.approx(13850)
    assert record["keyId"] == "seefuture-benchmark-2026"
    assert record["packId"] == "cg-brazzaville-retail-2026.1"
    assert record["freshness"] == "fresh"


def test_list_packs_reports_verified_bundled_packs(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "data")
    service = BenchmarkService(user_dir=tmp_path / "user")
    result = service.list_packs(store)
    assert result["errors"] == []
    statuses = {(pack["packId"], pack["status"]) for pack in result["packs"]}
    assert ("cg-brazzaville-retail-2026.1", "verified") in statuses
    assert ("cf-bangui-retail-2026.1", "verified") in statuses


def test_import_verifies_signature_and_records_metadata(tmp_path: Path) -> None:
    source = _pack("cg-brazzaville-retail-2026.1.json")
    copied = tmp_path / source.name
    shutil.copy2(source, copied)
    shutil.copy2(Path(str(source) + ".sig"), Path(str(copied) + ".sig"))
    store = ProjectStore(tmp_path / "data")
    service = BenchmarkService(user_dir=tmp_path / "imported")

    result = service.import_pack(store, str(copied))

    assert result["replaced"] is False
    assert result["pack"]["status"] == "verified"
    record = store.benchmark_packs.get("Brazzaville — alimentation générale 2026.1", "2026.1")
    assert record is not None
    assert record.key_id == "seefuture-benchmark-2026"
    assert record.status == "active"
    events = store.benchmark_pack_events.list()
    assert events[-1].action == "installed"


def test_import_rejects_tampered_pack(tmp_path: Path) -> None:
    source = _pack("cg-brazzaville-retail-2026.1.json")
    copied = tmp_path / source.name
    data = source.read_bytes()
    copied.write_bytes(data.replace(b"13850", b"13851", 1))
    shutil.copy2(Path(str(source) + ".sig"), Path(str(copied) + ".sig"))
    store = ProjectStore(tmp_path / "data")
    service = BenchmarkService(user_dir=tmp_path / "imported")

    with pytest.raises(StorageValidationError):
        service.import_pack(store, str(copied))
