from __future__ import annotations

import os
import re
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .errors import IntegrityError, SchemaTooNewError
from .migrations import LATEST_SCHEMA_VERSION, MIGRATIONS
from .utils import utc_now

SECRET_COLUMN_PATTERN = re.compile(
    r"\b(api_key|secret|password|authorization|private_key|access_token|refresh_token)\b",
    re.IGNORECASE,
)


def default_data_dir() -> Path:
    override = os.environ.get("SEE_DATA_DIR")
    if override:
        return Path(override).expanduser()
    application = "SeeTheFuture"
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / application


def find_secret_like_columns(schema_sql: str | None = None) -> list[str]:
    source = schema_sql if schema_sql is not None else "\n".join(sql for _, sql in MIGRATIONS)
    return sorted({match.group(0).lower() for match in SECRET_COLUMN_PATTERN.finditer(source)})


def backup_database(conn: sqlite3.Connection, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(str(destination))
    try:
        conn.backup(target)
    finally:
        target.close()
    return destination


class Database:
    def __init__(
        self, path: str | Path, *, migrate: bool = True, journal_mode: str = "WAL"
    ) -> None:
        if journal_mode not in {"WAL", "DELETE", "TRUNCATE", "MEMORY", "OFF"}:
            raise ValueError(f"journal_mode invalide: {journal_mode}")
        self.path = None if str(path) == ":memory:" else Path(path)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(":memory:" if self.path is None else str(self.path), timeout=10)
        self.conn.row_factory = sqlite3.Row
        self._journal_mode = journal_mode
        try:
            self._configure()
            if migrate:
                self.migrate()
        except sqlite3.DatabaseError as error:
            self.conn.close()
            raise IntegrityError(f"base SQLite illisible: {error}") from error

    def _configure(self) -> None:
        self.conn.execute(f"PRAGMA journal_mode={self._journal_mode}")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("PRAGMA synchronous=NORMAL")

    def _current_version(self) -> int:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        version = int(self.conn.execute("PRAGMA user_version").fetchone()[0])
        if version == 0:
            row = self.conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            ).fetchone()
            version = int(row[0])
        return version

    def _backup_before_migration(self, version: int) -> None:
        if self.path is None or not self.path.exists() or self.path.stat().st_size == 0:
            return
        backup = self.path.parent / "backups" / f"{self.path.stem}.v{version}.bak"
        backup_database(self.conn, backup)

    def migrate(self) -> None:
        current = self._current_version()
        if current > LATEST_SCHEMA_VERSION:
            raise SchemaTooNewError(
                f"schéma local v{current} plus récent que v{LATEST_SCHEMA_VERSION}"
            )
        if 0 < current < LATEST_SCHEMA_VERSION:
            self._backup_before_migration(current)
        for version, sql in MIGRATIONS:
            if version <= current:
                continue
            script = (
                "BEGIN IMMEDIATE;\n"
                f"{sql}\n"
                "INSERT OR REPLACE INTO schema_migrations(version, applied_at) "
                f"VALUES ({version}, '{utc_now()}');\n"
                f"PRAGMA user_version = {version};\n"
                "COMMIT;"
            )
            try:
                self.conn.executescript(script)
            except sqlite3.Error as error:
                self.conn.rollback()
                raise IntegrityError(f"migration v{version} impossible: {error}") from error

    def integrity(self) -> tuple[bool, str]:
        rows = self.conn.execute("PRAGMA integrity_check").fetchall()
        messages = [str(row[0]) for row in rows]
        ok = len(messages) == 1 and messages[0].lower() == "ok"
        return ok, "; ".join(messages)

    def file_size(self) -> int:
        if self.path is None or not self.path.exists():
            return 0
        return self.path.stat().st_size

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        self.conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        try:
            yield self.conn
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
