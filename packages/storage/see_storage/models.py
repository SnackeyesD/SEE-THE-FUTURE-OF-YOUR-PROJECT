from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .utils import json_loads, to_camel


class Model:
    def to_dict(self) -> dict[str, Any]:
        return {
            to_camel(name): getattr(self, name) for name in self.__dataclass_fields__
        }


@dataclass(frozen=True, slots=True)
class Project(Model):
    id: str
    name: str
    description: str
    currency: str
    sector: str | None
    status: str
    created_at: str
    updated_at: str
    schema_version: int
    engine_version: str | None
    metadata: dict[str, Any]
    deleted_at: str | None

    @classmethod
    def from_row(cls, row: Any) -> Project:
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            currency=row["currency"],
            sector=row["sector"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            schema_version=row["schema_version"],
            engine_version=row["engine_version"],
            metadata=json_loads(row["metadata_json"], {}),
            deleted_at=row["deleted_at"],
        )


@dataclass(frozen=True, slots=True)
class Message(Model):
    id: str
    project_id: str
    role: str
    content: str
    token_count: int | None
    metadata: dict[str, Any]
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> Message:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            role=row["role"],
            content=row["content"],
            token_count=row["token_count"],
            metadata=json_loads(row["metadata_json"], {}),
            created_at=row["created_at"],
        )


@dataclass(frozen=True, slots=True)
class Brief(Model):
    id: str
    project_id: str
    version: int
    content: dict[str, Any]
    status: str
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> Brief:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            version=row["version"],
            content=json_loads(row["content_json"], {}),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True, slots=True)
class ScenarioRecord(Model):
    id: str
    project_id: str
    name: str
    model: str
    scenario: dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> ScenarioRecord:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            name=row["name"],
            model=row["model"],
            scenario=json_loads(row["scenario_json"], {}),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True, slots=True)
class SimulationRun(Model):
    id: str
    project_id: str
    scenario_id: str | None
    engine_version: str
    seed: int | None
    runs: int
    duration_ms: float | None
    summary: dict[str, Any]
    result: dict[str, Any] | None
    result_path: str | None
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> SimulationRun:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            scenario_id=row["scenario_id"],
            engine_version=row["engine_version"],
            seed=row["seed"],
            runs=row["runs"],
            duration_ms=row["duration_ms"],
            summary=json_loads(row["summary_json"], {}),
            result=json_loads(row["result_json"], None),
            result_path=row["result_path"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True, slots=True)
class ProviderProfile(Model):
    id: str
    project_id: str
    name: str
    provider: str
    base_url: str | None
    model: str | None
    keychain_ref: str | None
    capabilities: dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> ProviderProfile:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            name=row["name"],
            provider=row["provider"],
            base_url=row["base_url"],
            model=row["model"],
            keychain_ref=row["keychain_ref"],
            capabilities=json_loads(row["capabilities_json"], {}),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True, slots=True)
class RoleAssignment(Model):
    id: str
    project_id: str
    role: str
    provider_profile_id: str
    model: str
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> RoleAssignment:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            role=row["role"],
            provider_profile_id=row["provider_profile_id"],
            model=row["model"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True, slots=True)
class ProjectBudget(Model):
    project_id: str
    limit_micros: int
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> ProjectBudget:
        return cls(
            project_id=row["project_id"],
            limit_micros=int(row["limit_micros"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True, slots=True)
class UsageEntry(Model):
    id: str
    project_id: str
    provider_profile_id: str | None
    kind: str
    input_tokens: int
    output_tokens: int
    cost_micros: int
    metadata: dict[str, Any]
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> UsageEntry:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            provider_profile_id=row["provider_profile_id"],
            kind=row["kind"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cost_micros=row["cost_micros"],
            metadata=json_loads(row["metadata_json"], {}),
            created_at=row["created_at"],
        )


@dataclass(frozen=True, slots=True)
class ToolPermission(Model):
    id: str
    project_id: str
    tool: str
    scope: str
    decision: str
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> ToolPermission:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            tool=row["tool"],
            scope=row["scope"],
            decision=row["decision"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True, slots=True)
class BenchmarkPack(Model):
    id: str
    name: str
    version: str
    path: str
    checksum: str
    source: str | None
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> BenchmarkPack:
        return cls(
            id=row["id"],
            name=row["name"],
            version=row["version"],
            path=row["path"],
            checksum=row["checksum"],
            source=row["source"],
            created_at=row["created_at"],
        )

@dataclass(frozen=True, slots=True)
class AgentSession(Model):
    id: str
    project_id: str
    state: str
    role: str
    thread: list[dict[str, Any]]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> AgentSession:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            state=row["state"],
            role=row["role"],
            thread=json_loads(row["thread_json"], []),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True, slots=True)
class AgentTraceEntry(Model):
    id: str
    project_id: str
    session_id: str | None
    turn: int
    event: dict[str, Any]
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> AgentTraceEntry:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            session_id=row["session_id"],
            turn=int(row["turn"]),
            event=json_loads(row["event_json"], {}),
            created_at=row["created_at"],
        )


@dataclass(frozen=True, slots=True)
class PermissionEvent(Model):
    id: str
    project_id: str
    tool: str
    scope: str
    decision: str
    reason: str | None
    actor: str
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> PermissionEvent:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            tool=row["tool"],
            scope=row["scope"],
            decision=row["decision"],
            reason=row["reason"],
            actor=row["actor"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True, slots=True)
class SandboxAuditRecord(Model):
    id: str
    project_id: str
    code: str
    code_hash: str
    purpose: str
    decision: str
    status: str
    analysis: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    duration_ms: float | None
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> SandboxAuditRecord:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            code=row["code"],
            code_hash=row["code_hash"],
            purpose=row["purpose"],
            decision=row["decision"],
            status=row["status"],
            analysis=json_loads(row["analysis_json"], {}),
            result=json_loads(row["result_json"], None),
            error=row["error"],
            duration_ms=row["duration_ms"],
            created_at=row["created_at"],
        )

