from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from providers import ChatMessage, ToolCall, ToolDefinition

from agent_core import AgentLoop, ModelResponse, ToolContext, default_registry
from agent_core.eval import evaluate_case, load_cases

SCENARIO = {
    "name": "Évaluation",
    "currency": "XOF",
    "horizonMonths": 12,
    "assumptions": {
        "initial_cash": {"value": 1_000_000, "source": "test"},
        "unit_price": {"value": 500, "source": "test"},
        "unit_cost": {"value": 300, "source": "test"},
        "fixed_costs_monthly": {"value": 100_000, "source": "test"},
        "demand_mean_monthly": {"value": 1_500, "source": "test"},
    },
}


async def _run_case(case: Any, seed: int) -> Any:
    context = ToolContext(project_id=case.id, state="interviewing")

    def save_brief(content: dict[str, Any], status: str) -> None:
        context.brief = content

    def save_scenario(content: dict[str, Any]) -> None:
        context.scenario = content

    def save_run(result: Any, scenario_id: str | None) -> None:
        context.latest_result = result.model_dump(by_alias=True, mode="json")

    context.save_brief = save_brief
    context.save_scenario = save_scenario
    context.save_run = save_run
    step = 0
    tools_seen: list[str] = []
    final_result: dict[str, Any] = {}

    async def chat(messages: list[ChatMessage], tools: list[ToolDefinition]) -> ModelResponse:
        nonlocal step
        step += 1
        if step == 1:
            return ModelResponse(
                tool_calls=[
                    ToolCall(id="brief", name="update_brief", arguments=case.brief)
                ]
            )
        if step == 2:
            return ModelResponse(
                tool_calls=[
                    ToolCall(id="hyp", name="set_hypotheses", arguments=SCENARIO)
                ]
            )
        if step == 3:
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="run",
                        name="run_simulation",
                        arguments={"runs": 100, "seed": seed},
                    )
                ]
            )
        last_tool = next(
            (message for message in reversed(messages) if message.role == "tool"), None
        )
        if last_tool is not None:
            payload = json.loads(last_tool.content)
            if payload.get("tool") == "run_simulation":
                final_result.update(payload["result"]["metrics"])
        return ModelResponse(
            text=(
                "Bénéfice moyen simulé : "
                f"{final_result.get('meanProfit', 0):.2f}, "
                f"médiane : {final_result.get('p50', 0):.2f}."
            )
        )

    result = await AgentLoop(default_registry()).run(
        [],
        role="interviewer",
        state="interviewing",
        chat=chat,
        context=context,
    )
    tools_seen = [event.tool for event in result.tool_events]
    allowed = {float(value) for value in final_result.values()}
    evaluation = evaluate_case(
        case,
        brief=context.brief,
        tools=tools_seen,
        final_text=result.text,
        allowed_numbers=allowed,
    )
    return result, evaluation


async def test_eval_suite_is_reproducible() -> None:
    path = Path(__file__).parent / "eval" / "briefs.json"
    cases = load_cases(path)
    assert 20 <= len(cases) <= 50
    for index, case in enumerate(cases):
        result, evaluation = await _run_case(case, seed=index)
        assert result.status == "text", case.id
        assert result.state == "results_ready", case.id
        assert evaluation.brief_complete, case.id
        assert set(evaluation.tools) == {
            "update_brief",
            "set_hypotheses",
            "run_simulation",
        }, case.id
        assert not evaluation.invented_numbers, (case.id, evaluation.invented_numbers)


def test_eval_flags_invented_numbers() -> None:
    path = Path(__file__).parent / "eval" / "briefs.json"
    case = load_cases(path)[0]
    evaluation = evaluate_case(
        case,
        brief=case.brief,
        tools=["update_brief"],
        final_text="Le bénéfice sera de 9876543.21.",
        allowed_numbers={1000.0},
    )
    assert evaluation.invented_numbers == ("9876543.21",)
    assert not evaluation.passed
