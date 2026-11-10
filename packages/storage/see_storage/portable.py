from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .cloning import clone_project
from .database import Database
from .errors import IntegrityError, PortableError, SchemaTooNewError
from .migrations import LATEST_SCHEMA_VERSION
from .models import Project
from .repositories import ProjectRepository
from .utils import ensure_text, new_id, sha256_file, utc_now

FORMAT = "see-the-future.simproj"
FORMAT_VERSION = 1
CHECKSUM_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ExportInfo:
    path: Path
    checksum: str
    size_bytes: int


def _validate_archive_name(name: str) -> str:
    if not name or "\\" in name or "\x00" in name:
        raise PortableError(f"chemin d'archive invalide: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise PortableError(f"chemin d'archive interdit: {name}")
    if path.parts and ":" in path.parts[0]:
        raise PortableError(f"chemin d'archive absolu: {name}")
    return path.as_posix()


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _read_manifest(raw: bytes) -> dict[str, Any]:
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PortableError(f"manifeste illisible: {error}") from error
    if not isinstance(manifest, dict):
        raise PortableError("manifeste invalide")
    if manifest.get("format") != FORMAT:
        raise PortableError(f"format d'archive inconnu: {manifest.get('format')!r}")
    try:
        format_version = int(manifest.get("formatVersion", 0))
        schema_version = int(manifest.get("schemaVersion", 0))
    except (TypeError, ValueError) as error:
        raise PortableError("versions du manifeste invalides") from error
    if format_version < 1 or format_version > FORMAT_VERSION:
        raise PortableError(f"version d'archive non supportée: {format_version}")
    if schema_version < 1:
        raise PortableError("version de schéma absente du manifeste")
    if schema_version > LATEST_SCHEMA_VERSION:
        raise SchemaTooNewError(
            f"schéma du projet v{schema_version} plus récent que v{LATEST_SCHEMA_VERSION}"
        )
    if not isinstance(manifest.get("projectId"), str) or not manifest["projectId"]:
        raise PortableError("identifiant de projet absent du manifeste")
    if not isinstance(manifest.get("name"), str) or not manifest["name"].strip():
        raise PortableError("nom de projet absent du manifeste")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise PortableError("liste de fichiers absente du manifeste")
    if "manifest.json" in files:
        raise PortableError("le manifeste ne peut pas se référencer lui-même")
    for name, checksum in files.items():
        if not isinstance(name, str) or not isinstance(checksum, str):
            raise PortableError("entrée de fichier invalide dans le manifeste")
        _validate_archive_name(name)
        if not CHECKSUM_PATTERN.match(checksum):
            raise PortableError(f"empreinte invalide pour {name}")
    if "project.db" not in files:
        raise PortableError("base projet absente du manifeste")
    return manifest


def _extract_archive(archive: zipfile.ZipFile, destination: Path) -> set[str]:
    names: set[str] = set()
    for info in archive.infolist():
        if info.is_dir():
            continue
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise PortableError(f"lien symbolique interdit dans l'archive: {info.filename}")
        name = _validate_archive_name(info.filename)
        if name in names:
            raise PortableError(f"fichier dupliqué dans l'archive: {name}")
        names.add(name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, target.open("wb") as stream:
            shutil.copyfileobj(source, stream)
    return names


def _verify_extracted(extracted: Path, manifest: dict[str, Any], names: set[str]) -> None:
    files = manifest["files"]
    if "manifest.json" not in names:
        raise PortableError("manifeste absent de l'archive")
    expected = set(files)
    actual = {name for name in names if name != "manifest.json"}
    missing = expected - actual
    extra = actual - expected
    if missing:
        raise PortableError(f"fichiers manquants dans l'archive: {', '.join(sorted(missing))}")
    if extra:
        raise PortableError(f"fichiers non déclarés dans l'archive: {', '.join(sorted(extra))}")
    for name, checksum in files.items():
        path = extracted / name
        if not path.is_file():
            raise PortableError(f"fichier absent après extraction: {name}")
        if sha256_file(path) != checksum:
            raise PortableError(f"empreinte invalide pour {name}")


def export_project(
    conn: sqlite3.Connection,
    project_id: str,
    results_dir: Path,
    destination: Path,
) -> ExportInfo:
    project = ProjectRepository(conn).require(project_id)
    destination = destination.expanduser().resolve()
    if destination.suffix.lower() != ".simproj":
        raise PortableError("l'export doit porter l'extension .simproj")
    if destination.exists() and destination.is_dir():
        raise PortableError(f"destination invalide: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="see-export-") as temporary:
        root = Path(temporary)
        snapshot_path = root / "project.db"
        snapshot = Database(snapshot_path, journal_mode="DELETE")
        try:
            clone = clone_project(
                conn,
                snapshot.conn,
                project_id,
                preserve_ids=True,
                preserve_status=True,
                reset_timestamps=False,
            )
            snapshot.conn.commit()
        finally:
            snapshot.close()

        source_results = results_dir / project_id
        for old_path, _new_path in clone.run_paths:
            if not (source_results / old_path).is_file():
                raise PortableError(f"résultat détaillé manquant: {old_path}")

        if source_results.is_dir():
            for source in source_results.rglob("*"):
                if not source.is_file():
                    continue
                relative = source.relative_to(source_results).as_posix()
                target = root / "results" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

        file_paths = [snapshot_path]
        results_root = root / "results"
        if results_root.is_dir():
            file_paths.extend(sorted(path for path in results_root.rglob("*") if path.is_file()))

        files = {
            path.relative_to(root).as_posix(): sha256_file(path) for path in file_paths
        }
        manifest = {
            "format": FORMAT,
            "formatVersion": FORMAT_VERSION,
            "schemaVersion": LATEST_SCHEMA_VERSION,
            "projectId": project.id,
            "name": project.name,
            "createdAt": project.created_at,
            "updatedAt": project.updated_at,
            "exportedAt": utc_now(),
            "files": files,
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_bytes(_manifest_bytes(manifest))

        archive_path = destination.parent / f".{destination.name}.{new_id()}.tmp"
        try:
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted([manifest_path, *file_paths]):
                    archive.write(path, path.relative_to(root).as_posix())
            checksum = sha256_file(archive_path)
            size_bytes = archive_path.stat().st_size
            os.replace(archive_path, destination)
        finally:
            archive_path.unlink(missing_ok=True)

    return ExportInfo(path=destination, checksum=checksum, size_bytes=size_bytes)


def import_project(
    conn: sqlite3.Connection,
    results_dir: Path,
    source_path: Path,
    *,
    name: str | None = None,
) -> Project:
    source_path = Path(source_path).expanduser()
    if not source_path.is_file():
        raise PortableError(f"archive introuvable: {source_path}")
    results_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="see-import-") as temporary:
        root = Path(temporary)
        try:
            with zipfile.ZipFile(source_path) as archive:
                names = _extract_archive(archive, root)
                if "manifest.json" not in names:
                    raise PortableError("manifeste absent de l'archive")
                manifest = _read_manifest((root / "manifest.json").read_bytes())
        except zipfile.BadZipFile as error:
            raise PortableError(f"archive .simproj invalide: {error}") from error
        _verify_extracted(root, manifest, names)

        snapshot = Database(root / "project.db", journal_mode="DELETE")
        try:
            snapshot_project = ProjectRepository(snapshot.conn).get(manifest["projectId"])
            if snapshot_project is None:
                raise PortableError("projet déclaré absent de la base exportée")
            project_name = ensure_text(name or manifest["name"], "name")
            project_id = new_id()
            project_results = results_dir / project_id
            staging = results_dir / f".{project_id}.tmp"
            source_results = root / "results"
            if source_results.is_dir():
                shutil.copytree(source_results, staging)
            else:
                staging.mkdir(parents=True)

            own_transaction = not conn.in_transaction
            if own_transaction:
                conn.execute("BEGIN IMMEDIATE")
            try:
                clone = clone_project(
                    snapshot.conn,
                    conn,
                    snapshot_project.id,
                    new_project_id=project_id,
                    new_name=project_name,
                    preserve_ids=False,
                    preserve_status=False,
                    reset_timestamps=True,
                )
                for old_path, new_path in clone.run_paths:
                    source = source_results / old_path
                    if not source.is_file():
                        raise PortableError(f"résultat détaillé manquant: {old_path}")
                    target = staging / new_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if old_path != new_path:
                        shutil.copy2(source, target)
                        (staging / old_path).unlink(missing_ok=True)
                    if not target.is_file():
                        raise IntegrityError(f"résultat non copié: {new_path}")
                if own_transaction:
                    conn.commit()
            except Exception:
                if own_transaction:
                    conn.rollback()
                shutil.rmtree(staging, ignore_errors=True)
                raise
        finally:
            snapshot.close()

        try:
            os.replace(staging, project_results)
        except OSError as error:
            ProjectRepository(conn).delete(project_id)
            shutil.rmtree(staging, ignore_errors=True)
            raise PortableError(f"impossible d'installer les résultats: {error}") from error

    return ProjectRepository(conn).require(project_id)
