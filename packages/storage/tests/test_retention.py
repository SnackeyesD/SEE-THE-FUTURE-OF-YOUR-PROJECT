from __future__ import annotations

from pathlib import Path

import pytest

from see_storage import ProjectStore


def _run(
    store: ProjectStore,
    project_id: str,
    index: int,
    *,
    result_path: str | None = None,
    **kwargs: object,
):
    return store.runs.add(
        project_id,
        "0.3.0",
        index + 10,
        {"index": index},
        result_path=result_path or f"run-{index}.json.gz",
        created_at=f"2026-01-01T00:00:{index:02d}+00:00",
        **kwargs,
    )


def test_prune_keeps_pinned_and_versioned_runs(store: ProjectStore) -> None:
    project = store.create_project("Rétention")
    version = store.versions.create(
        project.id, None, "Référence", {"model": "retail_depot"}, seed=1
    )
    _run(store, project.id, 0, pinned=True)
    _run(store, project.id, 1, scenario_version_id=version.id)
    _run(store, project.id, 2)
    _run(store, project.id, 3)
    _run(store, project.id, 4)

    removed = store.runs.prune(project.id, keep_last=1)

    assert sorted(path for _identifier, path in removed) == [
        "run-2.json.gz",
        "run-3.json.gz",
    ]
    remaining = {run.summary["index"] for run in store.runs.list(project.id)}
    assert remaining == {0, 1, 4}


def test_prune_zero_keeps_only_protected_runs(store: ProjectStore) -> None:
    project = store.create_project("Rétention zéro")
    version = store.versions.create(
        project.id, None, "Référence", {"model": "retail_depot"}, seed=1
    )
    _run(store, project.id, 0, pinned=True)
    _run(store, project.id, 1, scenario_version_id=version.id)
    _run(store, project.id, 2)

    removed = store.runs.prune(project.id, keep_last=0)

    assert [path for _identifier, path in removed] == ["run-2.json.gz"]
    assert {run.summary["index"] for run in store.runs.list(project.id)} == {0, 1}


def test_project_store_prune_removes_result_files(
    store: ProjectStore, tmp_path: Path
) -> None:
    project = store.create_project("Fichiers")
    directory = store.results_dir / project.id
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        result = f"run-{index}.json.gz"
        _run(store, project.id, index, result_path=result)
        (directory / result).write_bytes(b"detail")

    assert store.prune_runs(project.id, keep_last=1) == 2
    assert sorted(path.name for path in directory.iterdir()) == ["run-2.json.gz"]


def test_prune_all_covers_every_project(store: ProjectStore) -> None:
    first = store.create_project("Premier")
    second = store.create_project("Deuxième")
    for index in range(2):
        _run(store, first.id, index)
        _run(store, second.id, index + 10)

    assert store.prune_all(keep_last=1) == 2
    assert store.runs.count(first.id) == 1
    assert store.runs.count(second.id) == 1


def test_save_run_externalizes_large_results(store: ProjectStore) -> None:
    project = store.create_project("Gros résultat")
    payload = {"series": list(range(1000))}

    run = store.save_run(
        project.id,
        "0.3.0",
        10,
        {"kind": "large"},
        result=payload,
        max_inline_bytes=64,
    )

    assert run.result is None
    assert run.result_path == f"{run.id}.json.gz"
    assert store.load_run_detail(project.id, run.id) == payload


def test_save_run_keeps_small_results_inline(store: ProjectStore) -> None:
    project = store.create_project("Petit résultat")
    run = store.save_run(
        project.id,
        "0.3.0",
        10,
        {"kind": "small"},
        result={"ok": True},
        max_inline_bytes=1024,
    )

    assert run.result == {"ok": True}
    assert run.result_path is None


def test_save_run_is_idempotent(store: ProjectStore) -> None:
    project = store.create_project("Idempotence résultat")
    first = store.save_run(
        project.id, "0.3.0", 10, {"value": 1}, result={"value": 1}, run_id="fixe"
    )
    second = store.save_run(
        project.id, "0.3.0", 10, {"value": 2}, result={"value": 2}, run_id="fixe"
    )

    assert second.id == first.id
    assert second.summary == {"value": 1}
    assert store.runs.count(project.id) == 1


def test_save_run_cleans_up_when_detail_write_fails(
    store: ProjectStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = store.create_project("Échec détail")

    def fail(*_args: object, **_kwargs: object) -> str:
        raise OSError("disque plein")

    monkeypatch.setattr(store, "save_run_detail", fail)
    with pytest.raises(OSError, match="disque plein"):
        store.save_run(
            project.id,
            "0.3.0",
            10,
            {},
            result={"series": list(range(100))},
            max_inline_bytes=8,
        )
    assert store.runs.count(project.id) == 0
