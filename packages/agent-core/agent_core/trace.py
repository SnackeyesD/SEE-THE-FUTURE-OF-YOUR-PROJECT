from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .guardrails import scrub_secrets


@dataclass(frozen=True, slots=True)
class TraceEvent:
    turn: int
    kind: str
    role: str | None
    data: dict[str, Any]
    created_at: str
    duration_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "turn": self.turn,
            "kind": self.kind,
            "createdAt": self.created_at,
            "data": self.data,
        }
        if self.role is not None:
            payload["role"] = self.role
        if self.duration_ms is not None:
            payload["durationMs"] = round(self.duration_ms, 3)
        return payload


TraceSink = Callable[[TraceEvent], None]


@dataclass
class TraceRecorder:
    turn: int = 0
    include_content: bool = False
    sink: TraceSink | None = None
    events: list[TraceEvent] = field(default_factory=list)
    max_events: int = 1000
    _started: float | None = field(default=None, init=False, repr=False)

    def begin_turn(self) -> None:
        self.turn += 1
        self._started = time.perf_counter()

    def record(
        self,
        kind: str,
        data: dict[str, Any] | None = None,
        *,
        role: str | None = None,
        duration_ms: float | None = None,
    ) -> TraceEvent:
        payload = scrub_secrets(data or {})
        if not self.include_content:
            payload = _redact_content(payload)
        event = TraceEvent(
            turn=self.turn,
            kind=kind,
            role=role,
            data=payload,
            created_at=datetime.now(UTC).isoformat(),
            duration_ms=duration_ms,
        )
        self.events.append(event)
        if len(self.events) > self.max_events:
            del self.events[0 : len(self.events) - self.max_events]
        if self.sink is not None:
            self.sink(event)
        return event

    def prompt_reference(self, messages: list[Any]) -> dict[str, Any]:
        rendered = json.dumps(
            [message.model_dump(by_alias=True) for message in messages],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return {
            "hash": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            "messageCount": len(messages),
            "roles": [getattr(message, "role", "unknown") for message in messages],
        }

    def elapsed_ms(self) -> float | None:
        if self._started is None:
            return None
        return (time.perf_counter() - self._started) * 1000.0

    def export(self) -> dict[str, Any]:
        return {
            "version": 1,
            "turn": self.turn,
            "includeContent": self.include_content,
            "events": [event.to_dict() for event in self.events],
        }

    def export_json(self) -> str:
        return json.dumps(self.export(), ensure_ascii=False, indent=2, sort_keys=True)


def _redact_content(value: Any, key: str | None = None) -> Any:
    content_keys = {"content", "prompt", "arguments", "result", "text", "message"}
    if isinstance(value, str):
        return f"[{len(value)} chars]" if key in content_keys else value
    if isinstance(value, list):
        return [_redact_content(item, key) for item in value]
    if isinstance(value, dict):
        return {name: _redact_content(item, str(name)) for name, item in value.items()}
    return value
