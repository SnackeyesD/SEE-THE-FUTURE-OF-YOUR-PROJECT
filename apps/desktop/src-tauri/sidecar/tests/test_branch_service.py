"""Tests de la phase 13 : branches, comparaison et versions nommées."""

from __future__ import annotations

from typing import Any

import pytest
from see_storage import ProjectStore, StorageValidationError

from sidecar import project_service
from sidecar.project_service import MAX_ACTIVE_BRANCHES

SCENARIO: dict[str, Any] = {
    "name": "Branche",
    "horizonMonths": 3,
    "assumptions": {
        "initial_cash": {"value": 10_000},
        "unit_price": {"value": 20},
        "unit_cost": {"value": 8},
    },
}


@pytest.fixture
def store(tmp_path):
    project_store = ProjectStore(tmp_path / "data")
    try:
        yield project_store
    finally:
        project_store.close()


@pytest.fixture
def project(store: ProjectStore):
    return store.create_project("Branches")


def _scenario(store: ProjectStore, project_id: str, name: str = "Base"):
    return store.scenarios.add(project_id, name, "retail_depot", SCENARIO)


def _run(
    store: ProjectStore,
    project_id: str,
    scenario_id: str,
    *,
    seed: int = 4,
    pinned: bool = False,
    run_id: str | None = None,
):
    return store.runs.add(
        project_id,
        "0.4.0",
        30,
        {"p50": 1_000},
        scenario_id=scenario_id,
        seed=seed,
        pinned=pinned,
        run_id=run_id,
        result={"runId": run_id, "seed": seed, "metrics": {"p50": 1_000}},
    )


def test_list_branches_exposes_last_final_run(store: ProjectStore, project) -> None:
    source = _scenario(store, project.id)
    branch = store.scenarios.duplicate(source.id, "Variante")
    run = _run(store, project.id, branch.id, seed=9)

    result = project_service.list_branches(store, {"projectId": project.id})
    by_id = {item["scenarioId"]: item for item in result["branches"]}

    assert by_id[branch.id]["lastFinalRunId"] == run.id
    assert by_id[branch.id]["seed"] == 9
    assert by_id[branch.id]["branchLabel"] == "Variante"
    assert by_id[branch.id]["parentId"] == source.id
    assert by_id[source.id]["lastFinalRunId"] is None
    assert by_id[source.id]["seed"] is None


def test_archive_hides_branch_and_requires_confirmation_with_pinned_run(
    store: ProjectStore, project
) -> None:
    source = _scenario(store, project.id)
    branch = store.scenarios.duplicate(source.id, "Variante")
    _run(store, project.id, branch.id, pinned=True)

    with pytest.raises(StorageValidationError, match="confirmez"):
        project_service.archive_scenario(
            store, {"projectId": project.id, "scenarioId": branch.id}
        )

    archived = project_service.archive_scenario(
        store,
        {"projectId": project.id, "scenarioId": branch.id, "confirmPinned": True},
    )
    assert archived["pinnedRuns"] == 1
    assert archived["scenario"]["archivedAt"] is not None

    visible = project_service.list_branches(store, {"projectId": project.id})
    assert {item["scenarioId"] for item in visible["branches"]} == {source.id}

    everything = project_service.list_branches(
        store, {"projectId": project.id, "includeArchived": True}
    )
    assert {item["scenarioId"] for item in everything["branches"]} == {
        source.id,
        branch.id,
    }


def test_unarchive_restores_visibility(store: ProjectStore, project) -> None:
    source = _scenario(store, project.id)
    branch = store.scenarios.duplicate(source.id, "Variante")
    project_service.archive_scenario(
        store, {"projectId": project.id, "scenarioId": branch.id, "confirmPinned": True}
    )

    restored = project_service.unarchive_scenario(
        store, {"projectId": project.id, "scenarioId": branch.id}
    )
    assert restored["scenario"]["archivedAt"] is None
    visible = project_service.list_branches(store, {"projectId": project.id})
    assert branch.id in {item["scenarioId"] for item in visible["branches"]}


def test_rename_updates_displayed_labels(store: ProjectStore, project) -> None:
    branch = _scenario(store, project.id)
    renamed = project_service.rename_scenario(
        store,
        {
            "projectId": project.id,
            "scenarioId": branch.id,
            "name": "Nouvelle base",
            "branchLabel": "Variante B",
        },
    )
    assert renamed["scenario"]["name"] == "Nouvelle base"
    assert renamed["scenario"]["branchLabel"] == "Variante B"


def test_branch_limit_is_enforced(store: ProjectStore, project) -> None:
    source = _scenario(store, project.id)
    for index in range(MAX_ACTIVE_BRANCHES - 1):
        store.scenarios.duplicate(source.id, f"Branche {index}")

    with pytest.raises(StorageValidationError, match="limite"):
        project_service.branch_scenario(
            store,
            {"projectId": project.id, "scenarioId": source.id, "label": "Trop"},
        )


def test_run_filter_and_pin(store: ProjectStore, project) -> None:
    scenario = _scenario(store, project.id)
    first = _run(store, project.id, scenario.id, seed=4)
    second = _run(store, project.id, scenario.id, seed=5)

    filtered = project_service.list_runs(
        store, {"projectId": project.id, "seed": 5}
    )
    assert [item["id"] for item in filtered["runs"]] == [second.id]

    pinned = project_service.pin_run(
        store, {"projectId": project.id, "runId": first.id, "pinned": True}
    )
    assert pinned["run"]["pinned"] is True

    pinned_only = project_service.list_runs(
        store, {"projectId": project.id, "scenarioId": scenario.id}
    )
    assert {item["id"] for item in pinned_only["runs"]} == {first.id, second.id}


