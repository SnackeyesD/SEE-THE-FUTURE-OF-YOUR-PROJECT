from __future__ import annotations

import pytest

from agent_core import (
    InvalidTransition,
    advance_path,
    apply_target,
    can_transition,
    require_state,
    role_for_state,
    validate_state,
)


def test_allowed_and_forbidden_transitions() -> None:
    assert can_transition("idea", "interviewing")
    assert not can_transition("idea", "results_ready")
    assert can_transition("hypotheses_set", "simulating")
    assert not can_transition("hypotheses_set", "narrating")


def test_path_crosses_intermediate_states() -> None:
    assert advance_path("hypotheses_set", "results_ready") == [
        "simulating",
        "results_ready",
    ]
    assert advance_path("idea", "brief_validated") == [
        "interviewing",
        "brief_validated",
    ]
    assert apply_target("hypotheses_set", "results_ready") == "results_ready"


def test_no_simulation_without_hypotheses() -> None:
    with pytest.raises(InvalidTransition):
        require_state("brief_validated", ("hypotheses_set", "simulating"))


def test_unknown_state_rejected() -> None:
    with pytest.raises(InvalidTransition):
        validate_state("almost_done")


def test_role_routing() -> None:
    assert role_for_state("interviewing") == "interviewer"
    assert role_for_state("brief_validated") == "modeler"
    assert role_for_state("results_ready") == "narrator"
    assert role_for_state("done") == "narrator"
