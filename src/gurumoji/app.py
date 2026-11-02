"""Local Web UI for speaker-diarized transcription.

The browser UI is intentionally bound to 127.0.0.1. Heavy speech-recognition
libraries are imported only inside the background worker so the UI can start
even while the Python environment is being diagnosed.
"""

from __future__ import annotations

import csv
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import warnings
import webbrowser
from contextlib import closing, contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from flask import Flask, g, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

# app.py is the composition root. Besides what it wires together, it
# re-exports names that tests, scripts and the Colab notebook reach as
# app.<name>; pyflakes reports those as unused imports.
from .research_analysis import build_research_analysis as _build_research_analysis
from .services import conversation_projection, media_assets
from .analysis_insights import search_kwic
from .transformer_analysis import (
    DEFAULT_MODEL as DEFAULT_TRANSFORMER_MODEL,
    analyze_transformer_topics,
    encode_texts as encode_transformer_texts,
    semantic_search as transformer_semantic_search,
)
from .ai_finishing import (
    FINISHING_VERSION,
    clean_transcript as finish_clean_transcript,
    create_outline as finish_create_outline,
    repair_recommended_segments as finish_repair_recommended_segments,
)
from .jev_review import (
    JEV_DEFAULT_MODEL,
    JEV_REVIEW_VERSION,
    attach_comparison as attach_jev_comparison,
    review_transcript as review_transcript_with_jev,
)
from .segment_classification import classify_with_jev
from .obsidian_finishing import ObsidianWorkbench
from .ai_effort import normalize_efforts
from .analysis_method_registry import method_results
from .analysis_store import AnalysisStore, StoreConflict
from .analysis_pipeline import AnalysisPipelineService
from .analysis_core import AnalysisContractError
from .analysis_orchestration import AnalysisOrchestrationService, recover_orchestration_runs
from .services.analysis_orchestration_adapters import make_orchestration_adapters, ADAPTER_VERSION as ORCHESTRATION_ADAPTER_VERSION
from .services.analysis_orchestration_methods import run_orchestration_method
from .services.analysis_orchestration_publication import (
    AnalysisOrchestrationPublicationService, recover_orchestration_publications,
)
from .web.analysis_orchestration_routes import register_orchestration_routes
from .services.analysis_history import AnalysisHistoryService
from .services.analysis_slides import AnalysisSlidesService
from .services.analysis_slide_templates import load_slide_templates
from .web.analysis_slides_routes import register_analysis_slides_routes
from .handlers.analysis_commands import AnalysisCommands, ComparisonRequestError
from .handlers.analysis_queries import AnalysisQueries
from .handlers.application_lifecycle import ApplicationLifecycle
from .handlers.jobs import JobHandler
from .handlers.speaker_registry import (
    SpeakerIdentificationHandler,
    SpeakerRegistryHandler,
)
from .web.analysis_routes import register_analysis_routes
from .web.job_routes import register_job_routes
from .web.obsidian_routes import register_obsidian_routes
from .web.speaker_routes import register_speaker_routes
from .web.system_routes import register_system_routes
from .services.obsidian_watcher import ObsidianWatcher, WatcherStatus
from .services.obsidian_workflows import ObsidianWorkflowService
from .services.transcription_reporting import TranscriptionReporter
from .services.vault_publication import VaultPublicationService, whisper_settings
from .services.ai import client as ai_client
from .services.ai import transcript_finishing as ai_transcript_finishing
from .services import durable_files
from .services import edit_transactions
from .services import data_backup
from .services import library_trash
from .services.edit_transactions import (
    EDIT_PREPARATION_MARKER_NAME,
    EDIT_TRANSACTION_MANIFEST_NAME,
    cleanup_edit_staging,
    edit_journal_mac,
    edit_relative_path_key,
    load_edit_transaction_manifest,
    remove_edit_directory_contents,
    safe_edit_relative_path,
)
from .services import outputs
from .services import group_analysis
from .services import speaker_registry as speaker_registry_store
from .services import training_corpus
from .services import interview_comparison
from .services.transcription import formatting as transcript_formatting
from .services.transcription import job_runner as transcription_job_runner
from .services.training_corpus import (
    insert_training_events,
    training_events_from_connection,
)
from .services.speaker_registry import speaker_registry_csv_bytes
from .services.group_analysis import (
    ANALYSIS_CSV_FIELDS,
    ANALYSIS_METHODS,
    analysis_csv_rows,
    analysis_csv_safe,
    normalize_analysis_group_by,
    text_mining_counter,
)
from .services.outputs import (
    rgb_to_ass_color,
    safe_output_stem,
    subtitle_text_pages,
    subtitle_text_width,
    write_ass_subtitles,
)
from .services.durable_files import (
    atomic_copy_file,
    atomic_write_text,
    durable_move,
    path_entry_exists,
    path_has_reparse_ancestor,
    path_is_link_or_reparse,
    path_is_within,
    sync_directory_metadata,
    sync_rename_metadata,
    windows_extended_path,
    posix_move_no_replace,
)
from .services import emotion as emotion_analysis
from .services.meeting_minutes import (
    build_meeting_minutes,
    meeting_external_payload,
    meeting_tasks_csv_text,
    normalize_meeting_minutes,
)
from .services.transcription import audio as transcription_audio
from .services.emotion import aist_emotion_model_keys, build_emotion_analysis_summary
from .services.transcription.segments import (
    TRIPLE_PASS_GAP_CONTEXT_SECONDS,
    TRIPLE_PASS_MIN_GAP_SECONDS,
    display_time,
    find_long_asr_gaps,
    make_display_segments,
    merge_supplemental_asr_segments,
    normalize_asr_segments,
    offset_asr_segments_to_gap,
)
from .env_settings import env_enabled, positive_env_int
from .text_utils import clean_single_line, json_load, utc_now_iso
from . import transcript_preparation as preparation
from .services.library_rows import (
    ensure_segment_ids,
    interview_comparison_identity,
    normalize_conversation_speaker_profiles,
    normalize_session_profile,
    row_meeting_minutes,
    row_original_segments,
    row_segments,
    row_session_profile,
    row_speaker_profiles,
)
from .services.transcription.audio import (
    AUDIO_PREPROCESS_PRESETS,
)
from .handlers.form_fields import parse_optional_float
from .services.word_cloud import (
    write_word_cloud,
)
from .web.library_group_routes import register_library_group_routes
from .web.training_routes import register_training_routes
from .web.export_routes import register_export_routes
from .web.analysis_view_routes import register_analysis_view_routes
from .web.ai_routes import register_ai_routes
from .services.machine_profile import (
    detect_machine_profile,
    get_machine_profile,
    recommend_machine_settings,
    system_activity_snapshot,
)
from .services.ai import settings as ai_settings
from .services.ai.settings import (
    AI_MODEL_PROVIDERS,
    TOKEN_FILE_NAME,
    TokenConfig,
    available_ai_models,
    configured_ai_credentials,
    is_colab_runtime,
    lmstudio_base_url,
    lmstudio_connection_status,
    lmstudio_model_id,
    lmstudio_reasoning_settings,
    local_llm_label,
    local_llm_short_label,
)
from .services.ai.client import (
    extract_google_text,
    extract_lmstudio_text,
    extract_openai_text,
    safe_token_count,
)
from .services import speaker_identification
from .services.speaker_identification import (
    apply_speaker_identity_repairs,
    make_speaker_registration,
    normalize_detected_speaker_name,
    speaker_identity_context_records,
)
from .handlers.speaker_identification import make_library_speaker_identification
from .services.analysis_jobs import InsightCancelled
from .services.analysis_jobs import make_insight_jobs
from .services.analysis_jobs import make_insight_commands
from .services.analysis_jobs import make_transformer_jobs
from .services.analysis_jobs import make_transformer_commands
from .services.analysis_archive import make_analysis_archive
from .handlers.segment_classification import make_segment_classification_command
from .services.analysis_pipeline_adapters import (
    run_analysis_pipeline_method,
)
from .services.analysis_pipeline_adapters import make_analysis_pipeline_adapters, make_staged_initial_builder
from .services.library_schema import make_library_schema
from .services.library_store import make_library_store
from .services.output_import import make_output_import
from .services.media_files import (
    is_unc_path,
    is_video_path,
    media_kind,
    safe_media_filename,
)
from .services.media_files import make_media_files
from .web.library_routes import register_library_routes
from .diagnostics import (
    HIDDEN_LOCAL_PATH_MESSAGE,
    public_diagnostic_text,
    sanitize_remote_json_payload,
)
from .web.security import bind_host_is_loopback
from .web.security import make_request_guards, register_request_security
from .runtime_state import RuntimeState
from .services.instance_lock import InstanceLock
from .services.transcription.job_record import JobRecord
from .services.transcription.diarization import (
    DIARIZATION_MODEL,
    configure_huggingface_hub_compatibility,
    configure_speechbrain_lazy_import_compatibility,
    create_diarization_pipeline,
    diarization_access_error_message,
    is_diarization_access_error,
)
from .services.subprocesses import (
    run_cancellable_subprocess,
)
from .services.transcription.vocabulary import (
    normalize_custom_vocabulary,
    whisper_vocabulary_prompt,
)
from .services.transcription.vocabulary import make_custom_vocabulary_store
from .services.transcription.options import (
    ACTIVE_JOB_STATUSES,
    CONVERSATION_MODES,
    JobOptions,
)
from .handlers.transcription_start import make_transcription_start
from .services.library_edits import (
    normalize_edited_segments,
)
from .services.library_edits import make_library_update
from .web.library_deletion import make_library_deletion
from .services.analysis_annotations import make_analysis_annotation_save


os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
warnings.filterwarnings(
    "ignore",
    message=r"\s*torchcodec is not installed correctly.*",
    category=UserWarning,
)

PRODUCT_NAME = "グルモジ"
APP_VERSION = "β0.46.1"
APP_CREATOR = "Re.kloc"
APP_NAME = f"{PRODUCT_NAME} | 話者分離文字起こし"
APP_DIRECTORY = Path(__file__).resolve().parent
PROJECT_DIRECTORY = APP_DIRECTORY.parents[1]
RUNTIME_DIRECTORY = PROJECT_DIRECTORY / "runtime"
AI_HTTP_WORKER_FILE = APP_DIRECTORY / "ai_http_worker.py"
DEFAULT_OUTPUT_DIRECTORY = Path(
    os.environ.get("MOJIOKOSI_OUTPUT_DIR", str(RUNTIME_DIRECTORY / "output"))
).expanduser()
UPLOAD_DIRECTORY = RUNTIME_DIRECTORY / "uploads"
DATA_DIRECTORY = Path(
    os.environ.get("MOJIOKOSI_DATA_DIR", str(RUNTIME_DIRECTORY / "data"))
).expanduser()
MEDIA_DIRECTORY = DATA_DIRECTORY / "media"
THUMBNAIL_DIRECTORY = DATA_DIRECTORY / "thumbnails"
TRAINING_DIRECTORY = DATA_DIRECTORY / "kushinada_training"
TRAINING_AUDIO_DIRECTORY = TRAINING_DIRECTORY / "audio"
TRAINING_JSONL_FILE = TRAINING_DIRECTORY / "corrections.jsonl"
TRAINING_MANIFEST_FILE = TRAINING_DIRECTORY / "manifest.csv"
CUSTOM_VOCABULARY_FILE = DATA_DIRECTORY / "custom_vocabulary.json"
DATABASE_FILE = DATA_DIRECTORY / "library.sqlite3"
INSTANCE_LOCK_FILE = UPLOAD_DIRECTORY / ".gurumoji.instance.lock"
DATA_INSTANCE_LOCK_FILE = DATA_DIRECTORY / ".gurumoji.instance.lock"
TOKEN_FILE = PROJECT_DIRECTORY / "config" / TOKEN_FILE_NAME


