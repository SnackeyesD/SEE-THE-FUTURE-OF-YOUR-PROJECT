from __future__ import annotations

import json
from pathlib import Path

from engine.cli import main

EXAMPLE = Path(__file__).parents[1] / "examples" / "retail_depot.json"


def test_validate_command_reports_resolved_assumptions(capsys) -> None:
    assert main(["validate", "--scenario", str(EXAMPLE)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["model"] == "retail_depot"
    assert payload["assumptions"]["unit_price"]["value"] == 500


def test_run_command_emits_a_simulation_result(capsys) -> None:
    code = main(
        [
            "run",
            "--scenario",
            str(EXAMPLE),
            "--runs",
            "100",
            "--seed",
            "3",
            "--quiet",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runs"] == 100
    assert payload["seed"] == 3
    assert "metrics" in payload
    assert "breakEven" in payload


def test_run_command_writes_output_file(tmp_path: Path, capsys) -> None:
    output = tmp_path / "result.json"
    code = main(
        [
            "run",
            "--scenario",
            str(EXAMPLE),
            "--runs",
            "50",
            "--quiet",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    assert capsys.readouterr().out == ""
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["runs"] == 50


def test_invalid_scenario_exits_with_code_two(tmp_path: Path, capsys) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"name": "Sans hypothèses"}), encoding="utf-8")
    code = main(["validate", "--scenario", str(broken)])
    assert code == 2
    assert "requise" in capsys.readouterr().err


def test_benchmark_emits_a_summary(capsys) -> None:
    code = main(
        ["benchmark", "--scenario", str(EXAMPLE), "--runs", "200", "--quiet"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runs"] == 200
    assert payload["runsPerSecond"] > 0
