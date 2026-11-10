from __future__ import annotations

import re
from typing import Any

from see_sandbox import ContractError, analyze_code, validate_result
from see_storage import ProjectStore, StorageValidationError

CODE_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DECISIONS = ("approved", "rejected")
STATUSES = ("succeeded", "failed", "timeout", "cancelled", "rejected")


def _required_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StorageValidationError(f"{key} doit être une chaîne non vide")
    return value.strip()


def _optional_text(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise StorageValidationError(f"{key} doit être une chaîne")
    return value.strip() or None


def _code(params: dict[str, Any]) -> str:
    value = params.get("code")
    if not isinstance(value, str) or not value:
        raise StorageValidationError("code doit être une chaîne non vide")
    return value


def analyze(_store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    return {"analysis": analyze_code(_code(params)).to_dict()}


def record_audit(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    code = _code(params)
    expected_hash = _required_text(params, "codeHash")
    if not CODE_HASH_PATTERN.match(expected_hash):
        raise StorageValidationError("codeHash invalide")
    decision = _required_text(params, "decision")
    status = _required_text(params, "status")
    if decision not in DECISIONS:
        raise StorageValidationError(f"decision invalide: {decision}")
    if status not in STATUSES:
        raise StorageValidationError(f"status invalide: {status}")
    purpose = _optional_text(params, "purpose") or ""

    analysis = analyze_code(code)
    if analysis.codeHash != expected_hash:
        raise StorageValidationError("le code ne correspond pas à l'empreinte approuvée")
    if decision == "approved" and not analysis.ok:
        raise StorageValidationError("un script refusé par l'analyse ne peut pas être approuvé")

    result = params.get("result")
    if status == "succeeded":
        if result is None:
            raise StorageValidationError("un succès doit fournir un résultat")
        try:
            result = validate_result(result)
        except ContractError as exc:
            raise StorageValidationError(str(exc)) from exc
    elif result is not None:
        raise StorageValidationError("seul un succès peut fournir un résultat")

    error = _optional_text(params, "error")
    duration = params.get("durationMs")
    if duration is not None and (
        isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0
    ):
        raise StorageValidationError("durationMs invalide")

    record = store.sandbox_audit.add(
        project_id,
        code,
        expected_hash,
        decision,
        status,
        analysis=analysis.to_dict(),
        purpose=purpose,
        result=result,
        error=error,
        duration_ms=duration,
    )
    return {"record": record.to_dict()}


def list_audit(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    limit = params.get("limit", 50)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 500:
        raise StorageValidationError("limit doit être un entier entre 1 et 500")
    records = store.sandbox_audit.list(project_id, limit=limit)
    return {
        "records": [record.to_dict() for record in records],
        "count": store.sandbox_audit.count(project_id),
    }


def export_audit(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    path, count = store.export_sandbox_audit(project_id)
    return {"path": str(path), "count": count}
