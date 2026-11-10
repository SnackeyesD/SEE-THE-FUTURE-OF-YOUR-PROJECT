from __future__ import annotations

from collections.abc import AsyncIterator

from providers import (
    Capabilities,
    ChatEvent,
    ChatRequest,
    FallbackAdapter,
    ModelInfo,
    ProviderDown,
)
from providers import (
    TestResult as ConnectionResult,
)


class FailingAdapter:
    id = "primary"

    def capabilities(self, model: str) -> Capabilities:
        return Capabilities()

    async def list_models(self) -> list[ModelInfo]:
        return []

    async def test_connection(self) -> ConnectionResult:
        return ConnectionResult(ok=False, message="down")

    async def aclose(self) -> None:
        return None

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        if False:
            yield ChatEvent(type="done")
        raise ProviderDown("primary down")


class WorkingAdapter(FailingAdapter):
    id = "secondary"

    async def test_connection(self) -> ConnectionResult:
        return ConnectionResult(ok=True, message="ok")

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        yield ChatEvent(type="text_delta", text="repli", provider=self.id)
        yield ChatEvent(type="done", provider=self.id)


async def test_falls_back_before_first_token() -> None:
    adapter = FallbackAdapter([FailingAdapter(), WorkingAdapter()])
    request = ChatRequest(model="m", messages=[{"role": "user", "content": "salut"}])
    events = [event async for event in adapter.chat(request)]
    assert [event.type for event in events] == ["fallback", "text_delta", "done"]
    assert events[0].provider == "primary"
    assert events[0].reason == "provider_down"
    assert events[1].text == "repli"
    assert (await adapter.test_connection()).ok is True
