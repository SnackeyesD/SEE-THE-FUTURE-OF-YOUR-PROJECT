from __future__ import annotations

from agent_core import PermissionResolver


def test_defaults_are_safe() -> None:
    resolver = PermissionResolver()
    assert resolver.resolve("update_brief") == "allow"
    assert resolver.resolve("web_search") == "ask"
    assert resolver.resolve("export_report") == "ask"
    assert resolver.resolve("run_custom_script") == "ask"
    assert resolver.resolve("unknown_tool") == "ask"


def test_project_overrides() -> None:
    resolver = PermissionResolver()
    assert resolver.resolve("web_search", {"web_search": "allow"}) == "allow"
    assert resolver.resolve("web_search", {"web_search": "deny"}) == "deny"
    assert resolver.resolve("update_brief", {"update_brief": "ask"}) == "ask"


def test_scripts_always_ask_even_when_allowed() -> None:
    resolver = PermissionResolver()
    assert resolver.resolve("run_custom_script", {"run_custom_script": "allow"}) == "ask"
    assert resolver.resolve("run_custom_script", {"run_custom_script": "deny"}) == "deny"


def test_requires_approval() -> None:
    resolver = PermissionResolver()
    assert resolver.requires_approval("web_search")
    assert not resolver.requires_approval("web_search", approved=True)
    assert resolver.requires_approval("web_search", {"web_search": "deny"})
    assert not resolver.requires_approval("update_brief")
