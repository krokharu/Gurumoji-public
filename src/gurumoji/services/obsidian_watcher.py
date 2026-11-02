"""Lifecycle-safe polling for the researcher-owned Obsidian workbench."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


WATCHER_MESSAGES = {
    "not_started": "Obsidianの監視は起動していません。",
    "starting": "Obsidianの作業台を復旧しています…",
    "running": "Obsidianの操作ノートとテーマを監視しています。",
    "polling_failed": "Obsidianの監視中にエラーが続いています。ログを確認してください。",
    "failed": (
        "起動時の復旧・移行に失敗したため、Obsidianの監視を停止しました。"
        "操作ノートのチェックとテーマ同期は反映されません。"
        "ログを確認してからアプリを再起動してください。"
    ),
    "stopped": "Obsidianの監視を終了しました。",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class WatcherStatus:
    """Thread-safe record of what the watcher is doing, for the UI (OBS-09)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = "not_started"
        self._since = ""
        self._detail = ""
        self._last_error_at = ""

    def set(self, state: str, detail: str = "") -> None:
        with self._lock:
            if state != self._state:
                self._since = _now()
            self._state = state
            self._detail = detail
            if state in {"failed", "polling_failed"}:
                self._last_error_at = _now()

    def poll_succeeded(self) -> None:
        with self._lock:
            if self._state == "polling_failed":
                self._state = "running"
                self._since = _now()
                self._detail = ""

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "active": self._state in {"starting", "running", "polling_failed"},
                "message": WATCHER_MESSAGES[self._state],
                "detail": self._detail,
                "since": self._since,
                "last_error_at": self._last_error_at,
            }


def _describe(exc: BaseException) -> str:
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


@dataclass(frozen=True)
class ObsidianWatcher:
    workbench: Callable[[], Any]
    engine: Callable[..., dict[str, Any]]
    migrate: Callable[[Any], None]
    log_exception: Callable[[str], None]
    status: WatcherStatus | None = None

    def start(self) -> tuple[threading.Event, threading.Thread]:
        stop = threading.Event()
        status = self.status or WatcherStatus()
        status.set("starting")

        def watch() -> None:
            try:
                current = self.workbench()
                current.recover()
                self.migrate(current.database_file)
            except Exception as exc:
                self.log_exception("Obsidian workbench recovery failed")
                status.set("failed", _describe(exc))
                stop.set()
                return
            status.set("running")
            last_theme_sync = 0.0
            while not stop.is_set():
                try:
                    current = self.workbench()
                    current.poll_once(self.engine, stop.is_set)
                    if time.monotonic() - last_theme_sync > 10:
                        current.layout.sync_themes()
                        last_theme_sync = time.monotonic()
                    status.poll_succeeded()
                except Exception as exc:
                    self.log_exception("Obsidian workbench polling failed")
                    status.set("polling_failed", _describe(exc))
                stop.wait(2)
            status.set("stopped")

        worker = threading.Thread(target=watch, name="obsidian-finishing", daemon=True)
        worker.start()
        return stop, worker
