from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .base import (
    Capabilities,
    ChatEvent,
    ChatMessage,
    ChatRequest,
    ModelInfo,
    TestResult,
    TokenUsage,
    ToolCall,
)
from .capabilities import capabilities_for, estimate_cost_micros
from .errors import InvalidRequest, ProviderDown, ProviderError
from .normalize import normalize_messages
from .transport import iter_sse, open_stream, request_json

ANTHROPIC_VERSION = "2023-06-01"


def _anthropic_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in normalize_messages(messages):
        if message.role == "system":
            continue
        if message.role == "tool":
            content: Any = [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id or "",
                    "content": message.content,
                }
            ]
            role = "user"
        elif message.tool_calls:
            blocks: list[dict[str, Any]] = []
            if message.content:
                blocks.append({"type": "text", "text": message.content})
            blocks.extend(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
                for call in message.tool_calls
            )
            content = blocks
            role = "assistant"
        else:
            content = message.content
            role = "assistant" if message.role == "assistant" else "user"
        if result and result[-1]["role"] == role and isinstance(content, str):
            previous = result[-1]["content"]
            if isinstance(previous, str):
                result[-1]["content"] = f"{previous}\n\n{content}"
                continue
        result.append({"role": role, "content": content})
    return result


class AnthropicAdapter:
    def __init__(
        self,
        provider_id: str,
        base_url: str,
        api_key: str | None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: httpx.Timeout | float = 60.0,
    ) -> None:
        self.id = provider_id
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    def _headers(self, *, stream: bool = False) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    def capabilities(self, model: str) -> Capabilities:
        return capabilities_for(self.id, model)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def list_models(self) -> list[ModelInfo]:
        payload = await request_json(
            self._client,
            "GET",
            f"{self.base_url}/v1/models",
            provider=self.id,
            headers=self._headers(),
        )
        raw_models = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(raw_models, list):
            raise ProviderDown("liste de modèles invalide", provider=self.id)
        models: list[ModelInfo] = []
        for entry in raw_models:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                continue
            identifier = entry["id"]
            models.append(
                ModelInfo(
                    id=identifier,
                    name=entry.get("display_name")
                    if isinstance(entry.get("display_name"), str)
                    else None,
                    capabilities=self.capabilities(identifier),
                )
            )
        return sorted(models, key=lambda model: model.id)

    async def test_connection(self) -> TestResult:
        started = time.perf_counter()
        try:
            models = await self.list_models()
        except ProviderError as error:
            return TestResult(ok=False, message=error.message)
        return TestResult(
            ok=True,
            message=f"connexion réussie ({len(models)} modèles)",
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            models=models,
        )

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        system = "\n\n".join(
            message.content
            for message in normalize_messages(request.messages)
            if message.role == "system" and message.content
        )
        body: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens or 4096,
            "messages": _anthropic_messages(request.messages),
            "stream": True,
            "temperature": request.temperature,
        }
        if system:
            body["system"] = system
        if request.tools:
            body["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters or {"type": "object"},
                }
                for tool in request.tools
            ]

        response = await open_stream(
            self._client,
            "POST",
            f"{self.base_url}/v1/messages",
            provider=self.id,
            headers=self._headers(stream=True),
            json=body,
        )
        tool_blocks: dict[int, dict[str, Any]] = {}
        usage = {"input": 0, "output": 0}
        finish_reason: str | None = None
        try:
            async for raw in iter_sse(response):
                chunk = json.loads(raw)
                if not isinstance(chunk, dict):
                    continue
                event_type = chunk.get("type")
                if event_type == "error":
                    error = chunk.get("error")
                    message = (
                        str(error.get("message") or "erreur du fournisseur")
                        if isinstance(error, dict)
                        else "erreur du fournisseur"
                    )
                    raise InvalidRequest(message, provider=self.id)
                if event_type == "message_start":
                    message = chunk.get("message")
                    if isinstance(message, dict) and isinstance(message.get("usage"), dict):
                        usage["input"] = int(message["usage"].get("input_tokens") or 0)
                    continue
                if event_type == "content_block_start":
                    index = int(chunk.get("index") or 0)
                    block = chunk.get("content_block")
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_blocks[index] = {
                            "id": str(block.get("id") or ""),
                            "name": str(block.get("name") or ""),
                            "arguments": "",
                        }
                    elif block.get("type") == "text" and block.get("text"):
                        yield ChatEvent(
                            type="text_delta", text=str(block["text"]), provider=self.id
                        )
                    continue
                if event_type == "content_block_delta":
                    index = int(chunk.get("index") or 0)
                    delta = chunk.get("delta")
                    if not isinstance(delta, dict):
                        continue
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield ChatEvent(
                            type="text_delta", text=str(delta["text"]), provider=self.id
                        )
                    elif delta.get("type") == "thinking_delta" and delta.get("thinking"):
                        yield ChatEvent(
                            type="reasoning_delta",
                            text=str(delta["thinking"]),
                            provider=self.id,
                        )
                    elif delta.get("type") == "input_json_delta":
                        current = tool_blocks.setdefault(
                            index, {"id": "", "name": "", "arguments": ""}
                        )
                        current["arguments"] += str(delta.get("partial_json") or "")
                    continue
                if event_type == "message_delta":
                    if isinstance(chunk.get("usage"), dict):
                        usage["output"] = int(chunk["usage"].get("output_tokens") or 0)
                    delta = chunk.get("delta")
                    if isinstance(delta, dict) and isinstance(delta.get("stop_reason"), str):
                        finish_reason = delta["stop_reason"]
        finally:
            await response.aclose()

        for index in sorted(tool_blocks):
            block = tool_blocks[index]
            if not block["name"]:
                continue
            try:
                arguments = json.loads(block["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {}
            yield ChatEvent(
                type="tool_call",
                tool_call=ToolCall(
                    id=block["id"] or f"tool_{index}",
                    name=block["name"],
                    arguments=arguments if isinstance(arguments, dict) else {},
                ),
                provider=self.id,
            )

        if usage["input"] or usage["output"]:
            capabilities = self.capabilities(request.model)
            yield ChatEvent(
                type="usage",
                usage=TokenUsage(
                    input_tokens=usage["input"],
                    output_tokens=usage["output"],
                    total_tokens=usage["input"] + usage["output"],
                    cost_micros=estimate_cost_micros(
                        capabilities, usage["input"], usage["output"]
                    ),
                    currency=capabilities.currency,
                ),
                provider=self.id,
            )
        yield ChatEvent(type="done", finish_reason=finish_reason, provider=self.id)
