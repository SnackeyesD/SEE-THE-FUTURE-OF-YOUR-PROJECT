from __future__ import annotations

from providers import (
    MATRIX_VERSION,
    capabilities_for,
    estimate_cost_micros,
    estimate_tokens,
)


def test_known_models_and_prices() -> None:
    capabilities = capabilities_for("openai", "gpt-4o-mini")
    assert capabilities.context_window == 128_000
    assert capabilities.native_tools is True
    assert capabilities.input_price_per_million == 0.15
    assert capabilities.version == MATRIX_VERSION
    assert estimate_cost_micros(capabilities, 1_000_000, 1_000_000) == 750_000


def test_prefix_lookup_and_unknown_fallback() -> None:
    assert capabilities_for("anthropic", "claude-3-5-sonnet-20241022").context_window == 200_000
    local = capabilities_for("ollama", "custom-local-model")
    assert local.context_window == 8_192
    assert local.input_price_per_million is None
    unknown = capabilities_for("openai", "future-model")
    assert unknown.source.endswith(":unknown")
    assert estimate_cost_micros(unknown, 1000, 1000) == 0


def test_token_estimation() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 9) == 3
