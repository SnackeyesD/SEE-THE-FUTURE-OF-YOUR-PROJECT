from __future__ import annotations

import json

import pytest

from see_sandbox import ContractError, validate_result
from see_sandbox.limits import MAX_OUTPUT_BYTES


def test_valid_structured_result() -> None:
    value = {
        "summary": "Trois points simulés.",
        "metrics": [{"label": "Moyenne", "value": 12.5, "unit": "XOF"}],
        "series": [{"label": "Ventes", "x": [1, 2, 3], "y": [10, 12, 16]}],
        "tables": [
            {
                "name": "Détail",
                "columns": ["mois", "ventes", "actif"],
                "rows": [[1, 10, True], [2, 12, None]],
            }
        ],
    }
    assert validate_result(value) == value


@pytest.mark.parametrize(
    "value",
    [
        {"unknown": []},
        {"summary": "<script>alert(1)</script>"},
        {"metrics": [{"label": "x", "value": float("nan")}]},
        {"metrics": [{"label": "x", "value": True}]},
        {"series": [{"label": "x", "x": [1], "y": []}]},
        {"tables": [{"name": "t", "columns": ["a"], "rows": [[1, 2]]}]},
        {"tables": [{"name": "t", "columns": ["a"], "rows": [[{"nested": 1}]]}]},
    ],
)
def test_invalid_structured_results_are_refused(value: object) -> None:
    with pytest.raises(ContractError):
        validate_result(value)


def test_output_size_limit() -> None:
    value = {"metrics": [{"label": "x" * 4_000, "value": index} for index in range(100)]}
    encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
    assert len(encoded) > MAX_OUTPUT_BYTES
    with pytest.raises(ContractError):
        validate_result(value)
