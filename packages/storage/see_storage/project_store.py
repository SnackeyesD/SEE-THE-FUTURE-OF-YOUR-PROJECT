from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path
from typing import Any

from .cloning import clone_project
from .database import Database, default_data_dir
from .errors import IntegrityError, StorageValidationError
from .integrity import backup as backup_database
from .integrity import check_integrity as check_database_integrity
from .locking import InstanceLock
from .models import Project
from .portable import ExportInfo, export_project, import_project
from .repositories import (
    AgentSessionRepository,
    AgentTraceRepository,
    BenchmarkPackEventRepository,
    BenchmarkPackRepository,
    BriefRepository,
    MessageRepository,
    PermissionEventRepository,
    PermissionRepository,
    ProjectBudgetRepository,
    ProjectRepository,
    ProviderProfileRepository,
    RoleAssignmentRepository,
    RunRepository,
    SandboxAuditRepository,
    ScenarioRepository,
    UsageRepository,
)
from .utils import ensure_text, new_id, safe_relative_path, utc_now


class ProjectStore:
    def __init__(self, data_dir: Path | str | None = None) -> None:
        self.data_dir = (
            Path(data_dir).expanduser().resolve() if data_dir is not None else default_data_dir()
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self.data_dir / "workspace.state"
        self._lock = InstanceLock(self.data_dir / "workspace.lock")
        self._lock.acquire()
        self._closed = False
        database = None
        try:
            self.recovery_message = self._state_path.read_text(encoding="utf-8") if (
                self._state_path.exists()
            ) else None
            database = Database(self.data_dir / "workspace.db")
            if self.recovery_message is not None:
                ok, message = database.integrity()
                if not ok:
                    raise IntegrityError(
                        f"base locale corrompue après arrêt anormal: {message}"
                    )
                self.recovery_message = message
            self.results_dir = self.data_dir / "results"
            self.results_dir.mkdir(parents=True, exist_ok=True)
            self.db = database
            self.projects = ProjectRepository(database.conn)
            self.messages = MessageRepository(database.conn)
            self.briefs = BriefRepository(database.conn)
            self.scenarios = ScenarioRepository(database.conn)
            self.runs = RunRepository(database.conn)
            self.provider_profiles = ProviderProfileRepository(database.conn)
            self.usage = UsageRepository(database.conn)
            self.permissions = PermissionRepository(database.conn)
            self.permission_events = PermissionEventRepository(database.conn)
            self.roles = RoleAssignmentRepository(database.conn)
            self.budgets = ProjectBudgetRepository(database.conn)
            self.agent_sessions = AgentSessionRepository(database.conn)
            self.agent_trace = AgentTraceRepository(database.conn)
            self.benchmark_packs = BenchmarkPackRepository(database.conn)
            self.benchmark_pack_events = BenchmarkPackEventRepository(database.conn)
            self.sandbox_audit = SandboxAuditRepository(database.conn)
            self._state_path.write_text(utc_now(), encoding="utf-8")
        except Exception:
            if database is not None:
                database.close()
            self._lock.release()
            raise

    def create_project(
        self,
        name: str,
        *,
        description: str = "",
        currency: str = "XOF",
        sector: str | None = None,
        metadata: dict[str, Any] | None = None,
        engine_version: str | None = None,
    ) -> Project:
        return self.projects.create(
            name,
            description=description,
            currency=currency,
            sector=sector,
            metadata=metadata,
            engine_version=engine_version,
        )

    def list_projects(
        self, *, include_archived: bool = False, include_trashed: bool = False
    ) -> list[Project]:
        return self.projects.list(
            include_archived=include_archived, include_trashed=include_trashed
        )

    def get_project(self, project_id: str) -> Project:
        return self.projects.require(project_id)

    def open_project(self, project_id: str) -> Project:
        project = self.projects.require(project_id)
        if project.status == "trashed":
            raise StorageValidationError("ce projet est dans la corbeille")
        return self.projects.update(project_id, status="active", deleted_at=None)

    def rename_project(self, project_id: str, name: str) -> Project:
        return self.projects.update(project_id, name=name)

    def duplicate_project(self, project_id: str, *, name: str | None = None) -> Project:
        source = self.projects.require(project_id)
        new_name = ensure_text(name, "name") if name is not None else f"{source.name} (copie)"
        new_project_id = new_id()
        source_results = self.results_dir / project_id
        final_results = self.results_dir / new_project_id
        staging = self.results_dir / f".{new_project_id}.tmp"
        try:
            with self.db.transaction(immediate=True):
                clone = clone_project(
                    self.db.conn,
                    self.db.conn,
                    project_id,
                    new_project_id=new_project_id,
                    new_name=new_name,
                    preserve_ids=False,
                    preserve_status=False,
                    reset_timestamps=True,
                )
                _install_results(source_results, staging, clone.run_paths)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        try:
            staging.replace(final_results)
        except OSError as error:
            self.projects.delete(new_project_id)
            shutil.rmtree(staging, ignore_errors=True)
            raise IntegrityError(f"impossible d'installer les résultats: {error}") from error
        return self.projects.require(new_project_id)

    def archive_project(self, project_id: str) -> Project:
        return self.projects.update(project_id, status="archived", deleted_at=None)

    def restore_project(self, project_id: str) -> Project:
        return self.projects.update(project_id, status="active", deleted_at=None)

    def trash_project(self, project_id: str) -> Project:
        return self.projects.update(
            project_id, status="trashed", deleted_at=utc_now()
        )

    def delete_project(self, project_id: str) -> bool:
        self.projects.require(project_id)
        deleted = self.projects.delete(project_id)
        if deleted:
            shutil.rmtree(self.results_dir / project_id, ignore_errors=True)
            shutil.rmtree(self.results_dir / f".{project_id}.tmp", ignore_errors=True)
        return deleted

    def project_size(self, project_id: str) -> dict[str, int]:
        self.projects.require(project_id)
        database_bytes = self._estimated_database_bytes(project_id)
        project_results = self.results_dir / project_id
        results_bytes = 0
        if project_results.is_dir():
            results_bytes = sum(
                path.stat().st_size for path in project_results.rglob("*") if path.is_file()
            )
        return {
            "databaseBytes": database_bytes,
            "resultsBytes": results_bytes,
            "totalBytes": database_bytes + results_bytes,
        }

    def export_project(self, project_id: str, destination: Path | str) -> ExportInfo:
        return export_project(
            self.db.conn, project_id, self.results_dir, Path(destination)
        )

    def import_project(self, source: Path | str, *, name: str | None = None) -> Project:
        return import_project(self.db.conn, self.results_dir, Path(source), name=name)

    def save_run_detail(
        self, project_id: str, run_id: str, payload: dict[str, Any]
    ) -> str:
        self.projects.require(project_id)
        run = self.runs.get(run_id)
        if run is None or run.project_id != project_id:
            raise StorageValidationError(f"run introuvable: {run_id}")
        directory = self.results_dir / project_id
        directory.mkdir(parents=True, exist_ok=True)
        relative = f"{run_id}.json.gz"
        target = directory / relative
        temporary = target.with_name(f"{target.name}.tmp")
        try:
            with gzip.open(temporary, "wt", encoding="utf-8") as stream:
                json.dump(
                    payload,
                    stream,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            temporary.replace(target)
            self.runs.attach_result(run_id, relative)
        except Exception:
            temporary.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            raise
        return relative

    def load_run_detail(self, project_id: str, run_id: str) -> dict[str, Any]:
        run = self.runs.get(run_id)
        if run is None or run.project_id != project_id:
            raise StorageValidationError(f"run introuvable: {run_id}")
        if run.result_path is None:
            raise StorageValidationError(f"run sans résultat détaillé: {run_id}")
        relative = safe_relative_path(run.result_path)
        path = self.results_dir / project_id / relative
        if not path.is_file():
            raise IntegrityError(f"résultat détaillé manquant: {run.result_path}")
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            value = json.load(stream)
        if not isinstance(value, dict):
            raise IntegrityError(f"résultat détaillé invalide: {run.result_path}")
        return value

    def prune_runs(self, project_id: str, *, keep: int = 50) -> int:
        self.projects.require(project_id)
        removed_paths = self.runs.prune(project_id, keep=keep)
        for path in removed_paths:
            relative = safe_relative_path(path)
            (self.results_dir / project_id / relative).unlink(missing_ok=True)
        return len(removed_paths)

    def export_sandbox_audit(self, project_id: str) -> tuple[Path, int]:
        self.projects.require(project_id)
        records = self.sandbox_audit.list(project_id, limit=100_000)
        directory = self.results_dir / project_id
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / "sandbox-audit.json"
        payload = {
            "version": 1,
            "projectId": project_id,
            "exportedAt": utc_now(),
            "count": len(records),
            "records": [record.to_dict() for record in records],
        }
        temporary = destination.with_name(f"{destination.name}.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination, len(records)

    def check_integrity(self) -> tuple[bool, str]:
        return check_database_integrity(self.db)

    def backup(self, destination_dir: Path | str | None = None) -> Path:
        directory = (
            Path(destination_dir).expanduser()
            if destination_dir is not None
            else self.data_dir / "backups"
        )
        return backup_database(self.db, directory)

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.db.close()
        finally:
            self._state_path.unlink(missing_ok=True)
            self._lock.release()
            self._closed = True

    def _estimated_database_bytes(self, project_id: str) -> int:
        queries = (
            (
                "SELECT LENGTH(COALESCE(name, '')) + LENGTH(COALESCE(description, ''))"
                " + LENGTH(COALESCE(metadata_json, '')) FROM projects WHERE id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(COALESCE(content, ''))"
                " + LENGTH(COALESCE(metadata_json, ''))), 0)"
                " FROM messages WHERE project_id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(COALESCE(content_json, ''))), 0)"
                " FROM briefs WHERE project_id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(COALESCE(scenario_json, ''))), 0)"
                " FROM scenarios WHERE project_id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(COALESCE(summary_json, ''))"
                " + LENGTH(COALESCE(result_json, ''))"
                " + LENGTH(COALESCE(result_path, ''))), 0)"
                " FROM simulation_runs WHERE project_id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(COALESCE(name, ''))"
                " + LENGTH(COALESCE(provider, ''))"
                " + LENGTH(COALESCE(base_url, ''))"
                " + LENGTH(COALESCE(model, ''))"
                " + LENGTH(COALESCE(keychain_ref, ''))"
                " + LENGTH(COALESCE(capabilities_json, ''))), 0)"
                " FROM provider_profiles WHERE project_id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(COALESCE(metadata_json, ''))), 0)"
                " FROM usage_log WHERE project_id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(COALESCE(tool, ''))"
                " + LENGTH(COALESCE(scope, ''))"
                " + LENGTH(COALESCE(decision, ''))), 0)"
                " FROM tool_permissions WHERE project_id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(COALESCE(thread_json, ''))), 0)"
                " FROM agent_sessions WHERE project_id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(COALESCE(event_json, ''))), 0)"
                " FROM agent_trace WHERE project_id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(COALESCE(tool, ''))"
                " + LENGTH(COALESCE(scope, ''))"
                " + LENGTH(COALESCE(decision, ''))"
                " + LENGTH(COALESCE(reason, ''))), 0)"
                " FROM permission_events WHERE project_id = ?",
                (project_id,),
            ),
            (
                "SELECT COALESCE(SUM(LENGTH(code) + LENGTH(code_hash)"
                " + LENGTH(purpose) + LENGTH(COALESCE(analysis_json, ''))"
                " + LENGTH(COALESCE(result_json, ''))"
                " + LENGTH(COALESCE(error, ''))), 0)"
                " FROM sandbox_audit WHERE project_id = ?",
                (project_id,),
            ),
        )
        total = 0
        for query, params in queries:
            total += int(self.db.conn.execute(query, params).fetchone()[0])
        return total

    def __enter__(self) -> ProjectStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _install_results(
    source_results: Path, staging: Path, run_paths: list[tuple[str, str]]
) -> None:
    if staging.exists():
        shutil.rmtree(staging)
    if source_results.is_dir():
        shutil.copytree(source_results, staging)
    else:
        staging.mkdir(parents=True)
    for old_path, new_path in run_paths:
        source = source_results / old_path
        if not source.is_file():
            raise IntegrityError(f"résultat détaillé manquant: {old_path}")
        target = staging / new_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if old_path != new_path:
            shutil.copy2(source, target)
            (staging / old_path).unlink(missing_ok=True)
        if not target.is_file():
            raise IntegrityError(f"résultat non copié: {new_path}")
