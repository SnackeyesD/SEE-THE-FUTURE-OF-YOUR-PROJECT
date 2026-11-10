from __future__ import annotations

import asyncio
from typing import Any

from providers import (
    MATRIX_VERSION,
    BudgetExceeded,
    ChatRequest,
    InvalidRequest,
    ProviderError,
    capabilities_for,
    catalog,
    create_adapter,
    estimate_cost_micros,
    estimate_tokens,
    estimate_usage,
)
from pydantic import ValidationError
from see_storage import ProjectStore, StorageValidationError

DEFAULT_MAX_TOKENS = 4096


def provider_catalog(_: ProjectStore) -> dict[str, Any]:
    return {"providers": catalog(), "capabilitiesVersion": MATRIX_VERSION}


def _profile_dict(profile: Any) -> dict[str, Any]:
    return profile.to_dict()


def _profile_payload(params: dict[str, Any]) -> dict[str, Any]:
    profile = params.get("profile")
    if not isinstance(profile, dict):
        raise InvalidRequest("profil fournisseur manquant")
    provider = profile.get("provider")
    project_id = profile.get("projectId")
    if not isinstance(provider, str) or not provider.strip():
        raise InvalidRequest("profil fournisseur sans fournisseur")
    if not isinstance(project_id, str) or not project_id.strip():
        raise InvalidRequest("profil fournisseur sans projet")
    return profile


def _capabilities_payload(capabilities: Any) -> dict[str, Any]:
    return capabilities.to_dict()


def _model_payload(model: Any) -> dict[str, Any]:
    return {
        "id": model.id,
        "name": model.name,
        "capabilities": _capabilities_payload(model.capabilities),
    }


def _usage_payload(usage: Any) -> dict[str, Any]:
    return usage.to_dict()


def budget_result(store: ProjectStore, project_id: str) -> dict[str, Any]:
    budget = store.budgets.get(project_id)
    summary = store.usage.summary(project_id)
    return {
        "projectId": project_id,
        "limitMicros": budget.limit_micros if budget is not None else 0,
        "spentMicros": summary["costMicros"],
        "createdAt": budget.created_at if budget is not None else None,
        "updatedAt": budget.updated_at if budget is not None else None,
    }


def _estimate_request_cost(
    request: ChatRequest,
    *,
    provider: str,
) -> int:
    capabilities = capabilities_for(provider, request.model)
    input_tokens = sum(estimate_tokens(message.content) for message in request.messages)
    output_tokens = request.max_tokens or DEFAULT_MAX_TOKENS
    return estimate_cost_micros(capabilities, input_tokens, output_tokens)


def assert_budget(
    store: ProjectStore,
    project_id: str,
    *,
    provider: str,
    request: ChatRequest,
) -> dict[str, Any]:
    budget = store.budgets.get(project_id)
    if budget is None or budget.limit_micros <= 0:
        return {}
    spent = store.usage.summary(project_id)["costMicros"]
    estimated = _estimate_request_cost(request, provider=provider)
    if spent + estimated > budget.limit_micros:
        raise BudgetExceeded(
            "plafond de dépense du projet atteint",
            provider=provider,
            details={
                "limitMicros": budget.limit_micros,
                "spentMicros": spent,
                "estimatedMicros": estimated,
            },
        )
    return {}


def _adapter(profile: dict[str, Any], api_key: str | None) -> Any:
    return create_adapter(
        str(profile["provider"]),
        base_url=profile.get("baseUrl"),
        api_key=api_key,
    )


def list_profiles(store: ProjectStore, project_id: str) -> dict[str, Any]:
    store.projects.require(project_id)
    return {"profiles": [profile.to_dict() for profile in store.provider_profiles.list(project_id)]}


