from __future__ import annotations

import json

import httpx
import pytest

from providers import AuthError, ChatRequest, OpenAICompatibleAdapter


def _sse(*chunks: dict[str, object]) -> bytes:
    lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


async def test_openai_contract_streaming_and_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret"
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-4o-mini"}]})
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=_sse(
                {"choices": [{"delta": {"content": "Bon"}}]},
                {"choices": [{"delta": {"reasoning_content": "réfléchit"}}]},
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_1",
                                        "function": {
                                            "name": "set_hypotheses",
                                            "arguments": '{"price":',
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {"index": 0, "function": {"arguments": "10}"}}
                                ]
                            }
                        }
                    ]
                },
                {
                    "choices": [{"delta": {}, "finish_reason": "tool_calls"}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                },
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleAdapter(
            "openai", "https://example.test/v1", "secret", client=client
        )
        models = await adapter.list_models()
        assert models[0].id == "gpt-4o-mini"
        request = ChatRequest(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "salut"}],
        )
        events = [event async for event in adapter.chat(request)]

    assert [event.type for event in events] == [
        "text_delta",
        "reasoning_delta",
        "tool_call",
        "usage",
        "done",
    ]
    assert events[0].text == "Bon"
    assert events[1].text == "réfléchit"
    assert events[2].tool_call is not None
    assert events[2].tool_call.name == "set_hypotheses"
    assert events[2].tool_call.arguments == {"price": 10}
    assert events[3].usage is not None
    assert events[3].usage.input_tokens == 100
    assert events[3].usage.output_tokens == 50
    assert events[3].usage.cost_micros == 45
    assert events[4].finish_reason == "tool_calls"


async def test_openai_auth_error_is_clean() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key=SECRET_VALUE")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleAdapter(
            "openai", "https://example.test/v1", "secret", client=client
        )
        with pytest.raises(AuthError) as captured:
            await adapter.list_models()
    assert "SECRET_VALUE" not in str(captured.value)
