from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import BinaryIO

from .errors import StorageError


class InstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: BinaryIO | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            self._lock(handle)
        except OSError as error:
            handle.close()
            raise StorageError(
                f"workspace déjà ouvert par une autre instance: {self.path}"
            ) from error
        self.handle = handle

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            self._unlock(self.handle)
        except OSError:
            pass
        finally:
            self.handle.close()
            self.handle = None

    def _lock(self, handle: BinaryIO) -> None:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(self, handle: BinaryIO) -> None:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
