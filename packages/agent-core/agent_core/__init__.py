"""Orchestration d'agent de See The Future.

Le LLM choisit les outils ; ce paquet valide, applique les permissions, appelle le
moteur et journalise. Il n'accède ni au réseau ni au trousseau.
"""

from __future__ import annotations

from .errors import (
    AgentConfigurationError,
    AgentError,
    BriefIncomplete,
    InvalidTransition,
    PromptInjectionDetected,
    StructuredOutputError,
    ToolError,
    UnknownTool,
)
from .guardrails import (
    detect_injection,
    sanitize_untrusted_records,
    scrub_secrets,
    wrap_untrusted,
)
from .loop import AgentLoop
from .memory import normalize_thread, trim_messages
from .models import (
    BRIEF_REQUIRED_FIELDS,
    AgentRoleName,
    BriefContent,
    BriefDraft,
    JourneyStateName,
    ModelResponse,
    PendingPermission,
    PermissionMode,
    ToolEvent,
    TurnResult,
    TurnStatus,
    UpdateBriefInput,
)
from .permissions import ALWAYS_ASK, DEFAULT_PERMISSIONS, PermissionResolver
from .roles import PROMPT_VERSION, system_message, system_prompt
from .state_machine import (
    JOURNEY_STATES,
    ROLE_FOR_STATE,
    TRANSITIONS,
    advance_path,
    apply_target,
    can_transition,
    require_state,
    role_for_state,
    validate_state,
)
from .structured import extract_json, parse_structured, run_structured
from .tools import ToolContext, ToolExecution, ToolOutcome, ToolRegistry, ToolSpec, default_registry
from .trace import TraceEvent, TraceRecorder

__version__ = "0.1.0"

__all__ = [
    "ALWAYS_ASK",
    "AgentConfigurationError",
    "AgentError",
    "AgentLoop",
    "AgentRoleName",
    "BRIEF_REQUIRED_FIELDS",
    "BriefContent",
    "BriefDraft",
    "BriefIncomplete",
    "DEFAULT_PERMISSIONS",
    "InvalidTransition",
    "JOURNEY_STATES",
    "JourneyStateName",
    "ModelResponse",
    "PROMPT_VERSION",
    "PendingPermission",
    "PermissionMode",
    "PermissionResolver",
    "PromptInjectionDetected",
    "ROLE_FOR_STATE",
    "StructuredOutputError",
    "TRANSITIONS",
    "ToolContext",
    "ToolError",
    "ToolEvent",
    "ToolExecution",
    "ToolOutcome",
    "ToolRegistry",
    "ToolSpec",
    "TraceEvent",
    "TraceRecorder",
    "TurnResult",
    "TurnStatus",
    "UnknownTool",
    "UpdateBriefInput",
    "advance_path",
    "apply_target",
    "can_transition",
    "default_registry",
    "detect_injection",
    "extract_json",
    "normalize_thread",
    "parse_structured",
    "require_state",
    "role_for_state",
    "run_structured",
    "sanitize_untrusted_records",
    "scrub_secrets",
    "system_message",
    "system_prompt",
    "trim_messages",
    "validate_state",
    "wrap_untrusted",
]
