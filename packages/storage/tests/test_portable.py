from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from see_storage import PortableError, ProjectStore, SchemaTooNewError


def _populate(store: ProjectStore, project_id: str) -> str:
    store.messages.add(project_id, "user", "Bonjour")
    store.briefs.add_version(project_id, {"problem": "Tester l'export"})
    profile = store.provider_profiles.upsert(
        project_id, "Local", "ollama", base_url="http://localhost:11434", model="qwen"
    )
    store.usage.add(
        project_id,
        "chat",
        provider_profile_id=profile.id,
        input_tokens=12,
        output_tokens=34,
        cost_micros=56,
    )
    store.permissions.set(project_id, "sandbox", "project", "ask")
    store.roles.set(project_id, "modeler", profile.id, "qwen")
    store.budgets.set(project_id, 5_000_000)
    session = store.agent_sessions.upsert(
        project_id,
        "interviewing",
        "interviewer",
        [{"role": "user", "content": "Bonjour"}],
    )
    store.agent_trace.add(
        project_id,
        {"kind": "response", "data": {"status": "ok"}},
        session_id=session.id,
        turn=1,
    )
    store.permission_events.add(project_id, "web_search", "project", "ask")
    store.sandbox_audit.add(
        project_id,
        "def main(data):\n    return {'metrics': []}\n",
        "c" * 64,
        "approved",
        "succeeded",
        analysis={"ok": True},
        result={"metrics": []},
        duration_ms=3.0,
    )
    scenario = store.scenarios.add(project_id, "Base", "retail_depot", {"model": "retail_depot"})
    run = store.runs.add(
        project_id,
        "0.1.0",
        100,
        {"mean": 1.0},
        scenario_id=scenario.id,
        result_path="detail.json.gz",
    )
    directory = store.results_dir / project_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / run.result_path).write_bytes(b"result-detail")
    return run.id


def _rewrite(
    source: Path,
    destination: Path,
    transform: Callable[[str, bytes], bytes | None],
) -> None:
    with zipfile.ZipFile(source) as reader, zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED
    ) as writer:
        for info in reader.infolist():
            if info.is_dir():
                continue
            data = transform(info.filename, reader.read(info.filename))
            if data is not None:
                writer.writestr(info, data)


