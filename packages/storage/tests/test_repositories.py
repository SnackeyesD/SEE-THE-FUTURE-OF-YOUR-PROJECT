from __future__ import annotations

import pytest

from see_storage import ProjectNotFound, ProjectStore, StorageValidationError


def test_agent_session_and_trace(store: ProjectStore) -> None:
    project = store.create_project("Agent")
    session = store.agent_sessions.upsert(
        project.id,
        "interviewing",
        "interviewer",
        [{"role": "user", "content": "Bonjour"}],
    )
    assert session.state == "interviewing"
    updated = store.agent_sessions.upsert(
        project.id, "brief_draft", "interviewer", []
    )
    assert updated.id == session.id
    assert updated.state == "brief_draft"

    entry = store.agent_trace.add(
        project.id,
        {"kind": "tool", "data": {"tool": "update_brief"}},
        session_id=session.id,
        turn=1,
    )
    assert store.agent_trace.count(project.id) == 1
    assert store.agent_trace.list(project.id)[0].id == entry.id
    assert store.agent_trace.clear(project.id) == 1

    event = store.permission_events.add(
        project.id, "web_search", "project", "ask", reason="défaut"
    )
    assert store.permission_events.list(project.id)[0].id == event.id
    with pytest.raises(StorageValidationError):
        store.agent_sessions.upsert(project.id, "invalid", "interviewer", [])
    with pytest.raises(StorageValidationError):
        store.permission_events.add(project.id, "tool", "project", "maybe")


def test_project_repository_crud(store: ProjectStore) -> None:
    project = store.projects.create("  Alpha  ", currency="xof", sector="Retail")
    assert project.name == "Alpha"
    assert project.currency == "XOF"
    assert project.status == "active"
    assert [item.id for item in store.projects.list()] == [project.id]

    updated = store.projects.update(project.id, name="Beta", metadata={"version": 2})
    assert updated.name == "Beta"
    assert updated.metadata == {"version": 2}

    store.projects.update(project.id, status="archived")
    assert store.projects.list() == []
    assert [item.id for item in store.projects.list(include_archived=True)] == [project.id]

    assert store.projects.delete(project.id) is True
    with pytest.raises(ProjectNotFound):
        store.projects.require(project.id)


def test_message_repository_pagination(store: ProjectStore) -> None:
    project = store.create_project("Messages")
    for index in range(5):
        store.messages.add(
            project.id,
            "user",
            f"message {index}",
            token_count=index,
            created_at=f"2026-01-01T00:00:{index:02d}+00:00",
        )
    assert store.messages.count(project.id) == 5
    first = store.messages.list(project.id, limit=2)
    second = store.messages.list(project.id, limit=2, offset=2)
    assert [item.content for item in first] == ["message 0", "message 1"]
    assert [item.content for item in second] == ["message 2", "message 3"]
    with pytest.raises(StorageValidationError):
        store.messages.add(project.id, "invalid", "nope")


def test_brief_versions(store: ProjectStore) -> None:
    project = store.create_project("Brief")
    first = store.briefs.add_version(project.id, {"problem": "A"})
    second = store.briefs.add_version(project.id, {"problem": "B"}, status="validated")
    assert (first.version, second.version) == (1, 2)
    assert store.briefs.latest(project.id).version == 2
    assert store.briefs.set_status(first.id, "archived").status == "archived"
    assert [item.version for item in store.briefs.list(project.id)] == [2, 1]


def test_scenario_repository_crud(store: ProjectStore) -> None:
    project = store.create_project("Scénarios")
    scenario = store.scenarios.add(project.id, "Base", "retail_depot", {"runs": 10})
    assert scenario.scenario == {"runs": 10}
    updated = store.scenarios.update(scenario.id, name="Variante", scenario={"runs": 20})
    assert updated.name == "Variante"
    assert updated.scenario == {"runs": 20}
    assert store.scenarios.delete(scenario.id) is True
    assert store.scenarios.list(project.id) == []


def test_runs_and_prune(store: ProjectStore) -> None:
    project = store.create_project("Runs")
    paths = []
    for index in range(3):
        run = store.runs.add(
            project.id,
            "0.1.0",
            100 + index,
            {"index": index},
            result_path=f"result-{index}.json.gz",
            created_at=f"2026-01-01T00:00:{index:02d}+00:00",
        )
        paths.append(run.result_path)
    removed = store.runs.prune(project.id, keep=1)
    assert sorted(removed) == sorted(paths[:2])
    assert store.runs.count(project.id) == 1
    assert store.runs.list(project.id)[0].summary == {"index": 2}


