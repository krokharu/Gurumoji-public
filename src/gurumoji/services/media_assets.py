"""Read-only media inspection, persisted facts, and a once-per-startup backfill."""

from __future__ import annotations

import json
import math
import sqlite3
import subprocess
import threading
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from ..text_utils import utc_now_iso
from .outputs import MEDIA_SESSION_DATE_TAGS, probe_media_payload

FIELDS = ("path", "original_filename", "bytes", "file_modified_at", "media_created_at", "imported_at",
          "duration_seconds", "container", "video_codec", "width", "height", "fps", "audio_codec",
          "sample_rate", "channels", "probe_tool_version", "probe_json", "probed_at", "path_checked_at",
          "path_exists", "unknown_reasons_json")
PROBED_FIELDS = ("media_created_at", "duration_seconds", "container", "video_codec", "width", "height",
                 "fps", "audio_codec", "sample_rate", "channels", "probe_tool_version")


def initialize(connection: sqlite3.Connection) -> None:
    numeric = {"bytes": "INTEGER", "duration_seconds": "REAL", "width": "INTEGER", "height": "INTEGER",
               "fps": "REAL", "sample_rate": "INTEGER", "channels": "INTEGER", "path_exists": "INTEGER"}
    connection.execute(f"""CREATE TABLE IF NOT EXISTS media_assets (
        item_id TEXT NOT NULL, role TEXT NOT NULL,
        {', '.join(field + ' ' + numeric.get(field, 'TEXT') for field in FIELDS)},
        PRIMARY KEY(item_id, role))""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS media_assets_delete_v1
        AFTER DELETE ON library_items BEGIN DELETE FROM media_assets WHERE item_id=OLD.id; END""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS media_assets_path_changed_v1
        AFTER UPDATE OF media_path ON library_items WHEN OLD.media_path IS NOT NEW.media_path
        BEGIN DELETE FROM media_assets WHERE item_id=NEW.id AND role='stored'; END""")


def _run(command: list[str], *, timeout: int, check_cancelled: Any = None) -> Any:
    if check_cancelled:
        check_cancelled()
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _number(value: Any, *, integer: bool = False) -> int | float | None:
    try:
        result = float(Fraction(str(value)))
        if not math.isfinite(result) or result < 0:
            return None
        if integer:
            return int(result) if result.is_integer() else None
        return result
    except (ValueError, ZeroDivisionError, TypeError, OverflowError):
        return None


def inspect(path: Path | None, *, imported_at: str, original_filename: str | None = None,
            run_subprocess: Callable[..., Any] = _run) -> dict[str, Any]:
    now = utc_now_iso()
    result: dict[str, Any] = {field: None for field in FIELDS}
    result.update(path=str(path) if path is not None else None, original_filename=(original_filename or path.name) if path is not None else None,
                  imported_at=imported_at, path_checked_at=now)
    reasons: dict[str, str] = {}
    problem = None
    try:
        if path is None:
            problem = "no_media_path"
            result["path_exists"] = None
        elif not path.is_file():
            problem = "file_not_found"
            result["path_exists"] = 0
        else:
            stat = path.stat()
            result.update(path_exists=1, bytes=stat.st_size,
                          file_modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat())
    except OSError:
        problem = "path_check_failed"
    payload = None
    if problem is None:
        payload, problem = probe_media_payload(path, run_subprocess=run_subprocess)
        result["probed_at"] = now
    if payload is not None:
        result["probe_json"] = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        fmt = payload.get("format") if isinstance(payload.get("format"), dict) else {}
        streams = [stream for stream in payload.get("streams", []) if isinstance(stream, dict)] if isinstance(payload.get("streams"), list) else []
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
        audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
        version = payload.get("program_version") if isinstance(payload.get("program_version"), dict) else {}
        result.update(duration_seconds=_number(fmt.get("duration")), container=fmt.get("format_name") or None,
                      video_codec=video.get("codec_name") or None, audio_codec=audio.get("codec_name") or None,
                      probe_tool_version=version.get("version") or None)
        for field in ("width", "height"):
            result[field] = _number(video.get(field), integer=True)
        result["fps"] = _number(video.get("avg_frame_rate"))
        for field in ("sample_rate", "channels"):
            result[field] = _number(audio.get(field), integer=True)
        # A valid embedded datetime/date is preserved separately from file and import times.
        tags = [{str(key).casefold(): value for key, value in obj["tags"].items()}
                for obj in [fmt, *streams] if isinstance(obj.get("tags"), dict)]
        for name in MEDIA_SESSION_DATE_TAGS:
            for tag in tags:
                raw = tag.get(name)
                if not isinstance(raw, str):
                    continue
                try:
                    datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    result["media_created_at"] = raw
                    break
                except ValueError:
                    pass
            if result["media_created_at"] is not None:
                break
    for field in PROBED_FIELDS:
        if result[field] is None:
            reasons[field] = problem or "metadata_unavailable"
    for field in ("bytes", "file_modified_at", "original_filename"):
        if result[field] is None:
            reasons[field] = problem or "metadata_unavailable"
    result["unknown_reasons_json"] = json.dumps(reasons, sort_keys=True)
    return result


