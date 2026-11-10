from __future__ import annotations

import pytest

from see_storage import (
    IntegrityError,
    ProjectNotFound,
    ProjectStore,
    StorageError,
    StorageValidationError,
)


def _populate(store: ProjectStore, project_id: str) -> None:
    store.messages.add(project_id, "user", "Bonjour")
    store.briefs.add_version(project_id, {"problem": "Tester"})
    scenario = store.scenarios.add(project_id, "Base", "retail_depot", {"model": "retail_depot"})
    run = store.runs.add(
        project_id, "0.1.0", 100, {"mean": 1.0}, scenario_id=scenario.id
    )
    store.runs.add(
        project_id,
        "0.1.0",
        100,
        {"mean": 2.0},
        scenario_id=scenario.id,
        result_path=f"{run.id}.json.gz",
    )
    directory = store.results_dir / project_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{run.id}.json.gz").write_bytes(b"result")


def test_project_lifecycle(store: ProjectStore) -> None:
    project = store.create_project("Cycle", description="desc")
    store.messages.add(project.id, "user", "salut")
    assert store.open_project(project.id).status == "active"
    assert store.rename_project(project.id, "Cycle renommé").name == "Cycle renommé"
    assert store.archive_project(project.id).status == "archived"
    assert store.list_projects() == []
    assert store.list_projects(include_archived=True)[0].id == project.id
    assert store.restore_project(project.id).status == "active"
    assert store.trash_project(project.id).status == "trashed"
    with pytest.raises(StorageValidationError):
        store.open_project(project.id)
    assert store.list_projects(include_trashed=True)[0].id == project.id
    assert store.restore_project(project.id).status == "active"
    assert store.delete_project(project.id) is True
    with pytest.raises(ProjectNotFound):
        store.get_project(project.id)


def test_duplicate_copies_children_and_results(store: ProjectStore) -> None:
    project = store.create_project("Original")
    _populate(store, project.id)
    duplicate = store.duplicate_project(project.id)
    assert duplicate.id != project.id
    assert duplicate.name == "Original (copie)"
    assert store.messages.count(duplicate.id) == 1
    assert store.briefs.latest(duplicate.id).content == {"problem": "Tester"}
    assert len(store.scenarios.list(duplicate.id)) == 1
    runs = store.runs.list(duplicate.id)
    assert len(runs) == 2
    detailed = [run for run in runs if run.result_path]
    assert len(detailed) == 1
    assert detailed[0].result_path == f"{detailed[0].id}.json.gz"
    assert (store.results_dir / duplicate.id / detailed[0].result_path).read_bytes() == b"result"


def test_delete_removes_project_results(store: ProjectStore) -> None:
    project = store.create_project("À supprimer")
    directory = store.results_dir / project.id
    directory.mkdir()
    (directory / "orphan.json").write_text("{}", encoding="utf-8")
    store.delete_project(project.id)
    assert not directory.exists()


def test_project_size_counts_database_and_results(store: ProjectStore) -> None:
    project = store.create_project("Taille")
    _populate(store, project.id)
    size = store.project_size(project.id)
    assert size["databaseBytes"] > 0
    assert size["resultsBytes"] > 0
    assert size["totalBytes"] == size["databaseBytes"] + size["resultsBytes"]


def test_duplicate_fails_when_detailed_result_is_missing(store: ProjectStore) -> None:
    project = store.create_project("Cassé")
    scenario = store.scenarios.add(project.id, "Base", "retail_depot", {})
    store.runs.add(
        project.id,
        "0.1.0",
        10,
        {},
        scenario_id=scenario.id,
        result_path="missing.json.gz",
    )
    with pytest.raises(IntegrityError, match="résultat détaillé manquant"):
        store.duplicate_project(project.id)
    assert len(store.list_projects()) == 1


def test_same_workspace_cannot_be_opened_twice(tmp_path) -> None:
    data_dir = tmp_path / "data"
    first = ProjectStore(data_dir)
    try:
        with pytest.raises(StorageError, match="déjà ouvert"):
            ProjectStore(data_dir)
    finally:
        first.close()
    reopened = ProjectStore(data_dir)
    reopened.close()


def test_unclean_shutdown_runs_integrity_check(tmp_path) -> None:
    data_dir = tmp_path / "data"
    store = ProjectStore(data_dir)
    project = store.create_project("Après crash")
    store.db.conn.close()
    store._lock.release()

    reopened = ProjectStore(data_dir)
    try:
        assert reopened.recovery_message == "ok"
        assert reopened.get_project(project.id).name == "Après crash"
    finally:
        reopened.close()


def test_prune_runs_removes_detailed_results(store: ProjectStore) -> None:
    project = store.create_project("Rotation")
    directory = store.results_dir / project.id
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        result = f"run-{index}.json.gz"
        store.runs.add(
            project.id,
            "0.1.0",
            10,
            {"index": index},
            result_path=result,
            created_at=f"2026-01-01T00:00:{index:02d}+00:00",
        )
        (directory / result).write_bytes(b"detail")
    assert store.prune_runs(project.id, keep=1) == 2
    assert sorted(path.name for path in directory.iterdir()) == ["run-2.json.gz"]


def test_save_and_load_detailed_result(store: ProjectStore) -> None:
    project = store.create_project("Détail")
    scenario = store.scenarios.add(project.id, "Base", "retail_depot", {})
    run = store.runs.add(project.id, "0.1.0", 10, {}, scenario_id=scenario.id)
    payload = {"series": [index % 7 for index in range(1000)]}
    relative = store.save_run_detail(project.id, run.id, payload)
    assert relative == f"{run.id}.json.gz"
    assert store.load_run_detail(project.id, run.id) == payload
    assert store.runs.get(run.id).result_path == relative
    assert store.project_size(project.id)["resultsBytes"] > 0
