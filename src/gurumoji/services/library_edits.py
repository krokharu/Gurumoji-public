"""Save an edited transcript: validation, output rewrite and the edit transaction.

The caller holds the library write lock (hence the _locked name). Output
files are staged and promoted through an edit manifest so an interrupted save
can be recovered at startup; training corrections are recorded from the same
diff."""

from __future__ import annotations

import csv
import math
import sqlite3
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable

from .. import transcript_preparation as preparation
from ..handlers.analysis_commands import TranscriptConflictError
from ..text_utils import json_load, validate_json_value
from .durable_files import path_entry_exists
from .edit_transactions import (
    capture_edit_cleanup_inventory,
    cleanup_edit_staging,
    edit_staging_identity,
    load_edit_preparation_marker,
)
from .emotion import AIST_EMOTION_MODELS, build_emotion_analysis_summary, emotion_label_ja
from .group_analysis import ANALYSIS_MAX_TIMELINE_SECONDS
from .library_rows import (
    normalize_conversation_speaker_profiles,
    normalize_session_profile,
    normalize_source_name,
    stable_segment_id,
)
from .media_files import is_video_path
from .meeting_minutes import build_meeting_minutes
from .training_corpus import discard_training_clips


def normalize_edited_segments(item_id: str, raw_segments: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_segments, list):
        raise ValueError("発話データは配列で指定してください。")
    if len(raw_segments) > 100000:
        raise ValueError("発話数が多すぎます。")
    validate_json_value(raw_segments)
    normalized: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    label_aliases = {"怒り": "ang", "喜び": "hap", "悲しみ": "sad", "平常": "neu"}
    valid_emotions = {"", "ang", "hap", "sad", "neu"}
    for index, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            raise ValueError(f"発話 {index + 1} の形式が不正です。")
        try:
            start_raw = raw.get("start", 0)
            if start_raw is None or start_raw == "":
                start_raw = 0
            if isinstance(start_raw, bool):
                raise ValueError
            start_number = float(start_raw)
            end_raw = raw.get("end", start_number)
            if end_raw is None or end_raw == "":
                end_raw = start_number
            if isinstance(end_raw, bool):
                raise ValueError
            end_number = float(end_raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"発話 {index + 1} の時刻が不正です。") from exc
        if not math.isfinite(start_number) or not math.isfinite(end_number):
            raise ValueError(f"発話 {index + 1} の時刻にNaN/Infinityは使用できません。")
        start = round(max(0.0, start_number), 3)
        end = round(end_number, 3)
        if end < start:
            raise ValueError(f"発話 {index + 1} の終了時刻は開始時刻以降にしてください。")
        if end > ANALYSIS_MAX_TIMELINE_SECONDS or end - start > 86400:
            raise ValueError(f"発話 {index + 1} の長さが不正です。")
        text_value = raw.get("text", "")
        if not isinstance(text_value, str) or len(text_value) > 50000:
            raise ValueError(f"発話 {index + 1} の本文が不正です。")
        speaker_value = raw.get("speaker") or "UNKNOWN"
        if not isinstance(speaker_value, str) or len(speaker_value) > 80:
            raise ValueError(f"発話 {index + 1} の話者ラベルが不正です。")
        speaker = speaker_value.strip().replace("\r", " ").replace("\n", " ")
        if "id" in raw and not isinstance(raw["id"], str):
            raise ValueError(f"発話 {index + 1} のIDが不正です。")
        segment = dict(raw)
        segment.update({"start": start, "end": end, "speaker": speaker or "UNKNOWN", "text": text_value.strip()})
        segment["text"] = text_value
        if raw.get("time_unknown") or any(raw.get(key) in (None, "") for key in ("start", "end")):
            segment["time_unknown"] = True
        segment_id = stable_segment_id(item_id, index, segment)
        if segment_id in used_ids:
            segment_id = uuid.uuid4().hex
        segment["id"] = segment_id
        used_ids.add(segment_id)

        if "kushinada_label" in raw:
            raw_label = raw.get("kushinada_label") or ""
            if not isinstance(raw_label, str):
                raise ValueError(f"発話 {index + 1} の感情ラベルが不正です。")
            requested_label = raw_label.strip().lower()
            requested_label = label_aliases.get(requested_label, requested_label)
            if requested_label not in valid_emotions:
                raise ValueError(f"発話 {index + 1} の感情ラベルが不正です。")
            emotions = dict(segment.get("emotions")) if isinstance(segment.get("emotions"), dict) else {}
            if requested_label:
                previous = emotions.get("kushinada") if isinstance(emotions.get("kushinada"), dict) else {}
                emotions["kushinada"] = {
                    **previous,
                    "model_name": "くしなだ",
                    "model_repo": AIST_EMOTION_MODELS["kushinada"]["emotion_repo"],
                    "label": requested_label,
                    "label_ja": emotion_label_ja(requested_label),
                    "manually_corrected": True,
                }
            else:
                emotions.pop("kushinada", None)
            segment["emotions"] = emotions
        normalized.append(segment)
    return sorted(normalized, key=lambda item: (float(item.get("start", 0)), float(item.get("end", 0)))) if all(
        preparation.valid_time(item) for item in normalized
    ) else normalized