def save(connection: sqlite3.Connection, item_id: str, role: str, facts: dict[str, Any]) -> None:
    # INSERT...SELECT cannot recreate an orphan after a concurrent delete.
    connection.execute(f"""INSERT INTO media_assets(item_id, role, {', '.join(FIELDS)})
        SELECT ?, ?, {', '.join('?' for _ in FIELDS)} WHERE EXISTS (SELECT 1 FROM library_items WHERE id=?)
        ON CONFLICT(item_id, role) DO UPDATE SET
        {', '.join(field + '=excluded.' + field for field in FIELDS)}""",
        (item_id, role, *(facts.get(field) for field in FIELDS), item_id))


def needs_inspection(connection: sqlite3.Connection, item_id: str, path: Path | None, role: str = "stored") -> bool:
    row = connection.execute("SELECT path, bytes, file_modified_at, path_exists FROM media_assets WHERE item_id=? AND role=?",
                             (item_id, role)).fetchone()
    if row is None or row[0] != (str(path) if path is not None else None):
        return True
    try:
        if path is None or not path.is_file():
            return row[3] == 1
        stat = path.stat()
        return row[1] != stat.st_size or row[2] != datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    except OSError:
        return True


def public(connection: sqlite3.Connection, item_id: str, *, reveal_paths: bool) -> list[dict[str, Any]]:
    assets = []
    for row in connection.execute("SELECT role, " + ", ".join(FIELDS) + " FROM media_assets WHERE item_id=? ORDER BY role", (item_id,)):
        facts = dict(zip(("role", *FIELDS), row))
        # Display checks are read-only; old measurements remain available with timestamps.
        try:
            facts["path_exists"] = Path(facts["path"]).is_file() if facts["path"] else None
            facts["path_status"] = "available" if facts["path_exists"] else "file_not_found" if facts["path"] else "no_media_path"
        except OSError:
            facts["path_exists"] = None
            facts["path_status"] = "path_check_failed"
        facts["unknown_reasons"] = json.loads(facts.pop("unknown_reasons_json") or "{}")
        facts.pop("probe_json")  # Raw ffprobe tags can contain local paths and private metadata.
        if not reveal_paths:
            facts["path"] = None
            facts["original_filename"] = None
        assets.append(facts)
    return assets


class Backfill:
    """A cancellable, once-per-process scan, started only after startup recovery."""

    def __init__(self, database_connection: Callable[..., Any], write_lock: Any):
        self.connection = database_connection
        self.write_lock = write_lock
        self._lock = threading.Lock()
        self._worker: tuple[threading.Event, threading.Thread] | None = None
        self._status: dict[str, Any] = {"status": "not_started", "total": None, "processed": 0, "unknown": 0, "failed": 0, "reasons": {}}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {**self._status, "reasons": dict(self._status["reasons"])}

    def _update(self, **values: Any) -> None:
        with self._lock:
            self._status.update(values)

    def start(self) -> tuple[threading.Event, threading.Thread]:
        with self._lock:
            if self._worker is not None:
                return self._worker
            stop = threading.Event()
            worker = threading.Thread(target=self.run, args=(stop,), name="media-metadata-backfill", daemon=True)
            self._worker = stop, worker
            worker.start()
            return self._worker

    def run(self, stop: threading.Event) -> None:
        self._update(status="running")
        processed = unknown = failed = 0
        reasons: dict[str, int] = {}
        try:
            with self.connection() as connection:
                rows = connection.execute("SELECT id, media_path, source_name, created_at FROM library_items").fetchall()
            self._update(total=len(rows))
            for identity, raw_path, source, created in rows:
                if stop.is_set():
                    self._update(status="cancelled")
                    return
                path = Path(raw_path) if raw_path else None
                try:
                    with self.connection() as connection:
                        needed = needs_inspection(connection, identity, path)
                    if needed:
                        facts = inspect(path, imported_at=created, original_filename=source)
                        if stop.is_set():
                            self._update(status="cancelled")
                            return
                        with self.write_lock, self.connection() as connection:
                            if stop.is_set():
                                self._update(status="cancelled")
                                return
                            current = connection.execute("SELECT media_path FROM library_items WHERE id=?", (identity,)).fetchone()
                            if current is not None and current[0] == raw_path:
                                save(connection, identity, "stored", facts)
                                item_reasons = set(json.loads(facts["unknown_reasons_json"]).values())
                                unknown += bool(item_reasons)
                                failed += bool(item_reasons & {"ffprobe_failed", "invalid_probe_json", "path_check_failed"})
                                for reason in item_reasons:
                                    reasons[reason] = reasons.get(reason, 0) + 1
                except (OSError, ValueError, sqlite3.Error):
                    failed += 1
                processed += 1
                self._update(processed=processed, unknown=unknown, failed=failed, reasons=dict(reasons))
            self._update(status="completed" if not failed else "completed_with_errors")
        except (OSError, sqlite3.Error):
            self._update(status="failed", failed=failed + 1)
