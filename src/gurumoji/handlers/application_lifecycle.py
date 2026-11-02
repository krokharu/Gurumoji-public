"""Application startup, background-worker, and shutdown coordination."""

from __future__ import annotations

import threading
from typing import Callable


class ApplicationLifecycle:
    """Preserve startup recovery order and own the single watcher instance."""

    def __init__(
        self,
        *,
        acquire_instance_lock: Callable[[], bool],
        release_instance_lock: Callable[[], None],
        initialize_library: Callable[[], None],
        recover_edits: Callable[[], list[str]],
        repair_provenance: Callable[[], None],
        recover_deletes: Callable[[], list[str]],
        repair_training: Callable[[], None],
        cleanup_uploads: Callable[[], None],
        import_outputs: Callable[[], None],
        report_edit_warning: Callable[[str], None],
        report_delete_warning: Callable[[str], None],
        spawn_watcher: Callable[[], tuple[threading.Event, threading.Thread]],
        spawn_media_worker: Callable[[], tuple[threading.Event, threading.Thread]] | None = None,
    ) -> None:
        self._acquire_instance_lock = acquire_instance_lock
        self._release_instance_lock = release_instance_lock
        self._initialize_library = initialize_library
        self._recover_edits = recover_edits
        self._repair_provenance = repair_provenance
        self._recover_deletes = recover_deletes
        self._repair_training = repair_training
        self._cleanup_uploads = cleanup_uploads
        self._import_outputs = import_outputs
        self._report_edit_warning = report_edit_warning
        self._report_delete_warning = report_delete_warning
        self._spawn_watcher = spawn_watcher
        self._spawn_media_worker = spawn_media_worker
        self._media_worker: tuple[threading.Event, threading.Thread] | None = None
        self._worker_lock = threading.Lock()
        self._watcher: tuple[threading.Event, threading.Thread] | None = None

    def initialize(self) -> None:
        if not self._acquire_instance_lock():
            raise RuntimeError(
                "Another Gurumoji process is already using this data directory."
            )
        try:
            self._initialize_library()
            for warning in self._recover_edits():
                self._report_edit_warning(warning)
            self._repair_provenance()
            for warning in self._recover_deletes():
                self._report_delete_warning(warning)
            self._repair_training()
            self._cleanup_uploads()
            self._import_outputs()
        except Exception:
            self._release_instance_lock()
            raise

    def start_watcher(self) -> tuple[threading.Event, threading.Thread]:
        with self._worker_lock:
            if self._spawn_media_worker is not None and self._media_worker is None:
                self._media_worker = self._spawn_media_worker()
            if self._watcher is not None and self._watcher[1].is_alive():
                return self._watcher
            self._watcher = self._spawn_watcher()
            return self._watcher

    def stop_watcher(self, *, timeout: float = 2) -> None:
        with self._worker_lock:
            watcher = self._watcher
            self._watcher = None
            media_worker = self._media_worker
        workers = [value for value in (watcher, media_worker) if value is not None]
        for stop, _worker in workers:
            stop.set()
        for _stop, worker in workers:
            worker.join(timeout=timeout)

    def shutdown(self) -> None:
        self.stop_watcher()
        self._release_instance_lock()