MAX_MEDIA_UPLOAD_BYTES = positive_env_int(
    "MOJIOKOSI_MAX_MEDIA_MB", 4096, minimum=1, maximum=1024 * 1024
) * 1024 * 1024
MAX_CSV_UPLOAD_BYTES = positive_env_int(
    "MOJIOKOSI_MAX_CSV_MB", 10, minimum=1, maximum=256
) * 1024 * 1024
MAX_JSON_REQUEST_BYTES = positive_env_int(
    "MOJIOKOSI_MAX_JSON_MB", 32, minimum=1, maximum=512
) * 1024 * 1024
MULTIPART_OVERHEAD_BYTES = 2 * 1024 * 1024
MAX_RETAINED_JOBS = positive_env_int(
    "MOJIOKOSI_MAX_RETAINED_JOBS", 50, minimum=1, maximum=10000
)
JOB_TTL_SECONDS = positive_env_int(
    "MOJIOKOSI_JOB_TTL_SECONDS", 24 * 60 * 60, minimum=60, maximum=30 * 86400
)
ORPHAN_UPLOAD_GRACE_SECONDS = positive_env_int(
    "MOJIOKOSI_ORPHAN_GRACE_SECONDS", 15 * 60, minimum=60, maximum=7 * 86400
)
BACKUP_DIRECTORY = Path(
    os.environ.get("MOJIOKOSI_BACKUP_DIR", str(RUNTIME_DIRECTORY / "backups"))
).expanduser()
REMOTE_ACCESS_ENABLED = env_enabled("MOJIOKOSI_ALLOW_REMOTE")
REMOTE_LOCAL_PATHS_ENABLED = env_enabled("MOJIOKOSI_ENABLE_REMOTE_LOCAL_PATHS")
REMOTE_ACCESS_TOKEN = os.environ.get("MOJIOKOSI_ACCESS_TOKEN", "").strip()
MAX_LOG_LINES = 200
NORMAL_VAD_ONSET = 0.5
NORMAL_VAD_OFFSET = 0.363
NORMAL_NO_SPEECH_THRESHOLD = 0.6
WHISPER_SAMPLE_RATE = 16000


class AnalysisConflictError(RuntimeError):
    pass


(
    trusted_request_hosts,
    local_path_access_allowed,
    remote_auth_valid,
    request_origin_allowed,
) = make_request_guards(
    remote_access_enabled=lambda: REMOTE_ACCESS_ENABLED,
    remote_access_token=lambda: REMOTE_ACCESS_TOKEN,
    remote_local_paths_enabled=lambda: REMOTE_LOCAL_PATHS_ENABLED,
)


def admit_transcription_job():
    """Reserve the single transcription slot before a create_job upload is read."""
    global _job_admission_id
    submission_id = request.headers.get("X-Gurumoji-Submission-Id", "").strip()
    if submission_id and not re.fullmatch(r"[0-9a-f]{32}", submission_id):
        return jsonify({"error": "Invalid transcription submission ID."}), 400
    with jobs_lock:
        prune_jobs_locked()
        existing = jobs.get(submission_id) if submission_id else None
        if existing is not None:
            status_code = 202 if existing.status in ACTIVE_JOB_STATUSES else 200
            return jsonify(existing.public()), status_code
        if _job_admission_id is not None:
            if submission_id and _job_admission_id == submission_id:
                return jsonify(admission_job_public(submission_id)), 202
            return jsonify({"error": "Another transcription job is already active."}), 409
        if any(job.status in ACTIVE_JOB_STATUSES for job in jobs.values()):
            return jsonify({"error": "Another transcription job is already active."}), 409
        _job_admission_id = submission_id or uuid.uuid4().hex
        g.job_admission_id = _job_admission_id
    return None


def release_job_admission() -> None:
    global _job_admission_id
    admission_id = getattr(g, "job_admission_id", None)
    if admission_id:
        with jobs_lock:
            if _job_admission_id == admission_id:
                _job_admission_id = None


# Process-local runtime state (see runtime_state.py). The module-level names
# below are the same objects, kept for existing callers and tests.
runtime = RuntimeState()
jobs = runtime.jobs
jobs_lock = runtime.jobs_lock
library_write_lock = runtime.library_write_lock
insight_jobs_lock = runtime.insight_jobs_lock
insight_cancel_events = runtime.insight_cancel_events
transformer_jobs_lock = runtime.transformer_jobs_lock
transformer_cancel_events = runtime.transformer_cancel_events
training_lock = runtime.training_lock
file_dialog_lock = runtime.file_dialog_lock
custom_vocabulary_lock = runtime.custom_vocabulary_lock
JobRecord.state_lock = jobs_lock
JobRecord.reveal_local_paths = staticmethod(lambda: local_path_access_allowed())
# The submission currently being admitted by the before_request hook. It is
# rebound (not mutated), so it stays a module global that tests can reset.
_job_admission_id: str | None = None


def prune_jobs_locked(now: float | None = None) -> None:
    runtime.prune_jobs_locked(
        now, ttl_seconds=JOB_TTL_SECONDS, max_retained=MAX_RETAINED_JOBS
    )


def cleanup_orphaned_uploads() -> None:
    if not UPLOAD_DIRECTORY.is_dir():
        return
    upload_root = UPLOAD_DIRECTORY.resolve()
    cutoff = time.time() - ORPHAN_UPLOAD_GRACE_SECONDS
    active_job_ids = runtime.active_job_ids(ACTIVE_JOB_STATUSES)
    for candidate in UPLOAD_DIRECTORY.iterdir():
        if not candidate.is_dir() or not re.fullmatch(r"[0-9a-f]{32}", candidate.name):
            continue
        if candidate.name in active_job_ids:
            continue
        try:
            if candidate.stat().st_mtime > cutoff:
                continue
        except OSError:
            continue
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.parent == upload_root:
            shutil.rmtree(resolved, ignore_errors=True)


def instance_lock_paths() -> list[Path]:
    unique: dict[str, Path] = {}
    for path in (INSTANCE_LOCK_FILE, DATA_INSTANCE_LOCK_FILE):
        key = os.path.normcase(str(path.resolve(strict=False)))
        unique.setdefault(key, path)
    return [unique[key] for key in sorted(unique)]


instance_lock = InstanceLock(lambda: instance_lock_paths())


def acquire_instance_lock() -> bool:
    return instance_lock.acquire()


def release_instance_lock() -> None:
    instance_lock.release()


