from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from providers import ChatMessage, ToolCall, ToolDefinition

from .errors import InvalidTransition
from .models import (
    AgentRoleName,
    JourneyStateName,
    ModelResponse,
    PendingPermission,
    PermissionMode,
    ToolEvent,
    TurnResult,
)
from .permissions import PermissionResolver
from .state_machine import apply_target
from .tools.base import ToolContext, ToolOutcome, ToolRegistry
from .trace import TraceRecorder

ChatFn = Callable[[list[ChatMessage], list[ToolDefinition]], Awaitable[ModelResponse]]


class AgentLoop:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        permissions: PermissionResolver | None = None,
        trace: TraceRecorder | None = None,
        max_iterations: int = 6,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations doit être supérieur ou égal à 1")
        self.registry = registry
        self.permissions = permissions or PermissionResolver()
        self.trace = trace or TraceRecorder()
        self.max_iterations = max_iterations

    async def run(
        self,
        messages: list[ChatMessage],
        *,
        role: AgentRoleName,
        state: JourneyStateName,
        chat: ChatFn,
        context: ToolContext,
        decisions: Mapping[str, PermissionMode] | None = None,
        approvals: set[str] | None = None,
    ) -> TurnResult:
        conversation = list(messages)
        approvals = approvals or set()
        tool_events: list[ToolEvent] = []
        usage: dict[str, int] = {}
        state_name: JourneyStateName = state
        text = ""

        pending = _pending_calls(conversation)
        if pending:
            status, state_name, pending_permissions, _ = self._resolve_pending(
                conversation,
                pending,
                state_name,
                context,
                decisions,
                approvals,
                tool_events,
            )
            if status is not None:
                return TurnResult(
                    status=status,
                    role=role,
                    state=state_name,
                    text="",
                    messages=conversation,
                    tool_events=tool_events,
                    pending_permissions=pending_permissions,
                    usage=usage,
                )

        for iteration in range(self.max_iterations):
            reference = self.trace.prompt_reference(conversation)
            self.trace.record("request", {"prompt": reference, "iteration": iteration}, role=role)
            try:
                response = await chat(conversation, self.registry.definitions())
            except Exception as error:
                self.trace.record(
                    "error",
                    {"message": str(error), "iteration": iteration},
                    role=role,
                )
                raise
            _merge_usage(usage, response.usage)
            self.trace.record(
                "response",
                {
                    "text": response.text,
                    "toolCalls": [call.name for call in response.tool_calls],
                    "provider": response.provider,
                    "model": response.model,
                    "finishReason": response.finish_reason,
                },
                role=role,
                duration_ms=self.trace.elapsed_ms(),
            )
            text = response.text or text
            conversation.append(
                ChatMessage(
                    role="assistant",
                    content=response.text,
                    tool_calls=response.tool_calls,
                )
            )
            if not response.tool_calls:
                return TurnResult(
                    status="text",
                    role=role,
                    state=state_name,
                    text=text,
                    messages=conversation,
                    tool_events=tool_events,
                    usage=usage,
                )

            for call in response.tool_calls:
                decision = self.permissions.resolve(call.name, decisions)
                if decision == "deny":
                    conversation.append(_tool_message(call, {"ok": False, "error": {
                        "code": "permission_denied",
                        "message": "outil refusé par la politique de permissions",
                    }}))
                    tool_events.append(
                        ToolEvent(
                            call_id=call.id,
                            tool=call.name,
                            ok=False,
                            error={
                                "code": "permission_denied",
                                "message": "outil refusé par la politique de permissions",
                            },
                        )
                    )
                    self.trace.record(
                        "permission", {"tool": call.name, "decision": "deny"}, role=role
                    )
                    return TurnResult(
                        status="permission_denied",
                        role=role,
                        state=state_name,
                        text=text,
                        messages=conversation,
                        tool_events=tool_events,
                        usage=usage,
                    )
                if decision == "ask" and not _approved(call, approvals):
                    pending_permissions = [
                        PendingPermission(
                            tool=call.name,
                            call_id=call.id,
                            decision="ask",
                            reason="cet outil demande une autorisation explicite",
                        )
                    ]
                    self.trace.record(
                        "permission", {"tool": call.name, "decision": "ask"}, role=role
                    )
                    return TurnResult(
                        status="permission_required",
                        role=role,
                        state=state_name,
                        text=text,
                        messages=conversation,
                        tool_events=tool_events,
                        pending_permissions=pending_permissions,
                        usage=usage,
                    )
                outcome = self.registry.execute(
                    call.name,
                    call.arguments,
                    context,
                    call_id=call.id,
                )
                state_name = self._apply_state(state_name, outcome, context)
                event = _tool_event(outcome)
                tool_events.append(event)
                self.trace.record(
                    "tool",
                    {
                        "tool": call.name,
                        "callId": call.id,
                        "ok": outcome.ok,
                        "error": outcome.error,
                    },
                    role=role,
                )
                conversation.append(_tool_message(call, _tool_payload(outcome)))
                if outcome.requires_review:
                    return TurnResult(
                        status="requires_review",
                        role=role,
                        state=state_name,
                        text=text,
                        messages=conversation,
                        tool_events=tool_events,
                        usage=usage,
                    )
                if not outcome.ok and outcome.error is not None:
                    continue

        self.trace.record("error", {"message": "limite d'itérations atteinte"}, role=role)
        return TurnResult(
            status="max_iterations",
            role=role,
            state=state_name,
            text=text,
            messages=conversation,
            tool_events=tool_events,
            usage=usage,
        )

    def _resolve_pending(
        self,
        conversation: list[ChatMessage],
        pending: list[ToolCall],
        state: JourneyStateName,
        context: ToolContext,
        decisions: Mapping[str, PermissionMode] | None,
        approvals: set[str],
        tool_events: list[ToolEvent],
    ) -> tuple[
        str | None,
        JourneyStateName,
        list[PendingPermission],
        ToolEvent | None,
    ]:
        state_name = state
        last_event: ToolEvent | None = None
        for call in pending:
            decision = self.permissions.resolve(call.name, decisions)
            if decision == "deny":
                conversation.append(
                    _tool_message(
                        call,
                        {
                            "ok": False,
                            "error": {
                                "code": "permission_denied",
                                "message": "outil refusé par la politique de permissions",
                            },
                        },
                    )
                )
                return "permission_denied", state_name, [], None
            if decision == "ask" and not _approved(call, approvals):
                return (
                    "permission_required",
                    state_name,
                    [
                        PendingPermission(
                            tool=call.name,
                            call_id=call.id,
                            decision="ask",
                            reason="cet outil demande une autorisation explicite",
                        )
                    ],
                    last_event,
                )
            outcome = self.registry.execute(
                call.name,
                call.arguments,
                context,
                call_id=call.id,
            )
            state_name = self._apply_state(state_name, outcome, context)
            last_event = _tool_event(outcome)
            tool_events.append(last_event)
            self.trace.record(
                "tool",
                {
                    "tool": call.name,
                    "callId": call.id,
                    "ok": outcome.ok,
                    "error": outcome.error,
                    "resumed": True,
                },
            )
            conversation.append(_tool_message(call, _tool_payload(outcome)))
            if outcome.requires_review:
                return "requires_review", state_name, [], last_event
        return None, state_name, [], last_event

    def _apply_state(
        self, current: JourneyStateName, outcome: ToolOutcome, context: ToolContext
    ) -> JourneyStateName:
        state = current
        for target in outcome.state_path:
            try:
                state = apply_target(state, target)
            except InvalidTransition:
                self.trace.record(
                    "error",
                    {
                        "message": "transition d'état refusée",
                        "current": state,
                        "target": target,
                    },
                )
                break
        context.state = state
        return state


