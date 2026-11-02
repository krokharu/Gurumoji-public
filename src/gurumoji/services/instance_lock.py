"""Cross-process lock that keeps a second app instance off the same data.

Two instances writing the same SQLite database, uploads or output folders
could interleave edits and recovery. The lock is an OS file lock (msvcrt on
Windows, flock elsewhere) on every configured lock file; it is released when
the process exits even if release() is never called.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Callable, Iterable


def lock_instance_stream(stream: Any) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def unlock_instance_stream(stream: Any) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class InstanceLock:
    """Hold non-blocking file locks on every path returned by ``paths``.

    ``paths`` is read on each acquire so a test or alternate data directory
    can repoint the lock files after import.
    """

    def __init__(self, paths: Callable[[], Iterable[Path]]) -> None:
        self._paths = paths
        self._streams: list[Any] = []
        self._guard = threading.Lock()

    def acquire(self) -> bool:
        with self._guard:
            if self._streams:
                return True
            acquired: list[Any] = []
            try:
                for lock_path in self._paths():
                    lock_path.parent.mkdir(parents=True, exist_ok=True)
                    stream = lock_path.open("a+b")
                    try:
                        lock_instance_stream(stream)
                    except Exception:
                        stream.close()
                        raise
                    acquired.append(stream)
            except (ImportError, OSError):
                for stream in reversed(acquired):
                    try:
                        unlock_instance_stream(stream)
                    except (ImportError, OSError):
                        pass
                    stream.close()
                return False
            self._streams = acquired
            return True

    def release(self) -> None:
        with self._guard:
            streams = self._streams
            if not streams:
                return
            for stream in reversed(streams):
                try:
                    unlock_instance_stream(stream)
                except (ImportError, OSError):
                    pass
                stream.close()
            self._streams = []
