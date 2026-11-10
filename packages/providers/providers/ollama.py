from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .base import (
    Capabilities,
    ChatEvent,
    ChatRequest,
    ModelInfo,
    TestResult,
    TokenUsage,
    ToolCall,
)
from .capabilities import capabilities_for, estimate_cost_micros
from .errors import InvalidRequest, ProviderDown, ProviderError
from .normalize import normalize_messages
from .transport import open_stream, request_json


class OllamaAdapter:
    def __init__(
        self,
        provider_id: str,
        base_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: httpx.Timeout | float = 60.0,
    ) -> None:
        self.id = provider_id
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    def capabilities(self, model: str) -> Capabilities:
        return capabilities_for(self.id, model)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def list_models(self) -> list[ModelInfo]:
        payload = await request_json(
            self._client,
            "GET",
            f"{self.base_url}/api/tags",
            provider=self.id,
            headers={"Accept": "application/json"},
        )
        raw_models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(raw_models, list):
            raise ProviderDown("liste de modèles Ollama invalide", provider=self.id)
        models: list[ModelInfo] = []
        for entry in raw_models:
            if not isinstance(entry, dict):
                continue
            identifier = entry.get("name") or entry.get("model")
            if not isinstance(identifier, str) or not identifier:
                continue
            models.append(
                ModelInfo(
                    id=identifier,
                    name=identifier,
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
            message=f"Ollama accessible ({len(models)} modèles)",
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            models=models,
        )

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        body: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {
                    "role": message.role,
                    **({"content": message.content} if message.content else {}),
                    **({"name": message.name} if message.name else {}),
                }
                for message in normalize_messages(request.messages)
            ],
            "stream": True,
            "options": {"temperature": request.temperature},
        }
        if request.max_tokens is not None:
            body["options"]["num_predict"] = request.max_tokens
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

        response = await open_stream(
            self._client,
            "POST",
            f"{self.base_url}/api/chat",
            provider=self.id,
            headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
            json=body,
        )
        finish_reason: str | None = None
        usage = {"input": 0, "output": 0}
        tool_index = 0
        try:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if not isinstance(chunk, dict):
                    continue
                error = chunk.get("error")
                if isinstance(error, str):
                    raise InvalidRequest(error, provider=self.id)
                message = chunk.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content:
                        yield ChatEvent(type="text_delta", text=content, provider=self.id)
                    thinking = message.get("thinking")
                    if isinstance(thinking, str) and thinking:
                        yield ChatEvent(
                            type="reasoning_delta", text=thinking, provider=self.id
                        )
                    calls = message.get("tool_calls")
                    if isinstance(calls, list):
                        for call in calls:
                            function = call.get("function") if isinstance(call, dict) else None
                            if not isinstance(function, dict) or not function.get("name"):
                                continue
                            arguments = function.get("arguments")
                            yield ChatEvent(
                                type="tool_call",
                                tool_call=ToolCall(
                                    id=f"call_{tool_index}",
                                    name=str(function["name"]),
                                    arguments=arguments if isinstance(arguments, dict) else {},
                                ),
                                provider=self.id,
                            )
                            tool_index += 1
                if chunk.get("done") is True:
                    usage["input"] = int(chunk.get("prompt_eval_count") or 0)
                    usage["output"] = int(chunk.get("eval_count") or 0)
                    if isinstance(chunk.get("done_reason"), str):
                        finish_reason = chunk["done_reason"]
                    break
        finally:
            await response.aclose()

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
