from __future__ import annotations

import pytest

from providers import ChatMessage, InvalidRequest, normalize_messages


def test_removes_provider_specific_fields_before_reinjection() -> None:
    messages = normalize_messages(
        [
            {
                "role": "assistant",
                "content": "Bonjour",
                "reasoning_details": [{"type": "reasoning.text", "text": "secret"}],
                "cache_control": {"type": "ephemeral"},
                "provider_metadata": {"id": "x"},
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "set_hypotheses",
                        "arguments": '{"price": 10}',
                        "provider_extra": True,
                    }
                ],
            }
        ]
    )
    assert messages == [
        ChatMessage(
            role="assistant",
            content="Bonjour",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "set_hypotheses",
                    "arguments": {"price": 10},
                }
            ],
        )
    ]


def test_rejects_invalid_history() -> None:
    with pytest.raises(InvalidRequest):
        normalize_messages([{"role": "unknown", "content": "x"}])
    with pytest.raises(InvalidRequest):
        normalize_messages(["pas un message"])
