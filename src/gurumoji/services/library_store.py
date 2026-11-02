"""Read and write library_items rows and shape them for the API."""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .. import transcript_preparation as preparation
from ..handlers.analysis_commands import TranscriptConflictError
from ..text_utils import json_load, utc_now_iso, validate_json_value
from .durable_files import path_is_within
from . import media_assets
from .group_analysis import analysis_segment_bounds
from .library_rows import (
    emotion_values,
    ensure_segment_ids,
    interview_comparison_identity,
    normalize_conversation_speaker_profiles,
    normalize_session_profile,
    row_meeting_minutes,
    row_session_outline,
)
from .meeting_minutes import normalize_meeting_minutes
from .transcription.segments import default_speaker_name


def make_library_store(
    *,
    media_directory: Callable[[], Any],
    database_connection: Any,
    local_path_access_allowed: Any,
    media_kind: Any,
    normalize_ai_usage: Any,
    row_segments: Any,
    row_session_profile: Any,
    row_speaker_profiles: Any,
) -> tuple[Callable[..., Any], ...]:
    def library_row(item_id: str) -> sqlite3.Row | None:
        with database_connection() as connection:
            return connection.execute("SELECT * FROM library_items WHERE id = ?", (item_id,)).fetchone()

    def library_group_name(group_id: str) -> str:
        if not group_id:
            return ""
        with database_connection() as connection:
            row = connection.execute(
                "SELECT name FROM library_groups WHERE id = ?", (group_id,)
            ).fetchone()
        return str(row["name"]) if row is not None else ""

    def library_public(
        row: sqlite3.Row, *, full: bool = True, match_count: int | None = None,
        group_name: str | None = None, segments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        # The list view passes the rows it already parsed; it needs no segment IDs (PERF-01).
        if full or segments is None:
            segments = row_segments(row)
        speaker_names = json_load(row["speaker_names_json"], {})
        if not isinstance(speaker_names, dict):
            speaker_names = {}
        speakers = sorted({
            str(speaker_names.get(str(item.get("speaker") or "")) or default_speaker_name(item.get("speaker")))
            for item in segments
            if item.get("speaker")
        })
        emotions = sorted({value for item in segments for value in emotion_values(item)})
        media_path = Path(row["media_path"]) if row["media_path"] else None
        file_paths = [Path(value) for value in json_load(row["files_json"], []) if isinstance(value, str)]
        output_root = Path(row["output_dir"])
        session_profile = row_session_profile(row)
        comparison_key, comparison_label, comparison_source = interview_comparison_identity(
            session_profile
        )
        group_id = str(row["group_id"] or "") if "group_id" in row.keys() else ""
        resolved_group_name = library_group_name(group_id) if group_name is None else group_name
        media_available = bool(
            media_path
            and path_is_within(media_path, media_directory() / str(row["id"]))
            and media_path.is_file()
        )
        # Shared, read-only timing bounds: malformed one-record input cannot break the list.
        timing = [analysis_segment_bounds(segment) for segment in segments]
        timed_ends = [end for _start, end, valid in timing if valid]
        result: dict[str, Any] = {
            "id": row["id"],
            "source_name": row["source_name"],
            "group_id": group_id,
            "group_name": resolved_group_name,
            "output_dir": row["output_dir"] if local_path_access_allowed() else "",
            "language": row["language"],
            "segment_count": len(segments),
            "duration": max(timed_ends, default=None),
            "timed_turn_count": len(timed_ends),
            "missing_time_turn_count": len(segments) - len(timed_ends),
            "speakers": speakers,
            "emotions": emotions,
            "preview": " ".join(str(item.get("text", "")).strip() for item in segments[:3]).strip()[:240],
            "thumbnail_url": (
                f"/api/library/{row['id']}/thumbnail?v="
                f"{urllib.parse.quote(str(row['updated_at']))}"
            ),
            "media_url": f"/api/library/{row['id']}/media" if media_available else None,
            "media_kind": media_kind(media_path) if media_available else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "revision_count": int(row["revision_count"] or 0),
            "analysis_revision": int(row["analysis_revision"] or 0),
            "analysis_updated_at": row["analysis_updated_at"],
            "match_count": match_count,
            "speaker_data_url": f"/api/library/{row['id']}/speakers.csv",
            "analysis_url": f"/api/library/{row['id']}/analysis",
            "analysis_export_url": f"/api/library/{row['id']}/analysis/export.json",
            # The key is only a matching token.  A guide-derived key never exposes
            # the guide text to the list API.
            "comparison_key": comparison_key,
            "comparison_label": comparison_label,
            "comparison_source": comparison_source,
            "files": [
                {"name": path.name, "url": f"/api/library/{row['id']}/files/{urllib.parse.quote(path.name)}"}
                for path in file_paths if path_is_within(path, output_root) and path.is_file()
            ],
        }
        if full:
            with database_connection() as connection:
                result["media_assets"] = media_assets.public(connection, str(row["id"]), reveal_paths=local_path_access_allowed())
            result.update({
                "status": "completed",
                "segments": segments,
                # Display-only, bound to the raw values; never written back to segments.
                "segment_timings": [
                    {"segment_id": segment.get("id"), "source_start": segment.get("start"),
                     "source_end": segment.get("end"), "source_time_unknown": segment.get("time_unknown"),
                     "valid": valid, "start": start if valid else None, "end": end if valid else None}
                    for segment, (start, end, valid) in zip(segments, timing)
                ],
                "speaker_names": speaker_names,
                "session_profile": session_profile,
                "speaker_profiles": row_speaker_profiles(row, segments, speaker_names),
                "outline": json_load(row["outline_json"], None),
                "session_outline": row_session_outline(row, session_profile),
                "meeting_minutes": row_meeting_minutes(row),
                "emotion_analysis": json_load(row["emotion_analysis_json"], None),
                "formatting_result": json_load(row["formatting_result_json"], {}),
                "ai_usage": normalize_ai_usage(json_load(row["ai_usage_json"], {})),
                "write_srt": bool(row["write_srt"]),
                "write_json": True,
                "burn_subtitled_video": bool(row["burn_subtitled_video"]),
            })
        # Media duration is independent of the final transcript timestamp.
        result["media_duration_seconds"] = row["media_duration_seconds"] if "media_duration_seconds" in row.keys() else next(
            (asset["duration_seconds"] for asset in result.get("media_assets", []) if asset["role"] == "stored"), None)
        result["media_created_at"] = row["media_created_at"] if "media_created_at" in row.keys() else next(
            (asset["media_created_at"] for asset in result.get("media_assets", []) if asset["role"] == "stored"), None)
        return result

    def upsert_library_item(
        *, item_id: str, source_name: str, output_dir: Path, media_path: Path | None,
        language: str | None, segments: list[dict[str, Any]], speaker_names: dict[str, str],
        outline: dict[str, Any] | None, emotion_analysis: dict[str, Any] | None,
        files: list[Path], write_srt: bool, write_json: bool, increment_revision: bool = False,
        created_at: str | None = None, session_profile: dict[str, Any] | None = None,
        speaker_profiles: dict[str, Any] | None = None, burn_subtitled_video: bool = False,
        expected_revision: int | None = None,
        connection: sqlite3.Connection | None = None,
        ai_usage: dict[str, Any] | None = None,
        meeting_minutes: dict[str, Any] | None = None,
        original_segments: list[dict[str, Any]] | None = None,
        formatting_result: dict[str, Any] | None = None,
        original_media_path: Path | None = None,
        finishing_history: list[dict[str, Any]] | None = None,
    ) -> sqlite3.Row:
        validate_json_value(segments)
        validate_json_value(original_segments)
        validate_json_value(speaker_names)
        validate_json_value(outline)
        validate_json_value(emotion_analysis)
        validate_json_value(session_profile)
        validate_json_value(speaker_profiles)
        validate_json_value(meeting_minutes)
        validate_json_value(formatting_result)
        ai_usage = normalize_ai_usage(ai_usage)
        validate_json_value(ai_usage)
        now = utc_now_iso()
        segments = ensure_segment_ids(item_id, segments)
        import_segments = ensure_segment_ids(item_id, original_segments) if original_segments is not None else segments
        session_profile = normalize_session_profile(session_profile)
        meeting_minutes = normalize_meeting_minutes(meeting_minutes)
        labels = {str(item.get("speaker") or "UNKNOWN") for item in segments}
        speaker_profiles = normalize_conversation_speaker_profiles(
            speaker_profiles,
            labels,
            speaker_names,
        )
        def prepare_media(active_connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
            previous = active_connection.execute("SELECT created_at FROM library_items WHERE id=?", (item_id,)).fetchone()
            imported_at = previous[0] if previous is not None else created_at or now
            prepared = {}
            for role, path in (("stored", media_path), ("original", original_media_path)):
                if role == "original" and path is None:
                    continue
                if media_assets.needs_inspection(active_connection, item_id, path, role):
                    prepared[role] = media_assets.inspect(path, imported_at=imported_at, original_filename=source_name)
            return prepared

        # Slow subprocesses stay outside the write transaction in the usual import path.
        if connection is not None:
            prepared_media = prepare_media(connection)
        else:
            with database_connection() as read_connection:
                prepared_media = prepare_media(read_connection)

        def persist(active_connection: sqlite3.Connection) -> sqlite3.Row:
            if not active_connection.in_transaction:
                active_connection.execute("BEGIN IMMEDIATE")
            previous = active_connection.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
            if expected_revision is not None:
                if not active_connection.in_transaction:
                    active_connection.execute("BEGIN IMMEDIATE")
                current = active_connection.execute(
                    "SELECT revision_count FROM library_items WHERE id = ?", (item_id,)
                ).fetchone()
                if current is None:
                    raise LookupError("The transcript no longer exists.")
                current_revision = int(current["revision_count"] or 0)
                if current_revision != expected_revision:
                    raise TranscriptConflictError(current_revision)
            if previous is not None:
                preparation.capture(active_connection, previous, "legacy_current_baseline")
            persisted_formatting_result = formatting_result
            if persisted_formatting_result is None and previous is not None:
                persisted_formatting_result = json_load(previous["formatting_result_json"], {})
            active_connection.execute(
                """
                INSERT INTO library_items (
                    id, source_name, output_dir, media_path, language, segments_json,
                    original_segments_json, original_segments_status,
                    speaker_names_json, outline_json, meeting_minutes_json, emotion_analysis_json,
                    formatting_result_json, ai_usage_json, files_json,
                    write_srt, write_json, burn_subtitled_video, revision_count, created_at, updated_at,
                    session_profile_json, speaker_profiles_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_name=excluded.source_name, output_dir=excluded.output_dir,
                    media_path=excluded.media_path, language=excluded.language,
                    segments_json=excluded.segments_json, speaker_names_json=excluded.speaker_names_json,
                    outline_json=excluded.outline_json, meeting_minutes_json=excluded.meeting_minutes_json,
                    emotion_analysis_json=excluded.emotion_analysis_json,
                    formatting_result_json=excluded.formatting_result_json,
                    ai_usage_json=excluded.ai_usage_json,
                    files_json=excluded.files_json, write_srt=excluded.write_srt,
                    write_json=excluded.write_json,
                    burn_subtitled_video=excluded.burn_subtitled_video,
                    session_profile_json=excluded.session_profile_json,
                    speaker_profiles_json=excluded.speaker_profiles_json,
                    revision_count=library_items.revision_count + ?, updated_at=excluded.updated_at
                """,
                (
                    item_id, source_name, str(output_dir), str(media_path) if media_path else None,
                    language, json.dumps(segments, ensure_ascii=False),
                    json.dumps(import_segments, ensure_ascii=False), "initial_import",
                    json.dumps(speaker_names, ensure_ascii=False),
                    json.dumps(outline, ensure_ascii=False) if outline else None,
                    json.dumps(meeting_minutes, ensure_ascii=False),
                    json.dumps(emotion_analysis, ensure_ascii=False) if emotion_analysis else None,
                    json.dumps(persisted_formatting_result or {}, ensure_ascii=False),
                    json.dumps(ai_usage, ensure_ascii=False),
                    json.dumps([str(path) for path in files], ensure_ascii=False),
                    int(write_srt), 1, int(burn_subtitled_video),
                    int(increment_revision), created_at or now, now,
                    json.dumps(session_profile, ensure_ascii=False),
                    json.dumps(speaker_profiles, ensure_ascii=False),
                    int(increment_revision),
                ),
            )
            row = active_connection.execute(
                "SELECT * FROM library_items WHERE id = ?", (item_id,)
            ).fetchone()
            if row is None:
                raise RuntimeError("The library record could not be read back before commit.")
            history_steps = None
            import_source = None
            if finishing_history is not None:
                final_source = preparation.source(row)
                history_steps = []
                if previous is None:
                    import_source = {**final_source, "segments": import_segments, "speaker_names": {},
                        "speaker_profiles": normalize_conversation_speaker_profiles(
                            None, {str(s.get("speaker") or "UNKNOWN") for s in import_segments}, {})}
                for step in finishing_history:
                    step_segments = ensure_segment_ids(item_id, step["segments"])
                    step_names = step.get("speaker_names", {})
                    step_profiles = step.get("speaker_profiles")
                    history_steps.append({**{k: v for k, v in step.items() if k not in {"segments", "speaker_names", "speaker_profiles"}},
                        "source": {**final_source, "segments": step_segments, "speaker_names": step_names,
                                   "speaker_profiles": normalize_conversation_speaker_profiles(
                                       step_profiles, {str(s.get("speaker") or "UNKNOWN") for s in step_segments}, step_names)}})
            preparation.capture(active_connection, row, "saved" if previous is not None else "initial_import",
                                previous_source=preparation.source(previous) if previous is not None else None,
                                history_steps=history_steps, import_source=import_source)
            for role, facts in prepared_media.items():
                media_assets.save(active_connection, item_id, role, facts)
            return row

        if connection is not None:
            return persist(connection)
        with database_connection() as owned_connection:
            return persist(owned_connection)

    return (
        library_row,
        library_group_name,
        library_public,
        upsert_library_item,
    )
