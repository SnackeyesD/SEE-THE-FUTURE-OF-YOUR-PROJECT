from __future__ import annotations

from collections import deque

from .errors import InvalidTransition
from .models import AgentRoleName, JourneyStateName

JOURNEY_STATES: tuple[JourneyStateName, ...] = (
    "idea",
    "interviewing",
    "brief_draft",
    "brief_validated",
    "hypotheses_set",
    "simulating",
    "results_ready",
    "narrating",
    "done",
)

TRANSITIONS: dict[JourneyStateName, tuple[JourneyStateName, ...]] = {
    "idea": ("interviewing",),
    "interviewing": ("interviewing", "brief_draft", "brief_validated"),
    "brief_draft": ("interviewing", "brief_draft", "brief_validated"),
    "brief_validated": ("brief_draft", "brief_validated", "hypotheses_set"),
    "hypotheses_set": ("brief_validated", "hypotheses_set", "simulating"),
    "simulating": ("simulating", "results_ready"),
    "results_ready": ("simulating", "results_ready", "narrating"),
    "narrating": ("results_ready", "narrating", "done"),
    "done": ("done",),
}

ROLE_FOR_STATE: dict[JourneyStateName, AgentRoleName] = {
    "idea": "interviewer",
    "interviewing": "interviewer",
    "brief_draft": "interviewer",
    "brief_validated": "modeler",
    "hypotheses_set": "modeler",
    "simulating": "modeler",
    "results_ready": "narrator",
    "narrating": "narrator",
    "done": "narrator",
}


def validate_state(state: str) -> JourneyStateName:
    if state not in JOURNEY_STATES:
        raise InvalidTransition(state, state)
    return state  # type: ignore[return-value]


def role_for_state(state: str) -> AgentRoleName:
    return ROLE_FOR_STATE[validate_state(state)]


def can_transition(current: str, target: str) -> bool:
    current_state = validate_state(current)
    target_state = validate_state(target)
    return target_state in TRANSITIONS[current_state]


def advance_path(current: str, target: str) -> list[JourneyStateName]:
    current_state = validate_state(current)
    target_state = validate_state(target)
    if current_state == target_state:
        return []
    queue: deque[tuple[JourneyStateName, list[JourneyStateName]]] = deque(
        [(current_state, [])]
    )
    seen = {current_state}
    while queue:
        state, path = queue.popleft()
        for candidate in TRANSITIONS[state]:
            if candidate == target_state:
                return [*path, candidate]
            if candidate not in seen:
                seen.add(candidate)
                queue.append((candidate, [*path, candidate]))
    raise InvalidTransition(current_state, target_state)


def apply_target(current: str, target: str) -> JourneyStateName:
    path = advance_path(current, target)
    return path[-1] if path else validate_state(current)


def require_state(current: str, allowed: tuple[JourneyStateName, ...]) -> None:
    state = validate_state(current)
    if state not in allowed:
        raise InvalidTransition(state, allowed[0] if allowed else state)
