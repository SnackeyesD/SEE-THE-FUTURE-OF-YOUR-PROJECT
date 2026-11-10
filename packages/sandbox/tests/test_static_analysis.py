from __future__ import annotations

import pytest

from see_sandbox import analyze_code

VALID_SCRIPT = """
import numpy as np
import pandas as pd

def main(data):
    frame = pd.DataFrame({"x": np.arange(3)})
    return {"metrics": [{"label": "lignes", "value": len(frame)}]}
"""


def test_valid_numpy_pandas_script_is_accepted() -> None:
    result = analyze_code(VALID_SCRIPT)
    assert result.ok is True
    assert result.issues == ()
    assert "numpy" in result.allowedImports
    assert len(result.codeHash) == 64


@pytest.mark.parametrize(
    "snippet",
    [
        "import os\n\ndef main(data):\n    return {'metrics': []}\n",
        "import socket\n\ndef main(data):\n    return {'metrics': []}\n",
        "import subprocess\n\ndef main(data):\n    return {'metrics': []}\n",
        "import ctypes\n\ndef main(data):\n    return {'metrics': []}\n",
        "import pyodide\n\ndef main(data):\n    return {'metrics': []}\n",
        "import js\n\ndef main(data):\n    return {'metrics': []}\n",
        "def main(data):\n    return open('/etc/passwd').read()\n",
        "def main(data):\n    return eval('1 + 1')\n",
        "def main(data):\n    return __import__('os').listdir('.')\n",
        "def main(data):\n    return getattr(data, '__class__')\n",
        "def main(data):\n    return data.__class__.__mro__\n",
        "from os import path\n\ndef main(data):\n    return {}\n",
        "from math import *\n\ndef main(data):\n    return {}\n",
    ],
)
def test_malicious_or_escaping_scripts_are_refused(snippet: str) -> None:
    result = analyze_code(snippet)
    assert result.ok is False
    assert any(issue.severity == "error" for issue in result.issues)


def test_missing_main_and_invalid_main_are_refused() -> None:
    assert analyze_code("print(1)").ok is False
    missing = analyze_code("x = 1")
    assert {issue.code for issue in missing.issues} >= {"missing_main"}
    invalid = analyze_code("def main():\n    return {}\n")
    assert {issue.code for issue in invalid.issues} >= {"invalid_main"}


def test_syntax_error_is_reported_with_location() -> None:
    result = analyze_code("def main(data):\n    return (\n")
    assert result.ok is False
    assert result.issues[0].code == "invalid_syntax"
    assert result.issues[0].line is not None


def test_code_size_limit() -> None:
    result = analyze_code("def main(data):\n    return {}\n" + "#" * 40_000)
    assert result.ok is False
    assert result.issues[0].code == "code_too_large"


def test_string_literal_limit() -> None:
    literal = "a" * 10_001
    result = analyze_code(f"def main(data):\n    x = {literal!r}\n    return {{}}\n")
    assert result.ok is False
    assert {issue.code for issue in result.issues} >= {"literal_too_large"}
