from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import see_storage.database as database_module
from see_storage import (
    LATEST_SCHEMA_VERSION,
    Database,
    IntegrityError,
    ProjectStore,
    SchemaTooNewError,
    assert_no_secret_columns,
    find_secret_like_columns,
    restore,
)
from see_storage.repositories import ProjectRepository


def test_migrations_are_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "workspace.db"
    database = Database(path)
    database.close()
    reopened = Database(path)
    version = reopened.conn.execute("PRAGMA user_version").fetchone()[0]
    tables = {
        row[0]
        for row in reopened.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    reopened.close()
    assert version == LATEST_SCHEMA_VERSION
    assert {"projects", "messages", "briefs", "simulation_runs"} <= tables
    assert {"role_assignments", "project_budgets"} <= tables
    assert {"agent_sessions", "agent_trace", "permission_events"} <= tables
    assert "sandbox_audit" in tables


def test_schema_newer_than_application_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "workspace.db"
    Database(path).close()
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA user_version = 99")
    raw.commit()
    raw.close()
    with pytest.raises(SchemaTooNewError):
        Database(path)


def test_schema_contains_no_secret_like_columns() -> None:
    assert find_secret_like_columns() == []
    assert_no_secret_columns()


def test_integrity_backup_and_restore(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    store = ProjectStore(data_dir)
    project = store.create_project("Sauvegardé")
    assert store.check_integrity() == (True, "ok")
    backup = store.backup(tmp_path / "backups")
    assert backup.is_file()
    store.projects.delete(project.id)
    store.close()

    restore(data_dir / "workspace.db", backup)
    reopened = ProjectStore(data_dir)
    try:
        assert reopened.get_project(project.id).name == "Sauvegardé"
    finally:
        reopened.close()


def test_corrupted_database_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "workspace.db"
    path.write_bytes(b"not a sqlite database")
    with pytest.raises(IntegrityError, match="illisible"):
        Database(path)


def test_two_connections_can_write_without_corruption(tmp_path: Path) -> None:
    path = tmp_path / "workspace.db"
    first = Database(path)
    second = Database(path)
    try:
        ProjectRepository(first.conn).create("Premier")
        ProjectRepository(second.conn).create("Second")
        assert ProjectRepository(first.conn).count() == 2
        ok, message = first.integrity()
        assert ok, message
    finally:
        first.close()
        second.close()


def test_migration_preserves_data_and_creates_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "workspace.db"
    first_migration = database_module.MIGRATIONS[0]
    monkeypatch.setattr(database_module, "LATEST_SCHEMA_VERSION", 1)
    monkeypatch.setattr(database_module, "MIGRATIONS", (first_migration,))
    database = Database(path)
    ProjectRepository(database.conn).create("Ancien projet")
    database.close()

    monkeypatch.setattr(database_module, "LATEST_SCHEMA_VERSION", 2)
    monkeypatch.setattr(
        database_module,
        "MIGRATIONS",
        (
            first_migration,
            (2, "ALTER TABLE projects ADD COLUMN test_flag INTEGER NOT NULL DEFAULT 0;"),
        ),
    )

    migrated = Database(path)
    try:
        assert ProjectRepository(migrated.conn).list()[0].name == "Ancien projet"
        version = migrated.conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 2
        assert (tmp_path / "backups" / "workspace.v1.bak").is_file()
    finally:
        migrated.close()