def _approved(call: ToolCall, approvals: set[str]) -> bool:
    return call.id in approvals or call.name in approvals


def _pending_calls(messages: list[ChatMessage]) -> list[ToolCall]:
    assistant_index = None
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == "assistant" and messages[index].tool_calls:
            assistant_index = index
            break
    if assistant_index is None:
        return []
    answered = {
        message.tool_call_id
        for message in messages[assistant_index + 1 :]
        if message.role == "tool"
    }
    return [
        call for call in messages[assistant_index].tool_calls if call.id not in answered
    ]


def _tool_payload(outcome: ToolOutcome) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": outcome.ok, "tool": outcome.tool}
    if outcome.ok:
        payload["result"] = outcome.result
    else:
        payload["error"] = outcome.error
    if outcome.requires_review:
        payload["requiresReview"] = True
    return payload


def _tool_message(call: ToolCall, payload: dict[str, Any]) -> ChatMessage:
    return ChatMessage(
        role="tool",
        content=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        name=call.name,
        tool_call_id=call.id,
    )


def _tool_event(outcome: ToolOutcome) -> ToolEvent:
    return ToolEvent(
        call_id=outcome.call_id,
        tool=outcome.tool,
        ok=outcome.ok,
        result=outcome.result,
        error=outcome.error,
        requires_review=outcome.requires_review,
    )


def _merge_usage(total: dict[str, int], usage: dict[str, Any] | None) -> None:
    if not usage:
        return
    for key, value in usage.items():
        if isinstance(value, int) and not isinstance(value, bool):
            total[key] = total.get(key, 0) + value





