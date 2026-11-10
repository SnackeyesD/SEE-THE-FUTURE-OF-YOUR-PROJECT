from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

MessageRole = Literal["system", "user", "assistant", "tool"]
ChatEventType = Literal[
    "text_delta",
    "reasoning_delta",
    "tool_call",
    "usage",
    "done",
    "fallback",
]
ResponseFormat = Literal["text", "json"]


class NormalizedModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class Capabilities(NormalizedModel):
    context_window: int | None = None
    native_tools: bool = False
    native_structured_output: bool = False
    reasoning: bool = False
    vision: bool = False
    input_price_per_million: float | None = None
    output_price_per_million: float | None = None
    currency: str = "USD"
    source: str = "matrix"
    version: str = "1"


class ToolDefinition(NormalizedModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolCall(NormalizedModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(NormalizedModel):
    role: MessageRole
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ChatRequest(NormalizedModel):
    model: str
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int | None = 4096
    tools: list[ToolDefinition] = Field(default_factory=list)
    response_format: ResponseFormat = "text"


class TokenUsage(NormalizedModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_micros: int = 0
    currency: str = "USD"


class ChatEvent(NormalizedModel):
    type: ChatEventType
    text: str | None = None
    tool_call: ToolCall | None = None
    usage: TokenUsage | None = None
    finish_reason: str | None = None
    provider: str | None = None
    reason: str | None = None


class ModelInfo(NormalizedModel):
    id: str
    name: str | None = None
    capabilities: Capabilities


class TestResult(NormalizedModel):
    ok: bool
    message: str
    latency_ms: float = 0
    models: list[ModelInfo] = Field(default_factory=list)


@runtime_checkable
class ProviderAdapter(Protocol):
    id: str

    async def list_models(self) -> list[ModelInfo]: ...

    async def test_connection(self) -> TestResult: ...

    def capabilities(self, model: str) -> Capabilities: ...

    def chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]: ...

    async def aclose(self) -> None: ...
