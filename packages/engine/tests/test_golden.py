from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from engine import Scenario, SimulationConfig, simulate

GOLDEN_PATH = Path(__file__).parent / "golden" / "retail_depot_three_months.json"


def test_retail_depot_golden_values() -> None:
    payload = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    scenario = Scenario.model_validate(payload["scenario"])
    config = SimulationConfig.model_validate(payload["config"])
    result = simulate(scenario, config)
    expected = payload["expected"]

    for field, value in expected["metrics"].items():
        actual = getattr(result.metrics, _snake_case(field))
        assert actual == pytest.approx(value), field

    for expected_month, actual_month in zip(
        expected["monthly"], result.monthly.values, strict=True
    ):
        actual = actual_month.model_dump(by_alias=True)
        for field, value in expected_month.items():
            assert actual[field] == pytest.approx(value), f"month {actual_month.index}: {field}"

    actual_break_even = result.break_even.model_dump(by_alias=True)
    for field, value in expected["breakEven"].items():
        assert actual_break_even[field] == pytest.approx(value), field

    assert result.runs_retained == expected["runsRetained"]
    assert [
        month.index for month in result.monthly.values if month.profit_histogram
    ] == [1]
    assert result.metrics.min_cash_cdf is not None
    actual_cdf = [
        point.model_dump(by_alias=True) for point in result.metrics.min_cash_cdf
    ]
    assert len(actual_cdf) == len(expected["cashCdf"])
    for actual_point, expected_point in zip(
        actual_cdf, expected["cashCdf"], strict=True
    ):
        assert actual_point["value"] == pytest.approx(expected_point["value"])
        assert actual_point["probability"] == pytest.approx(
            expected_point["probability"]
        )


def _snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
