from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from .base import ProviderAdapter
from .capabilities import MATRIX_VERSION
from .errors import AuthError, InvalidRequest


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    id: str
    label: str
    kind: str
    base_url: str | None
    requires_key: bool
    default_model: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)


_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        "openai",
        "OpenAI",
        "openai",
        "https://api.openai.com/v1",
        True,
        "gpt-4o-mini",
    ),
    ProviderSpec(
        "anthropic",
        "Anthropic",
        "anthropic",
        "https://api.anthropic.com",
        True,
        "claude-3-5-sonnet-latest",
        ("claude",),
    ),
    ProviderSpec(
        "gemini",
        "Google Gemini",
        "gemini",
        "https://generativelanguage.googleapis.com/v1beta",
        True,
        "gemini-2.0-flash",
        ("google", "google-gemini"),
    ),
    ProviderSpec(
        "ollama",
        "Ollama (local)",
        "ollama",
        "http://localhost:11434",
        False,
        "llama3.2",
        ("local",),
    ),
    ProviderSpec(
        "deepseek",
        "DeepSeek",
        "openai",
        "https://api.deepseek.com/v1",
        True,
        "deepseek-chat",
    ),
    ProviderSpec(
        "mistral",
        "Mistral AI",
        "openai",
        "https://api.mistral.ai/v1",
        True,
        "mistral-small-latest",
    ),
    ProviderSpec(
        "openrouter",
        "OpenRouter",
        "openai",
        "https://openrouter.ai/api/v1",
        True,
    ),
    ProviderSpec(
        "groq",
        "Groq",
        "openai",
        "https://api.groq.com/openai/v1",
        True,
        "llama-3.3-70b-versatile",
    ),
    ProviderSpec(
        "together",
        "Together AI",
        "openai",
        "https://api.together.xyz/v1",
        True,
    ),
    ProviderSpec(
        "nvidia",
        "NVIDIA NIM",
        "openai",
        "https://integrate.api.nvidia.com/v1",
        True,
    ),
    ProviderSpec(
        "lmstudio",
        "LM Studio (local)",
        "openai",
        "http://localhost:1234/v1",
        False,
        aliases=("lm-studio",),
    ),
    ProviderSpec(
        "vllm",
        "vLLM (local)",
        "openai",
        "http://localhost:8000/v1",
        False,
    ),
    ProviderSpec(
        "openai-compatible",
        "Endpoint compatible OpenAI",
        "openai",
        None,
        True,
    ),
)

_BY_NAME: dict[str, ProviderSpec] = {}
for _spec in _SPECS:
    _BY_NAME[_spec.id] = _spec
    for _alias in _spec.aliases:
        _BY_NAME[_alias] = _spec

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def resolve_provider(provider: str, *, base_url: str | None = None) -> ProviderSpec:
    normalized = provider.strip().lower()
    spec = _BY_NAME.get(normalized)
    if spec is not None:
        return spec
    if base_url and base_url.strip():
        return ProviderSpec(
            normalized,
            normalized,
            "openai",
            base_url.strip(),
            True,
        )
    raise InvalidRequest(f"fournisseur inconnu: {provider}")


def catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": spec.id,
            "label": spec.label,
            "kind": spec.kind,
            "baseUrl": spec.base_url,
            "requiresKey": spec.requires_key,
            "defaultModel": spec.default_model,
            "capabilitiesVersion": MATRIX_VERSION,
        }
        for spec in _SPECS
    ]


def create_adapter(
    provider: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
    timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
) -> ProviderAdapter:
    spec = resolve_provider(provider, base_url=base_url)
    effective_url = (base_url or spec.base_url or "").rstrip("/")
    if not effective_url:
        raise InvalidRequest("baseUrl est requis pour ce fournisseur")
    clean_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
    if spec.requires_key and clean_key is None:
        raise AuthError(
            "clé API manquante pour ce fournisseur",
            provider=spec.id,
        )

    if spec.kind == "openai":
        from .openai_compatible import OpenAICompatibleAdapter

        return OpenAICompatibleAdapter(
            spec.id,
            effective_url,
            clean_key,
            client=client,
            timeout=timeout,
        )
    if spec.kind == "anthropic":
        from .anthropic import AnthropicAdapter

        return AnthropicAdapter(
            spec.id,
            effective_url,
            clean_key,
            client=client,
            timeout=timeout,
        )
    if spec.kind == "gemini":
        from .gemini import GeminiAdapter

        return GeminiAdapter(
            spec.id,
            effective_url,
            clean_key or "",
            client=client,
            timeout=timeout,
        )
    if spec.kind == "ollama":
        from .ollama import OllamaAdapter

        return OllamaAdapter(spec.id, effective_url, client=client, timeout=timeout)
    raise InvalidRequest(f"type de fournisseur non supporté: {spec.kind}")