def save_profile(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    provider = _required_text(params, "provider")
    model = _optional_text(params, "model")
    capabilities = params.get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        capabilities = capabilities_for(provider, model or "").to_dict()
    profile = store.provider_profiles.upsert(
        project_id,
        _required_text(params, "name"),
        provider,
        base_url=_optional_text(params, "baseUrl"),
        model=model,
        keychain_ref=_optional_text(params, "keychainRef"),
        capabilities=capabilities,
    )
    return {"profile": _profile_dict(profile)}


def delete_profile(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    return {"deleted": store.provider_profiles.delete(_required_text(params, "profileId"))}


def list_roles(store: ProjectStore, project_id: str) -> dict[str, Any]:
    store.projects.require(project_id)
    return {"assignments": [item.to_dict() for item in store.roles.list(project_id)]}


def set_role(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    assignment = store.roles.set(
        _required_text(params, "projectId"),
        _required_text(params, "role"),
        _required_text(params, "providerProfileId"),
        _required_text(params, "model"),
    )
    return {"assignment": assignment.to_dict()}


def delete_role(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    deleted = store.roles.delete(
        _required_text(params, "projectId"), _required_text(params, "role")
    )
    return {"deleted": deleted}


def list_usage(store: ProjectStore, project_id: str) -> dict[str, Any]:
    store.projects.require(project_id)
    summary = store.usage.summary(project_id)
    return {
        "entries": [entry.to_dict() for entry in store.usage.list(project_id)],
        "inputTokens": summary["inputTokens"],
        "outputTokens": summary["outputTokens"],
        "costMicros": summary["costMicros"],
    }


def get_budget(store: ProjectStore, project_id: str) -> dict[str, Any]:
    store.projects.require(project_id)
    return budget_result(store, project_id)


def set_budget(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    limit = params.get("limitMicros")
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise StorageValidationError("limitMicros doit être un entier")
    store.budgets.set(project_id, limit)
    return budget_result(store, project_id)


def delete_budget(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    return {"deleted": store.budgets.delete(project_id)}


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


def _json_object(params: dict[str, Any], key: str) -> dict[str, Any]:
    value = params.get(key)
    if not isinstance(value, dict):
        raise InvalidRequest(f"{key} doit être un objet")
    return value


def _chat_request(params: dict[str, Any]) -> ChatRequest:
    try:
        return ChatRequest.model_validate(_json_object(params, "request"))
    except ValidationError as exc:
        raise InvalidRequest("requête de conversation invalide") from exc


async def test_connection(profile: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    adapter = _adapter(profile, api_key)
    try:
        result = await adapter.test_connection()
    finally:
        await adapter.aclose()
    return {
        "ok": result.ok,
        "message": result.message,
        "latencyMs": result.latency_ms,
        "models": [_model_payload(model) for model in result.models],
    }


async def list_models(profile: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    adapter = _adapter(profile, api_key)
    try:
        models = await adapter.list_models()
    finally:
        await adapter.aclose()
    return {"models": [_model_payload(model) for model in models]}


async def run_chat(
    store: ProjectStore,
    params: dict[str, Any],
) -> dict[str, Any]:
    project_id = _required_text(params, "projectId")
    store.projects.require(project_id)
    profile = _profile_payload(params)
    if profile["projectId"] != project_id:
        raise InvalidRequest("le profil fournisseur appartient à un autre projet")
    request = _chat_request(params)
    provider = str(profile["provider"])
    assert_budget(store, project_id, provider=provider, request=request)
    api_key = params.get("apiKey")
    if api_key is not None and not isinstance(api_key, str):
        raise InvalidRequest("apiKey doit être une chaîne")

    adapter = _adapter(profile, api_key)
    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    fallbacks: list[dict[str, str]] = []
    usage = None
    finish_reason = None
    try:
        async for event in adapter.chat(request):
            if event.type == "text_delta" and event.text:
                text_parts.append(event.text)
            elif event.type == "reasoning_delta" and event.text:
                reasoning_parts.append(event.text)
            elif event.type == "tool_call" and event.tool_call is not None:
                tool_calls.append(event.tool_call.to_dict())
            elif event.type == "usage" and event.usage is not None:
                usage = event.usage
            elif event.type == "fallback":
                fallbacks.append(
                    {
                        "provider": event.provider or provider,
                        "reason": event.text or event.reason or "fallback",
                    }
                )
            elif event.type == "done":
                finish_reason = event.finish_reason
    finally:
        await adapter.aclose()

    capabilities = capabilities_for(provider, request.model)
    text = "".join(text_parts)
    if usage is None:
        input_tokens = sum(estimate_tokens(message.content) for message in request.messages)
        usage = estimate_usage(
            capabilities,
            input_tokens=input_tokens,
            output_tokens=estimate_tokens(text),
        )
    elif usage.cost_micros == 0:
        cost = estimate_cost_micros(capabilities, usage.input_tokens, usage.output_tokens)
        usage = usage.model_copy(update={"cost_micros": cost})

    store.usage.add(
        project_id,
        "chat",
        provider_profile_id=profile.get("id"),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_micros=usage.cost_micros,
        metadata={
            "provider": provider,
            "model": request.model,
            "fallbackCount": len(fallbacks),
            "finishReason": finish_reason,
        },
    )

    result: dict[str, Any] = {
        "text": text,
        "toolCalls": tool_calls,
        "usage": _usage_payload(usage),
        "provider": provider,
        "model": request.model,
        "fallbacks": fallbacks,
        "budget": budget_result(store, project_id),
    }
    if reasoning_parts:
        result["reasoning"] = "".join(reasoning_parts)
    if finish_reason is not None:
        result["finishReason"] = finish_reason
    return result


def test(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_payload(params)
    api_key = params.get("apiKey")
    if api_key is not None and not isinstance(api_key, str):
        raise InvalidRequest("apiKey doit être une chaîne")
    return asyncio.run(test_connection(profile, api_key))


def models(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    profile = _profile_payload(params)
    api_key = params.get("apiKey")
    if api_key is not None and not isinstance(api_key, str):
        raise InvalidRequest("apiKey doit être une chaîne")
    return asyncio.run(list_models(profile, api_key))


def chat(store: ProjectStore, params: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(run_chat(store, params))


__all__ = [
    "ProviderError",
    "assert_budget",
    "budget_result",
    "chat",
    "delete_budget",
    "delete_profile",
    "delete_role",
    "get_budget",
    "list_models",
    "list_profiles",
    "list_roles",
    "list_usage",
    "models",
    "provider_catalog",
    "run_chat",
    "save_profile",
    "set_budget",
    "set_role",
    "test",
    "test_connection",
]
