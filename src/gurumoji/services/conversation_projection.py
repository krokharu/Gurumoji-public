"""Queryable copies of conversation JSON; JSON remains the authoritative input.

Segments include every valid-ID turn, including turns excluded by preparation.
Analysis denominators still belong to the frozen analysis snapshot. No text is copied.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

VERSION = "1"
VERSION_KEY = "conversation_projection_version"
SPEAKER_FIELDS = (
    "global_speaker_id", "display_name", "session_role", "organization", "department",
    "job_title", "consent_status", "recording_consent", "attendance_status", "registration_status",
)
SEGMENT_FIELDS = ("segment_id", "ordinal", "speaker_label", "start", "end", "char_count")


def _source(column: str, kind: str) -> str:
    # CASE guards both malformed JSON and valid JSON of the wrong root type.
    return (f"CASE WHEN json_valid(i.{column}) THEN CASE WHEN json_type(i.{column}) = '{kind}' "
            f"THEN i.{column} ELSE '{'[]' if kind == 'array' else '{}'}' END "
            f"ELSE '{'[]' if kind == 'array' else '{}'}' END")


def _select(table: str, where: str) -> str:
    if table == "conversation_speakers":
        fields = ", ".join(f"json_extract(j.value, '$.{field}')" for field in SPEAKER_FIELDS)
        return (f"SELECT i.id, j.key, {fields} FROM library_items i, "
                f"json_each({_source('speaker_profiles_json', 'object')}) j "
                f"WHERE {where} AND j.type = 'object'")
    # j.value can be an ordinary string, so never feed it unguarded to JSON functions.
    value = "CASE WHEN j.type = 'object' THEN j.value ELSE '{}' END"
    segment_id = f"json_extract({value}, '$.id')"
    return f"""SELECT i.id, {segment_id}, CAST(j.key AS INTEGER),
        json_extract({value}, '$.speaker'),
        CASE WHEN json_type({value}, '$.start') IN ('integer', 'real')
             THEN json_extract({value}, '$.start') END,
        CASE WHEN json_type({value}, '$.end') IN ('integer', 'real')
             THEN json_extract({value}, '$.end') END,
        CASE WHEN json_type({value}, '$.text') = 'text'
             THEN length(json_extract({value}, '$.text')) END
        FROM library_items i, json_each({_source('segments_json', 'array')}) j
        WHERE {where} AND json_type({value}, '$.id') = 'text'
        AND length({segment_id}) BETWEEN 1 AND 80
        AND {segment_id} NOT GLOB '*[^A-Za-z0-9_-]*'
        ORDER BY CAST(j.key AS INTEGER)"""


def initialize(connection: sqlite3.Connection) -> None:
    """Add schema and backfill once, without updating source JSON or revisions."""
    connection.execute(f"""CREATE TABLE IF NOT EXISTS conversation_speakers (
        item_id TEXT NOT NULL, speaker_label TEXT NOT NULL,
        {', '.join(field + ' TEXT' for field in SPEAKER_FIELDS)},
        PRIMARY KEY(item_id, speaker_label))""")
    connection.execute("CREATE INDEX IF NOT EXISTS conversation_speakers_global_idx "
                       "ON conversation_speakers(global_speaker_id)")
    connection.execute("""CREATE TABLE IF NOT EXISTS conversation_segments (
        item_id TEXT NOT NULL, segment_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
        speaker_label TEXT, start REAL, end REAL, char_count INTEGER,
        PRIMARY KEY(item_id, segment_id))""")
    connection.execute("CREATE INDEX IF NOT EXISTS conversation_segments_order_idx "
                       "ON conversation_segments(item_id, ordinal)")
    for table, column in (("conversation_speakers", "speaker_profiles_json"),
                          ("conversation_segments", "segments_json")):
        for event, clause in (("insert", "INSERT"), ("update", f"UPDATE OF {column}, id")):
            # On an ID change remove the old projection as well.
            old_delete = f"DELETE FROM {table} WHERE item_id = OLD.id;" if event == "update" else ""
            connection.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_{event}_v1
                AFTER {clause} ON library_items BEGIN
                {old_delete}
                DELETE FROM {table} WHERE item_id = NEW.id;
                INSERT OR IGNORE INTO {table} {_select(table, 'i.id = NEW.id')};
                END""")
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_delete_v1
            AFTER DELETE ON library_items BEGIN DELETE FROM {table} WHERE item_id = OLD.id; END""")
    marker = connection.execute("SELECT value FROM application_metadata WHERE key=?", (VERSION_KEY,)).fetchone()
    if marker is not None and marker[0] == VERSION:
        return
    for table in ("conversation_speakers", "conversation_segments"):
        connection.execute(f"DELETE FROM {table}")
        connection.execute(f"INSERT OR IGNORE INTO {table} {_select(table, '1')}")
    connection.execute("INSERT OR REPLACE INTO application_metadata(key, value) VALUES (?, ?)",
                       (VERSION_KEY, VERSION))


def check(connection: sqlite3.Connection, item_id: str | None = None) -> dict[str, Any]:
    """Read-only diagnostics, with IDs/ordinals rather than transcript contents."""
    issues: list[dict[str, Any]] = []
    count = 0
    where, parameters = (" WHERE id=?", (item_id,)) if item_id is not None else ("", ())
    for row in connection.execute("SELECT id, speaker_profiles_json, segments_json FROM library_items" + where, parameters):
        count += 1
        identity = row[0]
        for index, table, kind in ((1, "conversation_speakers", dict), (2, "conversation_segments", list)):
            try:
                source = json.loads(row[index])
            except (TypeError, ValueError):
                source = None
            expected = []
            if not isinstance(source, kind):
                issues.append({"item_id": identity, "table": table, "reason": "invalid_json_or_shape"})
            elif kind is dict:
                for label, profile in source.items():
                    if not isinstance(profile, dict):
                        issues.append({"item_id": identity, "table": table, "reason": "invalid_profile"})
                        continue
                    values = []
                    for field in SPEAKER_FIELDS:
                        value = profile.get(field)
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                        elif isinstance(value, bool):
                            value = str(int(value))
                        elif value is not None:
                            value = str(value)
                        values.append(value)
                    expected.append((identity, label, *values))
            else:
                seen: set[str] = set()
                for ordinal, segment in enumerate(source):
                    sid = segment.get("id") if isinstance(segment, dict) else None
                    reason = ("invalid_segment_id" if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", sid)
                              else "duplicate_segment_id" if sid in seen else None)
                    if reason:
                        issues.append({"item_id": identity, "table": table, "ordinal": ordinal, "reason": reason})
                        continue
                    seen.add(sid)
                    speaker = segment.get("speaker")
                    if isinstance(speaker, (dict, list)):
                        speaker = json.dumps(speaker, ensure_ascii=False, separators=(",", ":"))
                    elif isinstance(speaker, bool):
                        speaker = str(int(speaker))
                    elif speaker is not None:
                        speaker = str(speaker)
                    times = [segment.get(key) if type(segment.get(key)) in (int, float) else None for key in ("start", "end")]
                    text = segment.get("text")
                    # SQLite length stops at NUL, as does the derived char count.
                    expected.append((identity, sid, ordinal, speaker, *times,
                                     len(text.split("\0", 1)[0]) if isinstance(text, str) else None))
            actual = [tuple(value) for value in connection.execute(f"SELECT * FROM {table} WHERE item_id=?", (identity,))]
            if sorted(actual, key=lambda value: value[1]) != sorted(expected, key=lambda value: value[1]):
                issues.append({"item_id": identity, "table": table, "reason": "projection_mismatch"})
    for table in ("conversation_speakers", "conversation_segments"):
        for orphan in connection.execute(f"SELECT DISTINCT item_id FROM {table} WHERE item_id NOT IN (SELECT id FROM library_items)"):
            issues.append({"item_id": orphan[0], "table": table, "reason": "orphan"})
    # I1 is optional in older schemas. Full replay belongs in this explicit
    # diagnostic read, not in the ordinary save transaction.
    if connection.execute("SELECT 1 FROM sqlite_master WHERE name='transcript_change_bases' AND type='table'").fetchone():
        from .. import transcript_preparation
        for row in connection.execute("SELECT * FROM library_items" + where, parameters):
            if transcript_preparation.migration_dry_run(connection, row)["status"] == "conflict":
                issues.append({"item_id": row["id"], "table": "transcript_changes", "reason": "history_mismatch"})
    return {"ok": not issues, "checked_items": count, "issues": issues, "version": VERSION}
