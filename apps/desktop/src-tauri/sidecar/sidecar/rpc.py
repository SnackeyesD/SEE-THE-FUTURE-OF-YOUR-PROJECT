from __future__ import annotations

import json
import logging
import os
import platform
import sys
import traceback
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from agent_core import AgentError
from providers import BudgetExceeded, ProviderError
from pydantic import ValidationError
from see_sandbox import ContractError
from see_storage import ProjectNotFound, StorageError, StorageValidationError

from . import __version__, agent_service, project_service, provider_service, sandbox_service
from .protocol_models import PROTOCOL_VERSION, JSONRPCRequest
from .storage_service import close_store, get_store

logger = logging.getLogger("see.sidecar")

MAX_MESSAGE_BYTES = 1024 * 1024

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
NOT_FOUND = -32001
STORAGE_ERROR = -32002
PROVIDER_ERROR = -32003
BUDGET_ERROR = -32004
AGENT_ERROR = -32005


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class RequestContext:
    def __init__(self, notifier: Callable[[str, dict[str, Any]], None]) -> None:
        self._notifier = notifier

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._notifier(method, params)


Handler = Callable[[dict[str, Any], RequestContext], dict[str, Any]]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def health(_: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return {
        "status": "ok",
        "sidecarVersion": __version__,
        "protocolVersion": PROTOCOL_VERSION,
        "pid": os.getpid(),
        "python": platform.python_version(),
    }


def ping(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    result: dict[str, Any] = {"pong": True, "timestamp": _now()}
    echo = params.get("echo")
    if isinstance(echo, str):
        result["echo"] = echo
    return result


def log(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    level = params.get("level", "info")
    message = str(params.get("message", ""))
    logger_method = getattr(logger, level, logger.info)
    logger_method(message)
    return {"logged": True}


def simulate(params: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    from engine import EngineError, Scenario, SimulationConfig
    from engine import simulate as run_simulation

    try:
        scenario = Scenario.model_validate(params.get("scenario"))
        config = SimulationConfig.model_validate(params.get("config") or {})
    except ValidationError as exc:
        raise RpcError(
            INVALID_PARAMS,
            "paramètres de simulation invalides",
            exc.errors(include_url=False),
        ) from exc

    progress_callback = None
    if params.get("progress") is True:
        progress_callback = lambda fraction: context.notify(  # noqa: E731
            "simulate.progress", {"progress": round(fraction, 4)}
        )

    try:
        result = run_simulation(scenario, config, progress=progress_callback)
    except EngineError as exc:
        raise RpcError(INVALID_PARAMS, str(exc)) from exc

    return result.to_dict()


def _storage_handler(handler: Handler) -> Handler:
    @wraps(handler)
    def wrapped(params: dict[str, Any], context: RequestContext) -> dict[str, Any]:
        try:
            return handler(params, context)
        except RpcError:
            raise
        except ProjectNotFound as exc:
            raise RpcError(NOT_FOUND, str(exc)) from exc
        except StorageValidationError as exc:
            raise RpcError(INVALID_PARAMS, str(exc)) from exc
        except StorageError as exc:
            raise RpcError(STORAGE_ERROR, str(exc)) from exc

    return wrapped


def _provider_handler(handler: Handler) -> Handler:
    @wraps(handler)
    def wrapped(params: dict[str, Any], context: RequestContext) -> dict[str, Any]:
        try:
            return handler(params, context)
        except RpcError:
            raise
        except BudgetExceeded as exc:
            raise RpcError(BUDGET_ERROR, exc.message, exc.to_dict()) from exc
        except ProviderError as exc:
            raise RpcError(PROVIDER_ERROR, exc.message, exc.to_dict()) from exc
        except ProjectNotFound as exc:
            raise RpcError(NOT_FOUND, str(exc)) from exc
        except StorageValidationError as exc:
            raise RpcError(INVALID_PARAMS, str(exc)) from exc
        except StorageError as exc:
            raise RpcError(STORAGE_ERROR, str(exc)) from exc

    return wrapped


def _agent_handler(handler: Handler) -> Handler:
    @wraps(handler)
    def wrapped(params: dict[str, Any], context: RequestContext) -> dict[str, Any]:
        try:
            return handler(params, context)
        except RpcError:
            raise
        except AgentError as exc:
            raise RpcError(AGENT_ERROR, exc.message, exc.to_dict()) from exc
        except BudgetExceeded as exc:
            raise RpcError(BUDGET_ERROR, exc.message, exc.to_dict()) from exc
        except ProviderError as exc:
            raise RpcError(PROVIDER_ERROR, exc.message, exc.to_dict()) from exc
        except ProjectNotFound as exc:
            raise RpcError(NOT_FOUND, str(exc)) from exc
        except StorageValidationError as exc:
            raise RpcError(INVALID_PARAMS, str(exc)) from exc
        except StorageError as exc:
            raise RpcError(STORAGE_ERROR, str(exc)) from exc

    return wrapped


def _sandbox_handler(handler: Handler) -> Handler:
    @wraps(handler)
    def wrapped(params: dict[str, Any], context: RequestContext) -> dict[str, Any]:
        try:
            return handler(params, context)
        except RpcError:
            raise
        except ContractError as exc:
            raise RpcError(INVALID_PARAMS, str(exc)) from exc
        except ProjectNotFound as exc:
            raise RpcError(NOT_FOUND, str(exc)) from exc
        except StorageValidationError as exc:
            raise RpcError(INVALID_PARAMS, str(exc)) from exc
        except StorageError as exc:
            raise RpcError(STORAGE_ERROR, str(exc)) from exc

    return wrapped


def _require_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RpcError(INVALID_PARAMS, f"{key} doit être une chaîne non vide")
    return value.strip()


def _optional_text(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RpcError(INVALID_PARAMS, f"{key} doit être une chaîne")
    cleaned = value.strip()
    return cleaned or None


def _optional_bool(params: dict[str, Any], key: str) -> bool:
    value = params.get(key, False)
    if not isinstance(value, bool):
        raise RpcError(INVALID_PARAMS, f"{key} doit être un booléen")
    return value


def _project_result(project: Any) -> dict[str, Any]:
    return {"project": project.to_dict()}


@_storage_handler
def project_list(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    projects = get_store().list_projects(
        include_archived=_optional_bool(params, "includeArchived"),
        include_trashed=_optional_bool(params, "includeTrashed"),
    )
    return {"projects": [project.to_dict() for project in projects]}


@_storage_handler
def project_create(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    project = get_store().create_project(
        _require_text(params, "name"),
        description=_optional_text(params, "description") or "",
        currency=_optional_text(params, "currency") or "XOF",
        sector=_optional_text(params, "sector"),
    )
    return _project_result(project)


@_storage_handler
def project_open(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return _project_result(get_store().open_project(_require_text(params, "projectId")))


@_storage_handler
def project_rename(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    project = get_store().rename_project(
        _require_text(params, "projectId"), _require_text(params, "name")
    )
    return _project_result(project)


@_storage_handler
def project_duplicate(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    project = get_store().duplicate_project(
        _require_text(params, "projectId"), name=_optional_text(params, "name")
    )
    return _project_result(project)


@_storage_handler
def project_archive(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return _project_result(get_store().archive_project(_require_text(params, "projectId")))


@_storage_handler
def project_restore(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return _project_result(get_store().restore_project(_require_text(params, "projectId")))


@_storage_handler
def project_trash(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return _project_result(get_store().trash_project(_require_text(params, "projectId")))


@_storage_handler
def project_delete(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    deleted = get_store().delete_project(_require_text(params, "projectId"))
    return {"deleted": deleted}


@_storage_handler
def project_export(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    info = get_store().export_project(
        _require_text(params, "projectId"), _require_text(params, "destination")
    )
    return {"path": str(info.path), "checksum": info.checksum, "bytes": info.size_bytes}


@_storage_handler
def project_import(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    project = get_store().import_project(
        _require_text(params, "source"), name=_optional_text(params, "name")
    )
    return _project_result(project)


@_storage_handler
def project_size(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return get_store().project_size(_require_text(params, "projectId"))


@_storage_handler
def project_data(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return project_service.data(get_store(), params)


@_storage_handler
def project_brief_save(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return project_service.save_brief(get_store(), params)


@_storage_handler
def project_scenario_save(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return project_service.save_scenario(get_store(), params)


@_storage_handler
def project_simulate(params: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    progress = None
    if _optional_bool(params, "progress"):
        progress = lambda fraction: context.notify(  # noqa: E731
            "simulate.progress", {"progress": round(fraction, 4)}
        )
    return project_service.simulate(get_store(), params, progress=progress)


@_storage_handler
def integrity_check(_params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    ok, message = get_store().check_integrity()
    return {"ok": ok, "message": message}


@_storage_handler
def storage_backup(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    destination = _optional_text(params, "destination")
    path = get_store().backup(destination)
    return {"path": str(path)}


@_provider_handler
def provider_catalog(_params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.provider_catalog(get_store())


@_provider_handler
def provider_profile_list(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.list_profiles(get_store(), _require_text(params, "projectId"))


@_provider_handler
def provider_profile_save(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.save_profile(get_store(), params)


@_provider_handler
def provider_profile_delete(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.delete_profile(get_store(), params)


@_provider_handler
def provider_role_list(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.list_roles(get_store(), _require_text(params, "projectId"))


@_provider_handler
def provider_role_set(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.set_role(get_store(), params)


@_provider_handler
def provider_role_delete(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.delete_role(get_store(), params)


@_provider_handler
def provider_test(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.test(get_store(), params)


@_provider_handler
def provider_models(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.models(get_store(), params)


@_provider_handler
def provider_chat(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.chat(get_store(), params)


@_provider_handler
def provider_usage(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.list_usage(get_store(), _require_text(params, "projectId"))


@_provider_handler
def provider_budget_get(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.get_budget(get_store(), _require_text(params, "projectId"))


@_provider_handler
def provider_budget_set(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.set_budget(get_store(), params)


@_provider_handler
def provider_budget_delete(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return provider_service.delete_budget(get_store(), params)


@_agent_handler
def agent_prepare(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.prepare(get_store(), params)


@_agent_handler
def agent_state(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.state(get_store(), params)


@_agent_handler
def agent_start(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.start(get_store(), params)


@_agent_handler
def agent_reset(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.reset(get_store(), params)


@_agent_handler
def agent_turn(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.turn(get_store(), params)


@_agent_handler
def agent_permission_list(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.list_permissions(get_store(), params)


@_agent_handler
def agent_permission_set(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.set_permission(get_store(), params)


@_agent_handler
def agent_permission_delete(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.delete_permission(get_store(), params)


@_agent_handler
def agent_trace(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.trace(get_store(), params)


@_agent_handler
def agent_trace_export(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.export_trace(get_store(), params)


@_agent_handler
def agent_tools(_params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return agent_service.list_tools(get_store(), _params)


@_sandbox_handler
def sandbox_analyze(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return sandbox_service.analyze(get_store(), params)


@_sandbox_handler
def sandbox_audit_record(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return sandbox_service.record_audit(get_store(), params)


@_sandbox_handler
def sandbox_audit_list(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return sandbox_service.list_audit(get_store(), params)


@_sandbox_handler
def sandbox_audit_export(params: dict[str, Any], _context: RequestContext) -> dict[str, Any]:
    return sandbox_service.export_audit(get_store(), params)


def default_handlers() -> dict[str, Handler]:
    return {
        "ping": ping,
        "health": health,
        "log": log,
        "simulate": simulate,
        "project.list": project_list,
        "project.create": project_create,
        "project.open": project_open,
        "project.rename": project_rename,
        "project.duplicate": project_duplicate,
        "project.archive": project_archive,
        "project.restore": project_restore,
        "project.trash": project_trash,
        "project.delete": project_delete,
        "project.export": project_export,
        "project.import": project_import,
        "project.size": project_size,
        "project.data": project_data,
        "project.brief.save": project_brief_save,
        "project.scenario.save": project_scenario_save,
        "project.simulate": project_simulate,
        "integrity.check": integrity_check,
        "storage.backup": storage_backup,
        "provider.catalog": provider_catalog,
        "provider.profile.list": provider_profile_list,
        "provider.profile.save": provider_profile_save,
        "provider.profile.delete": provider_profile_delete,
        "provider.role.list": provider_role_list,
        "provider.role.set": provider_role_set,
        "provider.role.delete": provider_role_delete,
        "provider.test": provider_test,
        "provider.models": provider_models,
        "provider.chat": provider_chat,
        "provider.usage": provider_usage,
        "provider.budget.get": provider_budget_get,
        "provider.budget.set": provider_budget_set,
        "provider.budget.delete": provider_budget_delete,
        "agent.prepare": agent_prepare,
        "agent.state": agent_state,
        "agent.start": agent_start,
        "agent.reset": agent_reset,
        "agent.turn": agent_turn,
        "agent.permission.list": agent_permission_list,
        "agent.permission.set": agent_permission_set,
        "agent.permission.delete": agent_permission_delete,
        "agent.trace": agent_trace,
        "agent.trace.export": agent_trace_export,
        "agent.tools": agent_tools,
        "sandbox.analyze": sandbox_analyze,
        "sandbox.audit.record": sandbox_audit_record,
        "sandbox.audit.list": sandbox_audit_list,
        "sandbox.audit.export": sandbox_audit_export,
    }


class RpcServer:
    def __init__(
        self,
        handlers: Mapping[str, Handler] | None = None,
        max_message_bytes: int = MAX_MESSAGE_BYTES,
    ) -> None:
        self.handlers = dict(handlers or default_handlers())
        self.max_message_bytes = max_message_bytes
        self._shutdown = False

    def serve(self) -> int:
        logger.info("sidecar ready (pid=%s)", os.getpid())
        for raw in self._read_lines():
            if self._shutdown:
                break
            self._handle_line(raw)
        logger.info("sidecar stopped")
        return 0

    def _read_lines(self) -> Iterator[bytes]:
        stream = sys.stdin.buffer
        while not self._shutdown:
            line = stream.readline()
            if not line:
                return
            if len(line) > self.max_message_bytes:
                self._write_error(None, INVALID_REQUEST, "message too large")
                continue
            stripped = line.strip()
            if stripped:
                yield stripped

    def _handle_line(self, raw: bytes) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._write_error(None, PARSE_ERROR, f"parse error: {exc.msg}")
            return

        if not isinstance(payload, dict):
            self._write_error(None, INVALID_REQUEST, "request must be a JSON object")
            return

        is_notification = "id" not in payload
        request_id = payload.get("id")

        try:
            request = JSONRPCRequest.model_validate(payload)
        except ValidationError as exc:
            if not is_notification:
                self._write_error(
                    request_id,
                    INVALID_REQUEST,
                    "invalid request",
                    exc.errors(include_url=False),
                )
            return

        if request.method == "shutdown":
            if not is_notification:
                self._write({"jsonrpc": "2.0", "id": request.id, "result": {"ok": True}})
            self._shutdown = True
            return

        handler = self.handlers.get(request.method)
        if handler is None:
            if not is_notification:
                self._write_error(
                    request.id,
                    METHOD_NOT_FOUND,
                    f"method not found: {request.method}",
                )
            return

        context = RequestContext(self._notify)

        try:
            result = handler(request.params or {}, context)
        except RpcError as exc:
            if not is_notification:
                self._write_error(request.id, exc.code, exc.message, exc.data)
            return
        except Exception:
            logger.error("handler failed: %s\n%s", request.method, traceback.format_exc())
            if not is_notification:
                self._write_error(
                    request.id,
                    INTERNAL_ERROR,
                    f"internal error in {request.method}",
                )
            return

        if not is_notification:
            self._write({"jsonrpc": "2.0", "id": request.id, "result": result})

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _write_error(
        self,
        request_id: Any,
        code: int,
        message: str,
        data: Any = None,
    ) -> None:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        self._write({"jsonrpc": "2.0", "id": request_id, "error": error})

    def _write(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        sys.stdout.buffer.write(line.encode("utf-8") + b"\n")
        sys.stdout.buffer.flush()


def main() -> int:
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        return RpcServer().serve()
    except KeyboardInterrupt:
        return 130
    finally:
        close_store()
