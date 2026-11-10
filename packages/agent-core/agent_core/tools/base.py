from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from providers import ToolDefinition
from pydantic import BaseModel, ValidationError

from ..errors import ToolError, UnknownTool
from ..models import JourneyStateName, PermissionMode

InputT = TypeVar("InputT", bound=BaseModel)
HandlerResult = Any


@dataclass(slots=True)
class ToolExecution:
    result: Any
    state_path: tuple[JourneyStateName, ...] = ()
    requires_review: bool = False


@dataclass(slots=True)
class ToolContext:
    project_id: str
    state: str
    brief: dict[str, Any] | None = None
    scenario: dict[str, Any] | None = None
    scenario_id: str | None = None
    scenarios: dict[str, dict[str, Any]] = field(default_factory=dict)
    latest_result: dict[str, Any] | None = None
    save_brief: Callable[[dict[str, Any], str], None] | None = None
    save_scenario: Callable[[dict[str, Any]], None] | None = None
    save_run: Callable[[Any, str | None], None] | None = None
    search: Callable[[str, int], list[dict[str, Any]]] | None = None
    benchmark: Callable[[str], dict[str, Any] | None] | None = None
    export: Callable[[str, str], None] | None = None
    export_path: str | None = None


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[Any, ToolContext], HandlerResult]
    output_model: type[BaseModel] | None = None
    default_permission: PermissionMode = "ask"
    always_ask: bool = False


@dataclass(slots=True)
class ToolOutcome:
    tool: str
    call_id: str
    ok: bool
    result: Any = None
    error: dict[str, Any] | None = None
    state_path: tuple[JourneyStateName, ...] = ()
    requires_review: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"outil déjà enregistré: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownTool(name)
        return tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name=spec.name,
                description=spec.description,
                parameters=spec.input_model.model_json_schema(by_alias=True),
            )
            for spec in self._tools.values()
        ]

    def default_permission(self, name: str) -> PermissionMode:
        return self.get(name).default_permission

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ToolContext,
        *,
        call_id: str = "",
        allowed: bool = True,
    ) -> ToolOutcome:
        try:
            spec = self.get(name)
        except UnknownTool as error:
            return ToolOutcome(
                tool=name,
                call_id=call_id,
                ok=False,
                error=error.to_dict(),
            )
        if not allowed:
            return ToolOutcome(
                tool=name,
                call_id=call_id,
                ok=False,
                error={
                    "code": "permission_denied",
                    "message": "outil refusé par la politique de permissions",
                },
            )
        try:
            payload = spec.input_model.model_validate(arguments)
        except ValidationError as error:
            return ToolOutcome(
                tool=name,
                call_id=call_id,
                ok=False,
                error={
                    "code": "invalid_arguments",
                    "message": "arguments invalides pour l'outil",
                    "details": error.errors(include_url=False),
                },
            )
        try:
            outcome = spec.handler(payload, context)
        except ToolError as error:
            return ToolOutcome(
                tool=name,
                call_id=call_id,
                ok=False,
                error=error.to_dict(),
            )
        except ValueError as error:
            return ToolOutcome(
                tool=name,
                call_id=call_id,
                ok=False,
                error={"code": "invalid_value", "message": str(error)},
            )
        execution = outcome if isinstance(outcome, ToolExecution) else ToolExecution(outcome)
        result = execution.result
        if isinstance(result, BaseModel):
            result = result.model_dump(by_alias=True, mode="json")
        if spec.output_model is not None:
            try:
                validated = spec.output_model.model_validate(result)
            except ValidationError as error:
                return ToolOutcome(
                    tool=name,
                    call_id=call_id,
                    ok=False,
                    error={
                        "code": "invalid_output",
                        "message": "sortie invalide pour l'outil",
                        "details": error.errors(include_url=False),
                    },
                )
            result = validated.model_dump(by_alias=True, mode="json")
        return ToolOutcome(
            tool=name,
            call_id=call_id,
            ok=True,
            result=result,
            state_path=execution.state_path,
            requires_review=execution.requires_review,
        )
