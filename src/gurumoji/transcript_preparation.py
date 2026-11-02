"""Local, versioned transcript preparation. GET never writes or certifies evidence."""
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime, timezone


TEXT_STATES = {"unreviewed", "transcript_checked", "audio_verified", "unclear"}
ROLES = {"unknown", "participant", "moderator", "observer"}
FIELDS = [
    "interview_id", "group_id", "input_version", "source_hash", "segment_id",
    "order", "order_verified", "speaker_id", "speaker_verified", "role",
    "start", "end", "source_locator", "source_segment_ids", "original_text",
    "original_status", "text", "text_status", "boundary_verified",
    "previous_segment_id", "next_segment_id", "content_ready", "interaction_ready",
    "analysis_needs_review",
]


def encode(value):
    def safe(item):
        if isinstance(item, float) and not math.isfinite(item):
            return {"invalid_legacy_number": str(item)}
        if isinstance(item, list):
            return [safe(v) for v in item]
        if isinstance(item, dict):
            return {k: safe(v) for k, v in item.items()}
        return item
    return json.dumps(safe(value), ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize(connection):
    # Additive tables only. Existing originals and IDs are not migrated/replaced.
    connection.execute("""CREATE TABLE IF NOT EXISTS transcript_versions (
        item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
        version INTEGER NOT NULL, source_hash TEXT NOT NULL,
        source_json TEXT NOT NULL, origin TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(item_id, version))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS transcript_change_bases (
        item_id TEXT PRIMARY KEY REFERENCES library_items(id) ON DELETE CASCADE,
        format_version INTEGER NOT NULL, base_hash TEXT NOT NULL,
        base_json TEXT NOT NULL, raw_status TEXT NOT NULL,
        legacy_version INTEGER, legacy_hash TEXT, created_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS transcript_changes (
        item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
        seq INTEGER NOT NULL, version INTEGER NOT NULL, origin TEXT NOT NULL,
        process TEXT NOT NULL, process_version TEXT NOT NULL,
        base_hash TEXT NOT NULL, after_hash TEXT NOT NULL,
        ops_json TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(item_id, seq))""")
    if "metadata_json" not in {row[1] for row in connection.execute("PRAGMA table_info(transcript_changes)")}:
        connection.execute("ALTER TABLE transcript_changes ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
    connection.execute("""CREATE TABLE IF NOT EXISTS transcript_preparations (
        item_id TEXT PRIMARY KEY REFERENCES library_items(id) ON DELETE CASCADE,
        revision INTEGER NOT NULL, state_json TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS transcript_preparation_events (
        item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
        revision INTEGER NOT NULL, state_json TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(item_id, revision))""")
    # initialize_store creates the run catalog before these preparation tables.
    # Keep invalidation inside the same transaction, including multi-interview runs.
    for operation, record in (("INSERT", "NEW"), ("UPDATE", "NEW"), ("DELETE", "OLD")):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS preparation_runs_{operation.lower()}
            AFTER {operation} ON transcript_preparations
            BEGIN UPDATE analysis_runs SET stale=1
                WHERE item_id={record}.item_id OR id IN (
                    SELECT run_id FROM analysis_run_members WHERE item_id={record}.item_id);
            END""")


def source(row):
    return {key: json.loads(row[column] or default) for key, column, default in (
        ("segments", "segments_json", "[]"),
        ("speaker_profiles", "speaker_profiles_json", "{}"),
        ("speaker_names", "speaker_names_json", "{}"),
        ("session_profile", "session_profile_json", "{}"),
    )}


def _segment_map(segments):
    if not isinstance(segments, list):
        return None
    result = {}
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("id"), str) or not segment["id"]:
            return None
        if segment["id"] in result:
            return None
        result[segment["id"]] = segment
    return result


def _same_json(left, right):
    """JSON equality preserves number types, null and missing keys for hashes."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_json(value, right[key]) for key, value in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_json(a, b) for a, b in zip(left, right))
    if isinstance(left, float) and math.isnan(left):
        return math.isnan(right)
    if isinstance(left, float) and left == right == 0:
        return math.copysign(1, left) == math.copysign(1, right)
    return left == right


def diff_source(before, after):
    """Pure, lossless operations; missing keys and JSON null remain distinct."""
    ops = []
    for key in source_keys():
        old, new = before[key], after[key]
        if _same_json(old, new):
            continue
        if key == "segments":
            old_map, new_map = _segment_map(old), _segment_map(new)
            if old_map is not None and new_map is not None:
                for sid in sorted(old_map.keys() - new_map.keys()):
                    ops.append({"op": "segment_delete", "id": sid})
                for sid, segment in new_map.items():
                    if sid not in old_map:
                        ops.append({"op": "segment_add", "id": sid, "value": deepcopy(segment)})
                    elif not _same_json(old_map[sid], segment):
                        ops.extend(_key_ops(old_map[sid], segment, "segment", sid))
                if list(old_map) != list(new_map):
                    ops.append({"op": "segment_order", "value": list(new_map)})
                continue
        elif isinstance(old, dict) and isinstance(new, dict):
            ops.extend(_key_ops(old, new, "metadata", key))
            continue
        # Legacy transcripts with absent/duplicate IDs must remain lossless.
        ops.append({"op": "replace", "key": key, "value": deepcopy(new)})
    return ops


def source_keys():
    return ("segments", "speaker_profiles", "speaker_names", "session_profile")


def _key_ops(old, new, kind, target):
    ops = []
    for key in sorted(old.keys() - new.keys()):
        ops.append({"op": kind + "_unset", "target": target, "key": key})
    for key, value in new.items():
        if key not in old or not _same_json(old[key], value):
            ops.append({"op": kind + "_set", "target": target, "key": key, "value": deepcopy(value)})
    return ops


def apply_ops(value, ops):
    """Pure replay, without touching the supplied Raw or operations."""
    value = deepcopy(value)
    segments = None
    for op in ops:
        kind = op["op"]
        if kind == "replace":
            if op["key"] not in source_keys():
                raise ValueError("Unknown source field")
            value[op["key"]] = deepcopy(op["value"])
            if op["key"] == "segments":
                segments = None
        elif kind.startswith("metadata_") or kind.startswith("segment_"):
            if kind.startswith("metadata_"):
                if op["target"] not in source_keys()[1:]:
                    raise ValueError("Unknown metadata field")
                target = value[op["target"]]
            else:
                if segments is None:
                    segments = _segment_map(value["segments"])
                if segments is None:
                    raise ValueError("Invalid segment IDs in delta")
                if kind == "segment_add":
                    if op["id"] in segments or op["value"].get("id") != op["id"]:
                        raise ValueError("Duplicate or inconsistent segment ID")
                    segments[op["id"]] = deepcopy(op["value"])
                    continue
                if kind == "segment_delete":
                    del segments[op["id"]]
                    continue
                if kind == "segment_order":
                    if len(op["value"]) != len(segments) or set(op["value"]) != set(segments):
                        raise ValueError("Invalid segment order")
                    segments = {sid: segments[sid] for sid in op["value"]}
                    continue
                target = segments[op["target"]]
            if kind.endswith("_set"):
                target[op["key"]] = deepcopy(op["value"])
            elif kind.endswith("_unset"):
                del target[op["key"]]
            else:
                raise ValueError("Unknown transcript operation")
        else:
            raise ValueError("Unknown transcript operation")
    if segments is not None:
        value["segments"] = list(segments.values())
    return value


def reconstruct(base, changes):
    """Replay and verify the complete hash chain. No database or other I/O."""
    value = base
    for change in changes:
        if digest(value) != change["base_hash"]:
            raise ValueError("Transcript delta base hash mismatch")
        value = apply_ops(value, json.loads(change["ops_json"]))
        if digest(value) != change["after_hash"]:
            raise ValueError("Transcript delta result hash mismatch")
    return deepcopy(value) if not changes else value


def _base(connection, item_id):
    return connection.execute("SELECT * FROM transcript_change_bases WHERE item_id=?", (item_id,)).fetchone()


def _changes(connection, item_id):
    return [dict(v) for v in connection.execute(
        "SELECT * FROM transcript_changes WHERE item_id=? ORDER BY seq", (item_id,))]


def read_versions(connection, item_id, *, include_source=False):
    """One read-only adapter for legacy snapshots and delta versions."""
    versions = {}
    for row in connection.execute("SELECT * FROM transcript_versions WHERE item_id=? ORDER BY version", (item_id,)):
        value = json.loads(row["source_json"])
        if digest(value) != row["source_hash"]:
            raise ValueError("Legacy transcript hash mismatch")
        versions[row["version"]] = {"version": row["version"], "source_hash": row["source_hash"],
            "origin": row["origin"], "created_at": row["created_at"]}
        if include_source:
            versions[row["version"]]["source"] = value
    base = _base(connection, item_id)
    if base:
        if base["format_version"] != 1:
            raise ValueError("Unsupported transcript base format")
        value = json.loads(base["base_json"])
        if digest(value) != base["base_hash"]:
            raise ValueError("Transcript Raw base hash mismatch")
        previous_version = 0
        for seq, change in enumerate(_changes(connection, item_id), 1):
            if change["seq"] != seq or change["version"] < previous_version:
                raise ValueError("Transcript delta sequence mismatch")
            previous_version = change["version"]
            value = reconstruct(value, [change])
            version = change["version"]
            # Multiple operations of the same save share one version. A bridge
            # equal to a legacy snapshot retains its original list entry.
            if version in versions and versions[version]["source_hash"] == change["after_hash"]:
                continue
            if version in versions and change["process"] == "legacy_bridge":
                raise ValueError("Legacy/delta transcript version conflict")
            versions[version] = {"version": version, "source_hash": change["after_hash"],
                "origin": change["origin"], "created_at": change["created_at"]}
            if include_source:
                versions[version]["source"] = value
        # A code rollback may have introduced colliding legacy versions.
        for old in connection.execute("SELECT version, source_hash FROM transcript_versions WHERE item_id=?", (item_id,)):
            if versions[old["version"]]["source_hash"] != old["source_hash"]:
                raise ValueError("Legacy/delta transcript version conflict")
    result = [versions[v] for v in sorted(versions)]
    return result if include_source else [{k: v for k, v in entry.items() if k != "source"} for entry in result]


def read_version(connection, item_id, version):
    return next((v for v in read_versions(connection, item_id, include_source=True) if v["version"] == version), None)


def current_version(connection, row):
    versions = read_versions(connection, row["id"])
    return versions[-1]["version"] if versions and versions[-1]["source_hash"] == digest(source(row)) else None


def known_segment_ids(connection, row):
    ids = {s.get("id") for s in json.loads(row["original_segments_json"] or "[]")}
    for v in read_versions(connection, row["id"], include_source=True):
        ids.update(s.get("id") for s in v["source"]["segments"])
    return ids


def migration_dry_run(connection, row):
    """No DDL or writes. A stale active chain requires explicit reconciliation."""
    try:
        value = source(row)
        versions = read_versions(connection, row["id"])
        base = _base(connection, row["id"])
        if base:
            raw = json.loads(row["original_segments_json"] or "[]")
            if not _same_json(json.loads(base["base_json"])["segments"], raw) or base["raw_status"] != (row["original_segments_status"] or "unavailable"):
                raise ValueError("Raw changed after import")
            if current_version(connection, row) is None:
                raise ValueError("Current transcript is not the active delta version")
            changes = _changes(connection, row["id"])
            if not changes or changes[-1]["version"] != versions[-1]["version"]:
                raise ValueError("Legacy writes after delta activation require reconciliation")
            return {"status": "already_active", "version": versions[-1]["version"], "source_hash": digest(value)}
        raw = {key: {} for key in source_keys()}
        raw["segments"] = json.loads(row["original_segments_json"] or "[]")
        ops = diff_source(raw, value)
        if digest(apply_ops(raw, ops)) != digest(value):
            raise ValueError("Legacy bridge replay mismatch")
        latest = versions[-1] if versions else None
        version = latest["version"] if latest and latest["source_hash"] == digest(value) else (latest["version"] + 1 if latest else 1)
        return {"status": "ready", "version": version, "source_hash": digest(value),
            "raw_status": row["original_segments_status"] or "unavailable", "base": raw,
            "legacy_version": latest["version"] if latest else None,
            "legacy_hash": latest["source_hash"] if latest else None, "ops": ops}
    except (ValueError, TypeError, KeyError) as exc:
        return {"status": "conflict", "reason": str(exc)}


def _insert_change(connection, item_id, version, before, after, origin, process, *, process_version="1", metadata=None):
    seq = connection.execute("SELECT COALESCE(MAX(seq), 0)+1 FROM transcript_changes WHERE item_id=?", (item_id,)).fetchone()[0]
    connection.execute("""INSERT INTO transcript_changes
        (item_id, seq, version, origin, process, process_version, base_hash, after_hash, ops_json, created_at, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (item_id, seq, version, origin, process, process_version, digest(before), digest(after),
         encode(diff_source(before, after)), now(), encode(metadata or {})))


def activate_changes(connection, row):
    """Explicit write operation, atomic even if its caller catches an error."""
    report = migration_dry_run(connection, row)
    if report["status"] == "conflict":
        raise ValueError(report["reason"])
    if report["status"] == "already_active":
        return report["version"]
    connection.execute("SAVEPOINT transcript_activation")
    try:
        connection.execute("INSERT INTO transcript_change_bases VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (row["id"], 1, digest(report["base"]), encode(report["base"]), report["raw_status"],
             report["legacy_version"], report["legacy_hash"], now()))
        _insert_change(connection, row["id"], report["version"], report["base"], source(row), "rule", "legacy_bridge")
        if current_version(connection, row) != report["version"]:
            raise ValueError("Legacy bridge verification failed")
        connection.execute("RELEASE transcript_activation")
    except Exception:
        connection.execute("ROLLBACK TO transcript_activation")
        connection.execute("RELEASE transcript_activation")
        raise
    return report["version"]


def _active_tail(connection, row, base):
    """Validate the current cache against committed history without replaying it.

    Full chain verification remains in the read adapter and cutover dry run.
    This keeps each ordinary save independent of the number of older edits.
    """
    raw = json.loads(row["original_segments_json"] or "[]")
    initial = json.loads(base["base_json"])
    if (base["format_version"] != 1 or digest(initial) != base["base_hash"] or not _same_json(initial["segments"], raw)
            or base["raw_status"] != (row["original_segments_status"] or "unavailable")):
        raise ValueError("Raw changed after import")
    tail = connection.execute("SELECT * FROM transcript_changes WHERE item_id=? ORDER BY seq DESC LIMIT 1", (row["id"],)).fetchone()
    if tail is None:
        raise ValueError("Transcript history is missing")
    count = connection.execute("SELECT COUNT(*) FROM transcript_changes WHERE item_id=?", (row["id"],)).fetchone()[0]
    if count != tail["seq"]:
        raise ValueError("Transcript delta sequence mismatch")
    legacy = connection.execute("SELECT MAX(version) FROM transcript_versions WHERE item_id=?", (row["id"],)).fetchone()[0]
    collision = connection.execute("""SELECT 1 FROM transcript_versions v JOIN transcript_changes c
        ON v.item_id=c.item_id AND v.version=c.version
        WHERE v.item_id=? AND v.source_hash<>c.after_hash LIMIT 1""", (row["id"],)).fetchone()
    if collision or legacy is not None and legacy > tail["version"]:
        raise ValueError("Legacy writes after delta activation require reconciliation")
    return tail


def capture(connection, row, origin="saved", *, previous_source=None, history_steps=None, import_source=None):
    """The only transcript history writer; runs inside the save transaction."""
    value = source(row)
    base = _base(connection, row["id"])
    if origin in {"legacy_current_baseline", "preparation_baseline"}:
        if base is None:
            return activate_changes(connection, row)
        tail = _active_tail(connection, row, base)
        if tail["after_hash"] != digest(value):
            raise ValueError("Current transcript is not the active delta version")
        return tail["version"]
    if base is None:
        if origin != "initial_import":
            return activate_changes(connection, row)
        raw = {key: {} for key in source_keys()}
        raw["segments"] = json.loads(row["original_segments_json"] or "[]")
        connection.execute("INSERT INTO transcript_change_bases VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (row["id"], 1, digest(raw), encode(raw), row["original_segments_status"] or "unavailable", None, None, now()))
        metadata = import_source if import_source is not None else {**value, "segments": raw["segments"]}
        if digest(metadata["segments"]) != digest(raw["segments"]):
            raise ValueError("Import metadata cannot change Raw")
        _insert_change(connection, row["id"], 1, raw, metadata, "rule", "import_metadata")
        if history_steps is not None:
            _capture_steps(connection, row["id"], 1, metadata, value, history_steps)
            return 1
        if digest(metadata) != digest(value):
            # I2 will supply AI provenance. I1 does not infer who changed text.
            _insert_change(connection, row["id"], 1, metadata, value, "rule", "import_current_snapshot")
        return 1
    tail = _active_tail(connection, row, base)
    before = previous_source if previous_source is not None else read_version(connection, row["id"], tail["version"])["source"]
    if digest(before) != tail["after_hash"]:
        raise ValueError("Transcript previous source hash mismatch")
    version = tail["version"] + 1
    if history_steps is not None:
        _capture_steps(connection, row["id"], version, before, value, history_steps)
        return version
    _insert_change(connection, row["id"], version, before, value, "researcher", "transcript_save")
    return version


def _capture_steps(connection, item_id, version, before, final, steps):
    for step in steps:
        after = step["source"]
        if set(after) != set(source_keys()) or step["origin"] not in {"ai", "rule", "researcher"}:
            raise ValueError("Invalid transcript history step")
        _insert_change(connection, item_id, version, before, after, step["origin"], step["process"],
                       process_version=step.get("process_version", "1"), metadata=step.get("metadata"))
        before = after
    if digest(before) != digest(final):
        _insert_change(connection, item_id, version, before, final, "rule", "finishing_output_normalization")
    elif not steps:
        _insert_change(connection, item_id, version, before, final, "rule", "finishing_no_change")


def ai_change_rows(connection, item_id, *, run_id=None, version=None):
    """Export only recorded AI deltas, excluding subsequent researcher/rule edits."""
    from .ai_finishing import finishing_changes
    base = _base(connection, item_id)
    if base is None:
        return None  # Explicit legacy fallback, never invent AI provenance.
    value = json.loads(base["base_json"])
    if digest(value) != base["base_hash"]:
        raise ValueError("Transcript base hash mismatch")
    result = []
    for seq, change in enumerate(_changes(connection, item_id), 1):
        if change["seq"] != seq:
            raise ValueError("Transcript delta sequence mismatch")
        after = reconstruct(value, [change])
        metadata = json.loads(change["metadata_json"])
        if (change["origin"] == "ai" and (run_id is None or metadata.get("run_id") == run_id)
                and (version is None or change["version"] == version)):
            for item in finishing_changes(value["segments"], after["segments"]):
                result.append({**item, "change_seq": change["seq"], "input_version": change["version"],
                               "change_type": "notation" if change["process"] == "notation" else "ai_finishing",
                               "process": change["process"], "process_version": change["process_version"],
                               "base_hash": change["base_hash"], "after_hash": change["after_hash"],
                               "metadata": metadata})
        value = after
    return result


def load_state(connection, item_id):
    row = connection.execute("SELECT * FROM transcript_preparations WHERE item_id=?", (item_id,)).fetchone()
    return (int(row["revision"]), json.loads(row["state_json"])) if row else (0, {})


def write_state(connection, item_id, revision, state):
    connection.execute("INSERT INTO transcript_preparations VALUES (?, ?, ?) "
                       "ON CONFLICT(item_id) DO UPDATE SET revision=excluded.revision, state_json=excluded.state_json",
                       (item_id, revision, encode(state)))
    connection.execute("INSERT INTO transcript_preparation_events VALUES (?, ?, ?, ?)",
                       (item_id, revision, encode(state), now()))


def valid_time(segment):
    values = [segment.get("start"), segment.get("end")]
    if segment.get("time_unknown") or any(v is None or v == "" or isinstance(v, bool) for v in values):
        return False
    try:
        start, end = map(float, values)
        return math.isfinite(start) and math.isfinite(end) and 0 <= start <= end
    except (TypeError, ValueError, OverflowError):
        return False


def segment_text(segment):
    """Imported transcripts may carry a null or numeric text; treat it as text, never crash."""
    value = segment.get("text")
    return value if isinstance(value, str) else ("" if value is None else str(value))


def basis_hash(source_hash, state):
    return digest({"source_hash": source_hash, "records": state.get("records", {}),
                   "order_verified": state.get("order_verified", False)})


def view(connection, row, segments):
    source_value = source(row)
    fingerprint = digest(source_value)
    revision, state = load_state(connection, row["id"])
    current = state.get("source_hash") == fingerprint
    records = state.get("records", {}) if current else {}
    order_verified = current and state.get("order_verified", False)
    versions = read_versions(connection, row["id"])
    version = versions[-1]["version"] if versions and versions[-1]["source_hash"] == fingerprint else None
    originals = {str(s.get("id")): s for s in json.loads(row["original_segments_json"] or "[]") if s.get("id")}
    original_status = row["original_segments_status"] or "unavailable"
    annotations = json.loads(row["analysis_annotations_json"] or "{}")
    stale = bool(annotations) and state.get("analysis_basis") != basis_hash(fingerprint, state if current else {})
    rows = []
    for index, segment in enumerate(segments):
        sid = segment["id"]
        record = records.get(sid, {})
        text_status = record.get("text_status", "unreviewed")
        speaker = segment.get("speaker")
        known = bool(speaker and speaker != "UNKNOWN")
        content_ready = bool(segment_text(segment).strip()) and text_status in {"transcript_checked", "audio_verified"} and record.get("boundary_verified", False)
        interaction_ready = bool(content_ready and order_verified and known and record.get("speaker_verified") and record.get("role", "unknown") != "unknown")
        rows.append({
            "interview_id": row["id"], "group_id": source_value["session_profile"].get("interview_group_id") or None,
            "input_version": version, "source_hash": fingerprint, "segment_id": sid,
            "order": index + 1, "order_verified": bool(order_verified),
            "speaker_id": speaker if known else None, "speaker_verified": bool(known and record.get("speaker_verified")),
            "role": record.get("role", "unknown"),
            "start": segment.get("start") if valid_time(segment) else None,
            "end": segment.get("end") if valid_time(segment) else None,
            "source_locator": record.get("source_locator", ""),
            "source_segment_ids": record.get("source_segment_ids", [sid] if sid in originals else []),
            "original_text": originals.get(sid, {}).get("text"), "original_status": original_status if sid in originals else "unavailable",
            "text": segment_text(segment), "text_status": text_status,
            "boundary_verified": bool(record.get("boundary_verified")),
            "previous_segment_id": segments[index - 1]["id"] if index else None,
            "next_segment_id": segments[index + 1]["id"] if index + 1 < len(segments) else None,
            "content_ready": bool(content_ready), "interaction_ready": interaction_ready,
            "analysis_needs_review": stale,
        })
    return {
        "schema_version": 1, "revision": revision, "source_hash": fingerprint, "input_version": version,
        "status": "confirmed" if current and state.get("confirmed") else "needs_review" if state and not current else "draft",
        "order_verified": bool(order_verified), "analysis_needs_review": stale,
        "analysis_source_hash": state.get("analysis_source_hash"),
        "participant_count": state.get("participant_count") if current else None,
        "metadata_sources": state.get("metadata_sources", ""),
        "rows": rows, "versions": versions,
        "content_ready_count": sum(r["content_ready"] for r in rows),
        "interaction_ready_count": sum(r["interaction_ready"] for r in rows),
        "known_speaker_count": len({r["speaker_id"] for r in rows if r["speaker_verified"]}),
        "unknown_speaker_turns": sum(not r["speaker_verified"] for r in rows),
    }


class Conflict(Exception):
    pass


def save(connection, row, segments, payload):
    before = view(connection, row, segments)
    if not isinstance(payload, dict):
        raise ValueError("準備データはJSONオブジェクトで指定してください。")
    if type(payload.get("revision")) is not int or not isinstance(payload.get("source_hash"), str):
        raise ValueError("準備revisionとsource_hashが必要です。")
    if payload["revision"] != before["revision"] or payload["source_hash"] != before["source_hash"]:
        raise Conflict("文字起こしまたは確認状態が更新されました。再読み込みしてください。")
    records = payload.get("records", {})
    if not isinstance(records, dict) or len(records) > len(segments):
        raise ValueError("発言の確認データが不正です。")
    ids = {s["id"] for s in segments}
    known_ids = set(ids)
    known_ids.update(known_segment_ids(connection, row))
    clean = {}
    by_id = {s["id"]: s for s in segments}
    for sid, record in records.items():
        if sid not in ids or not isinstance(record, dict):
            raise ValueError("存在しない発言IDです。")
        status, role = record.get("text_status", "unreviewed"), record.get("role", "unknown")
        if not isinstance(status, str) or not isinstance(role, str) or status not in TEXT_STATES or role not in ROLES:
            raise ValueError("本文の確認状態または役割が不正です。")
        for key in ("speaker_verified", "boundary_verified"):
            if type(record.get(key, False)) is not bool:
                raise ValueError("確認状態は真偽値で指定してください。")
        if record.get("speaker_verified") and by_id[sid].get("speaker") in (None, "", "UNKNOWN"):
            raise ValueError("話者不明の発言を話者確認済みにはできません。")
        if status == "audio_verified":
            from pathlib import Path
            if not row["media_path"] or not Path(row["media_path"]).is_file():
                raise ValueError("音声・動画ファイルがないため音声照合済みにはできません。")
        lineage = record.get("source_segment_ids", [])
        if not isinstance(lineage, list) or len(lineage) > 1000 or any(not isinstance(s, str) or s not in known_ids for s in lineage):
            raise ValueError("分割・結合元の発言IDを確認してください。")
        locator = record.get("source_locator", "")
        if not isinstance(locator, str) or len(locator) > 1000:
            raise ValueError("元データ位置は1000文字以内で指定してください。")
        clean[sid] = {"text_status": status, "role": role, "speaker_verified": record.get("speaker_verified", False),
                      "boundary_verified": record.get("boundary_verified", False), "source_segment_ids": list(dict.fromkeys(lineage)),
                      "source_locator": locator}
    for key in ("order_verified", "confirm", "review_analysis"):
        if type(payload.get(key, False)) is not bool:
            raise ValueError("確認指定は真偽値で指定してください。")
    count = payload.get("participant_count")
    if count is not None and (type(count) is not int or not 0 <= count <= 100000):
        raise ValueError("実参加人数は非負の整数または不明を指定してください。")
    metadata = payload.get("metadata_sources", "")
    if not isinstance(metadata, str) or len(metadata) > 10000:
        raise ValueError("資料・確認根拠は10000文字以内で指定してください。")
    if count is not None and not metadata.strip():
        raise ValueError("実参加人数を記入する場合は、名簿等の確認根拠を記入してください。")
    if payload.get("confirm") and (not segments or any(
        clean.get(s["id"], {}).get("text_status") not in {"transcript_checked", "audio_verified"}
        or not clean.get(s["id"], {}).get("boundary_verified") or not segment_text(s).strip()
        for s in segments
    )):
        raise ValueError("版の確定には全発言の本文と発言区切りの確認が必要です。話者不明は内容分析の制約として残ります。")
    _, old = load_state(connection, row["id"])
    state = {"source_hash": before["source_hash"], "records": clean, "order_verified": payload.get("order_verified", False),
             "confirmed": payload.get("confirm", False), "participant_count": count, "metadata_sources": metadata,
             "analysis_basis": old.get("analysis_basis"), "analysis_source_hash": old.get("analysis_source_hash")}
    if payload.get("review_analysis"):
        state["analysis_basis"] = basis_hash(before["source_hash"], state)
        state["analysis_source_hash"] = before["source_hash"]
    capture(connection, row, "preparation_baseline")
    write_state(connection, row["id"], before["revision"] + 1, state)
    return view(connection, row, segments)


def bind_analysis(connection, row):
    """Unrelated analysis saves must not silently clear a stale evidence binding."""
    revision, state = load_state(connection, row["id"])
    if state.get("analysis_basis"):
        return
    fingerprint = digest(source(row))
    active = state if state.get("source_hash") == fingerprint else {}
    state["analysis_basis"] = basis_hash(fingerprint, active)
    state["analysis_source_hash"] = fingerprint
    write_state(connection, row["id"], revision + 1, state)
