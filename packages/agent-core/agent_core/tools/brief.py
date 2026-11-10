from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..errors import ToolError
from ..models import AgentModel, BriefContent, BriefDraft, UpdateBriefInput
from .base import ToolContext, ToolExecution, ToolSpec


class BriefOutput(AgentModel):
    brief: dict[str, Any]
    complete: bool
    missing_fields: list[str]


def update_brief(payload: UpdateBriefInput, context: ToolContext) -> ToolExecution:
    merged: dict[str, Any] = dict(context.brief or {})
    patch = payload.model_dump(by_alias=True, exclude_unset=True, exclude_none=True)
    merged.update(patch)
    try:
        draft = BriefDraft.model_validate(merged)
    except ValidationError as error:
        raise ToolError(
            "le brief contient des champs invalides",
            code="invalid_brief",
            details=error.errors(include_url=False),
        ) from error
    missing = draft.missing_fields()
    status = "draft"
    if not missing:
        BriefContent.model_validate(draft.model_dump(by_alias=True))
        status = "validated"
    clean = draft.model_dump(by_alias=True, exclude_none=True)
    context.brief = clean
    if context.save_brief is not None:
        context.save_brief(clean, status)
    target = "brief_validated" if status == "validated" else "brief_draft"
    return ToolExecution(
        result={
            "brief": draft.model_dump(by_alias=True, exclude_none=True),
            "complete": not missing,
            "missingFields": missing,
        },
        state_path=(target,),
    )


SPEC = ToolSpec(
    name="update_brief",
    description=(
        "Écrit ou modifie les champs du brief du projet. Envoie uniquement les champs "
        "confirmés par l'utilisateur. Retourne les champs encore manquants."
    ),
    input_model=UpdateBriefInput,
    output_model=BriefOutput,
    handler=update_brief,
    default_permission="allow",
)
