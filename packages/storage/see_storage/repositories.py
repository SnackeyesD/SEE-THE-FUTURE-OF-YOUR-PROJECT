from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .errors import ProjectNotFound, StorageValidationError
from .models import (
    AgentSession,
    AgentTraceEntry,
    BenchmarkPack,
    BenchmarkPackEvent,
    Brief,
    Message,
    PermissionEvent,
    Project,
    ProjectBudget,
    ProviderProfile,
    RoleAssignment,
    SandboxAuditRecord,
    ScenarioRecord,
    SimulationRun,
    ToolPermission,
    UsageEntry,
)
from .utils import ensure_text, json_dumps, new_id, safe_relative_path, utc_now

PROJECT_STATUSES = ("active", "archived", "trashed")
MESSAGE_ROLES = ("system", "user", "assistant", "tool")
BRIEF_STATUSES = ("draft", "validated", "archived")
PERMISSION_DECISIONS = ("allow", "ask", "deny")
ROLE_NAMES = ("interviewer", "modeler", "narrator", "delegate", "coder")
JOURNEY_STATES = (
    "idea",
    "interviewing",
    "brief_draft",
    "brief_validated",
    "hypotheses_set",
    "simulating",
    "results_ready",
    "narrating",
    "done",
)
PERMISSION_ACTORS = ("agent", "user", "system")
SANDBOX_DECISIONS = ("approved", "rejected")
SANDBOX_STATUSES = ("succeeded", "failed", "timeout", "cancelled", "rejected")
BENCHMARK_STATUSES = ("active", "invalid", "removed")
BENCHMARK_EVENT_ACTIONS = ("installed", "replaced", "rejected", "removed")
CODE_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@contextmanager
def _write(conn: sqlite3.Connection) -> Iterator[None]:
    already_in_transaction = conn.in_transaction
    try:
        yield
    except Exception:
        if not already_in_transaction:
            conn.rollback()
        raise
    else:
        if not already_in_transaction:
            conn.commit()


@contextmanager
def _immediate(conn: sqlite3.Connection) -> Iterator[None]:
    started = not conn.in_transaction
    if started:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        if started:
            conn.rollback()
        raise
    else:
        if started:
            conn.commit()


def _optional_text(value: object, field: str, *, max_length: int = 500) -> str | None:
    if value is None:
        return None
    return ensure_text(value, field, max_length=max_length)


class ProjectRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(
        self,
        name: str,
        *,
        description: str = "",
        currency: str = "XOF",
        sector: str | None = None,
        metadata: dict[str, Any] | None = None,
        engine_version: str | None = None,
        project_id: str | None = None,
        status: str = "active",
        created_at: str | None = None,
        updated_at: str | None = None,
    ) -> Project:
        clean_name = ensure_text(name, "name")
        if not isinstance(description, str):
            raise StorageValidationError("description doit être une chaîne")
        clean_currency = ensure_text(currency, "currency", max_length=8).upper()
        clean_sector = _optional_text(sector, "sector", max_length=100)
        if status not in PROJECT_STATUSES:
            raise StorageValidationError(f"statut de projet invalide: {status}")
        now = created_at or utc_now()
        identifier = project_id or new_id()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO projects (
                    id, name, description, currency, sector, status, created_at,
                    updated_at, schema_version, engine_version, metadata_json, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    identifier,
                    clean_name,
                    description,
                    clean_currency,
                    clean_sector,
                    status,
                    now,
                    updated_at or now,
                    engine_version,
                    json_dumps(metadata or {}),
                    now if status == "trashed" else None,
                ),
            )
        return self.require(identifier)

    def get(self, project_id: str) -> Project | None:
        row = self.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return Project.from_row(row) if row is not None else None

    def require(self, project_id: str) -> Project:
        project = self.get(project_id)
        if project is None:
            raise ProjectNotFound(f"projet introuvable: {project_id}")
        return project

    def list(
        self,
        *,
        include_archived: bool = False,
        include_trashed: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Project]:
        clauses: list[str] = []
        params: list[Any] = []
        if not include_trashed:
            if include_archived:
                clauses.append("status IN ('active', 'archived')")
            else:
                clauses.append("status = 'active'")
        query = "SELECT * FROM projects"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC, name COLLATE NOCASE ASC LIMIT ? OFFSET ?"
        params.extend((max(1, limit), max(0, offset)))
        rows = self.conn.execute(query, params).fetchall()
        return [Project.from_row(row) for row in rows]

    def update(self, project_id: str, **fields: Any) -> Project:
        allowed = {
            "name",
            "description",
            "currency",
            "sector",
            "status",
            "engine_version",
            "metadata",
            "deleted_at",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise StorageValidationError(f"champs projet non modifiables: {sorted(unknown)}")
        if not fields:
            return self.require(project_id)
        assignments: list[str] = []
        params: list[Any] = []
        for key, value in fields.items():
            if key == "name":
                value = ensure_text(value, "name")
            elif key == "currency":
                value = ensure_text(value, "currency", max_length=8).upper()
            elif key == "sector":
                value = _optional_text(value, "sector", max_length=100)
            elif key == "status":
                if value not in PROJECT_STATUSES:
                    raise StorageValidationError(f"statut de projet invalide: {value}")
            elif key == "metadata":
                key = "metadata_json"
                value = json_dumps(value or {})
            elif key == "description" and not isinstance(value, str):
                raise StorageValidationError("description doit être une chaîne")
            assignments.append(f"{key} = ?")
            params.append(value)
        assignments.append("updated_at = ?")
        params.append(utc_now())
        params.append(project_id)
        with _write(self.conn):
            cursor = self.conn.execute(
                f"UPDATE projects SET {', '.join(assignments)} WHERE id = ?", params
            )
        if cursor.rowcount == 0:
            raise ProjectNotFound(f"projet introuvable: {project_id}")
        return self.require(project_id)

    def touch(self, project_id: str) -> Project:
        with _write(self.conn):
            cursor = self.conn.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?", (utc_now(), project_id)
            )
        if cursor.rowcount == 0:
            raise ProjectNotFound(f"projet introuvable: {project_id}")
        return self.require(project_id)

    def delete(self, project_id: str) -> bool:
        with _write(self.conn):
            cursor = self.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cursor.rowcount > 0

    def count(self, *, include_trashed: bool = True) -> int:
        query = "SELECT COUNT(*) FROM projects"
        if not include_trashed:
            query += " WHERE status != 'trashed'"
        return int(self.conn.execute(query).fetchone()[0])


class MessageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        project_id: str,
        role: str,
        content: str,
        *,
        token_count: int | None = None,
        metadata: dict[str, Any] | None = None,
        message_id: str | None = None,
        created_at: str | None = None,
    ) -> Message:
        if role not in MESSAGE_ROLES:
            raise StorageValidationError(f"rôle de message invalide: {role}")
        if not isinstance(content, str):
            raise StorageValidationError("content doit être une chaîne")
        identifier = message_id or new_id()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO messages (
                    id, project_id, role, content, token_count, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    project_id,
                    role,
                    content,
                    token_count,
                    json_dumps(metadata or {}),
                    created_at or utc_now(),
                ),
            )
        return self.get(identifier)  # type: ignore[return-value]

    def get(self, message_id: str) -> Message | None:
        row = self.conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        return Message.from_row(row) if row is not None else None

    def list(
        self, project_id: str, *, limit: int = 100, offset: int = 0, newest_first: bool = False
    ) -> list[Message]:
        order = "DESC" if newest_first else "ASC"
        rows = self.conn.execute(
            f"""
            SELECT * FROM messages WHERE project_id = ?
            ORDER BY created_at {order}, id {order} LIMIT ? OFFSET ?
            """,
            (project_id, max(1, limit), max(0, offset)),
        ).fetchall()
        return [Message.from_row(row) for row in rows]

    def count(self, project_id: str) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM messages WHERE project_id = ?", (project_id,)
            ).fetchone()[0]
        )

    def delete(self, message_id: str) -> bool:
        with _write(self.conn):
            cursor = self.conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        return cursor.rowcount > 0


class BriefRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add_version(
        self,
        project_id: str,
        content: dict[str, Any],
        *,
        status: str = "draft",
        brief_id: str | None = None,
        created_at: str | None = None,
    ) -> Brief:
        if status not in BRIEF_STATUSES:
            raise StorageValidationError(f"statut de brief invalide: {status}")
        now = created_at or utc_now()
        identifier = brief_id or new_id()
        with _immediate(self.conn):
            version = int(
                self.conn.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 FROM briefs WHERE project_id = ?",
                    (project_id,),
                ).fetchone()[0]
            )
            self.conn.execute(
                """
                INSERT INTO briefs (
                    id, project_id, version, content_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (identifier, project_id, version, json_dumps(content), status, now, now),
            )
        return self.get(identifier)  # type: ignore[return-value]

    def get(self, brief_id: str) -> Brief | None:
        row = self.conn.execute("SELECT * FROM briefs WHERE id = ?", (brief_id,)).fetchone()
        return Brief.from_row(row) if row is not None else None

    def latest(self, project_id: str) -> Brief | None:
        row = self.conn.execute(
            "SELECT * FROM briefs WHERE project_id = ? ORDER BY version DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        return Brief.from_row(row) if row is not None else None

    def list(self, project_id: str, *, limit: int = 100, offset: int = 0) -> list[Brief]:
        rows = self.conn.execute(
            """
            SELECT * FROM briefs WHERE project_id = ?
            ORDER BY version DESC LIMIT ? OFFSET ?
            """,
            (project_id, max(1, limit), max(0, offset)),
        ).fetchall()
        return [Brief.from_row(row) for row in rows]

    def set_status(self, brief_id: str, status: str) -> Brief:
        if status not in BRIEF_STATUSES:
            raise StorageValidationError(f"statut de brief invalide: {status}")
        with _write(self.conn):
            cursor = self.conn.execute(
                "UPDATE briefs SET status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), brief_id),
            )
        if cursor.rowcount == 0:
            raise StorageValidationError(f"brief introuvable: {brief_id}")
        return self.get(brief_id)  # type: ignore[return-value]


class ScenarioRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        project_id: str,
        name: str,
        model: str,
        scenario: dict[str, Any],
        *,
        scenario_id: str | None = None,
        created_at: str | None = None,
    ) -> ScenarioRecord:
        clean_name = ensure_text(name, "name")
        clean_model = ensure_text(model, "model")
        now = created_at or utc_now()
        identifier = scenario_id or new_id()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO scenarios (
                    id, project_id, name, model, scenario_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (identifier, project_id, clean_name, clean_model, json_dumps(scenario), now, now),
            )
        return self.get(identifier)  # type: ignore[return-value]

    def get(self, scenario_id: str) -> ScenarioRecord | None:
        row = self.conn.execute(
            "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)
        ).fetchone()
        return ScenarioRecord.from_row(row) if row is not None else None

    def list(self, project_id: str, *, limit: int = 100, offset: int = 0) -> list[ScenarioRecord]:
        rows = self.conn.execute(
            """
            SELECT * FROM scenarios WHERE project_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (project_id, max(1, limit), max(0, offset)),
        ).fetchall()
        return [ScenarioRecord.from_row(row) for row in rows]

    def update(self, scenario_id: str, **fields: Any) -> ScenarioRecord:
        allowed = {"name", "model", "scenario"}
        unknown = set(fields) - allowed
        if unknown:
            raise StorageValidationError(f"champs scénario non modifiables: {sorted(unknown)}")
        if not fields:
            return self.get(scenario_id)  # type: ignore[return-value]
        assignments: list[str] = []
        params: list[Any] = []
        for key, value in fields.items():
            if key == "scenario":
                key = "scenario_json"
                value = json_dumps(value)
            elif key == "name":
                value = ensure_text(value, "name")
            elif key == "model":
                value = ensure_text(value, "model")
            assignments.append(f"{key} = ?")
            params.append(value)
        assignments.append("updated_at = ?")
        params.extend((utc_now(), scenario_id))
        with _write(self.conn):
            cursor = self.conn.execute(
                f"UPDATE scenarios SET {', '.join(assignments)} WHERE id = ?", params
            )
        if cursor.rowcount == 0:
            raise StorageValidationError(f"scénario introuvable: {scenario_id}")
        return self.get(scenario_id)  # type: ignore[return-value]

    def delete(self, scenario_id: str) -> bool:
        with _write(self.conn):
            cursor = self.conn.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
        return cursor.rowcount > 0


class RunRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        project_id: str,
        engine_version: str,
        runs: int,
        summary: dict[str, Any],
        *,
        scenario_id: str | None = None,
        seed: int | None = None,
        duration_ms: float | None = None,
        result: dict[str, Any] | None = None,
        result_path: str | None = None,
        run_id: str | None = None,
        created_at: str | None = None,
    ) -> SimulationRun:
        clean_engine = ensure_text(engine_version, "engineVersion")
        if runs < 1:
            raise StorageValidationError("runs doit être supérieur ou égal à 1")
        clean_path = safe_relative_path(result_path) if result_path is not None else None
        identifier = run_id or new_id()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO simulation_runs (
                    id, project_id, scenario_id, engine_version, seed, runs, duration_ms,
                    summary_json, result_json, result_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    project_id,
                    scenario_id,
                    clean_engine,
                    seed,
                    runs,
                    duration_ms,
                    json_dumps(summary),
                    json_dumps(result) if result is not None else None,
                    clean_path,
                    created_at or utc_now(),
                ),
            )
        return self.get(identifier)  # type: ignore[return-value]

    def get(self, run_id: str) -> SimulationRun | None:
        row = self.conn.execute(
            "SELECT * FROM simulation_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return SimulationRun.from_row(row) if row is not None else None

    def list(
        self, project_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[SimulationRun]:
        rows = self.conn.execute(
            """
            SELECT * FROM simulation_runs WHERE project_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (project_id, max(1, limit), max(0, offset)),
        ).fetchall()
        return [SimulationRun.from_row(row) for row in rows]

    def count(self, project_id: str) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM simulation_runs WHERE project_id = ?", (project_id,)
            ).fetchone()[0]
        )

    def attach_result(self, run_id: str, result_path: str | None) -> SimulationRun:
        clean_path = safe_relative_path(result_path) if result_path is not None else None
        with _write(self.conn):
            cursor = self.conn.execute(
                "UPDATE simulation_runs SET result_path = ? WHERE id = ?",
                (clean_path, run_id),
            )
        if cursor.rowcount == 0:
            raise StorageValidationError(f"run introuvable: {run_id}")
        return self.get(run_id)  # type: ignore[return-value]

    def prune(self, project_id: str, *, keep: int) -> list[str]:
        if keep < 0:
            raise StorageValidationError("keep doit être positif ou nul")
        with _immediate(self.conn):
            rows = self.conn.execute(
                """
                SELECT id, result_path FROM simulation_runs WHERE project_id = ?
                ORDER BY created_at DESC, id DESC LIMIT -1 OFFSET ?
                """,
                (project_id, keep),
            ).fetchall()
            if not rows:
                return []
            identifiers = [row["id"] for row in rows]
            placeholders = ", ".join("?" for _ in identifiers)
            self.conn.execute(
                f"DELETE FROM simulation_runs WHERE id IN ({placeholders})", identifiers
            )
        return [row["result_path"] for row in rows if row["result_path"]]


class ProviderProfileRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert(
        self,
        project_id: str,
        name: str,
        provider: str,
        *,
        base_url: str | None = None,
        model: str | None = None,
        keychain_ref: str | None = None,
        capabilities: dict[str, Any] | None = None,
    ) -> ProviderProfile:
        clean_name = ensure_text(name, "name")
        clean_provider = ensure_text(provider, "provider")
        now = utc_now()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO provider_profiles (
                    id, project_id, name, provider, base_url, model, keychain_ref,
                    capabilities_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, name) DO UPDATE SET
                    provider = excluded.provider,
                    base_url = excluded.base_url,
                    model = excluded.model,
                    keychain_ref = excluded.keychain_ref,
                    capabilities_json = excluded.capabilities_json,
                    updated_at = excluded.updated_at
                """,
                (
                    new_id(),
                    project_id,
                    clean_name,
                    clean_provider,
                    base_url,
                    model,
                    keychain_ref,
                    json_dumps(capabilities or {}),
                    now,
                    now,
                ),
            )
        return self.get_by_name(project_id, clean_name)  # type: ignore[return-value]

    def get(self, profile_id: str) -> ProviderProfile | None:
        row = self.conn.execute(
            "SELECT * FROM provider_profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return ProviderProfile.from_row(row) if row is not None else None

    def get_by_name(self, project_id: str, name: str) -> ProviderProfile | None:
        row = self.conn.execute(
            "SELECT * FROM provider_profiles WHERE project_id = ? AND name = ?",
            (project_id, name),
        ).fetchone()
        return ProviderProfile.from_row(row) if row is not None else None

    def list(self, project_id: str) -> list[ProviderProfile]:
        rows = self.conn.execute(
            "SELECT * FROM provider_profiles WHERE project_id = ? ORDER BY name COLLATE NOCASE",
            (project_id,),
        ).fetchall()
        return [ProviderProfile.from_row(row) for row in rows]

    def delete(self, profile_id: str) -> bool:
        with _write(self.conn):
            cursor = self.conn.execute(
                "DELETE FROM provider_profiles WHERE id = ?", (profile_id,)
            )
        return cursor.rowcount > 0


class RoleAssignmentRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def set(
        self,
        project_id: str,
        role: str,
        provider_profile_id: str,
        model: str,
    ) -> RoleAssignment:
        if role not in ROLE_NAMES:
            raise StorageValidationError(f"rôle invalide: {role}")
        clean_model = ensure_text(model, "model", max_length=200)
        profile = self.conn.execute(
            "SELECT project_id FROM provider_profiles WHERE id = ?",
            (provider_profile_id,),
        ).fetchone()
        if profile is None or profile["project_id"] != project_id:
            raise StorageValidationError("profil fournisseur absent de ce projet")
        now = utc_now()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO role_assignments (
                    id, project_id, role, provider_profile_id, model, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, role) DO UPDATE SET
                    provider_profile_id = excluded.provider_profile_id,
                    model = excluded.model,
                    updated_at = excluded.updated_at
                """,
                (new_id(), project_id, role, provider_profile_id, clean_model, now, now),
            )
        return self.get(project_id, role)  # type: ignore[return-value]

    def get(self, project_id: str, role: str) -> RoleAssignment | None:
        row = self.conn.execute(
            "SELECT * FROM role_assignments WHERE project_id = ? AND role = ?",
            (project_id, role),
        ).fetchone()
        return RoleAssignment.from_row(row) if row is not None else None

    def list(self, project_id: str) -> list[RoleAssignment]:
        rows = self.conn.execute(
            "SELECT * FROM role_assignments WHERE project_id = ? ORDER BY role",
            (project_id,),
        ).fetchall()
        return [RoleAssignment.from_row(row) for row in rows]

    def delete(self, project_id: str, role: str) -> bool:
        with _write(self.conn):
            cursor = self.conn.execute(
                "DELETE FROM role_assignments WHERE project_id = ? AND role = ?",
                (project_id, role),
            )
        return cursor.rowcount > 0


class ProjectBudgetRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, project_id: str) -> ProjectBudget | None:
        row = self.conn.execute(
            "SELECT * FROM project_budgets WHERE project_id = ?", (project_id,)
        ).fetchone()
        return ProjectBudget.from_row(row) if row is not None else None

    def set(self, project_id: str, limit_micros: int) -> ProjectBudget:
        if not isinstance(limit_micros, int) or limit_micros < 0:
            raise StorageValidationError("limitMicros doit être un entier positif ou nul")
        now = utc_now()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO project_budgets (
                    project_id, limit_micros, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    limit_micros = excluded.limit_micros,
                    updated_at = excluded.updated_at
                """,
                (project_id, limit_micros, now, now),
            )
        return self.get(project_id)  # type: ignore[return-value]

    def delete(self, project_id: str) -> bool:
        with _write(self.conn):
            cursor = self.conn.execute(
                "DELETE FROM project_budgets WHERE project_id = ?", (project_id,)
            )
        return cursor.rowcount > 0


class UsageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        project_id: str,
        kind: str,
        *,
        provider_profile_id: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_micros: int = 0,
        metadata: dict[str, Any] | None = None,
        entry_id: str | None = None,
        created_at: str | None = None,
    ) -> UsageEntry:
        clean_kind = ensure_text(kind, "kind")
        for field, value in (
            ("inputTokens", input_tokens),
            ("outputTokens", output_tokens),
            ("costMicros", cost_micros),
        ):
            if not isinstance(value, int) or value < 0:
                raise StorageValidationError(f"{field} doit être un entier positif ou nul")
        identifier = entry_id or new_id()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO usage_log (
                    id, project_id, provider_profile_id, kind, input_tokens,
                    output_tokens, cost_micros, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    project_id,
                    provider_profile_id,
                    clean_kind,
                    input_tokens,
                    output_tokens,
                    cost_micros,
                    json_dumps(metadata or {}),
                    created_at or utc_now(),
                ),
            )
        return self.get(identifier)  # type: ignore[return-value]

    def get(self, entry_id: str) -> UsageEntry | None:
        row = self.conn.execute("SELECT * FROM usage_log WHERE id = ?", (entry_id,)).fetchone()
        return UsageEntry.from_row(row) if row is not None else None

    def list(self, project_id: str, *, limit: int = 100, offset: int = 0) -> list[UsageEntry]:
        rows = self.conn.execute(
            """
            SELECT * FROM usage_log WHERE project_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (project_id, max(1, limit), max(0, offset)),
        ).fetchall()
        return [UsageEntry.from_row(row) for row in rows]

    def summary(self, project_id: str) -> dict[str, int]:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS entries,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(cost_micros), 0) AS cost_micros
            FROM usage_log WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
        return {
            "entries": int(row["entries"]),
            "inputTokens": int(row["input_tokens"]),
            "outputTokens": int(row["output_tokens"]),
            "costMicros": int(row["cost_micros"]),
        }


class PermissionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def set(self, project_id: str, tool: str, scope: str, decision: str) -> ToolPermission:
        clean_tool = ensure_text(tool, "tool")
        clean_scope = ensure_text(scope, "scope")
        if decision not in PERMISSION_DECISIONS:
            raise StorageValidationError(f"décision de permission invalide: {decision}")
        now = utc_now()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO tool_permissions (
                    id, project_id, tool, scope, decision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, tool, scope) DO UPDATE SET
                    decision = excluded.decision,
                    updated_at = excluded.updated_at
                """,
                (new_id(), project_id, clean_tool, clean_scope, decision, now, now),
            )
        return self.get(project_id, clean_tool, clean_scope)  # type: ignore[return-value]

    def get(self, project_id: str, tool: str, scope: str) -> ToolPermission | None:
        row = self.conn.execute(
            """
            SELECT * FROM tool_permissions
            WHERE project_id = ? AND tool = ? AND scope = ?
            """,
            (project_id, tool, scope),
        ).fetchone()
        return ToolPermission.from_row(row) if row is not None else None

    def list(self, project_id: str) -> list[ToolPermission]:
        rows = self.conn.execute(
            "SELECT * FROM tool_permissions WHERE project_id = ? ORDER BY tool, scope",
            (project_id,),
        ).fetchall()
        return [ToolPermission.from_row(row) for row in rows]

    def delete(self, project_id: str, tool: str, scope: str) -> bool:
        with _write(self.conn):
            cursor = self.conn.execute(
                """
                DELETE FROM tool_permissions
                WHERE project_id = ? AND tool = ? AND scope = ?
                """,
                (project_id, tool, scope),
            )
        return cursor.rowcount > 0


class BenchmarkPackRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        name: str,
        version: str,
        path: str,
        checksum: str,
        *,
        source: str | None = None,
        pack_id: str | None = None,
        published_at: str | None = None,
        installed_at: str | None = None,
        signature: str | None = None,
        key_id: str | None = None,
        status: str = "active",
        country: str | None = None,
        region: str | None = None,
        sector: str | None = None,
        subsector: str | None = None,
        value_count: int = 0,
        error: str | None = None,
        created_at: str | None = None,
    ) -> BenchmarkPack:
        clean_name = ensure_text(name, "name")
        clean_version = ensure_text(version, "version")
        clean_path = ensure_text(path, "path", max_length=1000)
        clean_checksum = ensure_text(checksum, "checksum", max_length=128)
        if status not in BENCHMARK_STATUSES:
            raise StorageValidationError(f"statut de pack invalide: {status}")
        if not isinstance(value_count, int) or isinstance(value_count, bool) or value_count < 0:
            raise StorageValidationError("valueCount doit être un entier positif ou nul")
        now = created_at or utc_now()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO benchmark_packs (
                    id, name, version, path, checksum, source, pack_id,
                    published_at, installed_at, signature, key_id, status,
                    country, region, sector, subsector, value_count, error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name, version) DO UPDATE SET
                    path = excluded.path,
                    checksum = excluded.checksum,
                    source = excluded.source,
                    pack_id = excluded.pack_id,
                    published_at = excluded.published_at,
                    installed_at = excluded.installed_at,
                    signature = excluded.signature,
                    key_id = excluded.key_id,
                    status = excluded.status,
                    country = excluded.country,
                    region = excluded.region,
                    sector = excluded.sector,
                    subsector = excluded.subsector,
                    value_count = excluded.value_count,
                    error = excluded.error
                """,
                (
                    new_id(),
                    clean_name,
                    clean_version,
                    clean_path,
                    clean_checksum,
                    source,
                    pack_id,
                    published_at,
                    installed_at,
                    signature,
                    key_id,
                    status,
                    country,
                    region,
                    sector,
                    subsector,
                    value_count,
                    error,
                    now,
                ),
            )
        return self.get(clean_name, clean_version)  # type: ignore[return-value]

    def get(self, name: str, version: str) -> BenchmarkPack | None:
        row = self.conn.execute(
            "SELECT * FROM benchmark_packs WHERE name = ? AND version = ?", (name, version)
        ).fetchone()
        return BenchmarkPack.from_row(row) if row is not None else None

    def list(self) -> list[BenchmarkPack]:
        rows = self.conn.execute(
            """
            SELECT * FROM benchmark_packs
            ORDER BY COALESCE(published_at, '') DESC, name COLLATE NOCASE, version
            """
        ).fetchall()
        return [BenchmarkPack.from_row(row) for row in rows]

    def delete(self, name: str, version: str) -> bool:
        with _write(self.conn):
            cursor = self.conn.execute(
                "DELETE FROM benchmark_packs WHERE name = ? AND version = ?",
                (name, version),
            )
        return cursor.rowcount > 0


class BenchmarkPackEventRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        name: str,
        version: str,
        action: str,
        *,
        pack_id: str | None = None,
        checksum: str | None = None,
        key_id: str | None = None,
        reason: str | None = None,
        event_id: str | None = None,
        created_at: str | None = None,
    ) -> BenchmarkPackEvent:
        clean_name = ensure_text(name, "name")
        clean_version = ensure_text(version, "version")
        if action not in BENCHMARK_EVENT_ACTIONS:
            raise StorageValidationError(f"action de pack invalide: {action}")
        identifier = event_id or new_id()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO benchmark_pack_events (
                    id, pack_id, name, version, action, checksum, key_id, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    pack_id,
                    clean_name,
                    clean_version,
                    action,
                    checksum,
                    key_id,
                    reason,
                    created_at or utc_now(),
                ),
            )
        return self.get(identifier)  # type: ignore[return-value]

    def get(self, event_id: str) -> BenchmarkPackEvent | None:
        row = self.conn.execute(
            "SELECT * FROM benchmark_pack_events WHERE id = ?", (event_id,)
        ).fetchone()
        return BenchmarkPackEvent.from_row(row) if row is not None else None

    def list(self, *, limit: int = 100, offset: int = 0) -> list[BenchmarkPackEvent]:
        rows = self.conn.execute(
            """
            SELECT * FROM benchmark_pack_events
            ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?
            """,
            (max(1, limit), max(0, offset)),
        ).fetchall()
        return [BenchmarkPackEvent.from_row(row) for row in rows]


class AgentSessionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, project_id: str) -> AgentSession | None:
        row = self.conn.execute(
            "SELECT * FROM agent_sessions WHERE project_id = ?", (project_id,)
        ).fetchone()
        return AgentSession.from_row(row) if row is not None else None

    def upsert(
        self,
        project_id: str,
        state: str,
        role: str,
        thread: list[dict[str, Any]],
    ) -> AgentSession:
        if state not in JOURNEY_STATES:
            raise StorageValidationError(f"état d'agent invalide: {state}")
        if role not in ROLE_NAMES:
            raise StorageValidationError(f"rôle d'agent invalide: {role}")
        if not isinstance(thread, list):
            raise StorageValidationError("thread doit être une liste")
        now = utc_now()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO agent_sessions (
                    id, project_id, state, role, thread_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    state = excluded.state,
                    role = excluded.role,
                    thread_json = excluded.thread_json,
                    updated_at = excluded.updated_at
                """,
                (new_id(), project_id, state, role, json_dumps(thread), now, now),
            )
        return self.get(project_id)  # type: ignore[return-value]

    def delete(self, project_id: str) -> bool:
        with _write(self.conn):
            cursor = self.conn.execute(
                "DELETE FROM agent_sessions WHERE project_id = ?", (project_id,)
            )
        return cursor.rowcount > 0


class AgentTraceRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        project_id: str,
        event: dict[str, Any],
        *,
        session_id: str | None = None,
        turn: int = 0,
        entry_id: str | None = None,
        created_at: str | None = None,
    ) -> AgentTraceEntry:
        if not isinstance(event, dict):
            raise StorageValidationError("event doit être un objet")
        if not isinstance(turn, int) or turn < 0:
            raise StorageValidationError("turn doit être un entier positif ou nul")
        identifier = entry_id or new_id()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO agent_trace (
                    id, project_id, session_id, turn, event_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    project_id,
                    session_id,
                    turn,
                    json_dumps(event),
                    created_at or utc_now(),
                ),
            )
        return self.get(identifier)  # type: ignore[return-value]

    def get(self, entry_id: str) -> AgentTraceEntry | None:
        row = self.conn.execute(
            "SELECT * FROM agent_trace WHERE id = ?", (entry_id,)
        ).fetchone()
        return AgentTraceEntry.from_row(row) if row is not None else None

    def list(
        self,
        project_id: str,
        *,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[AgentTraceEntry]:
        rows = self.conn.execute(
            """
            SELECT * FROM agent_trace WHERE project_id = ?
            ORDER BY created_at, id LIMIT ? OFFSET ?
            """,
            (project_id, max(1, limit), max(0, offset)),
        ).fetchall()
        return [AgentTraceEntry.from_row(row) for row in rows]

    def count(self, project_id: str) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM agent_trace WHERE project_id = ?", (project_id,)
            ).fetchone()[0]
        )

    def next_turn(self, project_id: str) -> int:
        return int(
            self.conn.execute(
                "SELECT COALESCE(MAX(turn), 0) + 1 FROM agent_trace WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
        )

    def clear(self, project_id: str) -> int:
        with _write(self.conn):
            cursor = self.conn.execute(
                "DELETE FROM agent_trace WHERE project_id = ?", (project_id,)
            )
        return cursor.rowcount


class PermissionEventRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        project_id: str,
        tool: str,
        scope: str,
        decision: str,
        *,
        reason: str | None = None,
        actor: str = "agent",
        event_id: str | None = None,
        created_at: str | None = None,
    ) -> PermissionEvent:
        clean_tool = ensure_text(tool, "tool")
        clean_scope = ensure_text(scope, "scope")
        if decision not in PERMISSION_DECISIONS:
            raise StorageValidationError(f"décision de permission invalide: {decision}")
        if actor not in PERMISSION_ACTORS:
            raise StorageValidationError(f"acteur de permission invalide: {actor}")
        identifier = event_id or new_id()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO permission_events (
                    id, project_id, tool, scope, decision, reason, actor, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    project_id,
                    clean_tool,
                    clean_scope,
                    decision,
                    reason,
                    actor,
                    created_at or utc_now(),
                ),
            )
        return self.get(identifier)  # type: ignore[return-value]

    def get(self, event_id: str) -> PermissionEvent | None:
        row = self.conn.execute(
            "SELECT * FROM permission_events WHERE id = ?", (event_id,)
        ).fetchone()
        return PermissionEvent.from_row(row) if row is not None else None

    def list(
        self, project_id: str, *, limit: int = 500, offset: int = 0
    ) -> list[PermissionEvent]:
        rows = self.conn.execute(
            """
            SELECT * FROM permission_events WHERE project_id = ?
            ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?
            """,
            (project_id, max(1, limit), max(0, offset)),
        ).fetchall()
        return [PermissionEvent.from_row(row) for row in rows]


class SandboxAuditRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        project_id: str,
        code: str,
        code_hash: str,
        decision: str,
        status: str,
        *,
        analysis: dict[str, Any] | None = None,
        purpose: str = "",
        result: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: float | None = None,
        record_id: str | None = None,
        created_at: str | None = None,
    ) -> SandboxAuditRecord:
        if not isinstance(code, str) or not code:
            raise StorageValidationError("code de sandbox invalide")
        if len(code.encode("utf-8")) > 65_536:
            raise StorageValidationError("code de sandbox trop volumineux")
        if not isinstance(code_hash, str) or not CODE_HASH_PATTERN.match(code_hash):
            raise StorageValidationError("empreinte de script invalide")
        if decision not in SANDBOX_DECISIONS:
            raise StorageValidationError(f"décision de sandbox invalide: {decision}")
        if status not in SANDBOX_STATUSES:
            raise StorageValidationError(f"statut de sandbox invalide: {status}")
        if not isinstance(purpose, str):
            raise StorageValidationError("purpose doit être une chaîne")
        if len(purpose) > 2_000:
            raise StorageValidationError("purpose dépasse 2000 caractères")
        if duration_ms is not None and (
            isinstance(duration_ms, bool)
            or not isinstance(duration_ms, (int, float))
            or duration_ms < 0
        ):
            raise StorageValidationError("durationMs invalide")
        if error is not None and not isinstance(error, str):
            raise StorageValidationError("error doit être une chaîne")
        if error is not None and len(error) > 4_000:
            error = error[:4_000]
        payload = analysis or {}
        if not isinstance(payload, dict):
            raise StorageValidationError("analysis doit être un objet")
        if result is not None and not isinstance(result, dict):
            raise StorageValidationError("result doit être un objet")
        try:
            analysis_json = json_dumps(payload)
            result_json = None if result is None else json_dumps(result)
        except (TypeError, ValueError) as exc:
            raise StorageValidationError(f"contenu de sandbox non sérialisable: {exc}") from exc
        identifier = record_id or new_id()
        with _write(self.conn):
            self.conn.execute(
                """
                INSERT INTO sandbox_audit (
                    id, project_id, code, code_hash, purpose, decision, status,
                    analysis_json, result_json, error, duration_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    project_id,
                    code,
                    code_hash,
                    purpose,
                    decision,
                    status,
                    analysis_json,
                    result_json,
                    error,
                    None if duration_ms is None else float(duration_ms),
                    created_at or utc_now(),
                ),
            )
        return self.get(identifier)  # type: ignore[return-value]

    def get(self, record_id: str) -> SandboxAuditRecord | None:
        row = self.conn.execute(
            "SELECT * FROM sandbox_audit WHERE id = ?", (record_id,)
        ).fetchone()
        return SandboxAuditRecord.from_row(row) if row is not None else None

    def list(
        self, project_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[SandboxAuditRecord]:
        rows = self.conn.execute(
            """
            SELECT * FROM sandbox_audit WHERE project_id = ?
            ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?
            """,
            (project_id, max(1, limit), max(0, offset)),
        ).fetchall()
        return [SandboxAuditRecord.from_row(row) for row in rows]

    def count(self, project_id: str) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM sandbox_audit WHERE project_id = ?", (project_id,)
            ).fetchone()[0]
        )
