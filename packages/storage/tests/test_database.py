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
    scenario = store.scenarios.add(project.id, "Base", "retail_depot", {"runs": 1})
    version = store.versions.create(
        project.id, scenario.id, "Référence", scenario.scenario, seed=3
    )
    assert store.check_integrity() == (True, "ok")
    backup = store.backup(tmp_path / "backups")
    assert backup.is_file()
    store.projects.delete(project.id)
    store.close()

    restore(data_dir / "workspace.db", backup)
    reopened = ProjectStore(data_dir)
    try:
        assert reopened.get_project(project.id).name == "Sauvegardé"
        assert reopened.versions.get(version.id) is not None
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


def test_migration_v5_to_v6_preserves_data_and_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "workspace.db"
    original_migrations = database_module.MIGRATIONS
    original_latest = database_module.LATEST_SCHEMA_VERSION
    monkeypatch.setattr(database_module, "LATEST_SCHEMA_VERSION", 5)
    monkeypatch.setattr(database_module, "MIGRATIONS", original_migrations[:5])

    legacy = Database(path)
    now = "2026-01-01T00:00:00+00:00"
    legacy.conn.execute(
        """
        INSERT INTO projects (
            id, name, description, currency, sector, status, created_at, updated_at,
            schema_version, engine_version, metadata_json, deleted_at
        ) VALUES ('p1', 'Ancien', '', 'XOF', NULL, 'active', ?, ?, 1, NULL, '{}', NULL)
        """,
        (now, now),
    )
    legacy.conn.execute(
        """
        INSERT INTO scenarios (
            id, project_id, name, model, scenario_json, created_at, updated_at
        ) VALUES ('s1', 'p1', 'Base', 'retail_depot', '{"runs": 10}', ?, ?)
        """,
        (now, now),
    )
    legacy.conn.execute(
        """
        INSERT INTO simulation_runs (
            id, project_id, scenario_id, engine_version, seed, runs, duration_ms,
            summary_json, result_json, result_path, created_at
        ) VALUES ('r1', 'p1', 's1', '0.2.0', 1, 10, 1.0, '{}', '{}', NULL, ?)
        """,
        (now,),
    )
    legacy.conn.commit()
    legacy.close()

    monkeypatch.setattr(database_module, "LATEST_SCHEMA_VERSION", original_latest)
    monkeypatch.setattr(database_module, "MIGRATIONS", original_migrations)
    migrated = Database(path)
    try:
        version = migrated.conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == LATEST_SCHEMA_VERSION
        scenario = migrated.conn.execute(
            "SELECT * FROM scenarios WHERE id = 's1'"
        ).fetchone()
        assert scenario["parent_id"] is None
        assert scenario["branch_label"] is None
        assert scenario["version"] == 1
        run = migrated.conn.execute(
            "SELECT * FROM simulation_runs WHERE id = 'r1'"
        ).fetchone()
        assert run["quality"] == "final"
        assert run["scenario_version_id"] is None
        assert run["pinned"] == 0
        assert run["status"] == "complete"
        assert run["summary_json"] == "{}"
    finally:
        migrated.close()
    assert (tmp_path / "backups" / "workspace.v5.bak").is_file()


def test_integrity_detects_cross_project_version(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "data")
    try:
        first = store.create_project("Premier")
        second = store.create_project("Deuxième")
        scenario = store.scenarios.add(second.id, "Base", "retail_depot", {})
        store.db.conn.execute("PRAGMA foreign_keys=OFF")
        store.db.conn.execute(
            """
            INSERT INTO scenario_versions (
                id, project_id, scenario_id, label, scenario_json, seed,
                engine_version, created_at
            ) VALUES ('v1', ?, ?, 'Croisée', '{}', NULL, NULL, ?)
            """,
            (first.id, scenario.id, "2026-01-01T00:00:00+00:00"),
        )
        store.db.conn.commit()
        store.db.conn.execute("PRAGMA foreign_keys=ON")

        ok, message = store.check_integrity()
        assert not ok
        assert "autre projet" in message
    finally:
        store.close()


def test_integrity_detects_missing_foreign_key(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "data")
    try:
        store.db.conn.execute("PRAGMA foreign_keys=OFF")
        store.db.conn.execute(
            """
            INSERT INTO scenario_versions (
                id, project_id, scenario_id, label, scenario_json, seed,
                engine_version, created_at
            ) VALUES ('v1', 'absent', NULL, 'Orpheline', '{}', NULL, NULL, ?)
            """,
            ("2026-01-01T00:00:00+00:00",),
        )
        store.db.conn.commit()
        store.db.conn.execute("PRAGMA foreign_keys=ON")

        ok, message = store.check_integrity()
        assert not ok
        assert "clés étrangères invalides" in message
    finally:
        store.close()
