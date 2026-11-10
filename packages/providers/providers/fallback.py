from __future__ import annotations

from collections.abc import AsyncIterator

from .base import (
    Capabilities,
    ChatEvent,
    ChatRequest,
    ModelInfo,
    ProviderAdapter,
    TestResult,
)
from .errors import ProviderError


class FallbackAdapter:
    id = "fallback"

    def __init__(self, adapters: list[ProviderAdapter]) -> None:
        if not adapters:
            raise ValueError("une chaîne de repli doit contenir au moins un adaptateur")
        self.adapters = adapters

    def capabilities(self, model: str) -> Capabilities:
        return self.adapters[0].capabilities(model)

    async def list_models(self) -> list[ModelInfo]:
        return await self.adapters[0].list_models()

    async def test_connection(self) -> TestResult:
        failures: list[str] = []
        for adapter in self.adapters:
            result = await adapter.test_connection()
            if result.ok:
                return result
            failures.append(f"{adapter.id}: {result.message}")
        return TestResult(ok=False, message="; ".join(failures))

    async def aclose(self) -> None:
        for adapter in self.adapters:
            await adapter.aclose()

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        for index, adapter in enumerate(self.adapters):
            emitted = False
            try:
                async for event in adapter.chat(request):
                    emitted = True
                    yield event
                return
            except ProviderError as error:
                if emitted or index == len(self.adapters) - 1:
                    raise
                yield ChatEvent(
                    type="fallback",
                    provider=adapter.id,
                    reason=error.code,
                    text=error.message,
                )
