from __future__ import annotations

from typing import Any

from providers import ToolCall, ToolDefinition

from agent_core import (
    AgentLoop,
    ModelResponse,
    ToolContext,
    default_registry,
)


def _complete_brief_call(call_id: str = "brief") -> ModelResponse:
    return ModelResponse(
        text="",
        tool_calls=[
            ToolCall(
                id=call_id,
                name="update_brief",
                arguments={
                    "problem": "Un problème",
                    "customer": "Des clients",
                    "valueProposition": "Une promesse",
                    "revenueModel": "Marge",
                    "costStructure": "Achats",
                    "geography": "Abidjan",
                },
            )
        ],
    )


async def test_loop_executes_tool_then_returns_text() -> None:
    responses = [
        _complete_brief_call(),
        ModelResponse(text="Le brief est complet."),
    ]
    calls: list[list[ToolDefinition]] = []

    async def chat(messages: list[Any], tools: list[ToolDefinition]) -> ModelResponse:
        calls.append(tools)
        return responses.pop(0)

    loop = AgentLoop(default_registry())
    result = await loop.run(
        [],
        role="interviewer",
        state="interviewing",
        chat=chat,
        context=ToolContext(project_id="p", state="interviewing"),
    )
    assert result.status == "text"
    assert result.text == "Le brief est complet."
    assert result.state == "brief_validated"
    assert result.tool_events[0].ok
    assert any(tool.name == "update_brief" for tool in calls[0])


async def test_loop_sends_invalid_arguments_back_to_model() -> None:
    responses = [
        ModelResponse(
            text="",
            tool_calls=[ToolCall(id="bad", name="update_brief", arguments={"oops": 1})],
        ),
        _complete_brief_call("good"),
        ModelResponse(text="Corrigé."),
    ]

    async def chat(messages: list[Any], tools: list[ToolDefinition]) -> ModelResponse:
        return responses.pop(0)

    result = await AgentLoop(default_registry()).run(
        [],
        role="interviewer",
        state="interviewing",
        chat=chat,
        context=ToolContext(project_id="p", state="interviewing"),
    )
    assert result.status == "text"
    assert result.tool_events[0].error is not None
    assert result.tool_events[0].error["code"] == "invalid_arguments"
    assert result.tool_events[1].ok


async def test_ask_permission_pauses_then_resumes() -> None:
    search_call = ToolCall(id="web-1", name="web_search", arguments={"query": "marché"})
    responses = [
        ModelResponse(text="", tool_calls=[search_call]),
        ModelResponse(text="Voici le contexte."),
    ]

    async def chat(messages: list[Any], tools: list[ToolDefinition]) -> ModelResponse:
        return responses.pop(0)

    context = ToolContext(
        project_id="p",
        state="results_ready",
        search=lambda query, limit: [
            {"title": "Marché", "url": "https://example.test", "content": "Donnée"}
        ],
    )
    loop = AgentLoop(default_registry())
    paused = await loop.run(
        [],
        role="narrator",
        state="results_ready",
        chat=chat,
        context=context,
    )
    assert paused.status == "permission_required"
    assert paused.pending_permissions[0].tool == "web_search"

    resumed = await loop.run(
        paused.messages,
        role="narrator",
        state=paused.state,
        chat=chat,
        context=context,
        approvals={"web-1"},
    )
    assert resumed.status == "text"
    assert resumed.text == "Voici le contexte."
    assert any(event.tool == "web_search" and event.ok for event in resumed.tool_events)


async def test_denied_tool_is_not_executed() -> None:
    executed: list[str] = []

    def search(query: str, limit: int) -> list[dict[str, Any]]:
        executed.append(query)
        return []

    async def chat(messages: list[Any], tools: list[ToolDefinition]) -> ModelResponse:
        return ModelResponse(
            text="",
            tool_calls=[
                ToolCall(id="web-2", name="web_search", arguments={"query": "test"})
            ],
        )

    result = await AgentLoop(default_registry()).run(
        [],
        role="narrator",
        state="results_ready",
        chat=chat,
        context=ToolContext(project_id="p", state="results_ready", search=search),
        decisions={"web_search": "deny"},
    )
    assert result.status == "permission_denied"
    assert executed == []


async def test_iteration_limit() -> None:
    async def chat(messages: list[Any], tools: list[ToolDefinition]) -> ModelResponse:
        return ModelResponse(
            text="",
            tool_calls=[
                ToolCall(
                    id="brief",
                    name="update_brief",
                    arguments={"problem": "Encore"},
                )
            ],
        )

    result = await AgentLoop(default_registry(), max_iterations=2).run(
        [],
        role="interviewer",
        state="interviewing",
        chat=chat,
        context=ToolContext(project_id="p", state="interviewing"),
    )
    assert result.status == "max_iterations"
    assert len(result.tool_events) == 2