def make_library_update(
    *,
    default_output_directory: Callable[[], Any],
    database_connection: Any,
    durable_move: Any,
    edit_journal_secret: Any,
    edit_storage_id: Any,
    insert_training_events: Any,
    jobs: Any,
    jobs_lock: Any,
    library_public: Any,
    library_row: Any,
    manual_output_directory: Any,
    prepare_training_corrections: Any,
    promote_staged_files: Any,
    reconcile_edit_transactions_before_mutation: Any,
    record_output_import_provenance: Any,
    row_segments: Any,
    row_session_profile: Any,
    training_events_from_connection: Any,
    training_lock: Any,
    upsert_library_item: Any,
    write_edit_preparation_marker: Any,
    write_edit_transaction_manifest: Any,
    write_outputs: Any,
    write_subtitled_video_assets: Any,
    write_training_exports: Any,
) -> Callable[..., Any]:
    def _update_library_from_payload_locked(
        item_id: str,
        payload: Any,
        *,
        ai_usage_override: dict[str, Any] | None = None,
        record_training: bool = True,
        outline_override: dict[str, Any] | None = None,
        check_cancelled: Callable[[], None] | None = None,
        finishing_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        row = library_row(item_id)
        if row is None:
            raise LookupError("データが見つかりません。")
        if not isinstance(payload, dict):
            raise ValueError("編集内容が JSON ではありません。")
        validate_json_value(payload)
        expected_revision = payload.get("revision_count")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
            raise ValueError("revision_count is required and must be an integer.")
        current_revision = int(row["revision_count"] or 0)
        if expected_revision != current_revision:
            raise TranscriptConflictError(current_revision)
        recovery_errors, _ = reconcile_edit_transactions_before_mutation(item_id, row)
        if recovery_errors:
            raise OSError(
                'A pending edit transaction could not be recovered safely. Restart the application.'
            )
        row = library_row(item_id)
        if row is None:
            raise LookupError('データが見つかりません。')
        current_revision = int(row['revision_count'] or 0)
        if expected_revision != current_revision:
            raise TranscriptConflictError(current_revision)
        old_segments = row_segments(row)
        old_names = json_load(row["speaker_names_json"], {})
        if not isinstance(old_names, dict):
            old_names = {}
        new_segments = normalize_edited_segments(item_id, payload.get("segments"))
        raw_names = payload.get("speaker_names", {})
        if not isinstance(raw_names, dict):
            raise ValueError("話者名の形式が不正です。")
        labels = {str(item.get("speaker") or "UNKNOWN") for item in new_segments}
        new_names: dict[str, str] = {}
        for label, value in raw_names.items():
            if not isinstance(label, str) or not isinstance(value, str) or len(label) > 80:
                raise ValueError("Invalid speaker name mapping.")
            clean_name = value.strip().replace("\r", " ").replace("\n", " ")
            if label in labels and clean_name:
                if len(clean_name) > 80:
                    raise ValueError("話者名は 80 文字以内にしてください。")
                new_names[label] = clean_name
        source_value = payload.get("source_name") or row["source_name"]
        if not isinstance(source_value, str):
            raise ValueError("Invalid source name.")
        source_name = normalize_source_name(source_value)
        if not source_name or len(source_name) > 255:
            raise ValueError("データ名は 1～255 文字で指定してください。")
        session_profile = (
            normalize_session_profile(payload.get("session_profile"))
            if "session_profile" in payload
            else row_session_profile(row)
        )
        speaker_profiles = normalize_conversation_speaker_profiles(
            payload.get("speaker_profiles")
            if "speaker_profiles" in payload
            else json_load(row["speaker_profiles_json"], {}),
            labels,
            new_names,
        )
        for label, profile in speaker_profiles.items():
            if profile["display_name"]:
                new_names[label] = profile["display_name"]

        outline = outline_override if outline_override is not None else json_load(row["outline_json"], None)
        meeting_minutes = (
            build_meeting_minutes(new_segments, new_names, session_profile, outline)
            if session_profile.get("session_type") == "meeting"
            else {}
        )
        emotion_analysis = json_load(row["emotion_analysis_json"], None)
        model_keys = sorted({
            str(model_key)
            for segment in new_segments
            for model_key in ((segment.get("emotions") or {}).keys() if isinstance(segment.get("emotions"), dict) else [])
        })
        if model_keys:
            emotion_analysis = build_emotion_analysis_summary(new_segments, model_keys, status="completed")
        output_dir = Path(row["output_dir"])
        try:
            uses_shared_default = output_dir.resolve() == default_output_directory().resolve()
        except OSError:
            uses_shared_default = output_dir == default_output_directory()
        if uses_shared_default:
            output_dir = manual_output_directory(source_name, item_id)
        raw_previous_files = json_load(row["files_json"], [])
        previous_output_dir = Path(str(row['output_dir']))
        previous_files = (
            [Path(str(value)) for value in raw_previous_files]
            if isinstance(raw_previous_files, list)
            else []
        )
        staging_dir = output_dir / f".edit-staging-{uuid.uuid4().hex}"
        transaction_id = staging_dir.name.removeprefix('.edit-staging-')
        preparing_dir = output_dir / f'.edit-preparing-{transaction_id}-{uuid.uuid4().hex}'
        preparing_dir.mkdir(parents=True, exist_ok=False)
        preparing_identity = edit_staging_identity(preparing_dir)
        staging_identity: tuple[int, int] | None = None
        preparation_inventory = capture_edit_cleanup_inventory(preparing_dir, {})

        def cleanup_if_owned(candidate: Path) -> list[str]:
            if not path_entry_exists(candidate):
                return []
            try:
                if edit_staging_identity(candidate) != preparing_identity:
                    return []
            except OSError:
                return []
            return cleanup_edit_staging(
                candidate,
                expected_identity=preparing_identity,
                inventory=preparation_inventory,
            )

        try:
            write_edit_preparation_marker(
                preparing_dir,
                output_dir,
                item_id=item_id,
                expected_revision=current_revision,
                previous_output_dir=previous_output_dir,
            )
            with database_connection() as connection:
                preparation_storage_id = edit_storage_id(connection)
                preparation_secret = edit_journal_secret(connection)
            preparation_payload = load_edit_preparation_marker(
                preparing_dir,
                expected_storage_id=preparation_storage_id,
                expected_secret=preparation_secret,
            )
            preparation_inventory = preparation_payload['_cleanup_inventory']
            durable_move(preparing_dir, staging_dir, replace_existing=False)
            if edit_staging_identity(staging_dir) != preparing_identity:
                raise OSError('The published edit staging identity changed unexpectedly.')
            staging_identity = preparing_identity
            formatting_result = json_load(row["formatting_result_json"], {})
            if isinstance(formatting_result, dict) and formatting_result:
                formatting_result = dict(formatting_result)
                formatting_result["manual_edit_status"] = "edited_after_formatting"
            else:
                formatting_result = {}
            staged_files = write_outputs(
                source_name, staging_dir, new_segments, row["language"], new_names,
                bool(row["write_srt"]), True, outline, emotion_analysis, speaker_profiles,
                meeting_minutes, check_cancelled,
                formatting_result=formatting_result,
                session_profile=session_profile,
            )
            write_edit_preparation_marker(
                staging_dir,
                output_dir,
                item_id=item_id,
                expected_revision=current_revision,
                previous_output_dir=previous_output_dir,
                staged_files=staged_files,
            )
            core_prepared_payload = load_edit_preparation_marker(
                staging_dir,
                expected_storage_id=preparation_storage_id,
                expected_secret=preparation_secret,
            )
            preparation_inventory = core_prepared_payload['_cleanup_inventory']
        except BaseException as preparation_exc:
            cleanup_errors = [
                *cleanup_if_owned(preparing_dir),
                *cleanup_if_owned(staging_dir),
            ]
            if cleanup_errors:
                raise OSError(
                    'Edit preparation failed and owned staging cleanup was incomplete: '
                    + '; '.join(cleanup_errors)
                ) from preparation_exc
            raise
        output_warning = ""
        media_path = Path(row["media_path"]) if row["media_path"] else None
        if bool(row["burn_subtitled_video"]) and media_path and media_path.is_file() and is_video_path(media_path):
            optional_assets_before = {
                candidate.resolve()
                for candidate in staging_dir.rglob('*')
                if candidate.is_file()
            }
            try:
                staged_files.extend(write_subtitled_video_assets(
                    media_path,
                    source_name,
                    staging_dir,
                    new_segments,
                    new_names,
                    speaker_profiles,
                ))
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                unexpected_optional = [
                    candidate
                    for candidate in staging_dir.rglob('*')
                    if candidate.is_file()
                    and candidate.resolve() not in optional_assets_before
                ]
                if unexpected_optional:
                    cleanup_errors = cleanup_edit_staging(
                        staging_dir,
                        expected_identity=staging_identity,
                        inventory=preparation_inventory,
                    )
                    raise OSError(
                        'Optional video generation left unauthenticated files; edit staging '
                        'was retained for safe recovery: '
                        + '; '.join(cleanup_errors)
                    ) from exc
                output_warning = f"字幕動画の再作成に失敗しました: {exc}"
        try:
            write_edit_preparation_marker(
                staging_dir,
                output_dir,
                item_id=item_id,
                expected_revision=current_revision,
                previous_output_dir=previous_output_dir,
                staged_files=staged_files,
            )
            prepared_payload = load_edit_preparation_marker(
                staging_dir,
                expected_storage_id=preparation_storage_id,
                expected_secret=preparation_secret,
            )
            preparation_inventory = prepared_payload['_cleanup_inventory']
        except BaseException as inventory_exc:
            cleanup_errors = cleanup_edit_staging(
                staging_dir,
                expected_identity=staging_identity,
                inventory=preparation_inventory,
            )
            if cleanup_errors:
                raise OSError(
                    'Edit output inventory could not be authenticated; staging was retained: '
                    + '; '.join(cleanup_errors)
                ) from inventory_exc
            raise
        if record_training:
            try:
                training_events, created_training_clips = prepare_training_corrections(
                    row, old_segments, new_segments, old_names, new_names
                )
            except BaseException as training_exc:
                cleanup_errors = cleanup_edit_staging(
                    staging_dir,
                    expected_identity=staging_identity,
                    inventory=preparation_inventory,
                )
                if cleanup_errors:
                    raise OSError(
                        'Training preparation failed and edit staging was retained: '
                        + '; '.join(cleanup_errors)
                    ) from training_exc
                raise
        else:
            training_events, created_training_clips = [], []
        learning_warning = ""
        learning_events = len(training_events)
        try:
            write_edit_transaction_manifest(
                staging_dir,
                output_dir,
                staged_files,
                item_id=item_id,
                expected_revision=current_revision,
                previous_output_dir=previous_output_dir,
            )
        except BaseException as manifest_exc:
            discard_training_clips(created_training_clips)
            cleanup_errors = cleanup_edit_staging(
                staging_dir,
                expected_identity=staging_identity,
                inventory=preparation_inventory,
            )
            if cleanup_errors:
                raise OSError(
                    'Edit manifest creation failed and staging cleanup was incomplete: '
                    + '; '.join(cleanup_errors)
                ) from manifest_exc
            raise
        try:
            with training_lock:
                all_training_events: list[dict[str, Any]] = []
                if check_cancelled is not None:
                    check_cancelled()
                with promote_staged_files(staging_dir, output_dir, staged_files) as files:
                    with database_connection() as connection:
                        connection.execute("BEGIN IMMEDIATE")
                        if check_cancelled is not None:
                            check_cancelled()
                        record_output_import_provenance(
                            connection, item_id, previous_files
                        )
                        record_output_import_provenance(
                            connection, item_id, files
                        )
                        updated = upsert_library_item(
                            item_id=item_id, source_name=source_name, output_dir=output_dir,
                            media_path=media_path,
                            language=row["language"], segments=new_segments,
                            speaker_names=new_names,
                            outline=outline, emotion_analysis=emotion_analysis, files=files,
                            write_srt=bool(row["write_srt"]), write_json=True,
                            increment_revision=True, created_at=row["created_at"],
                            session_profile=session_profile, speaker_profiles=speaker_profiles,
                            burn_subtitled_video=bool(row["burn_subtitled_video"]),
                            expected_revision=current_revision,
                            connection=connection,
                            ai_usage=(
                                ai_usage_override
                                if ai_usage_override is not None
                                else json_load(row["ai_usage_json"], {})
                            ),
                            meeting_minutes=meeting_minutes,
                            formatting_result=formatting_result,
                            finishing_history=finishing_history,
                        )
                        insert_training_events(connection, training_events)
                        if training_events:
                            all_training_events = training_events_from_connection(connection)
                if training_events:
                    try:
                        write_training_exports(all_training_events)
                    except (OSError, csv.Error) as exc:
                        learning_warning = (
                            "学習履歴はデータベースへ保存しましたが、派生ファイルを更新できませんでした: "
                            f"{exc}"
                        )
        except BaseException:
            discard_uncommitted_clips = False
            try:
                with database_connection() as connection:
                    revision_row = connection.execute(
                        'SELECT revision_count FROM library_items WHERE id = ?',
                        (item_id,),
                    ).fetchone()
                discard_uncommitted_clips = (
                    revision_row is not None
                    and int(revision_row['revision_count'] or 0) == current_revision
                )
            except (OSError, sqlite3.Error):
                # Preserve ambiguous clips. Startup repair removes them if no
                # committed training event references them.
                pass
            if discard_uncommitted_clips:
                discard_training_clips(created_training_clips)
            raise
        with jobs_lock:
            job = jobs.get(item_id)
            if job is not None:
                job.source_name = source_name
                job.segments = row_segments(updated)
                job.speaker_names = new_names
                job.session_profile = session_profile
                job.speaker_profiles = speaker_profiles
                job.emotion_analysis = emotion_analysis
                job.files = files
                job.outline = outline
                job.revision_count = int(updated["revision_count"] or 0)
                job.ai_usage = json_load(updated["ai_usage_json"], {})
        result = library_public(updated)
        result["learning_events"] = learning_events
        result["learning_warning"] = learning_warning
        result["output_warning"] = output_warning
        return result

    return _update_library_from_payload_locked
