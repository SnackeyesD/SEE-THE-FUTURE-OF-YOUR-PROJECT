from __future__ import annotations

from .anthropic import AnthropicAdapter
from .base import (
    Capabilities,
    ChatEvent,
    ChatMessage,
    ChatRequest,
    ModelInfo,
    ProviderAdapter,
    TestResult,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from .capabilities import (
    MATRIX_VERSION,
    capabilities_for,
    estimate_cost_micros,
    estimate_tokens,
)
from .costs import estimate_input_tokens, estimate_usage
from .errors import (
    AuthError,
    BudgetExceeded,
    ContextOverflow,
    InvalidRequest,
    ModelNotFound,
    ProviderDown,
    ProviderError,
    RateLimit,
    map_http_error,
    sanitize_message,
)
from .fallback import FallbackAdapter
from .gemini import GeminiAdapter
from .normalize import normalize_messages
from .ollama import OllamaAdapter
from .openai_compatible import OpenAICompatibleAdapter
from .registry import (
    DEFAULT_TIMEOUT,
    ProviderSpec,
    catalog,
    create_adapter,
    resolve_provider,
)
from .retry import DEFAULT_RETRY_POLICY, RetryPolicy, run_with_retry

__version__ = "0.1.0"

__all__ = [
    "AnthropicAdapter",
    "AuthError",
    "BudgetExceeded",
    "Capabilities",
    "ChatEvent",
    "ChatMessage",
    "ChatRequest",
    "ContextOverflow",
    "DEFAULT_RETRY_POLICY",
    "DEFAULT_TIMEOUT",
    "FallbackAdapter",
    "GeminiAdapter",
    "InvalidRequest",
    "MATRIX_VERSION",
    "ModelInfo",
    "ModelNotFound",
    "OllamaAdapter",
    "OpenAICompatibleAdapter",
    "ProviderAdapter",
    "ProviderDown",
    "ProviderError",
    "ProviderSpec",
    "RateLimit",
    "RetryPolicy",
    "TestResult",
    "TokenUsage",
    "ToolCall",
    "ToolDefinition",
    "capabilities_for",
    "catalog",
    "create_adapter",
    "estimate_cost_micros",
    "estimate_input_tokens",
    "estimate_tokens",
    "estimate_usage",
    "map_http_error",
    "normalize_messages",
    "resolve_provider",
    "run_with_retry",
    "sanitize_message",
]
