from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from .errors import SignatureMissingError
from .lookup import lookup_packs
from .schema import (
    BenchmarkLookupResult,
    BenchmarkPack,
    BenchmarkPackInfo,
    BenchmarkQuery,
    PublicKeySet,
    SignatureEnvelope,
)
from .signing import (
    SIGNATURE_SUFFIX,
    checksum_bytes,
    load_public_key_set,
    load_signature,
    verify_bytes,
)

PackSource = Literal["bundled", "user", "imported"]


@dataclass(frozen=True, slots=True)
class PackRoot:
    path: Path
    source: PackSource = "bundled"


@dataclass(frozen=True, slots=True)
class LoadedPack:
    pack: BenchmarkPack
    path: Path
    checksum: str
    key_id: str
    source: PackSource


@dataclass(frozen=True, slots=True)
class BenchmarkCatalog:
    packs: tuple[LoadedPack, ...]
    errors: tuple[str, ...]
    key_set: PublicKeySet | None

    @property
    def verified_count(self) -> int:
        return len(self.packs)

    def lookup(self, query: BenchmarkQuery) -> BenchmarkLookupResult:
        return lookup_packs(self.packs, query)

    def infos(self) -> list[BenchmarkPackInfo]:
        infos = [
            BenchmarkPackInfo(
                pack_id=loaded.pack.id,
                name=loaded.pack.name,
                version=loaded.pack.version,
                published_at=loaded.pack.published_at,
                country=loaded.pack.country,
                region=loaded.pack.region,
                currency=loaded.pack.currency,
                sector=loaded.pack.sector,
                subsector=loaded.pack.subsector,
                value_count=len(loaded.pack.values),
                checksum=loaded.checksum,
                key_id=loaded.key_id,
                status="verified",
                source=loaded.source,
                path=str(loaded.path),
            )
            for loaded in self.packs
        ]
        for error in self.errors:
            infos.append(
                BenchmarkPackInfo(
                    pack_id="invalid",
                    name="Pack refusé",
                    version="0.0",
                    published_at=date.today(),
                    country="GLOBAL",
                    currency="XAF",
                    sector="retail",
                    value_count=0,
                    checksum="",
                    key_id="",
                    status="invalid",
                    source="bundled",
                    error=error,
                )
            )
        return infos


class BenchmarkPackLoader:
    def __init__(
        self,
        roots: list[PackRoot],
        *,
        key_set_path: Path | None = None,
        require_signature: bool = True,
    ) -> None:
        self.roots = roots
        self.key_set_path = key_set_path
        self.require_signature = require_signature

    def _key_path(self) -> Path | None:
        if self.key_set_path is not None:
            return self.key_set_path
        for root in self.roots:
            candidate = root.path / "keys" / "public.json"
            if candidate.is_file():
                return candidate
        return None

    def load(self) -> BenchmarkCatalog:
        errors: list[str] = []
        key_set: PublicKeySet | None = None
        key_path = self._key_path()
        if self.require_signature:
            if key_path is None or not key_path.is_file():
                return BenchmarkCatalog(
                    packs=(),
                    errors=("jeu de clés publiques introuvable",),
                    key_set=None,
                )
            try:
                key_set = load_public_key_set(key_path)
            except Exception as error:  # noqa: BLE001 - domaine
                return BenchmarkCatalog(
                    packs=(),
                    errors=(str(error),),
                    key_set=None,
                )

        loaded: list[LoadedPack] = []
        seen: set[tuple[str, str]] = set()
        for root in self.roots:
            packs_dir = root.path / "packs" if (root.path / "packs").is_dir() else root.path
            if not packs_dir.is_dir():
                continue
            for path in sorted(packs_dir.glob("*.json")):
                if path.name.endswith(SIGNATURE_SUFFIX):
                    continue
                try:
                    pack, checksum, key_id = self._load_one(path, key_set)
                except Exception as error:  # noqa: BLE001 - agrégation d'erreurs
                    errors.append(f"{path.name}: {error}")
                    continue
                identity = (pack.id, pack.version)
                if identity in seen:
                    errors.append(
                        f"{path.name}: pack déjà chargé ({pack.id} {pack.version})"
                    )
                    continue
                seen.add(identity)
                loaded.append(
                    LoadedPack(
                        pack=pack,
                        path=path,
                        checksum=checksum,
                        key_id=key_id,
                        source=root.source,
                    )
                )
        return BenchmarkCatalog(
            packs=tuple(loaded),
            errors=tuple(errors),
            key_set=key_set,
        )

    def _load_one(
        self,
        path: Path,
        key_set: PublicKeySet | None,
    ) -> tuple[BenchmarkPack, str, str]:
        data = path.read_bytes()
        signature_path = Path(str(path) + SIGNATURE_SUFFIX)
        key_id = ""
        if self.require_signature:
            if key_set is None:
                raise SignatureMissingError("jeu de clés publiques absent")
            if not signature_path.is_file():
                raise SignatureMissingError("signature détachée absente")
            envelope: SignatureEnvelope = load_signature(signature_path)
            key_id = verify_bytes(data, envelope, key_set)
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as error:
            raise ValueError(f"JSON invalide: {error.msg}") from error
        if not isinstance(payload, dict):
            raise ValueError("le pack doit être un objet JSON")
        try:
            pack = BenchmarkPack.model_validate(payload)
        except ValidationError as error:
            details = "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                for item in error.errors(include_url=False)
            )
            raise ValueError(f"pack invalide: {details}") from error
        if not key_id:
            key_id = "unsigned"
        return pack, checksum_bytes(data), key_id


def load_catalog(
    roots: list[PackRoot],
    *,
    key_set_path: Path | None = None,
    require_signature: bool = True,
) -> BenchmarkCatalog:
    return BenchmarkPackLoader(
        roots,
        key_set_path=key_set_path,
        require_signature=require_signature,
    ).load()
