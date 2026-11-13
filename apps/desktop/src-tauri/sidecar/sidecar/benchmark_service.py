from __future__ import annotations

import os
import shutil
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from see_benchmarks import (
    SIGNATURE_SUFFIX,
    BenchmarkCatalog,
    BenchmarkPack,
    BenchmarkPackImportResult,
    BenchmarkPackInfo,
    BenchmarkPackListResult,
    BenchmarkPackLoader,
    BenchmarkQuery,
    BenchmarkRecord,
    PackRoot,
    checksum_bytes,
    load_public_key_set,
    load_signature,
    verify_bytes,
)
from see_benchmarks.errors import BenchmarkError
from see_storage import ProjectStore, StorageValidationError, default_data_dir

MAX_PACK_BYTES = 10 * 1024 * 1024


def bundled_benchmark_dir() -> Path:
    override = os.environ.get("SEE_BENCHMARK_DIR")
    if override:
        return Path(override).expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "data" / "benchmark-packs"


def user_benchmark_dir() -> Path:
    override = os.environ.get("SEE_BENCHMARK_USER_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return default_data_dir() / "benchmark-packs"


class BenchmarkService:
    def __init__(
        self,
        *,
        bundled_dir: Path | None = None,
        user_dir: Path | None = None,
    ) -> None:
        self.bundled_dir = (bundled_dir or bundled_benchmark_dir()).resolve()
        self.user_dir = (user_dir or user_benchmark_dir()).resolve()

    def _roots(self) -> list[PackRoot]:
        roots: list[PackRoot] = []
        if self.user_dir.is_dir():
            roots.append(PackRoot(self.user_dir, "user"))
        roots.append(PackRoot(self.bundled_dir, "bundled"))
        return roots

    def _key_set_path(self) -> Path | None:
        for directory in (self.bundled_dir, self.user_dir):
            candidate = directory / "keys" / "public.json"
            if candidate.is_file():
                return candidate
        return None

    def catalog(self) -> BenchmarkCatalog:
        return BenchmarkPackLoader(
            self._roots(),
            key_set_path=self._key_set_path(),
        ).load()

    def indicator_names(self) -> list[str]:
        return sorted(
            {
                value.indicator
                for loaded in self.catalog().packs
                for value in loaded.pack.values
            }
        )

    def lookup(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            query = BenchmarkQuery.model_validate(params)
        except ValidationError as error:
            raise StorageValidationError(
                f"requête benchmark invalide: {error.errors(include_url=False)}"
            ) from error
        try:
            result = self.catalog().lookup(query)
        except BenchmarkError as error:
            raise StorageValidationError(str(error)) from error
        return result.model_dump(by_alias=True, mode="json")

    def list_packs(self, store: ProjectStore) -> dict[str, Any]:
        catalog = self.catalog()
        infos = catalog.infos()
        known = {(info.pack_id, info.version) for info in infos}
        for record in store.benchmark_packs.list():
            identity = (record.pack_id or record.name, record.version)
            if identity in known:
                continue
            infos.append(
                BenchmarkPackInfo(
                    pack_id=record.pack_id or record.name,
                    name=record.name,
                    version=record.version,
                    published_at=date.fromisoformat(record.published_at)
                    if record.published_at
                    else date.today(),
                    country=record.country or "GLOBAL",
                    region=record.region,
                    currency="XAF",
                    sector=record.sector or "retail",
                    subsector=record.subsector,
                    value_count=record.value_count,
                    checksum=record.checksum,
                    key_id=record.key_id or "",
                    status="invalid" if record.status == "invalid" else "unverified",
                    source="imported",
                    path=record.path,
                    error=record.error,
                )
            )
        result = BenchmarkPackListResult(packs=infos, errors=list(catalog.errors))
        return result.model_dump(by_alias=True, mode="json")

    def import_pack(self, store: ProjectStore, path_value: str) -> dict[str, Any]:
        source = Path(path_value).expanduser().resolve()
        if not source.is_file():
            raise StorageValidationError("le pack à importer est introuvable")
        if source.suffix.lower() != ".json":
            raise StorageValidationError("le pack doit être un fichier .json")
        if source.stat().st_size > MAX_PACK_BYTES:
            raise StorageValidationError("le pack dépasse la taille maximale de 10 Mo")
        signature_path = Path(str(source) + SIGNATURE_SUFFIX)
        if not signature_path.is_file():
            raise StorageValidationError("signature détachée absente (.sig)")
        if signature_path.stat().st_size > MAX_PACK_BYTES:
            raise StorageValidationError("la signature dépasse la taille maximale de 10 Mo")

        key_path = self._key_set_path()
        if key_path is None:
            raise StorageValidationError("jeu de clés publiques introuvable")
        data = source.read_bytes()
        try:
            key_set = load_public_key_set(key_path)
            envelope = load_signature(signature_path)
            key_id = verify_bytes(data, envelope, key_set)
        except BenchmarkError as error:
            raise StorageValidationError(str(error)) from error
        try:
            pack = BenchmarkPack.model_validate_json(data)
        except ValidationError as error:
            raise StorageValidationError(
                f"pack invalide: {error.errors(include_url=False)}"
            ) from error

        destination_dir = self.user_dir / "packs"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source.name
        signature_destination = Path(str(destination) + SIGNATURE_SUFFIX)
        replaced = destination.exists()
        _atomic_copy(source, destination)
        _atomic_copy(signature_path, signature_destination)

        checksum = checksum_bytes(data)
        installed_at = datetime.now(UTC).isoformat()
        previous = store.benchmark_packs.get(pack.name, pack.version)
        store.benchmark_packs.add(
            pack.name,
            pack.version,
            str(destination),
            checksum,
            source="imported",
            pack_id=pack.id,
            published_at=pack.published_at.isoformat(),
            installed_at=installed_at,
            signature=envelope.value,
            key_id=key_id,
            status="active",
            country=pack.country,
            region=pack.region,
            sector=pack.sector,
            subsector=pack.subsector,
            value_count=len(pack.values),
        )
        store.benchmark_pack_events.add(
            pack.name,
            pack.version,
            "replaced" if previous is not None else "installed",
            pack_id=pack.id,
            checksum=checksum,
            key_id=key_id,
        )
        info = BenchmarkPackInfo(
            pack_id=pack.id,
            name=pack.name,
            version=pack.version,
            published_at=pack.published_at,
            country=pack.country,
            region=pack.region,
            currency=pack.currency,
            sector=pack.sector,
            subsector=pack.subsector,
            value_count=len(pack.values),
            checksum=checksum,
            key_id=key_id,
            status="verified",
            source="imported",
            path=str(destination),
        )
        return BenchmarkPackImportResult(pack=info, replaced=replaced).model_dump(
            by_alias=True, mode="json"
        )

    def record_lookup(self, params: dict[str, Any]) -> BenchmarkRecord | None:
        result = self.lookup(params)
        record = result.get("record")
        if record is None:
            return None
        return BenchmarkRecord.model_validate(record)


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


_service: BenchmarkService | None = None


def get_service() -> BenchmarkService:
    global _service
    if _service is None:
        _service = BenchmarkService()
    return _service


def reset_service() -> None:
    global _service
    _service = None


__all__ = [
    "BenchmarkError",
    "BenchmarkService",
    "MAX_PACK_BYTES",
    "bundled_benchmark_dir",
    "get_service",
    "reset_service",
    "user_benchmark_dir",
]