def read_upload_limited(upload: Any, maximum: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = upload.stream.read(min(1024 * 1024, maximum - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > maximum:
            raise RequestEntityTooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


def save_upload_limited(upload: Any, target: Path, maximum: int) -> int:
    total = 0
    try:
        with target.open("xb") as stream:
            while True:
                chunk = upload.stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    raise RequestEntityTooLarge()
                stream.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if total == 0:
        target.unlink(missing_ok=True)
        raise ValueError("The uploaded media file is empty.")
    return total


def copy_file_limited(source: Path, target: Path, maximum: int) -> int:
    total = 0
    try:
        with source.open("rb") as input_stream, target.open("xb") as output_stream:
            while True:
                chunk = input_stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    raise RequestEntityTooLarge()
                output_stream.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if total == 0:
        target.unlink(missing_ok=True)
        raise ValueError("The selected media file is empty.")
    return total


def _vault_nesting_warnings() -> list[str]:
    from .vault_registry import nesting_warnings
    try:
        return nesting_warnings(Path(DATABASE_FILE).parent)
    except OSError:
        return []


def runtime_info() -> dict[str, Any]:
    colab = is_colab_runtime()
    system = platform.system()
    configured_kind = os.environ.get("MOJIOKOSI_RUNTIME", "").strip().lower()
    kind = "colab" if colab else "cloud" if configured_kind == "cloud" else "local"
    default_label = "Colab / Google Drive" if colab else "クラウド実行環境" if kind == "cloud" else "Gurumoji実行環境"
    label = os.environ.get("MOJIOKOSI_RUNTIME_LABEL", "").strip()[:120] or default_label
    native_file_dialog = platform.system() == "Windows" and not colab and not REMOTE_ACCESS_ENABLED
    return {
        "kind": kind,
        "label": label,
        "os": system,
        "source_path_example": "/content/drive/MyDrive/..." if colab else r"C:\audio\recording.wav" if system == "Windows" else "/path/to/recording.wav",
        "qwen_setup_note": "Windowsで scripts\\setup_qwen_stack.bat を実行して準備します。モデルは初回起動時に取得される場合があります。" if system == "Windows" else "現在のQwen独立環境ランチャーはWindows用です。この実行環境の対応状況を確認してください。",
        "colab": colab,
        "native_file_dialog": native_file_dialog,
        "browser_upload": not native_file_dialog,
        "ephemeral_storage": colab and not str(DATA_DIRECTORY).startswith("/content/drive/"),
    }


@contextmanager
def database_connection():
    connection = sqlite3.connect(DATABASE_FILE, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


ensure_output_import_provenance_schema, initialize_library = make_library_schema(
    data_directory=lambda: DATA_DIRECTORY,
    media_directory=lambda: MEDIA_DIRECTORY,
    thumbnail_directory=lambda: THUMBNAIL_DIRECTORY,
    training_audio_directory=lambda: TRAINING_AUDIO_DIRECTORY,
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    repair_output_import_provenance=lambda *args, **kwargs: repair_output_import_provenance(*args, **kwargs),
)


def speaker_registry_snapshot(
    *,
    include_inactive: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    return speaker_registry_store.speaker_registry_snapshot(
        include_inactive=include_inactive, connect=database_connection
    )


def list_speaker_registry(*, include_inactive: bool = True) -> list[dict[str, Any]]:
    return speaker_registry_store.list_speaker_registry(
        include_inactive=include_inactive, connect=database_connection
    )

def save_speaker_registry_records(
    raw_records: Any,
    *,
    delete_ids: Any = None,
    expected_revision: int | None = None,
    merge_by_participant_code: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    return speaker_registry_handler().save(
        raw_records,
        delete_ids=delete_ids,
        expected_revision=expected_revision,
        merge_by_participant_code=merge_by_participant_code,
    )


# Speaker registry composition boundary.
def persist_speaker_registry_record(
    connection: sqlite3.Connection,
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    now: str,
    *, origin: str = "researcher", process: str = "speaker_registry_save",
) -> None:
    speaker_registry_store.persist_speaker_registry_record(
        connection, record, previous, now, origin=origin, process=process
    )


def _save_speaker_registry_records_locked(*args: Any, **kwargs: Any):
    kwargs.setdefault("connect", database_connection)
    return speaker_registry_store._save_speaker_registry_records_locked(*args, **kwargs)


def import_speaker_registry_csv(
    content: bytes,
    *,
    expected_revision: int,
    preview: bool = False,
) -> tuple[list[dict[str, Any]], int, int]:
    return speaker_registry_store.import_speaker_registry_csv(
        content,
        expected_revision=expected_revision,
        max_upload_bytes=MAX_CSV_UPLOAD_BYTES,
        save_records=(lambda *args, **kwargs: speaker_registry_store.preview_speaker_registry_records(
            *args, connect=database_connection, **kwargs
        )) if preview else save_speaker_registry_records,
    )


(
    library_row,
    library_group_name,
    library_public,
    upsert_library_item,
) = make_library_store(
    media_directory=lambda: MEDIA_DIRECTORY,
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    local_path_access_allowed=lambda *args, **kwargs: local_path_access_allowed(*args, **kwargs),
    media_kind=lambda *args, **kwargs: media_kind(*args, **kwargs),
    normalize_ai_usage=lambda *args, **kwargs: normalize_ai_usage(*args, **kwargs),
    row_segments=lambda *args, **kwargs: row_segments(*args, **kwargs),
    row_session_profile=lambda *args, **kwargs: row_session_profile(*args, **kwargs),
    row_speaker_profiles=lambda *args, **kwargs: row_speaker_profiles(*args, **kwargs),
)


(
    stage_media_archive,
    commit_staged_media,
    archive_media,
    remove_owned_directory,
    cleanup_uncommitted_job_artifacts,
    resolve_local_media_path,
    prepare_output_root,
    thumbnail_cache_path,
    generate_word_cloud_thumbnail,
    generate_video_thumbnail,
) = make_media_files(
    default_output_directory=lambda: DEFAULT_OUTPUT_DIRECTORY,
    max_media_upload_bytes=MAX_MEDIA_UPLOAD_BYTES,
    media_directory=lambda: MEDIA_DIRECTORY,
    thumbnail_directory=lambda: THUMBNAIL_DIRECTORY,
    durable_move=lambda *args, **kwargs: durable_move(*args, **kwargs),
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
)


# Edit transaction composition boundary: the module owns the crash-safe swap,
# this layer binds it to the application database.
def edit_storage_id(connection: sqlite3.Connection | None = None) -> str:
    return edit_transactions.edit_storage_id(connection, connect=database_connection)


def edit_journal_secret(connection: sqlite3.Connection | None = None) -> bytes:
    return edit_transactions.edit_journal_secret(connection, connect=database_connection)


def write_edit_preparation_marker(*args: Any, **kwargs: Any) -> Path:
    kwargs.setdefault("connect", database_connection)
    return edit_transactions.write_edit_preparation_marker(*args, **kwargs)


def write_edit_transaction_manifest(*args: Any, **kwargs: Any) -> Path:
    kwargs.setdefault("connect", database_connection)
    return edit_transactions.write_edit_transaction_manifest(*args, **kwargs)


def reconcile_edit_transaction_with_database(
    staging_root: Path,
    payload: dict[str, Any],
) -> list[str]:
    return edit_transactions.reconcile_edit_transaction_with_database(
        staging_root, payload, connect=database_connection
    )


def promote_staged_files(staging_dir: Path, output_dir: Path, staged_files: list[Path]):
    return edit_transactions.promote_staged_files(
        staging_dir, output_dir, staged_files, connect=database_connection
    )


# Group analysis composition boundary: the module computes, this layer supplies
# the library row accessors and the database connection.
def build_research_analysis(analysis):
    from .research_analysis import derived_storage
    from .services.derived_analysis_store import DATABASE
    with derived_storage(DATABASE_FILE.parent / DATABASE):
        return _build_research_analysis(analysis)


def group_analysis_for_row(
    row: sqlite3.Row,
    *,
    include_research_rows: bool = False,
    execute: bool = True,
    defer_research: bool = False,
) -> dict[str, Any]:
    from .research_analysis import derived_storage
    from .services.derived_analysis_store import DATABASE
    with derived_storage(DATABASE_FILE.parent / DATABASE):
        return group_analysis.group_analysis_for_row(
            row,
            include_research_rows=include_research_rows,
            execute=execute,
            defer_research=defer_research,
            connect=database_connection,
            row_segments=row_segments,
            row_original_segments=row_original_segments,
            row_speaker_profiles=row_speaker_profiles,
            row_session_profile=row_session_profile,
            list_speaker_registry=list_speaker_registry,
        )


summarize_codebook_change, _save_group_analysis_locked = make_analysis_annotation_save(
    AnalysisConflictError=AnalysisConflictError,
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    row_segments=lambda *args, **kwargs: row_segments(*args, **kwargs),
)


def save_group_analysis(item_id: str, payload: Any) -> dict[str, Any]:
    with library_write_lock:
        result = _save_group_analysis_locked(item_id, payload)
        refresh_archive_index(item_id)
        return result


(
    canonical_output_import_path,
    record_output_import_provenance,
    existing_output_artifacts,
    machine_json_owner_for_row,
    repair_output_import_provenance,
    import_existing_outputs,
) = make_output_import(
    default_output_directory=lambda: DEFAULT_OUTPUT_DIRECTORY,
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    publish_input_vault=lambda *args, **kwargs: publish_input_vault(*args, **kwargs),
    upsert_library_item=lambda *args, **kwargs: upsert_library_item(*args, **kwargs),
)


load_custom_vocabulary, save_custom_vocabulary, reconcile_custom_vocabulary = make_custom_vocabulary_store(
    custom_vocabulary_file=lambda: CUSTOM_VOCABULARY_FILE,
    custom_vocabulary_lock=custom_vocabulary_lock,
    database_connection=lambda: database_connection(),
)


_audio_processor = transcription_audio.AudioProcessor(
    AUDIO_PREPROCESS_PRESETS, WHISPER_SAMPLE_RATE, run_cancellable_subprocess
)
audio_preprocess_label = _audio_processor.label
audio_preprocess_filters = _audio_processor.filters
run_audio_preprocess = _audio_processor.preprocess
run_audio_interval_preprocess = _audio_processor.preprocess_interval
run_diarization_audio_preprocess = _audio_processor.preprocess_for_diarization


TRANSCRIPT_FINISHING_MODES = transcript_formatting.TRANSCRIPT_FINISHING_MODES
TRANSCRIPT_FORMATTING_VERSION = transcript_formatting.TRANSCRIPT_FORMATTING_VERSION
normalize_transcript_punctuation = transcript_formatting.normalize_transcript_punctuation


def transcript_formatting_result(
    original_segments: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    *,
    mode: str,
    audio_preprocess: str = "none",
    speaker_names: dict[str, str] | None = None,
    speaker_diagnostics: dict[str, Any] | None = None,
    speaker_repair_summary: dict[str, int] | None = None,
    finishing_stages: dict[str, str] | None = None,
    ai_usage: dict[str, Any] | None = None,
    jev_usage: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return transcript_formatting.transcript_formatting_result(
        original_segments, segments, mode=mode, audio_preprocess=audio_preprocess,
        speaker_names=speaker_names, speaker_diagnostics=speaker_diagnostics,
        speaker_repair_summary=speaker_repair_summary, finishing_stages=finishing_stages,
        ai_usage=ai_usage, jev_usage=jev_usage,
        normalize_ai_usage=normalize_ai_usage, safe_token_count=safe_token_count,
        normalize_detected_speaker_name=normalize_detected_speaker_name,
    )


# Transcript output composition boundary.
def manual_output_directory(source_name: str, item_id: str) -> Path:
    return outputs.manual_output_directory(
        source_name, item_id, output_root=DEFAULT_OUTPUT_DIRECTORY
    )


def media_metadata_session_date(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> str:
    return outputs.media_metadata_session_date(
        source_path, check_cancelled,
        run_subprocess=run_cancellable_subprocess, is_video_path=is_video_path,
    )


def session_profile_from_media(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, str]:
    return outputs.session_profile_from_media(
        source_path, check_cancelled,
        run_subprocess=run_cancellable_subprocess, is_video_path=is_video_path,
    )


def probe_video_dimensions(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[int, int]:
    return outputs.probe_video_dimensions(
        source_path, check_cancelled, run_subprocess=run_cancellable_subprocess
    )


def burn_ass_subtitles_into_video(
    source_path: Path,
    ass_path: Path,
    target: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> Path:
    return outputs.burn_ass_subtitles_into_video(
        source_path, ass_path, target, check_cancelled,
        run_subprocess=run_cancellable_subprocess, is_video_path=is_video_path,
    )


def write_subtitled_video_assets(
    source_path: Path,
    source_name: str,
    output_dir: Path,
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Path]:
    return outputs.write_subtitled_video_assets(
        source_path, source_name, output_dir, segments, speaker_names,
        speaker_profiles, check_cancelled,
        run_subprocess=run_cancellable_subprocess, is_video_path=is_video_path,
    )


def write_outputs(*args: Any, **kwargs: Any) -> list[Path]:
    kwargs.setdefault("write_word_cloud", write_word_cloud)
    kwargs.setdefault("emotion_csv_text", emotion_csv_text)
    return outputs.write_outputs(*args, **kwargs)


# AIST emotion analysis composition boundary.
def emotion_csv_text(segments: list[dict[str, Any]], speaker_names: dict[str, str]) -> str:
    return emotion_analysis.emotion_csv_text(
        segments, speaker_names, csv_safe=analysis_csv_safe
    )


def extract_emotion_segment_wavs(
    audio_path: Path,
    segments: list[dict[str, Any]],
    work_dir: Path,
    check_cancelled: Callable[[], None],
) -> tuple[Path, list[dict[str, Any]]]:
    return emotion_analysis.extract_emotion_segment_wavs(
        audio_path, segments, work_dir, check_cancelled,
        run_subprocess=run_cancellable_subprocess,
    )


def run_aist_emotion_analysis(
    audio_path: Path,
    segments: list[dict[str, Any]],
    model_choice: str,
    hf_token: str,
    device: str,
    work_dir: Path,
    status: Callable[[str], None],
    check_cancelled: Callable[[], None],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return emotion_analysis.run_aist_emotion_analysis(
        audio_path, segments, model_choice, hf_token, device, work_dir, status,
        check_cancelled,
        runtime_directory=RUNTIME_DIRECTORY,
        run_subprocess=run_cancellable_subprocess,
    )


def load_token_config(path: Path = TOKEN_FILE) -> TokenConfig:
    """Read all credentials from tokens.json; credentials are never accepted by the UI."""
    return ai_settings.load_token_config(path)


def update_token_model(provider: str, model: str, path: Path = TOKEN_FILE) -> TokenConfig:
    return ai_settings.update_token_model(provider, model, path)


def post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int = 240,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
    return ai_client.post_json(
        url, headers, payload, worker_file=AI_HTTP_WORKER_FILE,
        run_subprocess=run_cancellable_subprocess, timeout=timeout,
        check_cancelled=check_cancelled,
    )


def normalize_ai_usage(value: Any) -> dict[str, Any]:
    return ai_client.normalize_ai_usage(value, AI_MODEL_PROVIDERS)


def merge_ai_usage(current_value: Any, sample_value: Any) -> dict[str, Any]:
    return ai_client.merge_ai_usage(current_value, sample_value, AI_MODEL_PROVIDERS)


def call_ai_json(
    provider: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
    check_cancelled: Callable[[], None] | None = None,
    usage_callback: Callable[[dict[str, Any]], None] | None = None,
    base_url: str = "",
    ai_efforts: dict | None = None,
) -> dict[str, Any]:
    return ai_client.call_ai_json(
        provider, api_key, model, system_prompt, user_prompt, schema_name, schema,
        post=post_json, lmstudio_base=lmstudio_base_url,
        lmstudio_model_id=lmstudio_model_id,
        lmstudio_reasoning=lmstudio_reasoning_settings,
        extract_openai=extract_openai_text, extract_google=extract_google_text,
        extract_lmstudio=extract_lmstudio_text,
        providers=AI_MODEL_PROVIDERS, check_cancelled=check_cancelled,
        usage_callback=usage_callback, base_url=base_url, ai_efforts=ai_efforts,
    )


def detect_speaker_names_with_ai(*args: Any, **kwargs: Any) -> dict[str, str]:
    return speaker_identification.detect_speaker_names_with_ai(
        *args, call_ai_json=call_ai_json, **kwargs
    )


link_detected_speakers_to_registry, register_detected_speakers = make_speaker_registration(
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    library_write_lock=library_write_lock,
    list_speaker_registry=lambda *args, **kwargs: list_speaker_registry(*args, **kwargs),
    persist_speaker_registry_record=lambda *args, **kwargs: persist_speaker_registry_record(*args, **kwargs),
)


# The composition boundary passes dependencies into the Flask-free service.
def clean_segments_with_ai(
    segments: list[dict[str, Any]], provider: str, api_key: str, model: str,
    status: Callable[[str], None], check_cancelled: Callable[[], None],
    usage_callback: Callable[[dict[str, Any]], None] | None = None, base_url: str = "",
    outline: dict[str, Any] | None = None, ai_efforts: dict | None = None,
) -> list[dict[str, Any]]:
    return ai_transcript_finishing.clean(
        segments, provider, api_key, model, status, check_cancelled,
        call_json=call_ai_json, finish=finish_clean_transcript,
        usage_callback=usage_callback, base_url=base_url, outline=outline,
        ai_efforts=ai_efforts,
    )


def review_segments_with_jev(
    segments: list[dict[str, Any]], api_key: str, model: str,
    status: Callable[[str], None], check_cancelled: Callable[[], None],
    outline: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    return ai_transcript_finishing.review_with_jev(
        segments, api_key, model, status, check_cancelled,
        clean_single_line=clean_single_line, default_model=JEV_DEFAULT_MODEL,
        post=post_json, review=review_transcript_with_jev, outline=outline,
    )


def clean_recommended_segments_with_ai(
    segments: list[dict[str, Any]], reviews: dict[str, dict[str, Any]],
    provider: str, api_key: str, model: str, status: Callable[[str], None],
    check_cancelled: Callable[[], None],
    usage_callback: Callable[[dict[str, Any]], None] | None = None,
    base_url: str = "", ai_efforts: dict | None = None, effort: str = "medium",
    outline: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return ai_transcript_finishing.repair_recommended(
        segments, reviews, provider, api_key, model, status, check_cancelled,
        call_json=call_ai_json, repair=finish_repair_recommended_segments,
        usage_callback=usage_callback, base_url=base_url, ai_efforts=ai_efforts,
        effort=effort, outline=outline,
    )


def classify_segments_with_jev(
    segments: list[dict[str, Any]], topics: list[dict[str, str]], api_key: str,
    model: str, status: Callable[[str], None] = lambda _message: None,
    check_cancelled: Callable[[], None] = lambda: None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    return ai_transcript_finishing.classify_with_jev(
        segments, topics, api_key, model, clean_single_line=clean_single_line,
        default_model=JEV_DEFAULT_MODEL, post=post_json, classify=classify_with_jev,
        status=status, check_cancelled=check_cancelled,
    )


def create_outline_with_ai(
    segments: list[dict[str, Any]], speaker_names: dict[str, str],
    provider: str, api_key: str, model: str, status: Callable[[str], None],
    check_cancelled: Callable[[], None],
    usage_callback: Callable[[dict[str, Any]], None] | None = None, base_url: str = "",
    ai_efforts: dict | None = None,
) -> dict[str, Any]:
    return ai_transcript_finishing.create_outline(
        segments, speaker_names, provider, api_key, model, status, check_cancelled,
        call_json=call_ai_json, create=finish_create_outline, now_iso=utc_now_iso,
        usage_callback=usage_callback, base_url=base_url, ai_efforts=ai_efforts,
    )


def update_job(job: JobRecord, **changes: Any) -> None:
    runtime.update_job(job, max_log_lines=MAX_LOG_LINES, **changes)


def run_transcription_job(job: JobRecord, options: JobOptions) -> None:
    dependencies = {
        "unify_notation": unify_notation,
        "CONVERSATION_MODES": CONVERSATION_MODES,
        "DIARIZATION_MODEL": DIARIZATION_MODEL,
        "MAX_LOG_LINES": MAX_LOG_LINES,
        "NORMAL_NO_SPEECH_THRESHOLD": NORMAL_NO_SPEECH_THRESHOLD,
        "NORMAL_VAD_OFFSET": NORMAL_VAD_OFFSET,
        "NORMAL_VAD_ONSET": NORMAL_VAD_ONSET,
        "TRIPLE_PASS_GAP_CONTEXT_SECONDS": TRIPLE_PASS_GAP_CONTEXT_SECONDS,
        "TRIPLE_PASS_MIN_GAP_SECONDS": TRIPLE_PASS_MIN_GAP_SECONDS,
        "TranscriptionReporter": TranscriptionReporter,
        "UPLOAD_DIRECTORY": UPLOAD_DIRECTORY,
        "WHISPER_SAMPLE_RATE": WHISPER_SAMPLE_RATE,
        "aist_emotion_model_keys": aist_emotion_model_keys,
        "apply_speaker_identity_repairs": apply_speaker_identity_repairs,
        "attach_jev_comparison": attach_jev_comparison,
        "audio_preprocess_label": audio_preprocess_label,
        "build_emotion_analysis_summary": build_emotion_analysis_summary,
        "build_meeting_minutes": build_meeting_minutes,
        "clean_recommended_segments_with_ai": clean_recommended_segments_with_ai,
        "clean_segments_with_ai": clean_segments_with_ai,
        "cleanup_uncommitted_job_artifacts": cleanup_uncommitted_job_artifacts,
        "commit_staged_media": commit_staged_media,
        "configure_huggingface_hub_compatibility": configure_huggingface_hub_compatibility,
        "configure_speechbrain_lazy_import_compatibility": configure_speechbrain_lazy_import_compatibility,
        "create_diarization_pipeline": create_diarization_pipeline,
        "create_outline_with_ai": create_outline_with_ai,
        "detect_speaker_names_with_ai": detect_speaker_names_with_ai,
        "diarization_access_error_message": diarization_access_error_message,
        "display_time": display_time,
        "ensure_segment_ids": ensure_segment_ids,
        "find_long_asr_gaps": find_long_asr_gaps,
        "is_diarization_access_error": is_diarization_access_error,
        "is_video_path": is_video_path,
        "jobs_lock": jobs_lock,
        "json_load": json_load,
        "make_display_segments": make_display_segments,
        "merge_ai_usage": merge_ai_usage,
        "merge_supplemental_asr_segments": merge_supplemental_asr_segments,
        "normalize_ai_usage": normalize_ai_usage,
        "normalize_asr_segments": normalize_asr_segments,
        "normalize_conversation_speaker_profiles": normalize_conversation_speaker_profiles,
        "normalize_meeting_minutes": normalize_meeting_minutes,
        "obsidian_workbench": obsidian_workbench,
        "offset_asr_segments_to_gap": offset_asr_segments_to_gap,
        "path_entry_exists": path_entry_exists,
        "publish_input_vault": publish_input_vault,
        "publish_meeting_minutes_to_obsidian": publish_meeting_minutes_to_obsidian,
        "register_detected_speakers": register_detected_speakers,
        "review_segments_with_jev": review_segments_with_jev,
        "row_segments": row_segments,
        "row_session_profile": row_session_profile,
        "row_speaker_profiles": row_speaker_profiles,
        "run_aist_emotion_analysis": run_aist_emotion_analysis,
        "run_audio_interval_preprocess": run_audio_interval_preprocess,
        "run_audio_preprocess": run_audio_preprocess,
        "run_diarization_audio_preprocess": run_diarization_audio_preprocess,
        "safe_output_stem": safe_output_stem,
        "safe_token_count": safe_token_count,
        "session_profile_from_media": session_profile_from_media,
        "stage_media_archive": stage_media_archive,
        "transcript_formatting_result": transcript_formatting_result,
        "update_job": update_job,
        "upsert_library_item": upsert_library_item,
        "whisper_vault_settings": whisper_vault_settings,
        "whisper_vocabulary_prompt": whisper_vocabulary_prompt,
        "write_outputs": write_outputs,
        "write_subtitled_video_assets": write_subtitled_video_assets,
    }
    transcription_job_runner.run_transcription_job(job, options, dependencies)


# Kushinada training corpus composition boundary.
def _training_store() -> training_corpus.TrainingStore:
    # Built per call: the corpus paths are module-level configuration that
    # tests and alternate data directories rebind after import.
    return training_corpus.TrainingStore(
        directory=TRAINING_DIRECTORY,
        audio_directory=TRAINING_AUDIO_DIRECTORY,
        jsonl_file=TRAINING_JSONL_FILE,
        manifest_file=TRAINING_MANIFEST_FILE,
        lock=training_lock,
        connect=lambda: database_connection(),
        logger=app.logger,
    )


def extract_training_clip(
    media_path: Path | None, item_id: str, event_id: str, segment: dict[str, Any]
) -> Path | None:
    return training_corpus.extract_training_clip(
        media_path, item_id, event_id, segment, store=_training_store()
    )


def write_training_exports(events: list[dict[str, Any]]) -> None:
    training_corpus.write_training_exports(events, store=_training_store())


def legacy_training_events() -> list[dict[str, Any]]:
    return training_corpus.legacy_training_events(store=_training_store())


def cleanup_unreferenced_training_clips(events: list[dict[str, Any]]) -> None:
    training_corpus.cleanup_unreferenced_training_clips(events, store=_training_store())


def repair_training_artifacts() -> None:
    training_corpus.repair_training_artifacts(store=_training_store())


def refresh_training_exports() -> list[dict[str, Any]]:
    return training_corpus.refresh_training_exports(store=_training_store())


def prepare_training_corrections(*args: Any, **kwargs: Any):
    kwargs.setdefault("store", _training_store())
    return training_corpus.prepare_training_corrections(*args, **kwargs)


def record_training_corrections(*args: Any, **kwargs: Any) -> int:
    kwargs.setdefault("store", _training_store())
    return training_corpus.record_training_corrections(*args, **kwargs)

def update_library_from_payload(item_id: str, payload: Any) -> dict[str, Any]:
    return analysis_commands().update_item(item_id, payload)


def vault_registry():
    from .vault_registry import VaultRegistry
    return VaultRegistry(DATABASE_FILE, PROJECT_DIRECTORY / "docs" / "program-vault")


def vault_publications() -> VaultPublicationService:
    return VaultPublicationService(
        registry=vault_registry,
        database_connection=database_connection,
        preparation_view=preparation.view,
        row_segments=row_segments,
        row_session_profile=row_session_profile,
        database_error=sqlite3.Error,
        warn=lambda message, exc: app.logger.warning("%s: %s", message, exc),
        research_layout=research_layout,
    )


def research_layout():
    from .obsidian_layout import ObsidianLayout
    return ObsidianLayout(DATABASE_FILE)


def publish_input_vault(row, whisper: dict[str, Any] | None = None, *, source_kind: str | None = None) -> None:
    vault_publications().publish_input(row, whisper, source_kind=source_kind)


def retire_input_vault(item_id: str) -> None:
    vault_publications().retire_input(item_id)


def whisper_vault_settings(options: JobOptions, language: str | None) -> dict[str, Any]:
    diarization_model = (
        "nvidia/Nemotron-3-Diarization"
        if getattr(options, "transcription_backend", "whisperx") == "qwen3_nemotron"
        else DIARIZATION_MODEL
    )
    return whisper_settings(options, language, diarization_model=diarization_model)


_update_library_from_payload_locked = make_library_update(
    default_output_directory=lambda: DEFAULT_OUTPUT_DIRECTORY,
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    durable_move=lambda *args, **kwargs: durable_move(*args, **kwargs),
    edit_journal_secret=lambda *args, **kwargs: edit_journal_secret(*args, **kwargs),
    edit_storage_id=lambda *args, **kwargs: edit_storage_id(*args, **kwargs),
    insert_training_events=lambda *args, **kwargs: insert_training_events(*args, **kwargs),
    jobs=jobs,
    jobs_lock=jobs_lock,
    library_public=lambda *args, **kwargs: library_public(*args, **kwargs),
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    manual_output_directory=lambda *args, **kwargs: manual_output_directory(*args, **kwargs),
    prepare_training_corrections=lambda *args, **kwargs: prepare_training_corrections(*args, **kwargs),
    promote_staged_files=lambda *args, **kwargs: promote_staged_files(*args, **kwargs),
    reconcile_edit_transactions_before_mutation=lambda *args, **kwargs: reconcile_edit_transactions_before_mutation(*args, **kwargs),
    record_output_import_provenance=lambda *args, **kwargs: record_output_import_provenance(*args, **kwargs),
    row_segments=lambda *args, **kwargs: row_segments(*args, **kwargs),
    row_session_profile=lambda *args, **kwargs: row_session_profile(*args, **kwargs),
    training_events_from_connection=lambda *args, **kwargs: training_events_from_connection(*args, **kwargs),
    training_lock=training_lock,
    upsert_library_item=lambda *args, **kwargs: upsert_library_item(*args, **kwargs),
    write_edit_preparation_marker=lambda *args, **kwargs: write_edit_preparation_marker(*args, **kwargs),
    write_edit_transaction_manifest=lambda *args, **kwargs: write_edit_transaction_manifest(*args, **kwargs),
    write_outputs=lambda *args, **kwargs: write_outputs(*args, **kwargs),
    write_subtitled_video_assets=lambda *args, **kwargs: write_subtitled_video_assets(*args, **kwargs),
    write_training_exports=lambda *args, **kwargs: write_training_exports(*args, **kwargs),
)


def trash_directory() -> Path:
    # Beside the database, like analysis_store, so a relocated library keeps its trash.
    return Path(DATABASE_FILE).parent / "trash"


def trash_retention_days() -> int:
    return library_trash.retention_days(
        os.environ.get("MOJIOKOSI_TRASH_RETENTION_DAYS", str(library_trash.DEFAULT_RETENTION_DAYS)))


def _trash_move(source: Path, target: Path) -> None:
    durable_move(source, target, replace_existing=False)


def recover_delete_quarantines() -> list[str]:
    def row_exists(item_id: str) -> bool:
        with database_connection() as connection:
            return connection.execute("SELECT 1 FROM library_items WHERE id=?", (item_id,)).fetchone() is not None

    # Committed deletes reach the trash first; the quarantine recovery then sees nothing left.
    warnings = library_trash.recover_pending(trash_directory(), row_exists=row_exists, move=_trash_move)
    warnings += edit_transactions.recover_delete_quarantines(
        connect=database_connection,
        media_directory=MEDIA_DIRECTORY,
        thumbnail_directory=THUMBNAIL_DIRECTORY,
    )
    for entry_id in library_trash.purge_expired(trash_directory(), trash_retention_days()):
        app.logger.info("保持期間を過ぎたゴミ箱の項目を完全に削除しました: %s", entry_id)
    return warnings


def list_library_trash() -> dict[str, Any]:
    days = trash_retention_days()
    entries = library_trash.list_entries(trash_directory(), days)
    return {"entries": entries, "retention_days": days, "total_bytes": sum(e["bytes"] for e in entries)}


def restore_library_trash(entry_id: str) -> str:
    item_id = library_trash.restore(
        trash_directory(), entry_id, connect=database_connection,
        targets={"media": MEDIA_DIRECTORY, "thumbnail": THUMBNAIL_DIRECTORY}, move=_trash_move)
    # Clears the ResearchVault deletion mark and republishes the InputVault ledger.
    publish_input_vault(library_row(item_id))
    return item_id


def purge_library_trash(entry_id: str) -> None:
    library_trash.purge(trash_directory(), entry_id)


def create_data_backup(include_media: bool = False) -> dict[str, Any]:
    """Back up the data directory while every Vault and library writer is paused (DATA-03)."""
    from .analysis_store import STORE_LOCK
    from .obsidian_layout import LAYOUT_LOCK
    from .vault_registry import VAULT_LOCK
    # Same order as the writers take them: library -> store -> layout -> generated Vaults.
    with library_write_lock, STORE_LOCK, LAYOUT_LOCK, VAULT_LOCK:
        return data_backup.create_backup(
            DATABASE_FILE.parent, BACKUP_DIRECTORY, include_media=include_media, app_version=APP_VERSION,
        )


def discover_edit_transaction_staging_dirs(
    *,
    additional_output_roots: list[Path] | None = None,
    include_database_outputs: bool = True,
) -> list[Path]:
    return edit_transactions.discover_edit_transaction_staging_dirs(
        additional_output_roots=additional_output_roots,
        include_database_outputs=include_database_outputs,
        connect=database_connection,
        output_root=DEFAULT_OUTPUT_DIRECTORY,
    )


def recover_edit_transactions() -> list[str]:
    return edit_transactions.recover_edit_transactions(
        connect=database_connection, output_root=DEFAULT_OUTPUT_DIRECTORY
    )


def reconcile_edit_transactions_before_mutation(
    item_id: str,
    library_item: sqlite3.Row,
) -> tuple[list[str], list[Path]]:
    return edit_transactions.reconcile_edit_transactions_before_mutation(
        item_id, library_item,
        connect=database_connection, output_root=DEFAULT_OUTPUT_DIRECTORY,
    )


def reconcile_edit_transactions_before_delete(
    item_id: str,
    library_item: sqlite3.Row,
) -> tuple[list[str], list[Path]]:
    return edit_transactions.reconcile_edit_transactions_before_delete(
        item_id, library_item,
        connect=database_connection, output_root=DEFAULT_OUTPUT_DIRECTORY,
    )

def initialize_application() -> None:
    application_lifecycle().initialize()


comparison_rate = interview_comparison.comparison_rate


def build_interview_comparison(
    rows: list[sqlite3.Row], *, allow_different_content: bool,
) -> dict[str, Any]:
    return interview_comparison.build_interview_comparison(
        rows, allow_different_content=allow_different_content,
        row_session_profile=row_session_profile,
        interview_comparison_identity=interview_comparison_identity,
        group_analysis_for_row=group_analysis_for_row,
        text_mining_counter=text_mining_counter,
    )


def interview_comparison_request(payload: Any) -> tuple[list[sqlite3.Row], bool]:
    """Validate a 2-8 interview selection and read the rows in the selected order."""
    if isinstance(payload, dict) and payload.get('data_group_id'):
        from .services import data_catalog
        with database_connection() as connection:
            try:
                ids = data_catalog.members(connection, payload['data_group_id'])
            except LookupError as exc:
                raise ComparisonRequestError(str(exc), 404) from exc
        if payload.get('item_ids') and sorted(set(payload['item_ids'])) != ids:
            raise ComparisonRequestError("グループの対象集合が変わっています。再集計してください。", 409)
        payload = {**payload, 'item_ids': ids}
    if not isinstance(payload, dict) or not isinstance(payload.get("item_ids"), list):
        raise ComparisonRequestError("比較するインタビューを指定してください。")
    item_ids: list[str] = []
    for value in payload["item_ids"]:
        item_id = str(value or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item_id):
            raise ComparisonRequestError("比較対象のIDが正しくありません。")
        if item_id not in item_ids:
            item_ids.append(item_id)
    if not 2 <= len(item_ids) <= 8:
        raise ComparisonRequestError("比較するインタビューは2〜8件選択してください。")
    allow_different = payload.get("allow_different_content", False)
    if not isinstance(allow_different, bool):
        raise ComparisonRequestError("内容が異なる比較の指定が正しくありません。")
    with database_connection() as connection:
        placeholders = ",".join("?" for _ in item_ids)
        fetched = connection.execute(
            f"SELECT * FROM library_items WHERE id IN ({placeholders})", item_ids
        ).fetchall()
    by_id = {str(row["id"]): row for row in fetched}
    if any(item_id not in by_id for item_id in item_ids):
        raise ComparisonRequestError("比較対象のデータが見つかりません。", 404)
    return [by_id[item_id] for item_id in item_ids], allow_different


identify_library_speakers = make_library_speaker_identification(
    _update_library_from_payload_locked=lambda *args, **kwargs: _update_library_from_payload_locked(*args, **kwargs),
    configured_ai_credentials=lambda *args, **kwargs: configured_ai_credentials(*args, **kwargs),
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    detect_speaker_names_with_ai=lambda *args, **kwargs: detect_speaker_names_with_ai(*args, **kwargs),
    library_public=lambda *args, **kwargs: library_public(*args, **kwargs),
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    library_write_lock=library_write_lock,
    load_token_config=lambda *args, **kwargs: load_token_config(*args, **kwargs),
    merge_ai_usage=lambda *args, **kwargs: merge_ai_usage(*args, **kwargs),
    public_diagnostic_text=lambda *args, **kwargs: public_diagnostic_text(*args, **kwargs),
    publish_input_vault=lambda *args, **kwargs: publish_input_vault(*args, **kwargs),
    refresh_archive_index=lambda *args, **kwargs: refresh_archive_index(*args, **kwargs),
    register_detected_speakers=lambda *args, **kwargs: register_detected_speakers(*args, **kwargs),
    row_segments=lambda *args, **kwargs: row_segments(*args, **kwargs),
    row_session_profile=lambda *args, **kwargs: row_session_profile(*args, **kwargs),
    row_speaker_profiles=lambda *args, **kwargs: row_speaker_profiles(*args, **kwargs),
)


def obsidian_workbench() -> ObsidianWorkbench:
    return ObsidianWorkbench(DATABASE_FILE)


def notation_workflows():
    from .services.notation_workflows import NotationWorkflows
    return NotationWorkflows(SimpleNamespace(
        database_connection=database_connection, library_row=library_row,
        row_segments=row_segments, load_token_config=load_token_config,
        configured_ai_credentials=configured_ai_credentials, call_ai_json=call_ai_json,
        merge_ai_usage=merge_ai_usage, library_write_lock=library_write_lock,
        update_library_item_locked=_update_library_from_payload_locked,
        archive_ai_finishing=archive_ai_finishing,
        save_custom_vocabulary=save_custom_vocabulary, load_custom_vocabulary=load_custom_vocabulary))


def unify_notation(*args, **kwargs):
    return notation_workflows().finish(*args, **kwargs)


def obsidian_workflows() -> ObsidianWorkflowService:
    """Build explicit dependencies for researcher-owned workbench operations."""
    return ObsidianWorkflowService(SimpleNamespace(
        sqlite_error=sqlite3.Error,
        workbench=obsidian_workbench,
        library_row=library_row,
        row_session_profile=row_session_profile,
        row_meeting_minutes=row_meeting_minutes,
        row_segments=row_segments,
        meeting_external_payload=meeting_external_payload,
        meeting_tasks_csv_text=meeting_tasks_csv_text,
        normalize_meeting_minutes=normalize_meeting_minutes,
        library_write_lock=library_write_lock,
        row_speaker_profiles=row_speaker_profiles,
        update_library_item_locked=_update_library_from_payload_locked,
        merge_ai_usage=merge_ai_usage,
        json_load=json_load,
        publish_input_vault=publish_input_vault,
        archive_ai_finishing=archive_ai_finishing,
        load_token_config=load_token_config,
        configured_ai_credentials=configured_ai_credentials,
        create_outline_with_ai=create_outline_with_ai,
        clean_segments_with_ai=clean_segments_with_ai,
        unify_notation=unify_notation,
        review_segments_with_jev=review_segments_with_jev,
        attach_jev_comparison=attach_jev_comparison,
        detect_speaker_names_with_ai=detect_speaker_names_with_ai,
        apply_speaker_identity_repairs=apply_speaker_identity_repairs,
    ))


def meeting_minutes_fingerprint(minutes: dict[str, Any]) -> str:
    return obsidian_workflows().meeting_minutes_fingerprint(minutes)


def publish_meeting_minutes_to_obsidian(row: sqlite3.Row) -> dict[str, Any]:
    return obsidian_workflows().publish_meeting_minutes(row)


def run_obsidian_finishing(action: str, state: dict, segments: list[dict],
                           context: dict, provider: str, check: Callable) -> dict:
    return obsidian_workflows().run_finishing(action, state, segments, context, provider, check)


obsidian_watcher_status = WatcherStatus()


def _spawn_obsidian_watcher() -> tuple[threading.Event, threading.Thread]:
    from .obsidian_migration import migrate
    return ObsidianWatcher(
        workbench=obsidian_workbench,
        engine=run_obsidian_finishing,
        migrate=lambda database: migrate(database, backup_root=BACKUP_DIRECTORY),
        log_exception=app.logger.exception,
        status=obsidian_watcher_status,
    ).start()


media_metadata_backfill = media_assets.Backfill(lambda: database_connection(), library_write_lock)


def library_storage_diagnostics() -> dict[str, Any]:
    """Explicit diagnostic read; never creates a DB, repairs rows or launches a probe."""
    if not DATABASE_FILE.is_file():
        return {"status": "not_initialized"}
    try:
        with closing(sqlite3.connect(DATABASE_FILE.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            from .services import data_catalog
            result = conversation_projection.check(connection)
            result['attributes'] = data_catalog.check(connection)
            result['ok'] = result['ok'] and result['attributes']['ok']
            return result
    except sqlite3.Error:
        return {"status": "unavailable", "ok": False}


_application_lifecycle: ApplicationLifecycle | None = None


def application_lifecycle() -> ApplicationLifecycle:
    global _application_lifecycle
    if _application_lifecycle is None:
        def initialize_runtime_library() -> None:
            # Called only after the application instance lock is acquired.
            # Routine schema checks and read requests never interrupt live work.
            initialize_library(repair_provenance=False)
            try:
                reconcile_custom_vocabulary()
            except (OSError, ValueError):
                app.logger.warning("登録語の写しを照合できませんでした。DBと既存ファイルを保持しています。")
            with database_connection() as connection:
                recover_orchestration_runs(connection)
                recover_orchestration_publications(connection)

        def repair_provenance() -> None:
            with database_connection() as connection:
                repair_output_import_provenance(connection)

        _application_lifecycle = ApplicationLifecycle(
            acquire_instance_lock=lambda: acquire_instance_lock(),
            release_instance_lock=lambda: release_instance_lock(),
            initialize_library=initialize_runtime_library,
            recover_edits=lambda: recover_edit_transactions(),
            repair_provenance=repair_provenance,
            recover_deletes=lambda: recover_delete_quarantines(),
            repair_training=lambda: repair_training_artifacts(),
            cleanup_uploads=lambda: cleanup_orphaned_uploads(),
            import_outputs=lambda: import_existing_outputs(),
            report_edit_warning=lambda warning: print(
                f"Edit recovery warning: {warning}", file=sys.stderr
            ),
            report_delete_warning=lambda warning: print(
                f"Delete recovery warning: {warning}", file=sys.stderr
            ),
            spawn_watcher=lambda: _spawn_obsidian_watcher(),
            spawn_media_worker=lambda: media_metadata_backfill.start(),
        )
    return _application_lifecycle


def start_obsidian_watcher() -> tuple[threading.Event, threading.Thread]:
    return application_lifecycle().start_watcher()


def analysis_archive_store() -> AnalysisStore:
    return AnalysisStore(DATABASE_FILE, database_connection)


(
    archive_source_stamp,
    archive_snapshot,
    archive_group_analysis,
    archive_segment_classification,
    archive_ai_finishing,
    archive_app_url,
    archive_meeting_minutes,
    interview_comparison_datasets,
    archive_interview_comparison,
    refresh_archive_index,
) = make_analysis_archive(
    analysis_archive_store=lambda *args, **kwargs: analysis_archive_store(*args, **kwargs),
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    row_segments=lambda *args, **kwargs: row_segments(*args, **kwargs),
    row_session_profile=lambda *args, **kwargs: row_session_profile(*args, **kwargs),
)


def analysis_queries() -> AnalysisQueries:
    """Build request-time query dependencies so patched settings stay effective."""
    return AnalysisQueries(
        store=analysis_archive_store(),
        find_item=library_row,
        source_fingerprint=archive_source_stamp,
        database_connection=database_connection,
        build_analysis=group_analysis_for_row,
        public_insight_request=public_insight_request,
        public_transformer_request=public_transformer_request,
        expose_local_paths=local_path_access_allowed(),
    )


build_analysis_pipeline_snapshot, advise_analysis_plan = make_analysis_pipeline_adapters(
    archive_snapshot=lambda *args, **kwargs: archive_snapshot(*args, **kwargs),
    archive_source_stamp=lambda *args, **kwargs: archive_source_stamp(*args, **kwargs),
    call_ai_json=lambda *args, **kwargs: call_ai_json(*args, **kwargs),
    configured_ai_credentials=lambda *args, **kwargs: configured_ai_credentials(*args, **kwargs),
    encode_transformer_texts=lambda *args, **kwargs: encode_transformer_texts(*args, **kwargs),
    group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
    load_token_config=lambda *args, **kwargs: load_token_config(*args, **kwargs),
)


def build_analysis_orchestration_snapshot(row):
    return build_analysis_pipeline_snapshot(row, schema_version=1)


def analysis_pipeline_service() -> AnalysisPipelineService:
    store = analysis_archive_store()

    def public_run(value: dict[str, Any]) -> dict[str, Any]:
        row = store.get(str(value.get("id") or ""))
        if row is None:
            raise LookupError("保存結果が見つかりません。")
        return store.public(row, local=local_path_access_allowed())

    return AnalysisPipelineService(
        connect=database_connection,
        find_item=library_row,
        source_fingerprint=archive_source_stamp,
        snapshot_builder=build_analysis_pipeline_snapshot,
        method_runner=run_analysis_pipeline_method,
        save_result=store.save,
        publish_result=lambda run_id, **kwargs: store.publish(run_id, reuse_completed=True, **kwargs),
        publication_outcomes=store.publication_outcomes,
        public_run=public_run,
        runtime_key=str(DATABASE_FILE.resolve()),
        plan_advisor=advise_analysis_plan,
    )


def call_orchestration_ai_json(
    provider, api_key, model, system_prompt, user_prompt, schema_name, schema,
    check_cancelled=None, usage_callback=None, base_url="", timeout_seconds=240,
    max_output_tokens=None, data_messages=None,
):
    """One transport dispatch per Handler task; retries must be ledgered.

    Other existing AI workflows retain their normal transient HTTP retry policy.
    An ambiguous response in this loop must never silently consume a second call.
    """
    def post_once(url, headers, payload, **kwargs):
        return ai_client.post_json(
            url, headers, payload, worker_file=AI_HTTP_WORKER_FILE,
            run_subprocess=run_cancellable_subprocess, retry_delays=(),
            timeout=timeout_seconds, **kwargs,
        )
    return ai_client.call_ai_json(
        provider, api_key, model, system_prompt, user_prompt, schema_name, schema,
        post=post_once, lmstudio_base=lmstudio_base_url,
        lmstudio_model_id=lmstudio_model_id,
        lmstudio_reasoning=lmstudio_reasoning_settings,
        extract_openai=extract_openai_text, extract_google=extract_google_text,
        extract_lmstudio=extract_lmstudio_text,
        providers=AI_MODEL_PROVIDERS, check_cancelled=check_cancelled,
        usage_callback=usage_callback, base_url=base_url,
        max_output_tokens=max_output_tokens,
        data_messages=data_messages,
    )


prepare_orchestration, run_orchestration_agent = make_orchestration_adapters(
    call_ai_json=lambda *args, **kwargs: call_orchestration_ai_json(*args, **kwargs),
    load_token_config=lambda: load_token_config(),
    configured_ai_credentials=lambda *args: configured_ai_credentials(*args),
)

_orchestration_services: dict[str, AnalysisOrchestrationService] = {}
_orchestration_publication_services: dict[str, AnalysisOrchestrationPublicationService] = {}
_orchestration_service_lock = threading.RLock()


def orchestration_source_guard(connection, item_id: str, expected_hash: str):
    row = connection.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
    if row is None:
        raise LookupError("対象の会話が削除されています。")
    if archive_source_stamp(row, connection=connection) != expected_hash:
        raise AnalysisContractError("元データが更新されています。固定成果物は残し、Vault公開を停止します。", code="revision_conflict")
    return dict(row)


def analysis_orchestration_service() -> AnalysisOrchestrationService:
    # Preserve process-local worker ownership across read/cancel/resume requests.
    # SQLite remains authoritative; this cache does not survive process restart.
    key = str(DATABASE_FILE.resolve())
    with _orchestration_service_lock:
        if key not in _orchestration_services:
            _orchestration_services[key] = AnalysisOrchestrationService(
                connect=lambda: database_connection(),
                find_item=lambda item_id: library_row(item_id),
                source_fingerprint=lambda row: archive_source_stamp(row),
                snapshot_builder=lambda row: build_analysis_orchestration_snapshot(row),
                initial_builder=make_staged_initial_builder(
                    derived_database=lambda: DATABASE_FILE.parent / "analysis-derived.sqlite3",
                    archive_snapshot=lambda *args, **kwargs: archive_snapshot(*args, **kwargs),
                    archive_source_stamp=lambda *args, **kwargs: archive_source_stamp(*args, **kwargs),
                    group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
                ),
                agent_runner=lambda *args: run_orchestration_agent(*args),
                outline_builder=lambda *args: run_orchestration_agent.prepare_outline(*args),
                method_runner=lambda *args: run_orchestration_method(*args),
                write_lock=library_write_lock,
                adapter_version=ORCHESTRATION_ADAPTER_VERSION,
                on_complete=lambda item_id, run_id: analysis_orchestration_publication_service().finalize(item_id, run_id),
            )
        return _orchestration_services[key]


@contextmanager
def analysis_history_connection():
    """Viewer reads cannot create a missing DB, migrate it, or commit writes."""
    connection = sqlite3.connect(DATABASE_FILE.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        yield connection
    finally:
        connection.close()


def analysis_history_item(item_id: str):
    with analysis_history_connection() as connection:
        return connection.execute("SELECT id,source_name FROM library_items WHERE id=?", (item_id,)).fetchone()


def analysis_history_service() -> AnalysisHistoryService:
    return AnalysisHistoryService(connect=analysis_history_connection, find_item=analysis_history_item)


def analysis_slides_service() -> AnalysisSlidesService:
    return AnalysisSlidesService(
        export_result=lambda item_id, run_id: analysis_history_service().saved_export(item_id, run_id),
        vault_factory=vault_registry,
        templates=load_slide_templates(PROJECT_DIRECTORY),
    )


def analysis_orchestration_publication_service() -> AnalysisOrchestrationPublicationService:
    key = str(DATABASE_FILE.resolve())
    with _orchestration_service_lock:
        if key not in _orchestration_publication_services:
            _orchestration_publication_services[key] = AnalysisOrchestrationPublicationService(
                connect=lambda: database_connection(),
                store_factory=lambda: analysis_archive_store(),
                source_guard=orchestration_source_guard,
                export_locked=lambda db, item_id, run_id: analysis_orchestration_service().result_locked(db, item_id, run_id),
                write_lock=library_write_lock,
            )
        return _orchestration_publication_services[key]


def mark_analysis_run_stale(run_id: str) -> None:
    with database_connection() as connection:
        connection.execute("UPDATE analysis_runs SET stale=1 WHERE id=?", (run_id,))


def freeze_comparison_selection(items, payload):
    from .services import data_catalog
    with database_connection() as connection:
        return data_catalog.freeze(connection, [str(item['id']) for item in items],
            group_ids=[payload['data_group_id']] if payload.get('data_group_id') else [], group_by=payload.get('group_by'))


def analysis_commands() -> AnalysisCommands:
    """Build save dependencies at request time so patched settings stay effective."""
    return AnalysisCommands(
        store=analysis_archive_store(),
        find_item=library_row,
        build_analysis=lambda row: group_analysis_for_row(
            row, include_research_rows=True
        ),
        search_kwic=search_kwic,
        archive_analysis=archive_group_analysis,
        source_fingerprint=archive_source_stamp,
        mark_stale=mark_analysis_run_stale,
        load_comparison_items=interview_comparison_request,
        build_comparison=build_interview_comparison,
        archive_comparison=archive_interview_comparison,
        freeze_comparison=freeze_comparison_selection,
        database_connection=database_connection,
        save_preparation_state=preparation.save,
        segments_for_item=row_segments,
        refresh_archive_index=refresh_archive_index,
        publish_input_vault=publish_input_vault,
        update_library_item_locked=_update_library_from_payload_locked,
        start_insights=start_analysis_insights_command,
        cancel_insights=cancel_analysis_insights_command,
        start_transformer=start_transformer_analysis_command,
        cancel_transformer=cancel_transformer_analysis_command,
        run_classification=run_segment_classifications_command,
        write_lock=library_write_lock,
        expose_local_paths=local_path_access_allowed(),
        pipeline_service=analysis_pipeline_service(),
    )


def speaker_registry_handler() -> SpeakerRegistryHandler:
    """Build request-time speaker dependencies so patched settings stay effective."""
    return SpeakerRegistryHandler(
        snapshot=speaker_registry_snapshot,
        save_records_locked=_save_speaker_registry_records_locked,
        database_connection=database_connection,
        refresh_archive_index=refresh_archive_index,
        write_lock=library_write_lock,
    )


def speaker_identification_handler() -> SpeakerIdentificationHandler:
    return SpeakerIdentificationHandler(identify_library_speakers)


def job_handler() -> JobHandler:
    return JobHandler(
        jobs=jobs,
        lock=jobs_lock,
        active_statuses=ACTIVE_JOB_STATUSES,
        prune=prune_jobs_locked,
        admission_id=lambda: _job_admission_id,
        admission_public=admission_job_public,
        start_job=start_transcription_job_command,
        update_job=update_job,
        update_transcript=update_library_from_payload,
        path_is_within=path_is_within,
    )


public_insight_request, update_insight_request, run_analysis_insight_job = make_insight_jobs(
    AnalysisConflictError=AnalysisConflictError,
    archive_group_analysis=lambda *args, **kwargs: archive_group_analysis(*args, **kwargs),
    call_ai_json=lambda *args, **kwargs: call_ai_json(*args, **kwargs),
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
    insight_cancel_events=insight_cancel_events,
    insight_jobs_lock=insight_jobs_lock,
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    library_write_lock=library_write_lock,
    merge_ai_usage=lambda *args, **kwargs: merge_ai_usage(*args, **kwargs),
    public_diagnostic_text=lambda *args, **kwargs: public_diagnostic_text(*args, **kwargs),
)


start_analysis_insights_command, cancel_analysis_insights_command = make_insight_commands(
    configured_ai_credentials=lambda *args, **kwargs: configured_ai_credentials(*args, **kwargs),
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
    insight_cancel_events=insight_cancel_events,
    insight_jobs_lock=insight_jobs_lock,
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    load_token_config=lambda *args, **kwargs: load_token_config(*args, **kwargs),
    public_insight_request=lambda *args, **kwargs: public_insight_request(*args, **kwargs),
    run_analysis_insight_job=lambda *args, **kwargs: run_analysis_insight_job(*args, **kwargs),
    update_insight_request=lambda *args, **kwargs: update_insight_request(*args, **kwargs),
)


public_transformer_request, update_transformer_request, run_transformer_analysis_job = make_transformer_jobs(
    AnalysisConflictError=AnalysisConflictError,
    analyze_transformer_topics=lambda *args, **kwargs: analyze_transformer_topics(*args, **kwargs),
    archive_group_analysis=lambda *args, **kwargs: archive_group_analysis(*args, **kwargs),
    build_research_analysis=lambda *args, **kwargs: build_research_analysis(*args, **kwargs),
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    library_write_lock=library_write_lock,
    public_diagnostic_text=lambda *args, **kwargs: public_diagnostic_text(*args, **kwargs),
    transformer_cancel_events=transformer_cancel_events,
    transformer_jobs_lock=transformer_jobs_lock,
)


start_transformer_analysis_command, cancel_transformer_analysis_command = make_transformer_commands(
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    public_transformer_request=lambda *args, **kwargs: public_transformer_request(*args, **kwargs),
    run_transformer_analysis_job=lambda *args, **kwargs: run_transformer_analysis_job(*args, **kwargs),
    transformer_cancel_events=transformer_cancel_events,
    transformer_jobs_lock=transformer_jobs_lock,
    update_transformer_request=lambda *args, **kwargs: update_transformer_request(*args, **kwargs),
)


run_segment_classifications_command = make_segment_classification_command(
    AnalysisConflictError=AnalysisConflictError,
    analysis_archive_store=lambda *args, **kwargs: analysis_archive_store(*args, **kwargs),
    archive_segment_classification=lambda *args, **kwargs: archive_segment_classification(*args, **kwargs),
    classify_segments_with_jev=lambda *args, **kwargs: classify_segments_with_jev(*args, **kwargs),
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    library_write_lock=library_write_lock,
    load_token_config=lambda *args, **kwargs: load_token_config(*args, **kwargs),
    local_path_access_allowed=lambda *args, **kwargs: local_path_access_allowed(*args, **kwargs),
    public_diagnostic_text=lambda *args, **kwargs: public_diagnostic_text(*args, **kwargs),
)


def meeting_minutes_export_row(item_id: str) -> tuple[sqlite3.Row, dict[str, Any]]:
    return obsidian_workflows().meeting_minutes_export_row(item_id)


_delete_library_item_locked = make_library_deletion(
    default_output_directory=lambda: DEFAULT_OUTPUT_DIRECTORY,
    media_directory=lambda: MEDIA_DIRECTORY,
    thumbnail_directory=lambda: THUMBNAIL_DIRECTORY,
    canonical_output_import_path=lambda *args, **kwargs: canonical_output_import_path(*args, **kwargs),
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    durable_move=lambda *args, **kwargs: durable_move(*args, **kwargs),
    jobs=jobs,
    jobs_lock=jobs_lock,
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    local_path_access_allowed=lambda *args, **kwargs: local_path_access_allowed(*args, **kwargs),
    reconcile_edit_transactions_before_delete=lambda *args, **kwargs: reconcile_edit_transactions_before_delete(*args, **kwargs),
    retire_input_vault=lambda *args, **kwargs: retire_input_vault(*args, **kwargs),
    trash_directory=lambda: trash_directory(),
    trash_retention_days=lambda: trash_retention_days(),
)


start_transcription_job_command, admission_job_public = make_transcription_start(
    JobRecord=JobRecord,
    MAX_MEDIA_UPLOAD_BYTES=MAX_MEDIA_UPLOAD_BYTES,
    TRANSCRIPT_FINISHING_MODES=TRANSCRIPT_FINISHING_MODES,
    upload_directory=lambda: UPLOAD_DIRECTORY,
    configured_ai_credentials=lambda *args, **kwargs: configured_ai_credentials(*args, **kwargs),
    copy_file_limited=lambda *args, **kwargs: copy_file_limited(*args, **kwargs),
    get_machine_profile=lambda *args, **kwargs: get_machine_profile(*args, **kwargs),
    jobs=jobs,
    jobs_lock=jobs_lock,
    load_token_config=lambda *args, **kwargs: load_token_config(*args, **kwargs),
    local_path_access_allowed=lambda *args, **kwargs: local_path_access_allowed(*args, **kwargs),
    prepare_output_root=lambda *args, **kwargs: prepare_output_root(*args, **kwargs),
    remove_owned_directory=lambda *args, **kwargs: remove_owned_directory(*args, **kwargs),
    resolve_local_media_path=lambda *args, **kwargs: resolve_local_media_path(*args, **kwargs),
    run_transcription_job=lambda *args, **kwargs: run_transcription_job(*args, **kwargs),
    save_custom_vocabulary=lambda *args, **kwargs: save_custom_vocabulary(*args, **kwargs),
    save_upload_limited=lambda *args, **kwargs: save_upload_limited(*args, **kwargs),
)


def create_app() -> Flask:
    """Build the Flask application: configuration, security hooks and routes.

    Building the app has no side effects on data. The database, startup
    recovery and the Obsidian watcher are started only by main() through
    application_lifecycle(), so tests and tools can create an app freely.
    Every call returns a new, independent Flask instance.
    """
    flask_app = Flask(__name__, template_folder="templates", static_folder="static")
    flask_app.config["JSON_AS_ASCII"] = False
    flask_app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    flask_app.config["MAX_CONTENT_LENGTH"] = MAX_MEDIA_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES

    from .web.notation_routes import register_notation_routes
    register_notation_routes(flask_app, service=notation_workflows)

    register_request_security(
        flask_app,
        remote_access_enabled=lambda: REMOTE_ACCESS_ENABLED,
        remote_access_token=lambda: REMOTE_ACCESS_TOKEN,
        remote_local_paths_enabled=lambda: REMOTE_LOCAL_PATHS_ENABLED,
        max_media_upload_bytes=lambda: MAX_MEDIA_UPLOAD_BYTES,
        max_csv_upload_bytes=lambda: MAX_CSV_UPLOAD_BYTES,
        max_json_request_bytes=lambda: MAX_JSON_REQUEST_BYTES,
        multipart_overhead_bytes=MULTIPART_OVERHEAD_BYTES,
        is_colab_runtime=is_colab_runtime,
        trusted_request_hosts=trusted_request_hosts,
        remote_auth_valid=lambda: remote_auth_valid(),
        request_origin_allowed=request_origin_allowed,
        admit_transcription_job=admit_transcription_job,
        release_job_admission=release_job_admission,
    )

    register_system_routes(
        flask_app,
        app_name=APP_NAME,
        product_name=PRODUCT_NAME,
        app_version=APP_VERSION,
        app_creator=APP_CREATOR,
        token_file=lambda: TOKEN_FILE,
        default_output_directory=lambda: DEFAULT_OUTPUT_DIRECTORY,
        runtime_info=runtime_info,
        local_llm_label=local_llm_label,
        local_llm_short_label=local_llm_short_label,
        get_machine_profile=lambda: get_machine_profile(),
        load_token_config=lambda path: load_token_config(path),
        lmstudio_connection_status=lmstudio_connection_status,
        local_path_access_allowed=local_path_access_allowed,
        load_custom_vocabulary=load_custom_vocabulary,
        save_custom_vocabulary=save_custom_vocabulary,
        available_ai_models=lambda provider, config: available_ai_models(provider, config),
        update_token_model=lambda provider, model, path: update_token_model(provider, model, path),
        system_activity_snapshot=lambda: system_activity_snapshot(),
        library_diagnostics=library_storage_diagnostics,
        media_metadata_status=lambda: media_metadata_backfill.snapshot(),
        obsidian_watcher_status=lambda: {**obsidian_watcher_status.snapshot(), "warnings": _vault_nesting_warnings()},
        create_backup=lambda include_media: create_data_backup(include_media),
    )

    register_analysis_routes(
        flask_app, analysis_queries, analysis_commands, AI_MODEL_PROVIDERS
    )

    register_orchestration_routes(flask_app, analysis_orchestration_service, prepare_orchestration,
                                  analysis_orchestration_publication_service,
                                  history_viewer=analysis_history_service)
    register_analysis_slides_routes(flask_app, analysis_slides_service)

    register_speaker_routes(
        flask_app,
        speaker_registry_handler,
        speaker_identification_handler,
        AI_MODEL_PROVIDERS,
        import_speaker_registry_csv,
        read_upload_limited,
        lambda: MAX_CSV_UPLOAD_BYTES,
    )

    register_job_routes(flask_app, job_handler)

    register_obsidian_routes(
        flask_app,
        local_access_allowed=local_path_access_allowed,
        library_row=library_row,
        row_segments=row_segments,
        workbench=obsidian_workbench,
        normalize_efforts=normalize_efforts,
        write_lock=library_write_lock,
        meeting_export_row=meeting_minutes_export_row,
        meeting_fingerprint=meeting_minutes_fingerprint,
        archive_meeting_minutes=archive_meeting_minutes,
        publish_meeting_minutes=publish_meeting_minutes_to_obsidian,
        log_warning=flask_app.logger.warning,
        watcher_status=lambda: obsidian_watcher_status.snapshot(),
    )

    register_library_group_routes(
        flask_app,
        database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
        library_write_lock=library_write_lock,
    )

    register_training_routes(
        flask_app,
        remote_access_enabled=lambda: REMOTE_ACCESS_ENABLED,
        database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
        refresh_training_exports=refresh_training_exports,
        training_events_from_connection=lambda *args, **kwargs: training_events_from_connection(*args, **kwargs),
    )

    register_export_routes(
        flask_app,
        database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
        group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
        library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
        list_speaker_registry=list_speaker_registry,
        meeting_minutes_export_row=meeting_minutes_export_row,
        row_segments=lambda *args, **kwargs: row_segments(*args, **kwargs),
        row_session_profile=lambda *args, **kwargs: row_session_profile(*args, **kwargs),
        row_speaker_profiles=lambda *args, **kwargs: row_speaker_profiles(*args, **kwargs),
    )

    register_analysis_view_routes(
        flask_app,
        AnalysisConflictError=AnalysisConflictError,
        analysis_archive_store=lambda *args, **kwargs: analysis_archive_store(*args, **kwargs),
        build_research_analysis=lambda *args, **kwargs: build_research_analysis(*args, **kwargs),
        group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
        library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
        public_diagnostic_text=public_diagnostic_text,
        save_group_analysis=save_group_analysis,
        transformer_semantic_search=lambda *args, **kwargs: transformer_semantic_search(*args, **kwargs),
    )

    register_ai_routes(
        flask_app,
        lmstudio_reasoning_settings=lambda *args, **kwargs: lmstudio_reasoning_settings(*args, **kwargs),
        load_token_config=lambda *args, **kwargs: load_token_config(*args, **kwargs),
    )

    register_library_routes(
        flask_app,
        media_directory=lambda: MEDIA_DIRECTORY,
        _delete_library_item_locked=_delete_library_item_locked,
        analysis_archive_store=lambda *args, **kwargs: analysis_archive_store(*args, **kwargs),
        archive_source_stamp=archive_source_stamp,
        build_interview_comparison=build_interview_comparison,
        database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
        file_dialog_lock=file_dialog_lock,
        generate_video_thumbnail=lambda *args, **kwargs: generate_video_thumbnail(*args, **kwargs),
        generate_word_cloud_thumbnail=generate_word_cloud_thumbnail,
        interview_comparison_request=interview_comparison_request,
        library_public=library_public,
        library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
        library_write_lock=library_write_lock,
        local_path_access_allowed=local_path_access_allowed,
        manual_output_directory=manual_output_directory,
        resolve_local_media_path=lambda *args, **kwargs: resolve_local_media_path(*args, **kwargs),
        row_segments=lambda *args, **kwargs: row_segments(*args, **kwargs),
        runtime_info=runtime_info,
        upsert_library_item=lambda *args, **kwargs: upsert_library_item(*args, **kwargs),
        list_library_trash=lambda: list_library_trash(),
        restore_library_trash=lambda entry_id: restore_library_trash(entry_id),
        purge_library_trash=lambda entry_id: purge_library_trash(entry_id),
    )
    from .web.research_workspace_routes import register_research_workspace_routes
    register_research_workspace_routes(flask_app,
        store=lambda: analysis_archive_store(), connect=lambda: database_connection(),
        find_item=lambda item_id: library_row(item_id), write_lock=library_write_lock,
        backup=lambda: create_data_backup(False), local_allowed=local_path_access_allowed,
        row_segments=lambda row: row_segments(row),
        row_profiles=lambda *args: row_speaker_profiles(*args), row_session=lambda row: row_session_profile(row))
    return flask_app


app = create_app()


def main() -> int:
    host = os.environ.get("MOJIOKOSI_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.environ.get("MOJIOKOSI_PORT", "7860"))
    except ValueError:
        print("MOJIOKOSI_PORT must be an integer.", file=sys.stderr)
        return 2
    if not 1 <= port <= 65535:
        print("MOJIOKOSI_PORT must be between 1 and 65535.", file=sys.stderr)
        return 2
    if not bind_host_is_loopback(host) and not REMOTE_ACCESS_ENABLED:
        print(
            "Refusing a non-loopback bind. Set MOJIOKOSI_ALLOW_REMOTE=1 and configure authentication explicitly.",
            file=sys.stderr,
        )
        return 2
    if REMOTE_ACCESS_ENABLED and len(REMOTE_ACCESS_TOKEN) < 20:
        print(
            "MOJIOKOSI_ACCESS_TOKEN must contain at least 20 characters when remote access is enabled.",
            file=sys.stderr,
        )
        return 2
    try:
        prepare_output_root("")
        initialize_application()
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"Application initialization failed: {exc}", file=sys.stderr)
        return 2
    try:
        return _run_initialized_application(host, port)
    finally:
        application_lifecycle().shutdown()


def _run_initialized_application(host: str, port: int) -> int:
    url = f"http://{host}:{port}"
    machine = get_machine_profile()
    recommendation = machine["recommended"]
    cpu = machine["cpu"]
    gpu = machine["gpu"]
    print(f"{APP_NAME}: {url}")
    print(
        f"CPU利用可: {cpu['name']} / {cpu['logical_threads']} threads / "
        f"RAM {machine['memory_gib']:.1f} GB"
    )
    if gpu["cuda_available"]:
        print(
            f"GPU利用可: {gpu['name']} / VRAM {gpu['vram_gib']:.1f} GB / "
            f"CUDA {gpu['cuda_version']} / Compute Capability {gpu['capability']}"
        )
    else:
        print(f"GPU利用不可: {gpu['reason']}")
    print(
        "推奨設定: "
        f"model={recommendation['model_name']} / "
        f"transcription={recommendation['device']} / "
        f"diarization={recommendation['diarization_device']}"
    )
    print("終了するにはこのウィンドウで Ctrl+C を押してください。")
    if os.environ.get("MOJIOKOSI_NO_BROWSER") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    start_obsidian_watcher()
    try:
        app.run(host=host, port=port, threaded=True, use_reloader=False)
    finally:
        application_lifecycle().stop_watcher()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
