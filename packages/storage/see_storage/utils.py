from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import StorageValidationError


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def new_id() -> str:
    return uuid.uuid4().hex


def to_camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def camelize(value: Any) -> Any:
    if isinstance(value, dict):
        return {to_camel(str(key)): camelize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [camelize(item) for item in value]
    return value


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_loads(raw: str | None, default: Any = None) -> Any:
    if raw is None or raw == "":
        return default
    return json.loads(raw)


def safe_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise StorageValidationError(f"chemin de résultat invalide: {value!r}")
    path = PurePosixPath(value)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or ":" in path.parts[0]
    ):
        raise StorageValidationError(f"chemin de résultat interdit: {value}")
    return path.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_text(value: object, field: str, *, max_length: int = 200) -> str:
    if not isinstance(value, str):
        raise StorageValidationError(f"{field} doit être une chaîne")
    cleaned = value.strip()
    if not cleaned:
        raise StorageValidationError(f"{field} ne peut pas être vide")
    if len(cleaned) > max_length:
        raise StorageValidationError(f"{field} dépasse {max_length} caractères")
    return cleaned
