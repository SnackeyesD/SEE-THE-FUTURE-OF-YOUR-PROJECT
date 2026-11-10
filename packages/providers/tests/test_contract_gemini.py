from __future__ import annotations

import json

import httpx

from providers import ChatRequest, GeminiAdapter


def _sse(*chunks: dict[str, object]) -> bytes:
    return "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks).encode()


async def test_gemini_contract_streaming() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["key"] == "gemini-secret"
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-2.0-flash",
                            "displayName": "Gemini 2.0 Flash",
                            "inputTokenLimit": 1048576,
                        }
                    ]
                },
            )
        assert request.url.path.endswith(":streamGenerateContent")
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=_sse(
                {
                    "candidates": [{"content": {"parts": [{"text": "Bonjour"}]}}],
                    "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
                },
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"functionCall": {"name": "run", "args": {"x": 1}}}]
                            },
                            "finishReason": "STOP",
                        }
                    ]
                },
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GeminiAdapter(
            "gemini", "https://generativelanguage.test/v1beta", "gemini-secret", client=client
        )
        model = (await adapter.list_models())[0]
        assert model.id == "gemini-2.0-flash"
        assert model.capabilities.context_window == 1_048_576
        request = ChatRequest(
            model="gemini-2.0-flash",
            messages=[{"role": "user", "content": "salut"}],
        )
        events = [event async for event in adapter.chat(request)]

    assert [event.type for event in events] == ["text_delta", "tool_call", "usage", "done"]
    assert events[0].text == "Bonjour"
    assert events[1].tool_call is not None
    assert events[1].tool_call.arguments == {"x": 1}
    assert events[2].usage is not None
    assert events[2].usage.cost_micros == 30
    assert events[3].finish_reason == "STOP"
