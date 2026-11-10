from __future__ import annotations

import json
import math
import re
from typing import Any

from .limits import MAX_OUTPUT_BYTES

HTML_TAG = re.compile(
    r"<\s*/?\s*(script|iframe|object|embed|style|img|svg|math|link|meta)\b",
    re.IGNORECASE,
)
CONTROL_CHARACTER = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
RESULT_KEYS = frozenset({"summary", "metrics", "series", "tables"})
METRIC_KEYS = frozenset({"label", "value", "unit"})
SERIES_KEYS = frozenset({"label", "x", "y"})
TABLE_KEYS = frozenset({"name", "columns", "rows"})


class ContractError(ValueError):
    pass


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{field} doit être un nombre")
    if not math.isfinite(value):
        raise ContractError(f"{field} doit être fini")
    return value


def _text(value: Any, field: str, *, max_length: int = 4_000) -> str:
    if not isinstance(value, str):
        raise ContractError(f"{field} doit être une chaîne")
    if len(value) > max_length:
        raise ContractError(f"{field} dépasse {max_length} caractères")
    if CONTROL_CHARACTER.search(value):
        raise ContractError(f"{field} contient des caractères de contrôle")
    if HTML_TAG.search(value):
        raise ContractError(f"{field} ne peut pas contenir de HTML")
    return value


def _object(value: Any, field: str, allowed: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{field} doit être un objet")
    unknown = set(value) - allowed
    if unknown:
        raise ContractError(f"{field} contient des clés inconnues: {', '.join(sorted(unknown))}")
    return value


def _list(value: Any, field: str, *, maximum: int) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError(f"{field} doit être une liste")
    if len(value) > maximum:
        raise ContractError(f"{field} dépasse {maximum} éléments")
    return value


def validate_result(value: Any) -> dict[str, Any]:
    result = _object(value, "result", RESULT_KEYS)

    if "summary" in result:
        _text(result["summary"], "summary", max_length=2_000)

    metrics = result.get("metrics", [])
    for index, metric in enumerate(_list(metrics, "metrics", maximum=100)):
        item = _object(metric, f"metrics[{index}]", METRIC_KEYS)
        _text(item.get("label"), f"metrics[{index}].label", max_length=200)
        _number(item.get("value"), f"metrics[{index}].value")
        if "unit" in item:
            _text(item["unit"], f"metrics[{index}].unit", max_length=40)

    series = result.get("series", [])
    for index, item in enumerate(_list(series, "series", maximum=20)):
        entry = _object(item, f"series[{index}]", SERIES_KEYS)
        _text(entry.get("label"), f"series[{index}].label", max_length=200)
        x_values = _list(entry.get("x"), f"series[{index}].x", maximum=1_000)
        y_values = _list(entry.get("y"), f"series[{index}].y", maximum=1_000)
        if len(x_values) != len(y_values):
            raise ContractError(f"series[{index}] doit avoir autant de x que de y")
        for point, number in enumerate(x_values):
            _number(number, f"series[{index}].x[{point}]")
        for point, number in enumerate(y_values):
            _number(number, f"series[{index}].y[{point}]")

    tables = result.get("tables", [])
    for index, item in enumerate(_list(tables, "tables", maximum=10)):
        entry = _object(item, f"tables[{index}]", TABLE_KEYS)
        _text(entry.get("name"), f"tables[{index}].name", max_length=200)
        columns = _list(entry.get("columns"), f"tables[{index}].columns", maximum=30)
        for column, name in enumerate(columns):
            _text(name, f"tables[{index}].columns[{column}]", max_length=100)
        rows = _list(entry.get("rows"), f"tables[{index}].rows", maximum=500)
        for row_index, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != len(columns):
                raise ContractError(
                    f"tables[{index}].rows[{row_index}] doit avoir {len(columns)} cellules"
                )
            for cell_index, cell in enumerate(row):
                field = f"tables[{index}].rows[{row_index}][{cell_index}]"
                if cell is None or isinstance(cell, bool):
                    continue
                if isinstance(cell, str):
                    _text(cell, field, max_length=500)
                else:
                    _number(cell, field)

    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_OUTPUT_BYTES:
        raise ContractError(f"résultat trop volumineux (max {MAX_OUTPUT_BYTES} octets)")
    return result
