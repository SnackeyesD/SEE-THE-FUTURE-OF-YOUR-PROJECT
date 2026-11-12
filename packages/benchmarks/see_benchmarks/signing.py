from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .errors import (
    InvalidSignatureError,
    KeyRetiredError,
    SignatureError,
    UnknownKeyError,
)
from .schema import (
    PACK_SCHEMA_VERSION,
    PublicKey,
    PublicKeySet,
    SignatureEnvelope,
)

SIGNATURE_SUFFIX = ".sig"
PRIVATE_KEY_SCHEMA_VERSION = "1.0.0"


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checksum_file(path: Path) -> str:
    return checksum_bytes(path.read_bytes())


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(value: str, field: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as error:  # noqa: BLE001 - message de domaine
        raise SignatureError(f"{field} doit être du Base64 valide") from error


def generate_keypair(
    key_id: str,
    *,
    created_at: date | None = None,
) -> tuple[dict[str, Any], PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    raw_private = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    raw_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    created = created_at or date.today()
    private_payload = {
        "schemaVersion": PRIVATE_KEY_SCHEMA_VERSION,
        "algorithm": "ed25519",
        "keyId": key_id,
        "createdAt": created.isoformat(),
        "privateKey": _b64encode(raw_private),
    }
    public_key = PublicKey(
        key_id=key_id,
        public_key=_b64encode(raw_public),
        status="active",
        created_at=created,
    )
    return private_payload, public_key


def write_private_key(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def write_public_key_set(path: Path, keys: list[PublicKey]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = PublicKeySet(keys=keys)
    path.write_text(
        payload.model_dump_json(by_alias=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_private_key(path: Path) -> tuple[Ed25519PrivateKey, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SignatureError(f"clé privée illisible: {path}") from error
    if not isinstance(payload, dict):
        raise SignatureError("clé privée invalide")
    key_id = payload.get("keyId")
    encoded = payload.get("privateKey")
    algorithm = payload.get("algorithm", "ed25519")
    if algorithm != "ed25519":
        raise SignatureError(f"algorithme de clé non supporté: {algorithm}")
    if not isinstance(key_id, str) or not key_id:
        raise SignatureError("keyId absent de la clé privée")
    if not isinstance(encoded, str) or not encoded:
        raise SignatureError("privateKey absent de la clé privée")
    raw = _b64decode(encoded, "privateKey")
    try:
        private_key = Ed25519PrivateKey.from_private_bytes(raw)
    except ValueError as error:
        raise SignatureError("clé privée Ed25519 invalide") from error
    return private_key, key_id


def load_public_key_set(path: Path) -> PublicKeySet:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SignatureError(f"jeu de clés publiques illisible: {path}") from error
    try:
        return PublicKeySet.model_validate(payload)
    except Exception as error:  # noqa: BLE001 - normalisation Pydantic
        raise SignatureError(f"jeu de clés publiques invalide: {error}") from error


def _public_key_objects(key_set: PublicKeySet) -> dict[str, tuple[Ed25519PublicKey, PublicKey]]:
    result: dict[str, tuple[Ed25519PublicKey, PublicKey]] = {}
    for key in key_set.keys:
        raw = _b64decode(key.public_key, f"publicKey[{key.key_id}]")
        try:
            parsed = Ed25519PublicKey.from_public_bytes(raw)
        except ValueError as error:
            raise SignatureError(f"clé publique Ed25519 invalide: {key.key_id}") from error
        result[key.key_id] = (parsed, key)
    return result


def sign_bytes(
    data: bytes,
    private_key: Ed25519PrivateKey,
    key_id: str,
) -> SignatureEnvelope:
    signature = private_key.sign(data)
    return SignatureEnvelope(
        schema_version=PACK_SCHEMA_VERSION,
        key_id=key_id,
        value=_b64encode(signature),
    )


def sign_file(
    pack_path: Path,
    private_key_path: Path,
    *,
    signature_path: Path | None = None,
) -> SignatureEnvelope:
    private_key, key_id = load_private_key(private_key_path)
    envelope = sign_bytes(pack_path.read_bytes(), private_key, key_id)
    target = signature_path or Path(str(pack_path) + SIGNATURE_SUFFIX)
    target.write_text(
        envelope.model_dump_json(by_alias=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return envelope


def load_signature(path: Path) -> SignatureEnvelope:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SignatureError(f"signature illisible: {path}") from error
    try:
        return SignatureEnvelope.model_validate(payload)
    except Exception as error:  # noqa: BLE001 - normalisation Pydantic
        raise SignatureError(f"signature invalide: {error}") from error


def verify_bytes(
    data: bytes,
    envelope: SignatureEnvelope,
    key_set: PublicKeySet,
    *,
    allow_retired: bool = False,
) -> str:
    keys = _public_key_objects(key_set)
    entry = keys.get(envelope.key_id)
    if entry is None:
        raise UnknownKeyError(f"clé publique inconnue: {envelope.key_id}")
    public_key, metadata = entry
    if metadata.status != "active" and not allow_retired:
        raise KeyRetiredError(f"clé publique retirée: {envelope.key_id}")
    signature = _b64decode(envelope.value, "signature")
    try:
        public_key.verify(signature, data)
    except InvalidSignature as error:
        raise InvalidSignatureError("signature Ed25519 invalide") from error
    return envelope.key_id


def verify_file(
    pack_path: Path,
    signature_path: Path,
    key_set_path: Path,
    *,
    allow_retired: bool = False,
) -> str:
    return verify_bytes(
        pack_path.read_bytes(),
        load_signature(signature_path),
        load_public_key_set(key_set_path),
        allow_retired=allow_retired,
    )
