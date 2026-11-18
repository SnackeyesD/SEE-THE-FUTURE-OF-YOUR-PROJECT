from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .database import Database, backup_database, find_secret_like_columns
from .errors import IntegrityError


def check_integrity(database: Database) -> tuple[bool, str]:
    ok, message = database.integrity()
    if not ok:
        return ok, message
    checks = (
        (
            "versions liées à un scénario d'un autre projet",
            """
            SELECT COUNT(*) FROM scenario_versions v
            JOIN scenarios s ON s.id = v.scenario_id
            WHERE s.project_id != v.project_id
            """,
        ),
        (
            "runs liés à un scénario d'un autre projet",
            """
            SELECT COUNT(*) FROM simulation_runs r
            JOIN scenarios s ON s.id = r.scenario_id
            WHERE s.project_id != r.project_id
            """,
        ),
        (
            "runs liés à une version d'un autre projet",
            """
            SELECT COUNT(*) FROM simulation_runs r
            JOIN scenario_versions v ON v.id = r.scenario_version_id
            WHERE v.project_id != r.project_id
            """,
        ),
        (
            "branches dont le parent appartient à un autre projet",
            """
            SELECT COUNT(*) FROM scenarios child
            JOIN scenarios parent ON parent.id = child.parent_id
            WHERE parent.project_id != child.project_id
            """,
        ),
    )
    problems = []
    for label, query in checks:
        count = int(database.conn.execute(query).fetchone()[0])
        if count:
            problems.append(f"{label}: {count}")
    if problems:
        return False, "; ".join(problems)
    return True, "ok"


def backup(database: Database, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    destination = destination_dir / f"workspace-{timestamp}.db"
    return backup_database(database.conn, destination)


def restore(database_path: Path, backup_path: Path) -> None:
    if not backup_path.is_file():
        raise IntegrityError(f"sauvegarde introuvable: {backup_path}")
    check = sqlite3.connect(str(backup_path))
    try:
        rows = check.execute("PRAGMA integrity_check").fetchall()
        messages = [str(row[0]) for row in rows]
        if len(messages) != 1 or messages[0].lower() != "ok":
            raise IntegrityError(f"sauvegarde corrompue: {'; '.join(messages)}")
    finally:
        check.close()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(f"{database_path}{suffix}").unlink(missing_ok=True)
    temporary = database_path.with_suffix(database_path.suffix + ".restore")
    shutil.copy2(backup_path, temporary)
    temporary.replace(database_path)


def assert_no_secret_columns() -> None:
    columns = find_secret_like_columns()
    if columns:
        raise IntegrityError(f"colonnes ressemblant à des secrets: {', '.join(columns)}")
