from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine import Scenario, SimulationConfig, simulate

EXAMPLE = Path(__file__).parents[1] / "examples" / "retail_depot.json"


@pytest.mark.slow
def test_one_hundred_thousand_runs_complete_under_two_seconds() -> None:
    scenario = Scenario.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))
    result = simulate(scenario, SimulationConfig(runs=100_000, seed=42))
    assert result.runs == 100_000
    assert result.duration_ms < 2_000.0
    assert json.dumps(result.to_dict())[:1] == "{"