def test_compare_runs_warns_on_seed_and_engine_mismatch(
    store: ProjectStore, project
) -> None:
    scenario = _scenario(store, project.id)
    first = _run(store, project.id, scenario.id, seed=4)
    same = _run(store, project.id, scenario.id, seed=4)
    other = store.runs.add(
        project.id,
        "0.5.0",
        30,
        {},
        scenario_id=scenario.id,
        seed=5,
        result={"metrics": {"p50": 2_000}},
    )

    aligned = project_service.compare_runs(
        store, {"projectId": project.id, "runIds": [first.id, same.id]}
    )
    assert aligned["sameSeed"] is True
    assert aligned["sameEngineVersion"] is True
    assert len(aligned["runs"]) == 2

    mismatch = project_service.compare_runs(
        store, {"projectId": project.id, "runIds": [first.id, other.id]}
    )
    assert mismatch["sameSeed"] is False
    assert mismatch["sameEngineVersion"] is False


def test_compare_rejects_run_from_another_project(
    store: ProjectStore, project
) -> None:
    scenario = _scenario(store, project.id)
    run = _run(store, project.id, scenario.id)
    other = store.create_project("Autre")
    other_run = _run(store, other.id, scenario.id)

    with pytest.raises(StorageValidationError, match="run introuvable"):
        project_service.compare_runs(
            store, {"projectId": project.id, "runIds": [run.id, other_run.id]}
        )


def test_versions_are_immutable_and_restore_creates_a_branch(
    store: ProjectStore, project
) -> None:
    scenario = _scenario(store, project.id)
    _run(store, project.id, scenario.id, seed=7)

    created = project_service.create_version(
        store, {"projectId": project.id, "label": "Référence", "seed": 7}
    )
    version = created["version"]
    assert version["label"] == "Référence"
    assert version["seed"] == 7
    assert version["engineVersion"] == "0.4.0"

    store.scenarios.update(
        scenario.id, scenario={**SCENARIO, "name": "Modifié"}
    )
    listed = project_service.list_versions(store, {"projectId": project.id})
    assert listed["versions"][0]["id"] == version["id"]

    restored = project_service.restore_version(
        store, {"projectId": project.id, "versionId": version["id"]}
    )
    branch = restored["scenario"]
    assert branch["id"] != scenario.id
    assert branch["parentId"] == scenario.id
    assert branch["archivedAt"] is None
    assert branch["scenario"]["name"] == "Branche"

    deleted = project_service.delete_version(
        store, {"projectId": project.id, "versionId": version["id"]}
    )
    assert deleted["deleted"] is True
    assert project_service.list_versions(store, {"projectId": project.id})["versions"] == []


ENGINE_SCENARIO: dict[str, Any] = {
    "name": "Branche simulable",
    "horizonMonths": 2,
    "assumptions": {
        "initial_cash": {"value": 0},
        "unit_price": {"value": 10},
        "unit_cost": {"value": 5},
        "fixed_costs_monthly": {"value": 0},
        "demand_mean_monthly": {"value": 10},
        "demand_cv": {"value": 0},
        "loss_rate": {"value": 0},
        "target_stock_months": {"value": 0},
        "reorder_lead_time_months": {"value": 1},
        "initial_stock": {"value": 100},
        "tax_rate": {"value": 0},
    },
}


def test_save_scenario_with_scenario_id_updates_branch(store: ProjectStore, project) -> None:
    branch = store.scenarios.add(project.id, "Base", "retail_depot", ENGINE_SCENARIO)
    updated_payload = {
        **ENGINE_SCENARIO,
        "assumptions": {
            **ENGINE_SCENARIO["assumptions"],
            "unit_price": {"value": 12},
        },
    }

    saved = project_service.save_scenario(
        store,
        {
            "projectId": project.id,
            "scenarioId": branch.id,
            "name": "Base ajustée",
            "scenario": updated_payload,
        },
    )

    assert saved["scenario"]["id"] == branch.id
    assert saved["scenario"]["name"] == "Base ajustée"
    assert saved["scenario"]["scenario"]["assumptions"]["unit_price"]["value"] == 12
    listed = store.scenarios.list(project.id)
    assert [record.id for record in listed] == [branch.id]


def test_simulate_binds_run_to_opened_branch(store: ProjectStore, project) -> None:
    branch = store.scenarios.add(project.id, "Base", "retail_depot", ENGINE_SCENARIO)
    other = store.scenarios.add(project.id, "Autre", "retail_depot", ENGINE_SCENARIO)

    result = project_service.simulate(
        store,
        {
            "projectId": project.id,
            "scenarioId": branch.id,
            "scenario": {
                **ENGINE_SCENARIO,
                "assumptions": {
                    **ENGINE_SCENARIO["assumptions"],
                    "unit_price": {"value": 11},
                },
            },
            "config": {"runs": 20, "seed": 3},
        },
    )

    assert result["run"]["scenarioId"] == branch.id
    refreshed = store.scenarios.get(branch.id)
    assert refreshed is not None
    assert refreshed.scenario["assumptions"]["unit_price"]["value"] == 11
    assert store.scenarios.get(other.id).scenario["assumptions"]["unit_price"]["value"] == 10


def test_simulate_without_scenario_uses_opened_branch(store: ProjectStore, project) -> None:
    branch = store.scenarios.add(project.id, "Base", "retail_depot", ENGINE_SCENARIO)

    result = project_service.simulate(
        store,
        {
            "projectId": project.id,
            "scenarioId": branch.id,
            "config": {"runs": 10, "seed": 9},
        },
    )

    assert result["run"]["scenarioId"] == branch.id
    assert result["run"]["seed"] == 9
