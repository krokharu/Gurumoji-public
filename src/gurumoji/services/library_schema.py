"""SQLite schema creation and in-place upgrades for the library database.

initialize_library is idempotent: it creates missing tables, adds columns
older databases lack and repairs derived state at startup."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from .. import transcript_preparation as preparation
from ..analysis_pipeline import initialize_pipeline_store
from ..analysis_orchestration import initialize_orchestration_store
from .analysis_orchestration_publication import initialize_orchestration_publication_store
from ..analysis_store import initialize_store
from ..text_utils import json_load
from . import conversation_projection, media_assets, vocabulary_store, segment_embeddings, data_catalog, research_notes, cross_search
from .sqlite_policy import configure_journal
from .ai.settings import is_colab_runtime


def make_library_schema(
    *,
    data_directory: Callable[[], Any],
    media_directory: Callable[[], Any],
    thumbnail_directory: Callable[[], Any],
    training_audio_directory: Callable[[], Any],
    database_connection: Any,
    repair_output_import_provenance: Any,
) -> tuple[Callable[..., Any], ...]:
    def ensure_output_import_provenance_schema(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS output_import_provenance (
                item_id TEXT NOT NULL,
                canonical_path TEXT NOT NULL,
                content_sha256 TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (item_id, canonical_path)
            )
            """
        )
        table_info = connection.execute(
            "PRAGMA table_info(output_import_provenance)"
        ).fetchall()
        primary_key = [
            str(row["name"])
            for row in sorted(table_info, key=lambda row: int(row["pk"] or 0))
            if int(row["pk"] or 0) > 0
        ]
        if primary_key != ["item_id", "canonical_path"]:
            columns = {str(row["name"]) for row in table_info}
            fingerprint_expression = (
                "COALESCE(content_sha256, '')"
                if "content_sha256" in columns
                else "''"
            )
            connection.execute("DROP TABLE IF EXISTS output_import_provenance_v2")
            connection.execute(
                """
                CREATE TABLE output_import_provenance_v2 (
                    item_id TEXT NOT NULL,
                    canonical_path TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (item_id, canonical_path)
                )
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO output_import_provenance_v2 "
                "(item_id, canonical_path, content_sha256) "
                f"SELECT item_id, canonical_path, {fingerprint_expression} "
                "FROM output_import_provenance"
            )
            connection.execute("DROP TABLE output_import_provenance")
            connection.execute(
                "ALTER TABLE output_import_provenance_v2 "
                "RENAME TO output_import_provenance"
            )
        else:
            columns = {str(row["name"]) for row in table_info}
            if "content_sha256" not in columns:
                connection.execute(
                    "ALTER TABLE output_import_provenance "
                    "ADD COLUMN content_sha256 TEXT NOT NULL DEFAULT ''"
                )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS output_import_provenance_path_idx "
            "ON output_import_provenance(canonical_path)"
        )

    def initialize_library(*, repair_provenance: bool = True) -> None:
        data_directory().mkdir(parents=True, exist_ok=True)
        media_directory().mkdir(parents=True, exist_ok=True)
        thumbnail_directory().mkdir(parents=True, exist_ok=True)
        training_audio_directory().mkdir(parents=True, exist_ok=True)
        with database_connection() as connection:
            configure_journal(connection, data_directory(), colab=is_colab_runtime())
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS library_items (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    group_id TEXT NOT NULL DEFAULT '',
                    output_dir TEXT NOT NULL,
                    media_path TEXT,
                    language TEXT,
                    segments_json TEXT NOT NULL,
                    original_segments_json TEXT NOT NULL DEFAULT '',
                    original_segments_status TEXT NOT NULL DEFAULT '',
                    speaker_names_json TEXT NOT NULL,
                    outline_json TEXT,
                    meeting_minutes_json TEXT NOT NULL DEFAULT '{}',
                    emotion_analysis_json TEXT,
                    formatting_result_json TEXT NOT NULL DEFAULT '{}',
                    ai_usage_json TEXT NOT NULL DEFAULT '{}',
                    files_json TEXT NOT NULL,
                    write_srt INTEGER NOT NULL DEFAULT 1,
                    write_json INTEGER NOT NULL DEFAULT 1,
                    burn_subtitled_video INTEGER NOT NULL DEFAULT 0,
                    analysis_config_json TEXT NOT NULL DEFAULT '{}',
                    analysis_annotations_json TEXT NOT NULL DEFAULT '{}',
                    segment_classification_json TEXT NOT NULL DEFAULT '{}',
                    analysis_revision INTEGER NOT NULL DEFAULT 0,
                    analysis_updated_at TEXT,
                    revision_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            library_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(library_items)").fetchall()
            }
            if "session_profile_json" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN session_profile_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "group_id" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN group_id TEXT NOT NULL DEFAULT ''"
                )
            if "original_segments_json" not in library_columns:
                # A transcript that existed before this schema revision cannot be
                # reconstructed.  Keep the then-current text in a separate column
                # and disclose that provenance instead of calling it a pristine
                # ASR/field transcript.
                connection.execute(
                    "ALTER TABLE library_items "
                    "ADD COLUMN original_segments_json TEXT NOT NULL DEFAULT ''"
                )
                connection.execute(
                    "ALTER TABLE library_items "
                    "ADD COLUMN original_segments_status TEXT NOT NULL DEFAULT ''"
                )
                connection.execute(
                    "UPDATE library_items SET original_segments_json = segments_json, "
                    "original_segments_status = 'migrated_current_snapshot' "
                    "WHERE original_segments_json = ''"
                )
            elif "original_segments_status" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items "
                    "ADD COLUMN original_segments_status TEXT NOT NULL DEFAULT ''"
                )
                connection.execute(
                    "UPDATE library_items SET original_segments_status = "
                    "CASE WHEN original_segments_json <> '' THEN 'migrated_current_snapshot' ELSE '' END"
                )
            if "speaker_profiles_json" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN speaker_profiles_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "meeting_minutes_json" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN meeting_minutes_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "ai_usage_json" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN ai_usage_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "formatting_result_json" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN formatting_result_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "burn_subtitled_video" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN burn_subtitled_video INTEGER NOT NULL DEFAULT 0"
                )
            if "analysis_config_json" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN analysis_config_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "analysis_annotations_json" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN analysis_annotations_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "analysis_revision" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN analysis_revision INTEGER NOT NULL DEFAULT 0"
                )
            if "analysis_updated_at" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN analysis_updated_at TEXT"
                )
            if "analysis_insights_json" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN analysis_insights_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "transformer_analysis_json" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN transformer_analysis_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "segment_classification_json" not in library_columns:
                connection.execute(
                    "ALTER TABLE library_items ADD COLUMN segment_classification_json TEXT NOT NULL DEFAULT '{}'"
                )
            connection.execute("""
                CREATE TABLE IF NOT EXISTS analysis_insight_requests (
                    request_id TEXT PRIMARY KEY, item_id TEXT NOT NULL,
                    source_revision INTEGER NOT NULL, analysis_revision INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
                    status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '', usage_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS insight_requests_item ON analysis_insight_requests(item_id, created_at)")
            connection.execute("""
                UPDATE analysis_insight_requests SET status = 'interrupted',
                    message = 'アプリが再起動されました。必要な場合は再生成してください。'
                WHERE status IN ('queued', 'running', 'cancelling')
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS transformer_analysis_requests (
                    request_id TEXT PRIMARY KEY, item_id TEXT NOT NULL,
                    source_revision INTEGER NOT NULL, analysis_revision INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL, model TEXT NOT NULL,
                    max_topics INTEGER NOT NULL, min_topic_size INTEGER NOT NULL,
                    topic_count INTEGER NOT NULL DEFAULT 0,
                    mode TEXT NOT NULL DEFAULT 'auto',
                    min_similarity REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
            """)
            transformer_request_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(transformer_analysis_requests)").fetchall()
            }
            if "topic_count" not in transformer_request_columns:
                connection.execute(
                    "ALTER TABLE transformer_analysis_requests "
                    "ADD COLUMN topic_count INTEGER NOT NULL DEFAULT 0"
                )
            if "mode" not in transformer_request_columns:
                connection.execute(
                    "ALTER TABLE transformer_analysis_requests "
                    "ADD COLUMN mode TEXT NOT NULL DEFAULT 'auto'"
                )
            if "min_similarity" not in transformer_request_columns:
                connection.execute(
                    "ALTER TABLE transformer_analysis_requests "
                    "ADD COLUMN min_similarity REAL NOT NULL DEFAULT 0"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS transformer_requests_item "
                "ON transformer_analysis_requests(item_id, created_at)"
            )
            connection.execute("""
                UPDATE transformer_analysis_requests SET status = 'interrupted',
                    message = 'アプリが再起動されました。必要な場合は再実行してください。'
                WHERE status IN ('queued', 'running', 'cancelling')
            """)
            connection.execute("UPDATE library_items SET write_json = 1 WHERE write_json <> 1")
            legacy_session_rows = connection.execute(
                "SELECT id, session_profile_json FROM library_items "
                "WHERE session_profile_json LIKE '%confidentiality_notes%'"
            ).fetchall()
            for legacy_row in legacy_session_rows:
                raw_profile = json_load(legacy_row["session_profile_json"], {})
                if not isinstance(raw_profile, dict) or "confidentiality_notes" not in raw_profile:
                    continue
                sanitized_profile = dict(raw_profile)
                sanitized_profile.pop("confidentiality_notes", None)
                connection.execute(
                    "UPDATE library_items SET session_profile_json = ? WHERE id = ?",
                    (json.dumps(sanitized_profile, ensure_ascii=False), legacy_row["id"]),
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS speaker_registry (
                    id TEXT PRIMARY KEY,
                    participant_code TEXT NOT NULL DEFAULT '',
                    display_name TEXT NOT NULL DEFAULT '',
                    pseudonym TEXT NOT NULL DEFAULT '',
                    default_role TEXT NOT NULL DEFAULT 'participant',
                    organization TEXT NOT NULL DEFAULT '',
                    department TEXT NOT NULL DEFAULT '',
                    job_title TEXT NOT NULL DEFAULT '',
                    consent_status TEXT NOT NULL DEFAULT 'unknown',
                    recording_consent TEXT NOT NULL DEFAULT 'unknown',
                    confidentiality_status TEXT NOT NULL DEFAULT 'unknown',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    attributes_json TEXT NOT NULL DEFAULT '{}',
                    notes TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS library_updated_idx ON library_items(updated_at DESC)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS library_groups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS library_group_name_idx ON library_groups(name COLLATE NOCASE)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS library_items_group_idx ON library_items(group_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS speaker_registry_code_idx "
                "ON speaker_registry(participant_code)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS speaker_registry_updated_idx "
                "ON speaker_registry(updated_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS application_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO application_metadata (key, value) VALUES (?, ?)",
                ("speaker_registry_revision", "0"),
            )
            connection.execute(
                "INSERT OR IGNORE INTO application_metadata (key, value) VALUES (?, ?)",
                ("training_events_migrated", "0"),
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS training_events (
                    event_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS training_events_created_idx "
                "ON training_events(created_at, event_id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS output_import_tombstones (
                    canonical_path TEXT PRIMARY KEY,
                    content_sha256 TEXT NOT NULL DEFAULT '',
                    deleted_at TEXT NOT NULL
                )
                """
            )
            tombstone_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(output_import_tombstones)"
                ).fetchall()
            }
            if "content_sha256" not in tombstone_columns:
                connection.execute(
                    "ALTER TABLE output_import_tombstones "
                    "ADD COLUMN content_sha256 TEXT NOT NULL DEFAULT ''"
                )
            ensure_output_import_provenance_schema(connection)
            initialize_store(connection)
            initialize_pipeline_store(connection)
            initialize_orchestration_store(connection)
            initialize_orchestration_publication_store(connection)
            preparation.initialize(connection)
            vocabulary_store.initialize(connection)
            conversation_projection.initialize(connection)
            data_catalog.initialize(connection)
            media_assets.initialize(connection)
            segment_embeddings.initialize(connection)
            research_notes.initialize(connection)
            cross_search.initialize(connection)
            if repair_provenance:
                repair_output_import_provenance(connection)
            for row in connection.execute("SELECT id, source_name FROM library_items").fetchall():
                source_path = Path(str(row["source_name"]))
                if source_path.is_absolute() and source_path.name:
                    connection.execute(
                        "UPDATE library_items SET source_name = ? WHERE id = ?",
                        (source_path.name, row["id"]),
                    )

    return (ensure_output_import_provenance_schema, initialize_library)
