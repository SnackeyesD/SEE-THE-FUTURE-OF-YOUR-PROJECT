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


def _model_path(model: str) -> str:
    return model if model.startswith("models/") else f"models/{model}"


def _model_id(name: str) -> str:
    return name.removeprefix("models/")


def _gemini_contents(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for message in normalize_messages(messages):
        if message.role == "system":
            continue
        role = "model" if message.role == "assistant" else "user"
        parts: list[dict[str, Any]] = []
        if message.content:
            parts.append({"text": message.content})
        if message.role == "tool" and message.tool_call_id:
            parts.append(
                {
                    "functionResponse": {
                        "name": message.tool_call_id,
                        "response": {"content": message.content},
                    }
                }
            )
        for call in message.tool_calls:
            parts.append(
                {"functionCall": {"name": call.name, "args": call.arguments}}
            )
        if not parts:
            parts.append({"text": ""})
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].extend(parts)
        else:
            contents.append({"role": role, "parts": parts})
    return contents


class GeminiAdapter:
    def __init__(
        self,
        provider_id: str,
        base_url: str,
        api_key: str,
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
        return {
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }

    def capabilities(self, model: str) -> Capabilities:
        return capabilities_for(self.id, _model_id(model))

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
            params={"key": self._api_key},
        )
        raw_models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(raw_models, list):
            raise ProviderDown("liste de modèles invalide", provider=self.id)
        models: list[ModelInfo] = []
        for entry in raw_models:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                continue
            identifier = _model_id(entry["name"])
            capabilities = self.capabilities(identifier)
            context = entry.get("inputTokenLimit")
            if isinstance(context, int) and context > 0:
                capabilities = capabilities.model_copy(update={"context_window": context})
            models.append(
                ModelInfo(
                    id=identifier,
                    name=entry.get("displayName")
                    if isinstance(entry.get("displayName"), str)
                    else None,
                    capabilities=capabilities,
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
            "contents": _gemini_contents(request.messages),
            "generationConfig": {
                "temperature": request.temperature,
            },
        }
        if request.max_tokens is not None:
            body["generationConfig"]["maxOutputTokens"] = request.max_tokens
        if request.response_format == "json":
            body["generationConfig"]["responseMimeType"] = "application/json"
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if request.tools:
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters or {"type": "object"},
                        }
                        for tool in request.tools
                    ]
                }
            ]

        response = await open_stream(
            self._client,
            "POST",
            f"{self.base_url}/{_model_path(request.model)}:streamGenerateContent",
            provider=self.id,
            headers=self._headers(stream=True),
            params={"alt": "sse", "key": self._api_key},
            json=body,
        )
        finish_reason: str | None = None
        usage = {"input": 0, "output": 0}
        tool_index = 0
        try:
            async for raw in iter_sse(response):
                chunk = json.loads(raw)
                if not isinstance(chunk, dict):
                    continue
                error = chunk.get("error")
                if isinstance(error, dict):
                    raise InvalidRequest(
                        str(error.get("message") or "erreur du fournisseur"),
                        provider=self.id,
                    )
                metadata = chunk.get("usageMetadata")
                if isinstance(metadata, dict):
                    usage["input"] = int(metadata.get("promptTokenCount") or 0)
                    usage["output"] = int(metadata.get("candidatesTokenCount") or 0)
                candidates = chunk.get("candidates")
                if not isinstance(candidates, list):
                    continue
                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    if isinstance(candidate.get("finishReason"), str):
                        finish_reason = candidate["finishReason"]
                    content = candidate.get("content")
                    if not isinstance(content, dict):
                        continue
                    parts = content.get("parts")
                    if not isinstance(parts, list):
                        continue
                    for part in parts:
                        if not isinstance(part, dict):
                            continue
                        text = part.get("text")
                        if isinstance(text, str) and text:
                            event_type = "reasoning_delta" if part.get("thought") else "text_delta"
                            yield ChatEvent(type=event_type, text=text, provider=self.id)
                        function = part.get("functionCall")
                        if isinstance(function, dict) and function.get("name"):
                            arguments = function.get("args")
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
