from __future__ import annotations

from collections.abc import Mapping

from .models import PermissionMode

DEFAULT_PERMISSIONS: dict[str, PermissionMode] = {
    "update_brief": "allow",
    "set_hypotheses": "allow",
    "run_simulation": "allow",
    "compare_scenarios": "allow",
    "get_benchmark": "allow",
    "web_search": "ask",
    "export_report": "ask",
    "run_custom_script": "ask",
}

ALWAYS_ASK = frozenset({"run_custom_script"})


class PermissionResolver:
    def __init__(
        self,
        defaults: Mapping[str, PermissionMode] | None = None,
        *,
        always_ask: frozenset[str] = ALWAYS_ASK,
    ) -> None:
        self.defaults = dict(defaults or DEFAULT_PERMISSIONS)
        self.always_ask = always_ask

    def default_for(self, tool: str) -> PermissionMode:
        return self.defaults.get(tool, "ask")

    def resolve(
        self,
        tool: str,
        decisions: Mapping[str, PermissionMode] | None = None,
    ) -> PermissionMode:
        override = (decisions or {}).get(tool)
        if override == "deny":
            return "deny"
        if tool in self.always_ask:
            return "ask"
        if override in ("allow", "ask"):
            return override
        return self.default_for(tool)

    def requires_approval(
        self,
        tool: str,
        decisions: Mapping[str, PermissionMode] | None = None,
        *,
        approved: bool = False,
    ) -> bool:
        decision = self.resolve(tool, decisions)
        if decision == "deny":
            return True
        return decision == "ask" and not approved
