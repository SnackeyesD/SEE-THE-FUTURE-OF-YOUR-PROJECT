from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import BriefContent

_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    idea: str
    brief: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvalCase:
        brief = BriefContent.model_validate(payload["brief"])
        return cls(
            id=str(payload["id"]),
            idea=str(payload["idea"]),
            brief=brief.model_dump(by_alias=True, exclude_none=True),
        )


@dataclass(frozen=True, slots=True)
class EvalResult:
    case_id: str
    brief_complete: bool
    tools: tuple[str, ...]
    invented_numbers: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.brief_complete and not self.invented_numbers


def load_cases(path: Path | str) -> list[EvalCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("le jeu d'évaluation doit être une liste")
    return [EvalCase.from_dict(item) for item in payload]


def number_tokens(text: str) -> list[str]:
    return [token.replace(",", ".") for token in _NUMBER.findall(text)]


def invented_numbers(text: str, allowed: set[float]) -> list[str]:
    invented: list[str] = []
    for token in number_tokens(text):
        value = float(token)
        tolerance = max(0.01, abs(value) * 0.001)
        if not any(abs(value - candidate) <= tolerance for candidate in allowed):
            invented.append(token)
    return invented


def evaluate_case(
    case: EvalCase,
    *,
    brief: dict[str, Any] | None,
    tools: list[str],
    final_text: str,
    allowed_numbers: set[float],
) -> EvalResult:
    complete = False
    if brief is not None:
        try:
            BriefContent.model_validate(brief)
            complete = True
        except ValueError:
            complete = False
    return EvalResult(
        case_id=case.id,
        brief_complete=complete,
        tools=tuple(tools),
        invented_numbers=tuple(invented_numbers(final_text, allowed_numbers)),
    )
