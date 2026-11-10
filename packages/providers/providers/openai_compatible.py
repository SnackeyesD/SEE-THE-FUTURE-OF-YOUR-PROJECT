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


def _reasoning_text(delta: dict[str, Any]) -> str | None:
    for key in ("reasoning_content", "reasoning"):
        value = delta.get(key)
        if isinstance(value, str) and value:
            return value
    details = delta.get("reasoning_details")
    if isinstance(details, list):
        parts = [
            str(item.get("text") or item.get("summary") or "")
            for item in details
            if isinstance(item, dict)
        ]
        text = "".join(parts)
        return text or None
    return None


def _openai_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in normalize_messages(messages):
        item: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.name:
            item["name"] = message.name
        if message.role == "tool" and message.tool_call_id:
            item["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ]
        result.append(item)
    return result


class OpenAICompatibleAdapter:
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
        headers = {"Content-Type": "application/json"}
        headers["Accept"] = "text/event-stream" if stream else "application/json"
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
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
            f"{self.base_url}/models",
            provider=self.id,
            headers=self._headers(),
        )
        raw_models = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(raw_models, list):
            raise ProviderDown("liste de modèles invalide", provider=self.id)
        models: list[ModelInfo] = []
        for entry in raw_models:
            if not isinstance(entry, dict):
                continue
            identifier = entry.get("id")
            if not isinstance(identifier, str) or not identifier:
                continue
            models.append(
                ModelInfo(
                    id=identifier,
                    name=entry.get("name") if isinstance(entry.get("name"), str) else None,
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
        body: dict[str, Any] = {
            "model": request.model,
            "messages": _openai_messages(request.messages),
            "stream": True,
            "temperature": request.temperature,
            "stream_options": {"include_usage": True},
        }
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
        if request.response_format == "json":
            body["response_format"] = {"type": "json_object"}

        response = await open_stream(
            self._client,
            "POST",
            f"{self.base_url}/chat/completions",
            provider=self.id,
            headers=self._headers(stream=True),
            json=body,
        )
        pending_calls: dict[int, dict[str, Any]] = {}
        usage: dict[str, int] | None = None
        finish_reason: str | None = None
        try:
            async for raw in iter_sse(response):
                chunk = json.loads(raw)
                if not isinstance(chunk, dict):
                    continue
                error = chunk.get("error")
                if isinstance(error, dict):
                    message = str(error.get("message") or "erreur du fournisseur")
                    raise InvalidRequest(message, provider=self.id)
                raw_usage = chunk.get("usage")
                if isinstance(raw_usage, dict):
                    usage = {
                        "input": int(raw_usage.get("prompt_tokens") or 0),
                        "output": int(raw_usage.get("completion_tokens") or 0),
                    }
                choices = chunk.get("choices")
                if not isinstance(choices, list):
                    continue
                for choice in choices:
                    if not isinstance(choice, dict):
                        continue
                    delta = choice.get("delta")
                    if isinstance(delta, dict):
                        text = delta.get("content")
                        if isinstance(text, str) and text:
                            yield ChatEvent(type="text_delta", text=text, provider=self.id)
                        reasoning = _reasoning_text(delta)
                        if reasoning:
                            yield ChatEvent(
                                type="reasoning_delta", text=reasoning, provider=self.id
                            )
                        calls = delta.get("tool_calls")
                        if isinstance(calls, list):
                            for call in calls:
                                if not isinstance(call, dict):
                                    continue
                                index = int(call.get("index") or 0)
                                current = pending_calls.setdefault(
                                    index, {"id": "", "name": "", "arguments": ""}
                                )
                                if isinstance(call.get("id"), str):
                                    current["id"] = call["id"]
                                function = call.get("function")
                                if isinstance(function, dict):
                                    if isinstance(function.get("name"), str):
                                        current["name"] += function["name"]
                                    if isinstance(function.get("arguments"), str):
                                        current["arguments"] += function["arguments"]
                    if isinstance(choice.get("finish_reason"), str):
                        finish_reason = choice["finish_reason"]
        finally:
            await response.aclose()

        for index in sorted(pending_calls):
            call = pending_calls[index]
            name = str(call.get("name") or "").strip()
            if not name:
                continue
            try:
                arguments = json.loads(call.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            yield ChatEvent(
                type="tool_call",
                tool_call=ToolCall(
                    id=str(call.get("id") or f"call_{index}"),
                    name=name,
                    arguments=arguments if isinstance(arguments, dict) else {},
                ),
                provider=self.id,
            )

        if usage is not None:
            input_tokens = usage["input"]
            output_tokens = usage["output"]
            capabilities = self.capabilities(request.model)
            yield ChatEvent(
                type="usage",
                usage=TokenUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    cost_micros=estimate_cost_micros(
                        capabilities, input_tokens, output_tokens
                    ),
                    currency=capabilities.currency,
                ),
                provider=self.id,
            )
        yield ChatEvent(type="done", finish_reason=finish_reason, provider=self.id)
