"""The Kushinada fine-tuning corpus built from the user's own corrections.

Every accepted transcript edit is recorded as a training event with the audio
clip it refers to.  SQLite is the record of truth; the JSONL and CSV files next
to it are rebuildable caches, so a Windows file lock on them must never block a
save or a startup migration.
"""

from __future__ import annotations

import csv
import io
import json
import re
import shutil
import subprocess
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..text_utils import clean_multiline, clean_single_line, json_load, utc_now_iso
from .durable_files import atomic_write_bytes, atomic_write_text, durable_move, sync_file_data, temporary_output_path
from .group_analysis import analysis_csv_safe


@dataclass(frozen=True)
class TrainingStore:
    """Where the corpus lives and how to reach the rest of the application."""

    directory: Path
    audio_directory: Path
    jsonl_file: Path
    manifest_file: Path
    lock: Any
    connect: Callable[[], Any]
    logger: Any


def kushinada_label(segment: dict[str, Any]) -> str:
    emotions = segment.get("emotions")
    if not isinstance(emotions, dict):
        return ""
    data = emotions.get("kushinada")
    return str(data.get("label") or "") if isinstance(data, dict) else ""


def correction_signature(segment: dict[str, Any] | None, speaker_names: dict[str, str]) -> dict[str, Any] | None:
    if segment is None:
        return None
    speaker = str(segment.get("speaker") or "UNKNOWN")
    return {
        "start": round(float(segment.get("start", 0) or 0), 3),
        "end": round(float(segment.get("end", segment.get("start", 0)) or 0), 3),
        "speaker": speaker,
        "speaker_name": str(speaker_names.get(speaker) or ""),
        "text": str(segment.get("text") or "").strip(),
        "emotion": kushinada_label(segment),
    }


