from __future__ import annotations

from typing import Any


class AgentError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "agent_error",
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return payload


class InvalidTransition(AgentError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"transition interdite: {current} -> {target}",
            code="invalid_transition",
            details={"current": current, "target": target},
        )


class BriefIncomplete(AgentError):
    def __init__(self, missing: list[str]) -> None:
        super().__init__(
            "le brief est incomplet",
            code="brief_incomplete",
            details={"missingFields": missing},
        )


class ToolError(AgentError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "tool_error",
        details: Any = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class UnknownTool(ToolError):
    def __init__(self, name: str) -> None:
        super().__init__(f"outil inconnu: {name}", code="unknown_tool", details={"tool": name})


class StructuredOutputError(AgentError):
    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message, code="structured_output_invalid", details=details)


class PromptInjectionDetected(AgentError):
    def __init__(self, patterns: list[str]) -> None:
        super().__init__(
            "contenu non fiable contenant une tentative d'instruction détectée",
            code="prompt_injection",
            details={"patterns": patterns},
        )


class AgentConfigurationError(AgentError):
    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message, code="agent_configuration", details=details)
