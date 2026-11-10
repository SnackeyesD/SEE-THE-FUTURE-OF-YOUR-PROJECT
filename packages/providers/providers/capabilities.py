from __future__ import annotations

from math import ceil

from .base import Capabilities

MATRIX_VERSION = "2026.11.1"

_MATRIX: dict[str, dict[str, object]] = {
    "gpt-4o-mini": {
        "context_window": 128_000,
        "native_tools": True,
        "native_structured_output": True,
        "vision": True,
        "input_price_per_million": 0.15,
        "output_price_per_million": 0.60,
    },
    "gpt-4o": {
        "context_window": 128_000,
        "native_tools": True,
        "native_structured_output": True,
        "vision": True,
        "input_price_per_million": 2.50,
        "output_price_per_million": 10.00,
    },
    "gpt-4.1-mini": {
        "context_window": 1_047_576,
        "native_tools": True,
        "native_structured_output": True,
        "vision": True,
        "input_price_per_million": 0.40,
        "output_price_per_million": 1.60,
    },
    "gpt-4.1": {
        "context_window": 1_047_576,
        "native_tools": True,
        "native_structured_output": True,
        "vision": True,
        "input_price_per_million": 2.00,
        "output_price_per_million": 8.00,
    },
    "o4-mini": {
        "context_window": 200_000,
        "native_tools": True,
        "native_structured_output": True,
        "reasoning": True,
        "vision": True,
        "input_price_per_million": 1.10,
        "output_price_per_million": 4.40,
    },
    "o3": {
        "context_window": 200_000,
        "native_tools": True,
        "native_structured_output": True,
        "reasoning": True,
        "vision": True,
        "input_price_per_million": 2.00,
        "output_price_per_million": 8.00,
    },
    "claude-3-5-sonnet": {
        "context_window": 200_000,
        "native_tools": True,
        "vision": True,
        "input_price_per_million": 3.00,
        "output_price_per_million": 15.00,
    },
    "claude-3-7-sonnet": {
        "context_window": 200_000,
        "native_tools": True,
        "reasoning": True,
        "vision": True,
        "input_price_per_million": 3.00,
        "output_price_per_million": 15.00,
    },
    "claude-sonnet-4": {
        "context_window": 200_000,
        "native_tools": True,
        "reasoning": True,
        "vision": True,
        "input_price_per_million": 3.00,
        "output_price_per_million": 15.00,
    },
    "claude-haiku-3-5": {
        "context_window": 200_000,
        "native_tools": True,
        "vision": True,
        "input_price_per_million": 0.80,
        "output_price_per_million": 4.00,
    },
    "gemini-2.5-pro": {
        "context_window": 1_048_576,
        "native_tools": True,
        "native_structured_output": True,
        "reasoning": True,
        "vision": True,
        "input_price_per_million": 1.25,
        "output_price_per_million": 10.00,
    },
    "gemini-2.5-flash": {
        "context_window": 1_048_576,
        "native_tools": True,
        "native_structured_output": True,
        "reasoning": True,
        "vision": True,
        "input_price_per_million": 0.30,
        "output_price_per_million": 2.50,
    },
    "gemini-2.0-flash": {
        "context_window": 1_048_576,
        "native_tools": True,
        "native_structured_output": True,
        "vision": True,
        "input_price_per_million": 0.10,
        "output_price_per_million": 0.40,
    },
    "gemini-1.5-pro": {
        "context_window": 2_097_152,
        "native_tools": True,
        "native_structured_output": True,
        "vision": True,
        "input_price_per_million": 1.25,
        "output_price_per_million": 5.00,
    },
    "gemini-1.5-flash": {
        "context_window": 1_048_576,
        "native_tools": True,
        "native_structured_output": True,
        "vision": True,
        "input_price_per_million": 0.075,
        "output_price_per_million": 0.30,
    },
    "deepseek-chat": {
        "context_window": 64_000,
        "native_tools": True,
        "native_structured_output": True,
        "input_price_per_million": 0.27,
        "output_price_per_million": 1.10,
    },
    "deepseek-reasoner": {
        "context_window": 64_000,
        "native_tools": False,
        "reasoning": True,
        "input_price_per_million": 0.55,
        "output_price_per_million": 2.19,
    },
    "mistral-large": {
        "context_window": 128_000,
        "native_tools": True,
        "native_structured_output": True,
        "input_price_per_million": 2.00,
        "output_price_per_million": 6.00,
    },
    "mistral-small": {
        "context_window": 128_000,
        "native_tools": True,
        "native_structured_output": True,
        "input_price_per_million": 0.20,
        "output_price_per_million": 0.60,
    },
    "llama-3.3-70b": {
        "context_window": 128_000,
        "native_tools": True,
    },
    "llama-3.1": {
        "context_window": 128_000,
        "native_tools": True,
    },
    "qwen2.5": {
        "context_window": 128_000,
        "native_tools": True,
        "native_structured_output": True,
    },
    "qwen3": {
        "context_window": 128_000,
        "native_tools": True,
        "reasoning": True,
    },
}

_LOCAL_PREFIXES = ("llama", "qwen", "mistral", "mixtral", "gemma", "phi", "deepseek-r1")


def _lookup(model: str) -> dict[str, object] | None:
    normalized = model.strip().lower()
    if normalized in _MATRIX:
        return _MATRIX[normalized]
    matches = [prefix for prefix in _MATRIX if normalized.startswith(prefix)]
    if not matches:
        return None
    return _MATRIX[max(matches, key=len)]


def capabilities_for(provider: str, model: str) -> Capabilities:
    values = _lookup(model)
    if values is not None:
        return Capabilities(source=f"matrix:{MATRIX_VERSION}", version=MATRIX_VERSION, **values)
    lowered_provider = provider.strip().lower()
    if lowered_provider == "ollama" or any(
        model.strip().lower().startswith(prefix) for prefix in _LOCAL_PREFIXES
    ):
        return Capabilities(
            context_window=8_192,
            source=f"matrix:{MATRIX_VERSION}:local",
            version=MATRIX_VERSION,
        )
    return Capabilities(source=f"matrix:{MATRIX_VERSION}:unknown", version=MATRIX_VERSION)


def estimate_cost_micros(
    capabilities: Capabilities, input_tokens: int, output_tokens: int
) -> int:
    input_tokens = max(0, int(input_tokens))
    output_tokens = max(0, int(output_tokens))
    input_price = capabilities.input_price_per_million
    output_price = capabilities.output_price_per_million
    if input_price is None or output_price is None:
        return 0
    return int(round(input_tokens * input_price + output_tokens * output_price))


def estimate_tokens(text: str) -> int:
    if not text:
        return 1
    return max(1, ceil(len(text) / 4))
