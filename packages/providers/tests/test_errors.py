from __future__ import annotations

from providers import (
    AuthError,
    ContextOverflow,
    ModelNotFound,
    ProviderDown,
    RateLimit,
    map_http_error,
    sanitize_message,
)


def test_sanitizes_secrets_in_messages() -> None:
    message = (
        "GET https://example.test/models?key=SECRET_VALUE&x=1 "
        "Authorization: Bearer sk-supersecret1234"
    )
    cleaned = sanitize_message(message)
    assert "SECRET_VALUE" not in cleaned
    assert "sk-supersecret1234" not in cleaned
    assert "[redacted]" in cleaned


def test_maps_http_failures() -> None:
    assert isinstance(map_http_error(401, "{}"), AuthError)
    rate = map_http_error(429, "{}", retry_after=2.5)
    assert isinstance(rate, RateLimit)
    assert rate.retry_after == 2.5
    assert isinstance(
        map_http_error(400, '{"error":{"message":"maximum context length exceeded"}}'),
        ContextOverflow,
    )
    assert isinstance(
        map_http_error(404, '{"error":{"message":"model not found"}}'),
        ModelNotFound,
    )
    assert isinstance(map_http_error(503, "down"), ProviderDown)


def test_error_payload_never_contains_secret() -> None:
    error = AuthError("clé incorrecte: key=abc123", provider="openai", status=401)
    payload = error.to_dict()
    assert "abc123" not in payload["message"]
    assert payload["code"] == "auth_error"
    assert payload["retryable"] is False