def extract_training_clip(
    media_path: Path | None, item_id: str, event_id: str, segment: dict[str, Any],
    *, store: TrainingStore,
) -> Path | None:
    if media_path is None or not media_path.is_file() or shutil.which("ffmpeg") is None:
        return None
    start = max(0.0, float(segment.get("start", 0) or 0))
    end = max(start, float(segment.get("end", start) or start))
    duration = end - start
    if duration <= 0:
        return None
    item_dir = store.audio_directory / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    target = item_dir / f"{event_id}.wav"
    temporary = temporary_output_path(target)
    try:
        completed = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-ss", f"{start:.3f}", "-i", str(media_path), "-t", f"{duration:.3f}",
                "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(temporary),
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if completed.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
            return None
        sync_file_data(temporary)
        durable_move(temporary, target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


TRAINING_MANIFEST_FIELDS = (
    "event_id", "audio_path", "emotion_label", "text", "speaker", "source_name",
    "start", "end", "operation", "created_at", "transcript_id", "segment_id",
)


def training_events_from_connection(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT payload_json FROM training_events ORDER BY created_at, event_id"
    ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        try:
            event = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise OSError("SQLite内の学習イベントが破損しています。") from exc
        if not isinstance(event, dict) or not isinstance(event.get("event_id"), str):
            raise OSError("SQLite内の学習イベント形式が不正です。")
        events.append(event)
    return events


def training_export_contents(events: list[dict[str, Any]]) -> tuple[str, str]:
    jsonl_content = "".join(
        json.dumps(event, ensure_ascii=False) + "\n" for event in events
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=TRAINING_MANIFEST_FIELDS)
    writer.writerow({header: analysis_csv_safe(header) for header in TRAINING_MANIFEST_FIELDS})
    for event in events:
        current = event.get("after") or event.get("before") or {}
        if not isinstance(current, dict):
            current = {}
        manifest_row = {
            "event_id": event["event_id"],
            "audio_path": event.get("audio_clip") or "",
            "emotion_label": current.get("emotion") or "",
            "text": current.get("text") or "",
            "speaker": current.get("speaker_name") or current.get("speaker") or "",
            "source_name": event.get("source_name") or "",
            "start": current.get("start", ""),
            "end": current.get("end", ""),
            "operation": event.get("operation") or "",
            "created_at": event.get("created_at") or "",
            "transcript_id": event.get("transcript_id") or "",
            "segment_id": event.get("segment_id") or "",
        }
        writer.writerow({key: analysis_csv_safe(value) for key, value in manifest_row.items()})
    return jsonl_content, stream.getvalue()


def write_training_exports(events: list[dict[str, Any]], *, store: TrainingStore) -> None:
    store.directory.mkdir(parents=True, exist_ok=True)
    if not events:
        store.jsonl_file.unlink(missing_ok=True)
        store.manifest_file.unlink(missing_ok=True)
        return
    jsonl_content, manifest_content = training_export_contents(events)
    try:
        current_jsonl = store.jsonl_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        current_jsonl = None
    if current_jsonl != jsonl_content:
        atomic_write_text(store.jsonl_file, jsonl_content, encoding="utf-8")
    try:
        current_manifest = store.manifest_file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        current_manifest = None
    if current_manifest != manifest_content:
        atomic_write_text(store.manifest_file, manifest_content, encoding="utf-8-sig")


def legacy_training_events(*, store: TrainingStore) -> list[dict[str, Any]]:
    if not store.jsonl_file.is_file():
        return []
    events: list[dict[str, Any]] = []
    try:
        lines = store.jsonl_file.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        raise
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_id = event.get("event_id") if isinstance(event, dict) else None
        valid_snapshots = all(
            event.get(field) is None or isinstance(event.get(field), dict)
            for field in ("before", "after")
        ) if isinstance(event, dict) else False
        if (
            isinstance(event_id, str)
            and re.fullmatch(r"[0-9a-f]{32}", event_id)
            and valid_snapshots
        ):
            events.append(event)
    return events


def cleanup_unreferenced_training_clips(
    events: list[dict[str, Any]], *, store: TrainingStore
) -> None:
    if not store.audio_directory.is_dir():
        return
    referenced_ids = {
        str(event.get("event_id"))
        for event in events
        if event.get("audio_clip") and re.fullmatch(r"[0-9a-f]{32}", str(event.get("event_id")))
    }
    for clip_path in store.audio_directory.rglob("*.wav"):
        if clip_path.stem not in referenced_ids:
            clip_path.unlink(missing_ok=True)
    directories = sorted(
        (path for path in store.audio_directory.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass


def repair_training_artifacts(*, store: TrainingStore) -> None:
    """Migrate legacy JSONL once, then rebuild all derived training files."""
    with store.lock:
        with store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            migrated_row = connection.execute(
                "SELECT value FROM application_metadata WHERE key = ?",
                ("training_events_migrated",),
            ).fetchone()
            migrated = migrated_row is not None and str(migrated_row["value"]) == "1"
            if not migrated:
                for event in legacy_training_events(store=store):
                    connection.execute(
                        "INSERT OR IGNORE INTO training_events (event_id, payload_json, created_at) "
                        "VALUES (?, ?, ?)",
                        (
                            event["event_id"],
                            json.dumps(event, ensure_ascii=False),
                            str(event.get("created_at") or ""),
                        ),
                    )
                connection.execute(
                    "UPDATE application_metadata SET value = ? WHERE key = ?",
                    ("1", "training_events_migrated"),
                )
            events = training_events_from_connection(connection)
        try:
            write_training_exports(events, store=store)
        except OSError:
            # JSONL/CSV are rebuildable caches and must not prevent startup or
            # roll back a completed one-time migration when Windows locks them.
            store.logger.exception("Could not rebuild derived training artifacts at startup")
    cleanup_unreferenced_training_clips(events, store=store)


def refresh_training_exports(*, store: TrainingStore) -> list[dict[str, Any]]:
    with store.lock:
        with store.connect() as connection:
            events = training_events_from_connection(connection)
        try:
            write_training_exports(events, store=store)
        except OSError:
            # JSONL/CSV are derived caches. Downloads are rendered directly
            # from the canonical SQLite snapshot even if Windows has a cache
            # file open or the cache directory is temporarily unavailable.
            store.logger.exception("Could not refresh derived training export files")
    return events


def prepare_training_corrections(
    row: sqlite3.Row,
    old_segments: list[dict[str, Any]],
    new_segments: list[dict[str, Any]],
    old_names: dict[str, str],
    new_names: dict[str, str],
    *,
    store: TrainingStore,
) -> tuple[list[dict[str, Any]], list[Path]]:
    old_by_id = {str(item.get("id")): item for item in old_segments}
    new_by_id = {str(item.get("id")): item for item in new_segments}
    ordered_ids = list(old_by_id) + [item_id for item_id in new_by_id if item_id not in old_by_id]
    media_path = Path(row["media_path"]) if row["media_path"] else None
    events: list[dict[str, Any]] = []
    created_clips: list[Path] = []
    try:
        for segment_id in ordered_ids:
            before = old_by_id.get(segment_id)
            after = new_by_id.get(segment_id)
            before_data = correction_signature(before, old_names)
            after_data = correction_signature(after, new_names)
            if before_data == after_data:
                continue
            operation = "add" if before is None else "delete" if after is None else "update"
            event_id = uuid.uuid4().hex
            reference = after or before
            assert reference is not None
            clip_path = extract_training_clip(
                media_path, row["id"], event_id, reference, store=store
            )
            if clip_path is not None:
                created_clips.append(clip_path)
            events.append({
                "schema_version": "1.0",
                "event_id": event_id,
                "created_at": utc_now_iso(),
                "transcript_id": row["id"],
                "segment_id": segment_id,
                "operation": operation,
                "source_name": row["source_name"],
                "source_media": str(media_path) if media_path else None,
                "audio_clip": str(clip_path) if clip_path else None,
                "before": before_data,
                "after": after_data,
                "ready_for_kushinada": bool(clip_path and after_data and after_data.get("emotion")),
            })
    except BaseException:
        for clip_path in created_clips:
            clip_path.unlink(missing_ok=True)
        raise
    return events, created_clips


def insert_training_events(
    connection: sqlite3.Connection,
    events: list[dict[str, Any]],
) -> None:
    for event in events:
        connection.execute(
            "INSERT INTO training_events (event_id, payload_json, created_at) "
            "VALUES (?, ?, ?)",
            (
                event["event_id"],
                json.dumps(event, ensure_ascii=False),
                event["created_at"],
            ),
        )
    if events:
        connection.execute(
            "UPDATE application_metadata SET value = ? WHERE key = ?",
            ("1", "training_events_migrated"),
        )


def discard_training_clips(created_clips: list[Path]) -> None:
    for clip_path in created_clips:
        try:
            clip_path.unlink(missing_ok=True)
        except OSError:
            # The canonical DB transaction has already been rolled back. Any
            # retained orphan is removed by repair_training_artifacts at boot.
            pass
    for directory in sorted(
        {clip_path.parent for clip_path in created_clips},
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass


def record_training_corrections(
    row: sqlite3.Row,
    old_segments: list[dict[str, Any]],
    new_segments: list[dict[str, Any]],
    old_names: dict[str, str],
    new_names: dict[str, str],
    *,
    store: TrainingStore,
) -> int:
    events, created_clips = prepare_training_corrections(
        row, old_segments, new_segments, old_names, new_names, store=store
    )
    if not events:
        return 0
    with store.lock:
        original_files: dict[Path, bytes | None] = {}
        try:
            for path in (store.jsonl_file, store.manifest_file):
                original_files[path] = path.read_bytes() if path.is_file() else None
            with store.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                insert_training_events(connection, events)
                write_training_exports(
                    training_events_from_connection(connection), store=store
                )
        except BaseException:
            for path, original in original_files.items():
                try:
                    if original is not None:
                        atomic_write_bytes(path, original)
                    else:
                        path.unlink(missing_ok=True)
                except OSError:
                    pass
            discard_training_clips(created_clips)
            raise
    return len(events)