def test_runs_reject_path_traversal(store: ProjectStore) -> None:
    project = store.create_project("Runs sûrs")
    with pytest.raises(StorageValidationError, match="interdit"):
        store.runs.add(
            project.id, "0.1.0", 10, {}, result_path="../evasion.json.gz"
        )


def test_usage_summary_and_permissions(store: ProjectStore) -> None:
    project = store.create_project("Usage")
    profile = store.provider_profiles.upsert(
        project.id, "Local", "ollama", base_url="http://localhost:11434", model="qwen"
    )
    store.usage.add(
        project.id,
        "chat",
        provider_profile_id=profile.id,
        input_tokens=10,
        output_tokens=20,
        cost_micros=30,
    )
    store.usage.add(project.id, "summary", input_tokens=1, output_tokens=2, cost_micros=3)
    assert store.usage.summary(project.id) == {
        "entries": 2,
        "inputTokens": 11,
        "outputTokens": 22,
        "costMicros": 33,
    }
    permission = store.permissions.set(project.id, "sandbox", "project", "ask")
    assert permission.decision == "ask"
    assert store.permissions.set(project.id, "sandbox", "project", "deny").decision == "deny"
    assert len(store.permissions.list(project.id)) == 1
    with pytest.raises(StorageValidationError):
        store.permissions.set(project.id, "sandbox", "project", "invalid")


def test_roles_and_project_budget(store: ProjectStore) -> None:
    project = store.create_project("Rôles")
    other = store.create_project("Autre")
    profile = store.provider_profiles.upsert(project.id, "Qualité", "openai", model="gpt-4o")
    foreign = store.provider_profiles.upsert(other.id, "Autre", "ollama", model="qwen")
    assignment = store.roles.set(project.id, "modeler", profile.id, "gpt-4o-mini")
    assert assignment.model == "gpt-4o-mini"
    assert store.roles.set(project.id, "modeler", profile.id, "gpt-4o").model == "gpt-4o"
    assert len(store.roles.list(project.id)) == 1
    with pytest.raises(StorageValidationError):
        store.roles.set(project.id, "modeler", foreign.id, "qwen")
    with pytest.raises(StorageValidationError):
        store.roles.set(project.id, "unknown", profile.id, "gpt-4o")
    budget = store.budgets.set(project.id, 2_000_000)
    assert budget.limit_micros == 2_000_000
    assert store.budgets.get(project.id).limit_micros == 2_000_000  # type: ignore[union-attr]
    with pytest.raises(StorageValidationError):
        store.budgets.set(project.id, -1)
    assert store.roles.delete(project.id, "modeler") is True
    assert store.budgets.delete(project.id) is True


def test_benchmark_packs_are_global(store: ProjectStore) -> None:
    store.benchmark_packs.add("retail", "1", "/packs/retail.zip", "a" * 64, source="builtin")
    store.benchmark_packs.add("retail", "1", "/packs/retail-v1.zip", "b" * 64)
    packs = store.benchmark_packs.list()
    assert len(packs) == 1
    assert packs[0].checksum == "b" * 64


def test_sandbox_audit_records_and_export(store: ProjectStore) -> None:
    project = store.create_project("Sandbox")
    record = store.sandbox_audit.add(
        project.id,
        "def main(data):\n    return {'metrics': []}\n",
        "a" * 64,
        "approved",
        "succeeded",
        analysis={"ok": True, "issues": []},
        purpose="test",
        result={"metrics": []},
        duration_ms=12.5,
    )
    assert record.code_hash == "a" * 64
    assert store.sandbox_audit.count(project.id) == 1
    assert store.sandbox_audit.list(project.id)[0].id == record.id
    path, count = store.export_sandbox_audit(project.id)
    assert path.is_file()
    assert count == 1
    with pytest.raises(StorageValidationError):
        store.sandbox_audit.add(
            project.id, "code", "not-a-hash", "approved", "succeeded"
        )
    with pytest.raises(StorageValidationError):
        store.sandbox_audit.add(
            project.id, "code", "b" * 64, "maybe", "succeeded"
        )
    with pytest.raises(StorageValidationError):
        store.sandbox_audit.add(
            project.id, "code", "b" * 64, "approved", "running"
        )
