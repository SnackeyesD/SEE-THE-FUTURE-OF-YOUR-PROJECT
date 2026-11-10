from __future__ import annotations

import json

import httpx

from providers import AnthropicAdapter, ChatRequest


def _sse(*chunks: dict[str, object]) -> bytes:
    body = "".join(
        f"event: {chunk.get('type', 'message')}\ndata: {json.dumps(chunk)}\n\n"
        for chunk in chunks
    )
    return body.encode()


async def test_anthropic_contract_streaming() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "anthropic-secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={"data": [{"id": "claude-3-5-sonnet-latest", "display_name": "Sonnet"}]},
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=_sse(
                {
                    "type": "message_start",
                    "message": {"usage": {"input_tokens": 20}},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "Salut"},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "thinking_delta", "thinking": "analyse"},
                },
                {
                    "type": "content_block_start",
                    "index": 1,
                    "content_block": {"type": "tool_use", "id": "tool_1", "name": "run"},
                },
                {
                    "type": "content_block_delta",
                    "index": 1,
                    "delta": {"type": "input_json_delta", "partial_json": '{"runs": 10}'},
                },
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "tool_use"},
                    "usage": {"output_tokens": 7},
                },
                {"type": "message_stop"},
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = AnthropicAdapter(
            "anthropic", "https://example.test", "anthropic-secret", client=client
        )
        assert (await adapter.list_models())[0].id == "claude-3-5-sonnet-latest"
        request = ChatRequest(
            model="claude-3-5-sonnet-latest",
            messages=[
                {"role": "system", "content": "Tu es prudent"},
                {"role": "user", "content": "salut"},
            ],
        )
        events = [event async for event in adapter.chat(request)]

    assert [event.type for event in events] == [
        "text_delta",
        "reasoning_delta",
        "tool_call",
        "usage",
        "done",
    ]
    assert events[0].text == "Salut"
    assert events[1].text == "analyse"
    assert events[2].tool_call is not None
    assert events[2].tool_call.arguments == {"runs": 10}
    assert events[3].usage is not None
    assert events[3].usage.cost_micros == 165
    assert events[4].finish_reason == "tool_use"
