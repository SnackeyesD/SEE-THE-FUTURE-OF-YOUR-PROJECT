from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from agent_core import StructuredOutputError, parse_structured, run_structured


class Payload(BaseModel):
    answer: str
    score: int


def test_parse_fenced_json() -> None:
    parsed = parse_structured('```json\n{"answer":"ok","score":2}\n```', Payload)
    assert parsed.answer == "ok"
    assert parsed.score == 2


def test_parse_json_surrounded_by_text() -> None:
    parsed = parse_structured('Voici: {"answer":"ok","score":2} merci', Payload)
    assert parsed.score == 2


def test_parse_invalid_raises() -> None:
    with pytest.raises(StructuredOutputError):
        parse_structured("pas de json", Payload)


async def test_repair_succeeds_on_second_attempt() -> None:
    calls: list[int] = []

    async def call(messages: list[Any]) -> str:
        calls.append(len(messages))
        if len(calls) == 1:
            return '{"answer":"ok","score":"bad"}'
        return '{"answer":"ok","score":3}'

    parsed, raw = await run_structured(
        call, [], Payload, max_attempts=2
    )
    assert parsed.score == 3
    assert raw == '{"answer":"ok","score":3}'
    assert len(calls) == 2


async def test_repair_fails_after_max_attempts() -> None:
    calls: list[int] = []

    async def call(messages: list[Any]) -> str:
        calls.append(len(messages))
        return '{"answer":"ok"}'

    with pytest.raises(StructuredOutputError):
        await run_structured(call, [], Payload, max_attempts=2)
    assert len(calls) == 2
