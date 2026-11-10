from __future__ import annotations

import json

import httpx

from providers import ChatRequest, OllamaAdapter


def _ndjson(*chunks: dict[str, object]) -> bytes:
    return "".join(f"{json.dumps(chunk)}\n" for chunk in chunks).encode()


async def test_ollama_contract_streaming_without_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3.2:latest"}]})
        return httpx.Response(
            200,
            headers={"content-type": "application/x-ndjson"},
            content=_ndjson(
                {"message": {"role": "assistant", "content": "Salut"}},
                {"message": {"role": "assistant", "content": " local"}},
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{"function": {"name": "run", "arguments": {"x": 2}}}],
                    }
                },
                {
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 12,
                    "eval_count": 6,
                },
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OllamaAdapter("ollama", "http://localhost:11434", client=client)
        assert (await adapter.list_models())[0].id == "llama3.2:latest"
        request = ChatRequest(
            model="llama3.2:latest",
            messages=[{"role": "user", "content": "salut"}],
        )
        events = [event async for event in adapter.chat(request)]

    assert [event.type for event in events] == [
        "text_delta",
        "text_delta",
        "tool_call",
        "usage",
        "done",
    ]
    assert events[0].text == "Salut"
    assert events[1].text == " local"
    assert events[2].tool_call is not None
    assert events[2].tool_call.arguments == {"x": 2}
    assert events[3].usage is not None
    assert events[3].usage.cost_micros == 0
    assert events[4].finish_reason == "stop"
