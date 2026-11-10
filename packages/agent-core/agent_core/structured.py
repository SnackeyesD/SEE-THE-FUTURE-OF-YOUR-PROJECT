from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from providers import ChatMessage
from pydantic import BaseModel, ValidationError

from .errors import StructuredOutputError

T = TypeVar("T", bound=BaseModel)
StructuredCall = Callable[[list[ChatMessage]], Awaitable[str]]

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_json(text: str) -> Any:
    candidates: list[str] = []
    for match in _FENCE.finditer(text):
        candidates.append(match.group(1).strip())
    stripped = text.strip()
    if stripped:
        candidates.append(stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if 0 <= start < end:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise StructuredOutputError(
        "aucun JSON valide dans la sortie du modèle",
        details={"preview": text[:500]},
    )


def parse_structured(text: str, schema: type[T]) -> T:
    payload = extract_json(text)
    if not isinstance(payload, dict):
        raise StructuredOutputError(
            "la sortie structurée doit être un objet JSON",
            details={"type": type(payload).__name__},
        )
    try:
        return schema.model_validate(payload)
    except ValidationError as error:
        raise StructuredOutputError(
            "la sortie structurée ne respecte pas le schéma",
            details=error.errors(include_url=False),
        ) from error


async def run_structured(
    call: StructuredCall,
    messages: list[ChatMessage],
    schema: type[T],
    *,
    max_attempts: int = 2,
) -> tuple[T, str]:
    if max_attempts < 1:
        raise ValueError("max_attempts doit être supérieur ou égal à 1")
    conversation = list(messages)
    last_error: StructuredOutputError | None = None
    for attempt in range(1, max_attempts + 1):
        text = await call(conversation)
        try:
            return parse_structured(text, schema), text
        except StructuredOutputError as error:
            last_error = error
            if attempt == max_attempts:
                break
            conversation = [
                *conversation,
                ChatMessage(role="assistant", content=text),
                ChatMessage(
                    role="user",
                    content=(
                        "La sortie précédente est invalide. Corrige uniquement le JSON pour "
                        f"respecter le schéma {schema.__name__}. Erreur: {error.message}. "
                        f"Détails: {json.dumps(error.details, ensure_ascii=False)}"
                    ),
                ),
            ]
    assert last_error is not None
    raise StructuredOutputError(
        f"échec de la sortie structurée après {max_attempts} tentative(s)",
        details=last_error.details,
    )
