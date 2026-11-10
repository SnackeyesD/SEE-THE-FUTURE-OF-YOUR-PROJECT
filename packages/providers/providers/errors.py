from __future__ import annotations

import json
import re
from typing import Any

_SECRET_PATTERNS = (
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password|"
            r"authorization|bearer|key)(\s*[=:]\s*)([^\s&\"']+)"
        ),
        r"\1\2[redacted]",
    ),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [redacted]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "[redacted]"),
    (re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"), "[redacted]"),
)

_CONTEXT_MARKERS = (
    "context length",
    "context window",
    "maximum context",
    "too many tokens",
    "prompt is too long",
    "input is too long",
    "exceeds the maximum",
)


def sanitize_message(message: str) -> str:
    cleaned = str(message)
    for pattern, replacement in _SECRET_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned.replace("\n", " ").strip()[:1000]


class ProviderError(Exception):
    code = "provider_error"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status: int | None = None,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = sanitize_message(message)
        self.provider = provider
        self.status = status
        self.retry_after = retry_after
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.provider is not None:
            result["provider"] = self.provider
        if self.status is not None:
            result["status"] = self.status
        if self.retry_after is not None:
            result["retryAfter"] = self.retry_after
        result.update(self.details)
        return result


class AuthError(ProviderError):
    code = "auth_error"


class RateLimit(ProviderError):
    code = "rate_limit"
    retryable = True


class ContextOverflow(ProviderError):
    code = "context_overflow"


class ProviderDown(ProviderError):
    code = "provider_down"
    retryable = True


class ModelNotFound(ProviderError):
    code = "model_not_found"


class InvalidRequest(ProviderError):
    code = "invalid_request"


class BudgetExceeded(ProviderError):
    code = "budget_exceeded"


def _error_message(body: str) -> str:
    try:
        payload = json.loads(body)
    except (TypeError, json.JSONDecodeError):
        return body
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("type") or body)
        if isinstance(error, str):
            return error
        if isinstance(payload.get("message"), str):
            return payload["message"]
    return body


def map_http_error(
    status: int,
    body: str,
    *,
    provider: str | None = None,
    retry_after: float | None = None,
) -> ProviderError:
    message = _error_message(body)
    lowered = message.lower()
    if status in (401, 403):
        return AuthError(
            "clé invalide ou accès refusé par le fournisseur",
            provider=provider,
            status=status,
        )
    if status == 429:
        return RateLimit(
            "limite de débit atteinte",
            provider=provider,
            status=status,
            retry_after=retry_after,
        )
    if status in (400, 413, 422) and any(marker in lowered for marker in _CONTEXT_MARKERS):
        return ContextOverflow(
            "contexte du modèle dépassé",
            provider=provider,
            status=status,
        )
    if status == 404 and "model" in lowered:
        return ModelNotFound(
            message or "modèle introuvable",
            provider=provider,
            status=status,
        )
    if status >= 500 or status in (408, 409):
        return ProviderDown(
            message or "fournisseur indisponible",
            provider=provider,
            status=status,
            retry_after=retry_after,
        )
    return InvalidRequest(
        message or f"requête refusée (HTTP {status})",
        provider=provider,
        status=status,
    )
