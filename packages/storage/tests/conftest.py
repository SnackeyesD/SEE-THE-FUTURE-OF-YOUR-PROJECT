from __future__ import annotations

from pathlib import Path

import pytest

from see_storage import ProjectStore


@pytest.fixture
def store(tmp_path: Path) -> ProjectStore:
    instance = ProjectStore(tmp_path / "data")
    try:
        yield instance
    finally:
        instance.close()
