from __future__ import annotations

from .base import Capabilities, TokenUsage
from .capabilities import estimate_cost_micros, estimate_tokens


def estimate_usage(
    capabilities: Capabilities,
    *,
    input_tokens: int,
    output_tokens: int,
) -> TokenUsage:
    input_tokens = max(0, int(input_tokens))
    output_tokens = max(0, int(output_tokens))
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cost_micros=estimate_cost_micros(capabilities, input_tokens, output_tokens),
        currency=capabilities.currency,
    )


def estimate_input_tokens(text: str) -> int:
    return estimate_tokens(text)
