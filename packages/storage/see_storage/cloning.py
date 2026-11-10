from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ProjectNotFound
from .utils import new_id, safe_relative_path, utc_now


@dataclass(slots=True)
class CloneResult:
    project_id: str
    run_paths: list[tuple[str, str]] = field(default_factory=list)
    provider_profiles: dict[str, str] = field(default_factory=dict)
    scenarios: dict[str, str] = field(default_factory=dict)
    runs: dict[str, str] = field(default_factory=dict)


def _result_suffix(result_path: str) -> str:
    return ".json.gz" if result_path.endswith(".json.gz") else Path(result_path).suffix


def clone_project(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    source_project_id: str,
    *,
    new_project_id: str | None = None,
    new_name: str | None = None,
    preserve_ids: bool = False,
    preserve_status: bool = False,
    reset_timestamps: bool = False,
) -> CloneResult:
    if source.row_factory is None:
        source.row_factory = sqlite3.Row
    project = source.execute(
        "SELECT * FROM projects WHERE id = ?", (source_project_id,)
    ).fetchone()
    if project is None:
        raise ProjectNotFound(f"projet introuvable: {source_project_id}")

    project_id = new_project_id or (source_project_id if preserve_ids else new_id())
    now = utc_now()
    created_at = now if reset_timestamps else project["created_at"]
    updated_at = now if reset_timestamps else project["updated_at"]
    status = project["status"] if preserve_status else "active"
    deleted_at = project["deleted_at"] if preserve_status else None

    target.execute(
        """
        INSERT INTO projects (
            id, name, description, currency, sector, status, created_at, updated_at,
            schema_version, engine_version, metadata_json, deleted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            new_name or project["name"],
            project["description"],
            project["currency"],
            project["sector"],
            status,
            created_at,
            updated_at,
            project["schema_version"],
            project["engine_version"],
            project["metadata_json"],
            deleted_at,
        ),
    )

    result = CloneResult(project_id=project_id)

    profiles = source.execute(
        "SELECT * FROM provider_profiles WHERE project_id = ? ORDER BY created_at, id",
        (source_project_id,),
    ).fetchall()
    for profile in profiles:
        profile_id = profile["id"] if preserve_ids else new_id()
        result.provider_profiles[profile["id"]] = profile_id
        target.execute(
            """
            INSERT INTO provider_profiles (
                id, project_id, name, provider, base_url, model, keychain_ref,
                capabilities_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                project_id,
                profile["name"],
                profile["provider"],
                profile["base_url"],
                profile["model"],
                profile["keychain_ref"],
                profile["capabilities_json"],
                now if reset_timestamps else profile["created_at"],
                now if reset_timestamps else profile["updated_at"],
            ),
        )

    for assignment in source.execute(
        "SELECT * FROM role_assignments WHERE project_id = ? ORDER BY role",
        (source_project_id,),
    ).fetchall():
        profile_id = result.provider_profiles.get(assignment["provider_profile_id"])
        if profile_id is None:
            continue
        target.execute(
            """
            INSERT INTO role_assignments (
                id, project_id, role, provider_profile_id, model, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assignment["id"] if preserve_ids else new_id(),
                project_id,
                assignment["role"],
                profile_id,
                assignment["model"],
                now if reset_timestamps else assignment["created_at"],
                now if reset_timestamps else assignment["updated_at"],
            ),
        )

    scenarios = source.execute(
        "SELECT * FROM scenarios WHERE project_id = ? ORDER BY created_at, id",
        (source_project_id,),
    ).fetchall()
    for scenario in scenarios:
        scenario_id = scenario["id"] if preserve_ids else new_id()
        result.scenarios[scenario["id"]] = scenario_id
        target.execute(
            """
            INSERT INTO scenarios (
                id, project_id, name, model, scenario_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                project_id,
                scenario["name"],
                scenario["model"],
                scenario["scenario_json"],
                now if reset_timestamps else scenario["created_at"],
                now if reset_timestamps else scenario["updated_at"],
            ),
        )

    for message in source.execute(
        "SELECT * FROM messages WHERE project_id = ? ORDER BY created_at, id",
        (source_project_id,),
    ).fetchall():
        target.execute(
            """
            INSERT INTO messages (
                id, project_id, role, content, token_count, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message["id"] if preserve_ids else new_id(),
                project_id,
                message["role"],
                message["content"],
                message["token_count"],
                message["metadata_json"],
                now if reset_timestamps else message["created_at"],
            ),
        )

    for brief in source.execute(
        "SELECT * FROM briefs WHERE project_id = ? ORDER BY version",
        (source_project_id,),
    ).fetchall():
        target.execute(
            """
            INSERT INTO briefs (
                id, project_id, version, content_json, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                brief["id"] if preserve_ids else new_id(),
                project_id,
                brief["version"],
                brief["content_json"],
                brief["status"],
                now if reset_timestamps else brief["created_at"],
                now if reset_timestamps else brief["updated_at"],
            ),
        )

    for permission in source.execute(
        "SELECT * FROM tool_permissions WHERE project_id = ? ORDER BY tool, scope",
        (source_project_id,),
    ).fetchall():
        target.execute(
            """
            INSERT INTO tool_permissions (
                id, project_id, tool, scope, decision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                permission["id"] if preserve_ids else new_id(),
                project_id,
                permission["tool"],
                permission["scope"],
                permission["decision"],
                now if reset_timestamps else permission["created_at"],
                now if reset_timestamps else permission["updated_at"],
            ),
        )

    session_id_map: dict[str, str] = {}
    for session in source.execute(
        "SELECT * FROM agent_sessions WHERE project_id = ?", (source_project_id,)
    ).fetchall():
        new_session_id = session["id"] if preserve_ids else new_id()
        session_id_map[session["id"]] = new_session_id
        target.execute(
            """
            INSERT INTO agent_sessions (
                id, project_id, state, role, thread_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_session_id,
                project_id,
                session["state"],
                session["role"],
                session["thread_json"],
                now if reset_timestamps else session["created_at"],
                now if reset_timestamps else session["updated_at"],
            ),
        )

    for entry in source.execute(
        "SELECT * FROM agent_trace WHERE project_id = ? ORDER BY created_at, id",
        (source_project_id,),
    ).fetchall():
        target.execute(
            """
            INSERT INTO agent_trace (
                id, project_id, session_id, turn, event_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry["id"] if preserve_ids else new_id(),
                project_id,
                session_id_map.get(entry["session_id"]) if entry["session_id"] else None,
                entry["turn"],
                entry["event_json"],
                now if reset_timestamps else entry["created_at"],
            ),
        )

    for event in source.execute(
        "SELECT * FROM permission_events WHERE project_id = ? ORDER BY created_at, id",
        (source_project_id,),
    ).fetchall():
        target.execute(
            """
            INSERT INTO permission_events (
                id, project_id, tool, scope, decision, reason, actor, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["id"] if preserve_ids else new_id(),
                project_id,
                event["tool"],
                event["scope"],
                event["decision"],
                event["reason"],
                event["actor"],
                now if reset_timestamps else event["created_at"],
            ),
        )

    for record in source.execute(
        "SELECT * FROM sandbox_audit WHERE project_id = ? ORDER BY created_at, id",
        (source_project_id,),
    ).fetchall():
        target.execute(
            """
            INSERT INTO sandbox_audit (
                id, project_id, code, code_hash, purpose, decision, status,
                analysis_json, result_json, error, duration_ms, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"] if preserve_ids else new_id(),
                project_id,
                record["code"],
                record["code_hash"],
                record["purpose"],
                record["decision"],
                record["status"],
                record["analysis_json"],
                record["result_json"],
                record["error"],
                record["duration_ms"],
                now if reset_timestamps else record["created_at"],
            ),
        )


    for run in source.execute(
        "SELECT * FROM simulation_runs WHERE project_id = ? ORDER BY created_at, id",
        (source_project_id,),
    ).fetchall():
        run_id = run["id"] if preserve_ids else new_id()
        result.runs[run["id"]] = run_id
        result_path = run["result_path"]
        if result_path is not None:
            result_path = safe_relative_path(result_path)
            new_path = result_path if preserve_ids else f"{run_id}{_result_suffix(result_path)}"
            result.run_paths.append((result_path, new_path))
            result_path = new_path
        target.execute(
            """
            INSERT INTO simulation_runs (
                id, project_id, scenario_id, engine_version, seed, runs, duration_ms,
                summary_json, result_json, result_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                project_id,
                result.scenarios.get(run["scenario_id"]) if run["scenario_id"] else None,
                run["engine_version"],
                run["seed"],
                run["runs"],
                run["duration_ms"],
                run["summary_json"],
                run["result_json"],
                result_path,
                now if reset_timestamps else run["created_at"],
            ),
        )

    for usage in source.execute(
        "SELECT * FROM usage_log WHERE project_id = ? ORDER BY created_at, id",
        (source_project_id,),
    ).fetchall():
        target.execute(
            """
            INSERT INTO usage_log (
                id, project_id, provider_profile_id, kind, input_tokens,
                output_tokens, cost_micros, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usage["id"] if preserve_ids else new_id(),
                project_id,
                result.provider_profiles.get(usage["provider_profile_id"])
                if usage["provider_profile_id"]
                else None,
                usage["kind"],
                usage["input_tokens"],
                usage["output_tokens"],
                usage["cost_micros"],
                usage["metadata_json"],
                now if reset_timestamps else usage["created_at"],
            ),
        )

    budget = source.execute(
        "SELECT * FROM project_budgets WHERE project_id = ?", (source_project_id,)
    ).fetchone()
    if budget is not None:
        target.execute(
            """
            INSERT INTO project_budgets (
                project_id, limit_micros, created_at, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                project_id,
                budget["limit_micros"],
                now if reset_timestamps else budget["created_at"],
                now if reset_timestamps else budget["updated_at"],
            ),
        )

    return result
