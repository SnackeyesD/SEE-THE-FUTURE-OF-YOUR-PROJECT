from __future__ import annotations

from pathlib import Path

from see_sandbox import analyze_code

FIXTURES = Path(__file__).parent


def test_repository_fixtures_match_policy() -> None:
    valid = (FIXTURES / "valid" / "numpy_pandas.py").read_text(encoding="utf-8")
    assert analyze_code(valid).ok is True
    for path in (FIXTURES / "malicious").glob("*.py"):
        result = analyze_code(path.read_text(encoding="utf-8"))
        assert result.ok is False, path.name
