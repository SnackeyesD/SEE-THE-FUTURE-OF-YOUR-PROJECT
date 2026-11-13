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


def test_accepts_camel_case_tool_fields_from_persisted_thread() -> None:
    messages = normalize_messages(
        [
            {
                "role": "assistant",
                "content": "",
                "toolCalls": [
                    {
                        "id": "call_1",
                        "name": "update_brief",
                        "arguments": '{"problem": "livraison"}',
                        "provider_extra": True,
                    }
                ],
            },
            {
                "role": "tool",
                "content": '{"ok": true}',
                "name": "update_brief",
                "toolCallId": "call_1",
            },
        ]
    )
    assert messages == [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "update_brief",
                    "arguments": {"problem": "livraison"},
                }
            ],
        ),
        ChatMessage(
            role="tool",
            content='{"ok": true}',
            name="update_brief",
            tool_call_id="call_1",
        ),
    ]


def test_rejects_invalid_history() -> None:
    with pytest.raises(InvalidRequest):
        normalize_messages([{"role": "unknown", "content": "x"}])
    with pytest.raises(InvalidRequest):
        normalize_messages(["pas un message"])
