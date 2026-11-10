from __future__ import annotations

from see_storage import ProjectStore, default_data_dir

_store: ProjectStore | None = None


def get_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore(default_data_dir())
    return _store


def close_store() -> None:
    global _store
    if _store is not None:
        _store.close()
        _store = None
