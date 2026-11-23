from __future__ import annotations

import pytest

from see_storage import ProjectStore, StorageValidationError


def test_duplicate_creates_branch(store: ProjectStore) -> None:
    project = store.create_project("Branches")
    source = store.scenarios.add(
        project.id,
        "Base",
        "retail_depot",
        {"model": "retail_depot", "runs": 10},
    )

    branch = store.scenarios.duplicate(source.id, "Variante")

    assert branch.id != source.id
    assert branch.parent_id == source.id
    assert branch.branch_label == "Variante"
    assert branch.name == "Base"
    assert branch.version == 1
    assert branch.scenario == source.scenario


def test_update_increments_version_only_for_structural_changes(
    store: ProjectStore,
) -> None:
    project = store.create_project("Versions d'édition")
    scenario = store.scenarios.add(project.id, "Base", "retail_depot", {"runs": 10})

    renamed = store.scenarios.update(scenario.id, name="Renommé")
    assert renamed.version == 1

    updated = store.scenarios.update(scenario.id, scenario={"runs": 20})
    assert updated.version == 2

    unchanged = store.scenarios.update(scenario.id, scenario={"runs": 20})
    assert unchanged.version == 2

    remodelled = store.scenarios.update(scenario.id, model="retail_depot")
    assert remodelled.version == 2


def test_scenario_version_snapshot_is_immutable(store: ProjectStore) -> None:
    project = store.create_project("Snapshots")
    scenario = store.scenarios.add(project.id, "Base", "retail_depot", {"runs": 10})

    version = store.versions.create(
        project.id,
        scenario.id,
        "Référence",
        scenario.scenario,
        seed=42,
        engine_version="0.3.0",
    )
    store.scenarios.update(scenario.id, scenario={"runs": 99})

    stored = store.versions.get(version.id)
    assert stored is not None
    assert stored.scenario == {"runs": 10}
    assert stored.seed == 42
    assert stored.engine_version == "0.3.0"
    assert [item.id for item in store.versions.list(project.id)] == [version.id]


def test_restore_version_creates_branch_without_destroying_source(
    store: ProjectStore,
) -> None:
    project = store.create_project("Restauration")
    source = store.scenarios.add(project.id, "Base", "retail_depot", {"runs": 10})
    version = store.versions.create(
        project.id, source.id, "Référence", source.scenario, seed=7
    )

    restored = store.versions.restore(version.id, label="Restauration")

    assert restored.id != source.id
    assert restored.parent_id == source.id
    assert restored.branch_label == "Restauration"
    assert restored.name == "Référence"
    assert restored.scenario == {"runs": 10}
    assert store.scenarios.get(source.id).scenario == {"runs": 10}
    assert store.versions.get(version.id) is not None


def test_version_survives_scenario_deletion(store: ProjectStore) -> None:
    project = store.create_project("Suppression")
    source = store.scenarios.add(
        project.id,
        "Base",
        "retail_depot",
        {"model": "retail_depot", "runs": 10},
    )
    version = store.versions.create(
        project.id, source.id, "Référence", source.scenario, seed=7
    )

    assert store.scenarios.delete(source.id) is True

    survivor = store.versions.get(version.id)
    assert survivor is not None
    assert survivor.scenario_id is None
    assert store.check_integrity() == (True, "ok")

    restored = store.versions.restore(version.id)
    assert restored.parent_id is None
    assert restored.name == "Référence"
    assert restored.model == "retail_depot"
    assert restored.scenario == survivor.scenario


def test_run_defaults_and_draft_rejected(store: ProjectStore) -> None:
    project = store.create_project("Runs V3")
    run = store.runs.add(project.id, "0.3.0", 10, {})

    assert run.quality == "final"
    assert run.pinned is False
    assert run.status == "complete"
    assert run.scenario_version_id is None

    with pytest.raises(StorageValidationError, match="draft"):
        store.runs.add(project.id, "0.3.0", 10, {}, quality="draft")
    with pytest.raises(StorageValidationError, match="statut"):
        store.runs.add(project.id, "0.3.0", 10, {}, status="inconnu")


def test_run_can_be_linked_to_version_and_pinned(store: ProjectStore) -> None:
    project = store.create_project("Runs liés")
    scenario = store.scenarios.add(project.id, "Base", "retail_depot", {"runs": 10})
    version = store.versions.create(
        project.id, scenario.id, "Référence", scenario.scenario, seed=7
    )

    run = store.runs.add(
        project.id,
        "0.3.0",
        10,
        {"mean": 1.0},
        scenario_id=scenario.id,
        seed=7,
        scenario_version_id=version.id,
        pinned=True,
    )
    assert run.scenario_version_id == version.id
    assert run.pinned is True

    unpinned = store.runs.set_pinned(run.id, False)
    assert unpinned.pinned is False

    other = store.create_project("Autre")
    with pytest.raises(StorageValidationError, match="autre projet"):
        store.runs.add(
            other.id,
            "0.3.0",
            10,
            {},
            scenario_version_id=version.id,
        )


def test_run_add_is_idempotent_by_run_id(store: ProjectStore) -> None:
    project = store.create_project("Idempotence")
    first = store.runs.add(
        project.id, "0.3.0", 10, {"value": 1}, run_id="run-fixe"
    )
    second = store.runs.add(
        project.id, "0.3.0", 10, {"value": 2}, run_id="run-fixe"
    )

    assert second.id == first.id
    assert second.summary == {"value": 1}
    assert store.runs.count(project.id) == 1

    other = store.create_project("Autre")
    with pytest.raises(StorageValidationError, match="autre projet"):
        store.runs.add(other.id, "0.3.0", 10, {}, run_id="run-fixe")


def test_archive_hides_branch_but_keeps_it(store: ProjectStore) -> None:
    project = store.create_project("Archivage")
    source = store.scenarios.add(project.id, "Base", "retail_depot", {"a": 1})
    branch = store.scenarios.duplicate(source.id, "Variante")

    archived = store.scenarios.archive(branch.id)
    assert archived.archived_at is not None

    visible = store.scenarios.list(project.id)
    assert {item.id for item in visible} == {source.id}
    everything = store.scenarios.list(project.id, include_archived=True)
    assert {item.id for item in everything} == {source.id, branch.id}

    restored = store.scenarios.archive(branch.id, archived=False)
    assert restored.archived_at is None
    assert {item.id for item in store.scenarios.list(project.id)} == {
        source.id,
        branch.id,
    }


def test_rename_branch_keeps_identity(store: ProjectStore) -> None:
    project = store.create_project("Renommage")
    branch = store.scenarios.add(project.id, "Base", "retail_depot", {"a": 1})

    renamed = store.scenarios.update(
        branch.id, name="Nouvelle base", branch_label="Variante B"
    )

    assert renamed.id == branch.id
    assert renamed.name == "Nouvelle base"
    assert renamed.branch_label == "Variante B"
    assert renamed.version == branch.version
