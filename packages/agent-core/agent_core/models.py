from __future__ import annotations

from typing import Any, Literal

from providers import ChatMessage, ToolCall
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

JourneyStateName = Literal[
    "idea",
    "interviewing",
    "brief_draft",
    "brief_validated",
    "hypotheses_set",
    "simulating",
    "results_ready",
    "narrating",
    "done",
]

AgentRoleName = Literal["interviewer", "modeler", "narrator", "delegate", "coder"]
PermissionMode = Literal["allow", "ask", "deny"]
TurnStatus = Literal[
    "text",
    "permission_required",
    "requires_review",
    "permission_denied",
    "tool_error",
    "max_iterations",
]


class AgentModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


BRIEF_REQUIRED_FIELDS = (
    "problem",
    "customer",
    "value_proposition",
    "revenue_model",
    "cost_structure",
    "geography",
)


class BriefDraft(AgentModel):
    problem: str | None = None
    customer: str | None = None
    value_proposition: str | None = None
    revenue_model: str | None = None
    cost_structure: str | None = None
    geography: str | None = None
    competitors: str | None = None
    constraints: str | None = None
    key_assumptions: list[str] = Field(default_factory=list)
    currency: str | None = None
    horizon_months: int | None = Field(default=None, ge=1, le=120)
    notes: str | None = None

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        for name in BRIEF_REQUIRED_FIELDS:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                missing.append(to_camel(name))
        return missing

    def complete(self) -> bool:
        return not self.missing_fields()


class BriefContent(BriefDraft):
    problem: str = Field(min_length=1, max_length=4000)
    customer: str = Field(min_length=1, max_length=4000)
    value_proposition: str = Field(min_length=1, max_length=4000)
    revenue_model: str = Field(min_length=1, max_length=4000)
    cost_structure: str = Field(min_length=1, max_length=4000)
    geography: str = Field(min_length=1, max_length=200)


class UpdateBriefInput(BriefDraft):
    pass


class ModelResponse(AgentModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: dict[str, Any] | None = None
    provider: str | None = None
    model: str | None = None
    finish_reason: str | None = None


class PendingPermission(AgentModel):
    tool: str
    call_id: str
    decision: PermissionMode
    reason: str


class ToolEvent(AgentModel):
    call_id: str
    tool: str
    ok: bool
    result: Any = None
    error: dict[str, Any] | None = None
    requires_review: bool = False


class TurnResult(AgentModel):
    status: TurnStatus
    role: AgentRoleName
    state: JourneyStateName
    text: str = ""
    messages: list[ChatMessage] = Field(default_factory=list)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    pending_permissions: list[PendingPermission] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
