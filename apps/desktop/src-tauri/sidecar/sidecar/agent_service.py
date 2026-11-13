from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from agent_core import (
    AgentConfigurationError,
    AgentError,
    AgentLoop,
    AgentRoleName,
    PermissionResolver,
    ToolContext,
    TraceRecorder,
    default_registry,
    normalize_thread,
    role_for_state,
    system_message,
    trim_messages,
    validate_state,
)
from agent_core.tools.base import ToolRegistry
from providers import (
    ChatMessage,
    ChatRequest,
    capabilities_for,
    create_adapter,
    estimate_tokens,
    estimate_usage,
)
from see_storage import AgentSession, ProjectStore, StorageValidationError

from . import benchmark_service, provider_service

DEFAULT_MAX_ITERATIONS = 6
DEFAULT_CONTEXT_TOKENS = 24_000


def _required_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StorageValidationError(f"{key} doit être une chaîne non vide")
    return value.strip()


def _optional_text(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise StorageValidationError(f"{key} doit être une chaîne")
    return value.strip() or None


def _role(value: Any) -> AgentRoleName:
    if value is None:
        return "interviewer"
    if not isinstance(value, str):
        raise StorageValidationError("role doit être une chaîne")
    if value not in ("interviewer", "modeler", "narrator", "delegate", "coder"):
        raise StorageValidationError(f"rôle invalide: {value}")
    return value  # type: ignore[return-value]


def _validate_role(value: Any) -> AgentRoleName:
    return _role(value)


def _profile_payload(params: dict[str, Any]) -> dict[str, Any]:
    profile = params.get("profile")
    if not isinstance(profile, dict):
        raise AgentConfigurationError("profil fournisseur manquant pour le tour d'agent")
    if (
        not isinstance(profile.get("id"), str)
        or not isinstance(profile.get("projectId"), str)
        or not isinstance(profile.get("provider"), str)
    ):
        raise AgentConfigurationError("profil fournisseur invalide")
    return profile


def _session_payload(session: AgentSession | None, project_id: str) -> dict[str, Any]:
    if session is None:
        return {
            "id": None,
            "projectId": project_id,
            "state": "idea",
            "role": "interviewer",
            "thread": [],
            "createdAt": None,
            "updatedAt": None,
        }
    return {
        "id": session.id,
        "projectId": session.project_id,
        "state": session.state,
        "role": session.role,
        "thread": session.thread,
        "createdAt": session.created_at,
        "updatedAt": session.updated_at,
    }


def _resolved_role(store: ProjectStore, project_id: str, params: dict[str, Any]) -> AgentRoleName:
    explicit = params.get("role")
    session = store.agent_sessions.get(project_id)
    state = session.state if session is not None else "idea"
    return _validate_role(explicit) if explicit is not None else role_for_state(state)


def prepare(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    role = _resolved_role(store, project_id, params)
    assignment = store.roles.get(project_id, role)
    if assignment is None:
        raise AgentConfigurationError(
            f"aucun profil fournisseur associé au rôle {role}",
            details={"role": role},
        )
    profile = store.provider_profiles.get(assignment.provider_profile_id)
    if profile is None:
        raise AgentConfigurationError(
            "profil fournisseur du rôle introuvable",
            details={"role": role},
        )
    session = store.agent_sessions.get(project_id)
    return {
        "role": role,
        "model": assignment.model,
        "profile": profile.to_dict(),
        "state": session.state if session is not None else "idea",
    }


def state(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    return {"session": _session_payload(store.agent_sessions.get(project_id), project_id)}


def start(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    store.agent_sessions.delete(project_id)
    store.agent_trace.clear(project_id)
    session = store.agent_sessions.upsert(project_id, "interviewing", "interviewer", [])
    return {"session": _session_payload(session, project_id)}


def reset(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    store.agent_sessions.delete(project_id)
    store.agent_trace.clear(project_id)
    return {"session": _session_payload(None, project_id)}


def _permissions(store: ProjectStore, project_id: str) -> dict[str, Any]:
    entries = store.permissions.list(project_id)
    resolver = PermissionResolver()
    return {
        "permissions": [entry.to_dict() for entry in entries],
        "defaults": dict(resolver.defaults),
        "alwaysAsk": sorted(resolver.always_ask),
        "events": [event.to_dict() for event in store.permission_events.list(project_id)],
    }


def list_permissions(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    return _permissions(store, project_id)


def set_permission(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    tool = _required_text(params, "tool")
    decision = _required_text(params, "decision")
    scope = _optional_text(params, "scope") or "project"
    permission = store.permissions.set(project_id, tool, scope, decision)
    store.permission_events.add(
        project_id,
        tool,
        scope,
        permission.decision,
        reason=_optional_text(params, "reason"),
        actor="user",
    )
    return {"permission": permission.to_dict(), **_permissions(store, project_id)}


def delete_permission(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    deleted = store.permissions.delete(
        project_id,
        _required_text(params, "tool"),
        _optional_text(params, "scope") or "project",
    )
    return {"deleted": deleted, **_permissions(store, project_id)}


def list_tools(_store: ProjectStore, _params: dict[str, Any]) -> dict[str, Any]:
    registry = default_registry()
    resolver = PermissionResolver()
    tools: list[dict[str, Any]] = []
    for definition in registry.definitions():
        spec = registry.get(definition.name)
        tools.append(
            {
                "name": definition.name,
                "description": definition.description,
                "parameters": definition.parameters,
                "defaultPermission": resolver.default_for(definition.name),
                "alwaysAsk": spec.always_ask,
            }
        )
    return {"tools": tools}


def trace(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    limit = params.get("limit", 1000)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise StorageValidationError("limit doit être un entier positif")
    entries = store.agent_trace.list(project_id, limit=limit)
    return {
        "events": [entry.to_dict() for entry in entries],
        "count": store.agent_trace.count(project_id),
    }


def export_trace(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    destination = Path(_required_text(params, "destination")).expanduser()
    store.projects.require(project_id)
    entries = store.agent_trace.list(project_id, limit=100_000)
    payload = {
        "version": 1,
        "projectId": project_id,
        "exportedAt": entries[-1].created_at if entries else None,
        "events": [entry.to_dict() for entry in entries],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {"path": str(destination), "count": len(entries)}


def _thread_has_pending(thread: list[dict[str, Any]]) -> bool:
    for index in range(len(thread) - 1, -1, -1):
        message = thread[index]
        calls = message.get("tool_calls") or message.get("toolCalls")
        if message.get("role") == "assistant" and calls:
            answered = {
                item.get("tool_call_id") or item.get("toolCallId")
                for item in thread[index + 1 :]
                if item.get("role") == "tool"
            }
            return any(
                isinstance(call, dict) and call.get("id") not in answered for call in calls
            )
    return False


def _latest_result(
    store: ProjectStore, project_id: str
) -> tuple[dict[str, Any] | None, str | None]:
    runs = store.runs.list(project_id, limit=1)
    if not runs:
        return None, None
    run = runs[0]
    payload = run.result
    if payload is None and run.result_path is not None:
        try:
            payload = store.load_run_detail(project_id, run.id)
        except Exception:
            payload = None
    return payload, run.id


def _benchmark_hint(brief: dict[str, Any] | None, sector: str | None) -> dict[str, Any]:
    geography = str((brief or {}).get("geography") or "").lower()
    country = None
    region = None
    if "brazzaville" in geography:
        country, region = "CG", "Brazzaville"
    elif "bangui" in geography:
        country, region = "CF", "Bangui"
    elif "centrafrique" in geography or "rca" in geography:
        country = "CF"
    elif "congo" in geography:
        country = "CG"
    hint: dict[str, Any] = {
        "sector": sector if sector in {"retail"} else "retail",
        "subsector": "alimentation_generale",
        "allowFallback": True,
    }
    if country is not None:
        hint["country"] = country
    if region is not None:
        hint["region"] = region
    return hint


def _benchmark_indicator_names() -> list[str]:
    try:
        return benchmark_service.get_service().indicator_names()
    except Exception:  # noqa: BLE001 - les benchmarks restent optionnels
        return []


def _normalize_benchmark_indicator(value: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")


def _benchmark_query(
    payload: dict[str, Any],
    *,
    brief: dict[str, Any] | None,
    sector: str | None,
) -> dict[str, Any]:
    query = dict(payload)
    indicator = query.get("indicator")
    if isinstance(indicator, str):
        query["indicator"] = _normalize_benchmark_indicator(indicator)
    return {**query, **_benchmark_hint(brief, sector)}


def _benchmark_unavailable(
    reason: str, indicators: list[str]
) -> dict[str, Any]:
    message = f"{reason.rstrip('.')}."
    if indicators:
        message = f"{message} Indicateurs disponibles: {', '.join(indicators)}."
    return {"found": False, "record": None, "reason": message}


def _chat_messages(
    thread: list[dict[str, Any]],
    *,
    role: AgentRoleName,
    state: str,
    brief: dict[str, Any] | None,
    scenario: dict[str, Any] | None,
    latest_result: dict[str, Any] | None,
    benchmark_indicators: list[str] | None = None,
) -> list[ChatMessage]:
    system = system_message(
        role,
        state=validate_state(state),
        brief=brief,
        scenario=scenario,
        latest_result=latest_result,
        benchmark_indicators=benchmark_indicators,
    )
    return [system, *trim_messages(normalize_thread(thread), max_tokens=DEFAULT_CONTEXT_TOKENS)]


async def _chat_once(
    store: ProjectStore,
    project_id: str,
    profile: dict[str, Any],
    model: str,
    api_key: str | None,
    messages: list[ChatMessage],
    tools: list[Any],
) -> Any:
    from agent_core import ModelResponse

    provider = str(profile["provider"])
    request = ChatRequest(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=4096,
        tools=tools,
        response_format="text",
    )
    provider_service.assert_budget(
        store, project_id, provider=provider, request=request
    )
    adapter = create_adapter(
        provider,
        base_url=profile.get("baseUrl"),
        api_key=api_key,
    )
    text_parts: list[str] = []
    tool_calls: list[Any] = []
    usage = None
    finish_reason = None
    try:
        async for event in adapter.chat(request):
            if event.type == "text_delta" and event.text:
                text_parts.append(event.text)
            elif event.type == "tool_call" and event.tool_call is not None:
                tool_calls.append(event.tool_call)
            elif event.type == "usage" and event.usage is not None:
                usage = event.usage
            elif event.type == "done":
                finish_reason = event.finish_reason
    finally:
        await adapter.aclose()
    text = "".join(text_parts)
    capabilities = capabilities_for(provider, model)
    if usage is None:
        usage = estimate_usage(
            capabilities,
            input_tokens=sum(estimate_tokens(message.content) for message in messages),
            output_tokens=estimate_tokens(text),
        )
    store.usage.add(
        project_id,
        "agent",
        provider_profile_id=profile.get("id"),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_micros=usage.cost_micros,
        metadata={
            "provider": provider,
            "model": model,
            "toolCalls": [call.name for call in tool_calls],
        },
    )
    return ModelResponse(
        text=text,
        tool_calls=tool_calls,
        usage=usage.to_dict(),
        provider=provider,
        model=model,
        finish_reason=finish_reason,
    )


async def _run_turn(
    store: ProjectStore,
    params: dict[str, Any],
) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    project = store.projects.require(project_id)
    profile = _profile_payload(params)
    if profile["projectId"] != project_id:
        raise AgentConfigurationError("le profil fournisseur appartient à un autre projet")
    role = _resolved_role(store, project_id, params)
    assignment = store.roles.get(project_id, role)
    if assignment is None:
        raise AgentConfigurationError(
            f"aucun profil fournisseur associé au rôle {role}",
            details={"role": role},
        )
    if profile.get("id") != assignment.provider_profile_id:
        raise AgentConfigurationError(
            "le profil fournisseur ne correspond pas au rôle demandé",
            details={"role": role},
        )
    api_key = params.get("apiKey")
    if api_key is not None and not isinstance(api_key, str):
        raise AgentConfigurationError("apiKey doit être une chaîne")

    session = store.agent_sessions.get(project_id)
    if session is None:
        session = store.agent_sessions.upsert(project_id, "interviewing", role, [])
    state_name = validate_state(session.state)
    if state_name == "idea":
        state_name = "interviewing"

    message = _optional_text(params, "message")
    thread = list(session.thread)
    if message and not _thread_has_pending(thread):
        thread.append({"role": "user", "content": message})
    raw_approvals = params.get("approvals", [])
    if not isinstance(raw_approvals, list):
        raise StorageValidationError("approvals doit être une liste")
    approvals = {
        item for item in raw_approvals if isinstance(item, str) and item.strip()
    }

    brief_record = store.briefs.latest(project_id)
    brief = brief_record.content if brief_record is not None else None
    scenarios = store.scenarios.list(project_id, limit=1)
    scenario_record = scenarios[0] if scenarios else None
    scenario = scenario_record.scenario if scenario_record is not None else None
    latest_result, _ = _latest_result(store, project_id)

    context = ToolContext(
        project_id=project_id,
        state=state_name,
        brief=brief,
        scenario=scenario,
        scenario_id=scenario_record.id if scenario_record is not None else None,
        latest_result=latest_result,
    )

    def save_brief(content: dict[str, Any], status: str) -> None:
        store.briefs.add_version(project_id, content, status=status)
        context.brief = content

    def save_scenario(content: dict[str, Any]) -> None:
        record = store.scenarios.add(
            project_id, str(content.get("name", "Scénario")), "retail_depot", content
        )
        context.scenario = content
        context.scenario_id = record.id

    def save_run(result: Any, scenario_id: str | None) -> None:
        store.runs.add(
            project_id,
            result.engine_version,
            result.runs,
            result.metrics.model_dump(by_alias=True, mode="json"),
            scenario_id=scenario_id,
            seed=result.seed,
            duration_ms=result.duration_ms,
            result=result.to_dict(),
            run_id=result.run_id,
        )
        context.latest_result = result.to_dict()

    benchmark_indicators = _benchmark_indicator_names()

    def query_benchmark(payload: dict[str, Any]) -> dict[str, Any]:
        query = _benchmark_query(
            payload,
            brief=context.brief,
            sector=project.sector,
        )
        try:
            result = benchmark_service.get_service().lookup(query)
        except StorageValidationError as error:
            return _benchmark_unavailable(str(error), benchmark_indicators)
        if not result.get("found"):
            return _benchmark_unavailable(
                str(result.get("reason") or "aucune valeur de référence trouvée"),
                benchmark_indicators,
            )
        return result

    context.save_brief = save_brief
    context.save_scenario = save_scenario
    context.save_run = save_run
    context.benchmark = query_benchmark
    export_path = _optional_text(params, "exportPath")
    context.export_path = export_path
    if export_path is not None:
        context.export = lambda path, content: Path(path).write_text(
            content, encoding="utf-8"
        )

    registry: ToolRegistry = default_registry()
    resolver = PermissionResolver()
    decisions = {
        item.tool: item.decision
        for item in store.permissions.list(project_id)
        if item.scope == "project"
    }
    trace = TraceRecorder(
        turn=store.agent_trace.next_turn(project_id) - 1,
        sink=lambda event: store.agent_trace.add(
            project_id,
            event.to_dict(),
            session_id=session.id,
            turn=event.turn,
        ),
    )
    trace.begin_turn()

    messages = _chat_messages(
        thread,
        role=role,
        state=state_name,
        brief=context.brief,
        scenario=context.scenario,
        latest_result=context.latest_result,
        benchmark_indicators=benchmark_indicators,
    )

    async def chat(current: list[ChatMessage], tools: list[Any]) -> Any:
        return await _chat_once(
            store,
            project_id,
            profile,
            assignment.model,
            api_key,
            current,
            tools,
        )

    loop = AgentLoop(
        registry,
        permissions=resolver,
        trace=trace,
        max_iterations=_max_iterations(params),
    )
    result = await loop.run(
        messages,
        role=role,
        state=state_name,
        chat=chat,
        context=context,
        decisions=decisions,
        approvals=approvals,
    )
    stored_thread = [
        message.model_dump(by_alias=True, exclude_none=True)
        for message in result.messages
        if message.role != "system"
    ]
    session = store.agent_sessions.upsert(
        project_id, result.state, result.role, stored_thread
    )
    _log_permissions(store, project_id, result)
    return {
        "status": result.status,
        "role": result.role,
        "state": result.state,
        "text": result.text,
        "pendingPermissions": [
            permission.to_dict() for permission in result.pending_permissions
        ],
        "toolEvents": [event.to_dict() for event in result.tool_events],
        "usage": result.usage,
        "budget": provider_service.budget_result(store, project_id),
        "session": _session_payload(session, project_id),
        "projectId": project.id,
    }


def _max_iterations(params: dict[str, Any]) -> int:
    value = params.get("maxIterations", DEFAULT_MAX_ITERATIONS)
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 20:
        raise StorageValidationError("maxIterations doit être un entier entre 1 et 20")
    return value


def _log_permissions(store: ProjectStore, project_id: str, result: Any) -> None:
    for event in result.tool_events:
        decision = "allow"
        reason = None
        if event.error is not None:
            if event.error.get("code") == "permission_denied":
                decision = "deny"
                reason = "refusé par la politique"
            else:
                continue
        store.permission_events.add(
            project_id,
            event.tool,
            "project",
            decision,
            reason=reason,
            actor="agent",
        )
    for pending in result.pending_permissions:
        store.permission_events.add(
            project_id,
            pending.tool,
            "project",
            "ask",
            reason=pending.reason,
            actor="agent",
        )


def turn(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_run_turn(store, params))


__all__ = [
    "AgentError",
    "delete_permission",
    "export_trace",
    "list_permissions",
    "list_tools",
    "prepare",
    "reset",
    "set_permission",
    "start",
    "state",
    "trace",
    "turn",
]
