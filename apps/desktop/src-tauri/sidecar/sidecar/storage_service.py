from __future__ import annotations

import logging

from see_storage import ProjectStore, default_data_dir

logger = logging.getLogger(__name__)

_store: ProjectStore | None = None


def get_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore(default_data_dir())
        try:
            removed = _store.prune_all()
        except Exception as error:  # pragma: no cover - défense au démarrage
            logger.warning("purge des runs impossible: %s", error)
        else:
            if removed:
                logger.info("purge des runs: %s supprimé(s)", removed)
    return _store


def close_store() -> None:
    global _store
    if _store is not None:
        _store.close()
        _store = None