def test_export_import_round_trip(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Portable", description="à transporter")
    run_id = _populate(store, project.id)
    archive = tmp_path / "portable.simproj"
    info = store.export_project(project.id, archive)

    assert info.path == archive.resolve()
    assert info.checksum
    with zipfile.ZipFile(archive) as reader:
        manifest = json.loads(reader.read("manifest.json"))
        assert manifest["format"] == "see-the-future.simproj"
        assert manifest["formatVersion"] == 1
        assert manifest["projectId"] == project.id
        assert manifest["name"] == "Portable"
        assert set(manifest["files"]) == {"project.db", "results/detail.json.gz"}
        for name, checksum in manifest["files"].items():
            assert hashlib.sha256(reader.read(name)).hexdigest() == checksum

    imported = store.import_project(archive, name="Portable importé")
    assert imported.id != project.id
    assert imported.name == "Portable importé"
    assert imported.status == "active"
    assert store.messages.count(imported.id) == 1
    assert store.briefs.latest(imported.id).content == {"problem": "Tester l'export"}
    assert store.usage.summary(imported.id)["inputTokens"] == 12
    assert store.permissions.list(imported.id)[0].decision == "ask"
    imported_profile = store.provider_profiles.list(imported.id)[0]
    imported_role = store.roles.get(imported.id, "modeler")
    assert imported_role is not None
    assert imported_role.provider_profile_id == imported_profile.id
    assert imported_role.model == "qwen"
    imported_budget = store.budgets.get(imported.id)
    assert imported_budget is not None
    assert imported_budget.limit_micros == 5_000_000
    imported_session = store.agent_sessions.get(imported.id)
    assert imported_session is not None
    assert imported_session.state == "interviewing"
    assert imported_session.thread == [{"role": "user", "content": "Bonjour"}]
    imported_trace = store.agent_trace.list(imported.id)
    assert len(imported_trace) == 1
    assert imported_trace[0].session_id == imported_session.id
    assert store.permission_events.list(imported.id)[0].tool == "web_search"
    imported_audit = store.sandbox_audit.list(imported.id)
    assert len(imported_audit) == 1
    assert imported_audit[0].result == {"metrics": []}
    runs = store.runs.list(imported.id)
    assert len(runs) == 1
    imported_run = runs[0]
    assert imported_run.id != run_id
    assert imported_run.result_path == f"{imported_run.id}.json.gz"
    assert (store.results_dir / imported.id / imported_run.result_path).read_bytes() == (
        b"result-detail"
    )


def test_import_rejects_corrupted_checksum(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Corrompu")
    _populate(store, project.id)
    archive = tmp_path / "source.simproj"
    store.export_project(project.id, archive)
    corrupted = tmp_path / "corrupted.simproj"
    _rewrite(
        archive,
        corrupted,
        lambda name, data: data[:-1] if name == "project.db" else data,
    )
    with pytest.raises(PortableError, match="empreinte invalide"):
        store.import_project(corrupted)


def test_import_rejects_missing_declared_file(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Manquant")
    _populate(store, project.id)
    archive = tmp_path / "source.simproj"
    store.export_project(project.id, archive)
    missing = tmp_path / "missing.simproj"
    _rewrite(
        archive,
        missing,
        lambda name, data: None if name.endswith(".json.gz") else data,
    )
    with pytest.raises(PortableError, match="fichiers manquants"):
        store.import_project(missing)


def test_import_rejects_extra_file(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Extra")
    archive = tmp_path / "source.simproj"
    store.export_project(project.id, archive)
    extra = tmp_path / "extra.simproj"
    _rewrite(archive, extra, lambda _name, data: data)
    with zipfile.ZipFile(extra, "a") as writer:
        writer.writestr("results/extra.txt", b"intrus")
    with pytest.raises(PortableError, match="fichiers non déclarés"):
        store.import_project(extra)


def test_import_rejects_path_traversal(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Traversée")
    archive = tmp_path / "source.simproj"
    store.export_project(project.id, archive)
    malicious = tmp_path / "traversal.simproj"
    _rewrite(archive, malicious, lambda _name, data: data)
    with zipfile.ZipFile(malicious, "a") as writer:
        writer.writestr("../evil.txt", b"intrus")
    with pytest.raises(PortableError, match="chemin d'archive interdit"):
        store.import_project(malicious)


def test_import_rejects_newer_schema(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Futur")
    archive = tmp_path / "source.simproj"
    store.export_project(project.id, archive)
    newer = tmp_path / "newer.simproj"

    def transform(name: str, data: bytes) -> bytes:
        if name != "manifest.json":
            return data
        manifest = json.loads(data)
        manifest["schemaVersion"] = 99
        return json.dumps(manifest).encode("utf-8")

    _rewrite(archive, newer, transform)
    with pytest.raises(SchemaTooNewError):
        store.import_project(newer)


def test_export_requires_simproj_suffix(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Extension")
    with pytest.raises(PortableError, match="extension .simproj"):
        store.export_project(project.id, tmp_path / "project.zip")


def test_export_rejects_missing_detailed_result(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Résultat manquant")
    scenario = store.scenarios.add(project.id, "Base", "retail_depot", {})
    store.runs.add(
        project.id,
        "0.1.0",
        10,
        {},
        scenario_id=scenario.id,
        result_path="missing.json.gz",
    )
    with pytest.raises(PortableError, match="résultat détaillé manquant"):
        store.export_project(project.id, tmp_path / "missing.simproj")


def test_archive_contains_no_secret_columns(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Sans secrets")
    store.provider_profiles.upsert(
        project.id,
        "Local",
        "ollama",
        keychain_ref=f"see-the-future:{project.id}:ollama",
        model="qwen",
    )
    archive = tmp_path / "safe.simproj"
    store.export_project(project.id, archive)
    with zipfile.ZipFile(archive) as reader:
        payload = b"".join(reader.read(name) for name in reader.namelist()).lower()
    for marker in (
        b"api_key",
        b"password",
        b"authorization",
        b"access_token",
        b"refresh_token",
    ):
        assert marker not in payload


def test_import_rejects_unknown_format(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Format")
    archive = tmp_path / "source.simproj"
    store.export_project(project.id, archive)
    unknown = tmp_path / "unknown.simproj"

    def transform(name: str, data: bytes) -> bytes:
        if name != "manifest.json":
            return data
        manifest = json.loads(data)
        manifest["format"] = "other.format"
        return json.dumps(manifest).encode("utf-8")

    _rewrite(archive, unknown, transform)
    with pytest.raises(PortableError, match="format d'archive inconnu"):
        store.import_project(unknown)


def test_detailed_result_survives_round_trip(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project("Détail portable")
    scenario = store.scenarios.add(project.id, "Base", "retail_depot", {})
    run = store.runs.add(project.id, "0.1.0", 10, {}, scenario_id=scenario.id)
    payload = {"series": [1.5, 2.5, 3.5]}
    store.save_run_detail(project.id, run.id, payload)
    archive = tmp_path / "detail.simproj"
    store.export_project(project.id, archive)
    imported = store.import_project(archive)
    imported_run = store.runs.list(imported.id)[0]
    assert imported_run.result_path
    assert store.load_run_detail(imported.id, imported_run.id) == payload
