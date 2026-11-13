from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from .base import ChatMessage, ToolCall
from .errors import InvalidRequest

_ALLOWED_MESSAGE_FIELDS = {"role", "content", "name", "tool_call_id", "tool_calls"}
_MESSAGE_FIELD_ALIASES = {
    "toolCallId": "tool_call_id",
    "toolCalls": "tool_calls",
}
_ALLOWED_TOOL_CALL_FIELDS = {"id", "name", "arguments"}


def _arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def normalize_messages(messages: Iterable[ChatMessage | dict[str, Any]]) -> list[ChatMessage]:
    normalized: list[ChatMessage] = []
    for item in messages:
        if isinstance(item, ChatMessage):
            normalized.append(item)
            continue
        if not isinstance(item, dict):
            raise InvalidRequest("message d'historique invalide")
        payload = {key: item[key] for key in _ALLOWED_MESSAGE_FIELDS if key in item}
        for alias, field in _MESSAGE_FIELD_ALIASES.items():
            if field not in payload and alias in item:
                payload[field] = item[alias]
        calls = payload.get("tool_calls")
        if calls is None:
            payload.pop("tool_calls", None)
        elif isinstance(calls, list):
            payload["tool_calls"] = [
                {
                    key: call[key]
                    for key in _ALLOWED_TOOL_CALL_FIELDS
                    if isinstance(call, dict) and key in call
                }
                for call in calls
                if isinstance(call, dict)
            ]
        for call in payload.get("tool_calls", []):
            if "arguments" in call:
                call["arguments"] = _arguments(call["arguments"])
        try:
            normalized.append(ChatMessage.model_validate(payload))
        except ValidationError as error:
            raise InvalidRequest("message d'historique invalide") from error
    return normalized


def normalize_tool_calls(calls: Iterable[ToolCall | dict[str, Any]]) -> list[ToolCall]:
    normalized: list[ToolCall] = []
    for call in calls:
        if isinstance(call, ToolCall):
            normalized.append(call)
            continue
        payload = {key: call[key] for key in _ALLOWED_TOOL_CALL_FIELDS if key in call}
        payload["arguments"] = _arguments(payload.get("arguments"))
        try:
            normalized.append(ToolCall.model_validate(payload))
        except ValidationError as error:
            raise InvalidRequest("appel d'outil invalide") from error
    return normalized
