"""Durable M0-M7 execution for the selected first analysis slice."""

from __future__ import annotations

import copy
import json
import math
import sqlite3
import statistics
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable

from .analysis_plan_advisor import sign_proposal, verify_proposal
from . import transcript_preparation as preparation
from . import analysis_core as core
from .analysis_method_registry import REGISTRY_VERSION
from .analysis_core import (
    AnalysisContractError,
    TRANSITION_VERSION,
    transition_guard,
    validate_transition,
    build_execution_binding,
    build_plan_envelope,
    canonical,
    capability_catalog,
    fingerprint,
    eligibility_assessment,
    validate_definition,
    validate_definitions,
    validate_publication_targets,
    PUBLICATION_TARGETS,
    EFFECTIVE_PUBLICATION_WRITERS,
    validate_planning_proposal,
)


ACTIVE_STEP_STATES = core.ACTIVE_STEP_STATES
TERMINAL_SUCCESS = core.TERMINAL_SUCCESS
MILESTONES = tuple(f"M{index}" for index in range(8))
RUNTIME_LOCK = threading.RLock()
RUNTIMES: dict[str, threading.Thread] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _event(connection: sqlite3.Connection, pipeline_id: str, kind: str, payload: dict[str, Any]) -> None:
    connection.execute("""INSERT INTO analysis_pipeline_events
        (pipeline_id,sequence,event_type,payload_json,created_at)
        SELECT ?,COALESCE(MAX(sequence),0)+1,?,?,? FROM analysis_pipeline_events WHERE pipeline_id=?""",
        (pipeline_id, kind, canonical(payload).decode("utf-8"), utc_now(), pipeline_id))


def _record_decision(connection: sqlite3.Connection, pipeline_id: str, result: dict[str, Any]) -> None:
    _event(connection, pipeline_id, "core_decision", {"contract": "CoreDecision",
        "value": result["decision"], "transitions": result["transitions"], "facts": result["facts"]})


_STATE_TABLES = {
    "pipeline": ("analysis_pipeline_requests", ("pipeline_id",)),
    "step": ("analysis_step_attempts", ("attempt_id",)),
    "publication": ("analysis_pipeline_publications", ("pipeline_id", "target_role")),
}
_STATE_FIELDS = {
    "pipeline": {"wait_reason", "error", "current_milestone", "cancel_requested", "generation"},
    "step": {"error_code", "error", "started_at", "ended_at", "artifact_json", "report_json",
             "reuse_key", "artifact_hash", "reused_from", "reused_at"},
    "publication": {"error", "result_run_id", "attempt_id", "generation"},
}


def _transition_state(connection: sqlite3.Connection, machine: str, key: tuple[str, ...],
                      target: str, *, generation: int, changes: dict[str, Any] | None = None,
                      guard_id: str | None = None) -> None:
    """Validate and compare-update inside the caller's transaction, without commit.

    Status and generation are compared for every entity. Step/publication writes
    additionally compare the owning request's generation, so late workers fail.
    """
    table, keys = _STATE_TABLES[machine]
    where = " AND ".join(name + "=?" for name in keys)
    row = connection.execute(f"SELECT status,generation,pipeline_id FROM {table} WHERE {where}", key).fetchone()
    if row is None:
        raise AnalysisContractError("状態更新の対象がありません。", code="stale_attempt")
    guard = guard_id if guard_id is not None else transition_guard(machine, row["status"], target) or "transition.invalid"
    validate_transition(machine, row["status"], target, guard)
    changes = dict(changes or {})
    if not changes.keys() <= _STATE_FIELDS[machine]:
        raise ValueError("Unsupported transition metadata")
    changes.update(status=target, updated_at=utc_now())
    fields = ",".join(name + "=?" for name in changes)
    if machine == "pipeline":
        compare_generation = generation
        owner_where, owner_values = "", ()
    else:
        compare_generation = row["generation"]
        owner_where = " AND EXISTS (SELECT 1 FROM analysis_pipeline_requests WHERE pipeline_id=? AND generation=?)"
        owner_values = (row["pipeline_id"], generation)
        if machine == "step" and compare_generation != generation:
            raise AnalysisContractError("旧世代の試行です。", code="stale_generation")
    updated = connection.execute(
        f"UPDATE {table} SET {fields} WHERE {where} AND status=? AND generation=?" + owner_where,
        (*changes.values(), *key, row["status"], compare_generation, *owner_values))
    if updated.rowcount != 1:
        raise AnalysisContractError("状態または世代が更新されています。", code="stale_generation")
    _event(connection, row["pipeline_id"], "state_transition", {
        "machine": machine, "key": list(key), "from": row["status"], "to": target,
        "guard_id": guard, "generation": generation,
        "rule_version": TRANSITION_VERSION,
    })


def initialize_pipeline_store(connection: sqlite3.Connection) -> None:
    from .services import change_log
    change_log.initialize(connection)
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_definitions (
        item_id TEXT NOT NULL, definition_id TEXT NOT NULL, revision INTEGER NOT NULL,
        status TEXT NOT NULL, payload_json TEXT NOT NULL, last_trial_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(item_id, definition_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_pipeline_requests (
        pipeline_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, item_id TEXT NOT NULL,
        source_revision INTEGER NOT NULL, analysis_revision INTEGER NOT NULL,
        input_hash TEXT NOT NULL, plan_hash TEXT NOT NULL, plan_json TEXT NOT NULL,
        binding_json TEXT NOT NULL DEFAULT '{}', snapshot_json TEXT NOT NULL,
        status TEXT NOT NULL, current_milestone TEXT NOT NULL DEFAULT 'M0',
        wait_reason TEXT NOT NULL DEFAULT '', result_run_id TEXT NOT NULL DEFAULT '',
        cancel_requested INTEGER NOT NULL DEFAULT 0, generation INTEGER NOT NULL DEFAULT 1,
        error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_pipeline_item ON analysis_pipeline_requests(item_id,created_at)")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_step_attempts (
        attempt_id TEXT PRIMARY KEY, pipeline_id TEXT NOT NULL, step_id TEXT NOT NULL,
        milestone TEXT NOT NULL, generation INTEGER NOT NULL, attempt INTEGER NOT NULL,
        status TEXT NOT NULL, directive_json TEXT NOT NULL DEFAULT '{}',
        report_json TEXT NOT NULL DEFAULT '{}', artifact_json TEXT NOT NULL DEFAULT '{}',
        error_code TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',
        started_at TEXT, updated_at TEXT NOT NULL, ended_at TEXT,
        UNIQUE(pipeline_id,step_id,attempt))""")
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_steps_pipeline ON analysis_step_attempts(pipeline_id,milestone,step_id,attempt)")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(analysis_step_attempts)")}
    for column in ("reuse_key", "artifact_hash", "reused_from", "reused_at"):
        if column not in columns:
            connection.execute(f"ALTER TABLE analysis_step_attempts ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_steps_reuse ON analysis_step_attempts(reuse_key,status)")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_pipeline_publications (
        pipeline_id TEXT NOT NULL, target_role TEXT NOT NULL, result_run_id TEXT NOT NULL DEFAULT '',
        package_hash TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, attempt_id TEXT NOT NULL DEFAULT '',
        error TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL, generation INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY(pipeline_id,target_role))""")
    if "generation" not in {row[1] for row in connection.execute("PRAGMA table_info(analysis_pipeline_publications)")}:
        connection.execute("ALTER TABLE analysis_pipeline_publications ADD COLUMN generation INTEGER NOT NULL DEFAULT 1")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_pipeline_events (
        pipeline_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(pipeline_id,sequence))""")
    # A crash may happen before any step starts or between committed milestones.
    # Record the generation even when no active attempt can carry an interruption.
    for row in connection.execute("SELECT pipeline_id,generation,status,cancel_requested,plan_hash FROM analysis_pipeline_requests WHERE status IN ('accepted','running','cancelling')").fetchall():
        pid, generation = row["pipeline_id"], row["generation"]
        _event(connection, pid, "process_restart", {"generation": generation,
               "previous_status": row["status"], "cancel_requested": bool(row["cancel_requested"])})
        decision = core.decide_restart(dict(row))
        _record_decision(connection, pid, decision)
        cancelled = decision["decision"]["action"] == "cancel"
        for step in _latest_steps(connection, pid):
            if step["generation"] != generation or step["status"] in TERMINAL_SUCCESS | {"failed", "cancelled", "interrupted"}:
                continue
            step_decision = core.decide_restart_step(step, cancelled=cancelled, context=dict(row))
            if step_decision["transitions"]:
                _record_decision(connection, pid, step_decision)
            for effect in step_decision["transitions"]:
                changes = ({"error_code": "cancelled", "ended_at": utc_now()} if cancelled else
                    {"error_code": "process_restart", "error": "アプリの再起動により中断しました。再開操作を待っています。", "ended_at": utc_now()})
                _transition_state(connection, "step", (step["attempt_id"],), effect["to"], generation=generation,
                    guard_id=effect["guard_id"], changes=changes if effect == step_decision["transitions"][-1] else {})
        for publication in connection.execute("SELECT target_role FROM analysis_pipeline_publications WHERE pipeline_id=? AND status='publishing'", (pid,)).fetchall():
            _transition_state(connection, "publication", (pid, publication["target_role"]), "unknown", generation=generation,
                              changes={"error": "再起動時点の公開結果を確認できません。"})
        if cancelled:
            if row["status"] != "cancelling":
                _transition_state(connection, "pipeline", (pid,), "cancelling", generation=generation)
            _transition_state(connection, "pipeline", (pid,), "cancelled", generation=generation, changes={"wait_reason": ""})
        else:
            _transition_state(connection, "pipeline", (pid,), "waiting", generation=generation,
                changes={"wait_reason": "retry", "error": "アプリの再起動後に再開操作を待っています。"})


def _has_restart_event(connection: sqlite3.Connection, pipeline_id: str, generation: int) -> bool:
    row = connection.execute("SELECT payload_json FROM analysis_pipeline_events WHERE pipeline_id=? AND event_type='process_restart' ORDER BY sequence DESC LIMIT 1", (pipeline_id,)).fetchone()
    return bool(row and json.loads(row[0]).get("generation") == generation)


def _latest_steps(connection: sqlite3.Connection, pipeline_id: str, *, include_payload: bool = True) -> list[dict[str, Any]]:
    columns = "attempt.*" if include_payload else ",".join("attempt." + column for column in (
        "step_id", "attempt_id", "attempt", "milestone", "status", "error_code", "error",
        "started_at", "updated_at", "ended_at",
        "reused_from", "reused_at",
    ))
    rows = connection.execute(f"""SELECT {columns} FROM analysis_step_attempts attempt
        JOIN (SELECT step_id,MAX(attempt) AS number FROM analysis_step_attempts
              WHERE pipeline_id=? GROUP BY step_id) latest
          ON latest.step_id=attempt.step_id AND latest.number=attempt.attempt
        WHERE attempt.pipeline_id=? ORDER BY attempt.milestone,attempt.step_id""",
        (pipeline_id, pipeline_id)).fetchall()
    return [dict(row) for row in rows]


class _MeasurementSourceMissing(ValueError):
    """A source placeholder must stay distinguishable from an observed value."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _measurement_value(segment: dict[str, Any], definition: dict[str, Any]) -> Any:
    rule = definition["measurement_rule"]
    column = definition["source_columns"][0]
    value = segment.get(column)
    # Participation analysis intentionally has a participant fallback. It is
    # not evidence of a recorded role, so do not export it as a measurement.
    # Legacy/unknown provenance is never upgraded from the current registry.
    if column == "role":
        if "recorded_role_source" in segment:
            source = segment["recorded_role_source"]
            if source not in ("explicit", "registry", "preparation"):
                raise _MeasurementSourceMissing("role_not_recorded" if source == "default" else "role_provenance_unknown")
            value = segment.get("recorded_role")
        elif segment.get("role_source") == "preparation":
            pass  # A fixed legacy preparation record is already explicit.
        elif segment.get("role_source") == "registered" and value not in (None, "", "participant"):
            pass  # Historical implicit fallback was participant only.
        else:
            reason = "role_not_recorded" if segment.get("role_source") == "default" else "role_provenance_unknown"
            raise _MeasurementSourceMissing(reason)
    # Duration's internal 0 placeholder is not an observed zero. Every rule
    # reading this source must honor the same timestamp validity boundary.
    if column == "duration" or rule == "duration":
        if segment.get("time_unknown") or not segment.get("valid_time", preparation.valid_time(segment)):
            raise ValueError("Duration requires valid source timestamps.")
        if isinstance(segment.get("duration"), bool):
            raise ValueError("Duration must be numeric.")
        duration = float(segment.get("duration"))
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("Duration must be finite and nonnegative.")
        value = duration
    if rule == "identity":
        if value is None:
            raise ValueError("Source value is missing.")
        if definition["data_type"] == "number" and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise ValueError("Numeric identity requires a finite number, not a boolean or string.")
        return value
    if rule == "text_length":
        if not isinstance(value, str):
            raise ValueError("Text length requires source text.")
        return len(value)
    if rule == "nonempty":
        if not isinstance(value, str):
            raise ValueError("Nonempty requires source text.")
        return bool(value.strip())
    if rule == "duration":
        return duration
    if rule == "boolean_true":
        if type(value) is not bool:
            raise ValueError("Boolean source value is missing or invalid.")
        return value
    raise AnalysisContractError("測定規則を実行できません。", code="measurement_unavailable")


def _typed_measurement(value: Any, definition: dict[str, Any]) -> Any:
    """Trial and full execution count only values matching the declared type."""
    kind = definition["data_type"]
    numeric = type(value) in {int, float} and math.isfinite(value)
    valid = {"number": numeric, "boolean": type(value) is bool,
             "string": isinstance(value, str),
             "category": isinstance(value, str) or type(value) is bool or numeric}[kind]
    if not valid:
        raise ValueError("Measured value does not match its declared type.")
    return value


def _included_segments(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Use the fixed analysis view's exclusion decision at every entry point."""
    return [segment for segment in analysis.get("segments", []) if not segment.get("excluded")]


def measure_segments(analysis: dict[str, Any], definitions: list[dict[str, Any]], *, limit: int | None = None) -> list[dict[str, Any]]:
    definitions = validate_definitions(definitions)
    rows: list[dict[str, Any]] = []
    segments = _included_segments(analysis)
    if limit is not None:
        segments = segments[:limit]
    for segment in segments:
        row = {
            "segment_id": segment.get("id"), "speaker": segment.get("speaker"),
            "speaker_name": segment.get("speaker_name"),
        }
        for definition in definitions:
            try:
                row[definition["output_column"]] = _typed_measurement(_measurement_value(segment, definition), definition)
                row[definition["output_column"] + "__missing_reason"] = ""
            except _MeasurementSourceMissing as exc:
                row[definition["output_column"]] = None
                row[definition["output_column"] + "__missing_reason"] = exc.reason
            except (TypeError, ValueError, OverflowError):
                row[definition["output_column"]] = None
                row[definition["output_column"] + "__missing_reason"] = "invalid_source_value"
        rows.append(row)
    return rows


def _manual_method(definitions: list[dict[str, Any]], rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, tuple[list[str], list[dict[str, Any]]]]]:
    fields = ["segment_id", "speaker", "speaker_name"]
    summaries = []
    for definition in definitions:
        column = definition["output_column"]
        fields.extend((column, column + "__missing_reason"))
        values = [row[column] for row in rows if row.get(column) is not None]
        if definition["method"] == "descriptive":
            numeric = [float(value) for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
            text = f"有効N={len(numeric)}"
            if numeric:
                text += f"、平均={statistics.fmean(numeric):.3f}、最小={min(numeric):.3f}、最大={max(numeric):.3f}"
        else:
            counts: dict[str, int] = {}
            for value in values:
                key = str(value)
                counts[key] = counts.get(key, 0) + 1
            text = f"有効N={len(values)}、度数=" + json.dumps(counts, ensure_ascii=False, sort_keys=True)
        summaries.append({"title": definition["name"], "text": text})
    method = {
        "method_id": "descriptive_statistics", "method_version": "analysis-pipeline-1",
        "title": "手入力定義の記述集計", "status": "completed",
        "datasets": ["measurements"], "findings": [], "summaries": summaries,
        "details": {"definitions": definitions},
        "previews": [{"dataset": "measurements", "fields": fields, "rows": rows[:10], "total": len(rows)}],
        "analysis_unit": "発話", "engine": {"name": "manual-measurement", "version": 1},
        "limitations": ["研究者が入力した定義に基づく記述集計です。推測統計は実行していません。"],
    }
    if any(definition["source_columns"] == ["role"] for definition in definitions):
        method["details"]["role_source_policy"] = {
            "version": 1, "value_field": "recorded_role", "provenance_field": "recorded_role_source",
            "accepted_sources": ["explicit", "registry", "preparation"],
            "ambiguous_legacy_participant": "missing", "analysis_defaults": "unchanged",
        }
    return method, {"measurements": (fields, rows)}


class AnalysisPipelineService:
    """Coordinate one durable pipeline using injected application boundaries."""

    def __init__(
        self, *, connect: Callable[[], sqlite3.Connection], find_item: Callable[[str], Any],
        source_fingerprint: Callable[[Any], str], snapshot_builder: Callable[[Any], dict[str, Any]],
        method_runner: Callable[[str, dict[str, Any]], dict[str, Any]],
        save_result: Callable[..., dict[str, Any]], publish_result: Callable[[str], dict[str, Any]],
        publication_outcomes: Callable[[str], dict[str, dict[str, str]]],
        public_run: Callable[[dict[str, Any]], dict[str, Any]],
        runtime_key: str,
        plan_advisor: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.connect = connect
        self.find_item = find_item
        self.source_fingerprint = source_fingerprint
        self.snapshot_builder = snapshot_builder
        self.method_runner = method_runner
        self.save_result = save_result
        self.publish_result = publish_result
        self.publication_outcomes = publication_outcomes
        self.public_run = public_run
        self.runtime_key = runtime_key
        self.plan_advisor = plan_advisor

    def capabilities(self) -> dict[str, Any]:
        return capability_catalog()

    def _snapshot(self, item):
        from .services.analysis_pipeline_adapters import validate_pipeline_snapshot
        return validate_pipeline_snapshot(self.snapshot_builder(item))

    def _definition_rows(self, connection: sqlite3.Connection, item_id: str, ids: list[str],
                         *, adopted_only: bool = True) -> list[dict[str, Any]]:
        if not ids:
            return []
        rows = connection.execute(
            f"SELECT * FROM analysis_definitions WHERE item_id=? AND definition_id IN ({','.join('?' for _ in ids)})",
            (item_id, *ids),
        ).fetchall()
        by_id = {row["definition_id"]: row for row in rows}
        result = []
        for identifier in ids:
            row = by_id.get(identifier)
            if row is None:
                raise AnalysisContractError("定義が見つかりません: " + identifier, code="definition_missing")
            if adopted_only and row["status"] != "adopted":
                raise AnalysisContractError("試行後に定義を採用してください: " + identifier, code="definition_not_adopted")
            value = validate_definition(json.loads(row["payload_json"]), require_version=True)
            if value["definition_id"] != identifier or type(row["revision"]) is not int or row["revision"] < 1:
                raise AnalysisContractError("保存定義のID・revisionが一致しません。", code="revision_conflict")
            result.append({**value, "revision": row["revision"]})
        validate_definitions(result)
        return result

    def _definitions(self, item_id: str, ids: list[str], *, adopted_only: bool = True) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return self._definition_rows(connection, item_id, ids, adopted_only=adopted_only)

    def get_definition(self, item_id: str, definition_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM analysis_definitions WHERE item_id=? AND definition_id=?",
                                     (item_id, definition_id)).fetchone()
        if row is None:
            raise LookupError("定義が見つかりません。")
        value = json.loads(row["payload_json"])
        result = {**value, "revision": row["revision"], "status": row["status"], "updated_at": row["updated_at"],
                  "last_trial": json.loads(row["last_trial_json"])}
        try:
            validate_definition(value, require_version=True)
        except AnalysisContractError as exc:
            result["validation_error"] = {"reason_code": exc.code, "message": str(exc)}
        return result

    def save_definition(self, item_id: str, definition_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if definition_id != payload.get("definition_id"):
            raise AnalysisContractError("URLと本文のdefinition_idが一致しません。", field="definition_id")
        value = validate_definition(payload)
        status = payload.get("status", "draft")
        if status not in {"draft", "adopted", "retired"}:
            raise AnalysisContractError("定義のstatusが正しくありません。", field="status")
        expected_revision = payload.get("expected_revision")
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 0):
            raise AnalysisContractError("expected_revisionは整数で指定してください。", code="revision_conflict")
        now = utc_now()
        from .services import change_log
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM analysis_definitions WHERE item_id=? AND definition_id=?", (item_id, definition_id),
            ).fetchone()
            if (existing is not None and expected_revision != existing["revision"]
                    or existing is None and expected_revision not in (None, 0)):
                raise AnalysisContractError("定義が更新されています。再読み込みしてください。", code="revision_conflict")
            previous = json.loads(existing["payload_json"]) if existing else None
            if previous is not None:
                if type(previous.get("version")) is not int or previous["version"] < 1:
                    raise AnalysisContractError("旧定義のversionを確認できません。別IDで保存してください。", code="definition_version_invalid")
                try:
                    previous = validate_definition(previous, require_version=True)
                except AnalysisContractError:
                    # A valid replacement may repair unsupported legacy content.
                    # Its real stored version still advances; old artifacts stay fixed.
                    previous = {k: v for k, v in previous.items() if k not in {"status", "revision", "expected_revision", "expected_trial"}}
            if previous is not None and previous["definition_id"] != definition_id:
                raise AnalysisContractError("保存定義のIDが一致しません。", code="revision_conflict")
            same_content = previous is not None and {k: v for k, v in previous.items() if k != "version"} == {
                k: v for k, v in value.items() if k != "version"}
            revision = existing["revision"] + 1 if existing else 1
            value["version"] = previous["version"] if same_content else (previous["version"] + 1 if previous else 1)
            last_trial = json.loads(existing["last_trial_json"]) if existing and same_content else {}
            if "expected_trial" in payload:
                expected = payload["expected_trial"]
                item = self.find_item(item_id)
                if (status != "adopted" or not isinstance(expected, dict) or not last_trial
                        or expected != last_trial or not same_content
                        or last_trial.get("definition_revision") != existing["revision"]
                        or last_trial.get("definition_hash") != fingerprint(value)
                        or item is None or self.source_fingerprint(item) != last_trial.get("input_hash")):
                    raise AnalysisContractError("試行した定義または入力が更新されています。再試行してください。", code="trial_conflict")
            with change_log.tracking(connection, [("analysis_definitions", item_id)], process="analysis_definition_save"):
                connection.execute("""INSERT INTO analysis_definitions
                    (item_id,definition_id,revision,status,payload_json,last_trial_json,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(item_id,definition_id) DO UPDATE SET
                    revision=excluded.revision,status=excluded.status,payload_json=excluded.payload_json,
                    last_trial_json=excluded.last_trial_json,updated_at=excluded.updated_at""",
                    (item_id, definition_id, revision, status, canonical(value).decode("utf-8"),
                     canonical(last_trial).decode("utf-8"), existing["created_at"] if existing else now, now),
                )
        return {**value, "revision": revision, "status": status, "updated_at": now, "last_trial": last_trial}

    def trial_definition(self, item_id: str, definition_id: str, *, limit: int = 20) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise AnalysisContractError("試行件数は1〜100の整数です。", field="limit")
        definition = self._definitions(item_id, [definition_id], adopted_only=False)[0]
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("分析対象が見つかりません。")
        snapshot = self._snapshot(item)
        rows = measure_segments(snapshot["analysis"], [definition], limit=limit)
        column = definition["output_column"]
        values = [row[column] for row in rows if row.get(column) is not None]
        segments = snapshot["analysis"].get("segments", [])
        trial = {
            "trial_id": uuid.uuid4().hex, "definition_id": definition_id,
            "definition_version": definition["version"], "definition_revision": definition["revision"],
            "definition_hash": fingerprint(validate_definition(definition, require_version=True)),
            "input_hash": snapshot["input_hash"], "source_revision": snapshot.get("source_revision"),
            "analysis_revision": snapshot.get("analysis_revision"), "total_count": len(segments),
            "excluded_count": sum(bool(segment.get("excluded")) for segment in segments),
            "sample_size": len(rows), "valid_count": len(values),
            "missing_count": len(rows) - len(values), "values": values[:20], "rows": rows,
            "external_calls": 0, "created_at": utc_now(),
        }
        from .services import change_log
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._definition_rows(connection, item_id, [definition_id], adopted_only=False)[0]
            latest_item = self.find_item(item_id)
            if current != definition or latest_item is None or self.source_fingerprint(latest_item) != snapshot["input_hash"]:
                raise AnalysisContractError("試行中に定義または入力が更新されました。", code="trial_conflict")
            with change_log.tracking(connection, [("analysis_definitions", item_id)], origin="rule", process="definition_trial"):
                connection.execute(
                    "UPDATE analysis_definitions SET last_trial_json=?,updated_at=? WHERE item_id=? AND definition_id=? AND revision=?",
                    (canonical(trial).decode("utf-8"), utc_now(), item_id, definition_id, definition["revision"]),
                )
        return trial

    @staticmethod
    def _check_expected_definitions(payload: dict[str, Any], definitions: list[dict[str, Any]], input_hash: str) -> None:
        expected = payload.get("expected_definition_versions")
        actual = {value["definition_id"]: value["version"] for value in definitions}
        if expected is not None and (not isinstance(expected, dict) or any(type(v) is not int or v < 1 for v in expected.values()) or expected != actual):
            raise AnalysisContractError("確認した定義版が更新されています。", code="revision_conflict")
        if "expected_input_hash" in payload and payload["expected_input_hash"] != input_hash:
            raise AnalysisContractError("確認した入力が更新されています。", code="revision_conflict")

    def _bound_definitions(self, pipeline: dict[str, Any]) -> list[dict[str, Any]]:
        """Read only the accepted payload. Never substitute today's mutable definition."""
        binding = json.loads(pipeline["binding_json"])
        resolved = binding.get("resolved", [])
        snapshots = binding.get("definition_snapshots")
        if binding.get("plan_hash") != pipeline["plan_hash"]:
            raise AnalysisContractError("固定定義の計画hashが一致しません。", code="binding_conflict")
        if snapshots is None:
            if resolved:
                raise AnalysisContractError("旧計画には固定定義がありません。旧成果を保持し、新しい計画を確認してください。", code="definition_snapshot_missing")
            return []
        if (binding.get("contract_version") != "analysis-binding-2"
                or binding.get("binding_hash") != fingerprint({"resolved": resolved, "definition_snapshots": snapshots})):
            raise AnalysisContractError("固定定義のhashが一致しません。", code="binding_conflict")
        if not isinstance(snapshots, dict) or set(snapshots) != {slot["definition_id"] for slot in resolved}:
            raise AnalysisContractError("固定定義の対象が一致しません。", code="binding_conflict")
        definitions = []
        for slot in resolved:
            snapshot = snapshots[slot["definition_id"]]
            value = validate_definition(snapshot["payload"], require_version=True)
            if (snapshot.get("status") != "adopted" or value["definition_id"] != slot["definition_id"]
                    or type(slot.get("definition_version")) is not int or value["version"] != slot["definition_version"]
                    or type(snapshot.get("revision")) is not int or snapshot["revision"] < 1
                    or type(slot.get("definition_revision")) is not int
                    or snapshot["revision"] != slot.get("definition_revision")
                    or fingerprint(value) != snapshot.get("definition_hash")
                    or snapshot["definition_hash"] != slot.get("definition_hash")
                    or value["method"] != slot.get("method") or value["output_column"] != slot.get("output_column")):
                raise AnalysisContractError("固定定義の版・ID・内容が一致しません。", code="binding_conflict")
            definitions.append(value)
        return validate_definitions(definitions)

    def preview(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("分析対象が見つかりません。")
        source_revision = int(item["revision_count"] or 0)
        analysis_revision = int(item["analysis_revision"] or 0)
        if (type(payload.get("source_revision")) is not int or type(payload.get("analysis_revision")) is not int
                or payload["source_revision"] != source_revision or payload["analysis_revision"] != analysis_revision):
            raise AnalysisContractError("入力版が更新されています。", code="revision_conflict")
        ids = payload.get("definition_ids", [])
        if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
            raise AnalysisContractError("definition_idsはIDの配列です。", field="definition_ids")
        definitions = self._definitions(item_id, ids)
        snapshot = self._snapshot(item)
        self._check_expected_definitions(payload, definitions, snapshot["input_hash"])
        if payload.get("planning_proposal") is not None:
            verify_proposal(payload["planning_proposal"])
        envelope = build_plan_envelope(
            item_id=item_id, source_revision=source_revision, analysis_revision=analysis_revision,
            input_fingerprint=snapshot["input_hash"], payload=payload, definitions=definitions,
            segment_count=len(_included_segments(snapshot["analysis"])),
        )
        binding = build_execution_binding(envelope, definitions)
        return {"plan": envelope, "binding": binding, "definitions": definitions,
                "capabilities": capability_catalog()["capabilities"]}

    def propose(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.plan_advisor is None:
            raise AnalysisContractError("計画候補の生成を利用できません。", code="method_unavailable")
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("分析対象が見つかりません。")
        source_revision = int(item["revision_count"] or 0)
        analysis_revision = int(item["analysis_revision"] or 0)
        if (payload.get("source_revision") != source_revision
                or payload.get("analysis_revision") != analysis_revision):
            raise AnalysisContractError("入力版が更新されています。", code="revision_conflict")
        snapshot = self._snapshot(item)
        proposal = self.plan_advisor(snapshot, payload)
        latest = self.find_item(item_id)
        if (latest is None
                or int(latest["revision_count"] or 0) != source_revision
                or int(latest["analysis_revision"] or 0) != analysis_revision
                or self.source_fingerprint(latest) != snapshot["input_hash"]):
            raise AnalysisContractError("候補生成中に入力が更新されました。", code="revision_conflict")
        normalized = validate_planning_proposal(
            proposal, input_hash=snapshot["input_hash"],
            source_revision=source_revision, analysis_revision=analysis_revision,
            provider_policy=payload.get("provider_policy", "local_only"),
        )
        return {"proposal": sign_proposal(normalized)}

    def start(self, item_id: str, payload: dict[str, Any], *, app_url: str) -> tuple[dict[str, Any], int]:
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or not 16 <= len(request_id) <= 100 or not request_id.replace("-", "").replace("_", "").isalnum():
            raise AnalysisContractError("request_idが正しくありません。", field="request_id")
        preview = self.preview(item_id, payload)
        if preview["plan"]["eligibility"]["execution"] != "allowed":
            raise AnalysisContractError("必須の適用性検査に合格していません。", code="ineligible")
        item = self.find_item(item_id)
        snapshot = self._snapshot(item)
        if snapshot["input_hash"] != preview["plan"]["input_hash"]:
            raise AnalysisContractError("計画確認中に入力が更新されました。", code="revision_conflict")
        library_key = self.runtime_key
        pipeline_id = uuid.uuid5(uuid.NAMESPACE_URL, library_key + request_id).hex
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM analysis_pipeline_requests WHERE request_id=?", (request_id,)
            ).fetchone()
            if existing:
                expected_plan, expected_binding = preview["plan"], preview["binding"]
                if "reuse" not in json.loads(existing["plan_json"]) and expected_plan["reuse"] == "auto":
                    # Retain idempotence for requests accepted before this additive
                    # policy field existed; never rewrite their frozen envelopes.
                    expected_plan = {k: v for k, v in expected_plan.items() if k not in {"reuse", "plan_hash"}}
                    expected_plan["plan_hash"] = fingerprint(expected_plan)
                    expected_binding = {**expected_binding, "plan_hash": expected_plan["plan_hash"]}
                if (existing["item_id"] != item_id or existing["plan_hash"] != expected_plan["plan_hash"]
                        or json.loads(existing["binding_json"]) != expected_binding):
                    raise AnalysisContractError("request_idが別の計画に使われています。", code="request_conflict")
                result = self.status(item_id, existing["pipeline_id"], ensure_running=False)
                if result["status"] in {"accepted", "running", "waiting"}:
                    self._schedule(existing["pipeline_id"], app_url)
                return result, 200
            current_definitions = self._definition_rows(connection, item_id, payload.get("definition_ids", []))
            if current_definitions != preview["definitions"]:
                raise AnalysisContractError("計画受付中に定義が更新されました。", code="revision_conflict")
            current_item = self.find_item(item_id)
            if current_item is None or self.source_fingerprint(current_item) != snapshot["input_hash"]:
                raise AnalysisContractError("計画受付中に入力が更新されました。", code="revision_conflict")
            self._check_expected_definitions(payload, current_definitions, snapshot["input_hash"])
            connection.execute("""INSERT INTO analysis_pipeline_requests
                (pipeline_id,request_id,item_id,source_revision,analysis_revision,input_hash,plan_hash,
                 plan_json,binding_json,snapshot_json,status,current_milestone,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,'accepted','M0',?,?)""",
                (pipeline_id, request_id, item_id, item["revision_count"], item["analysis_revision"],
                 snapshot["input_hash"], preview["plan"]["plan_hash"],
                 canonical(preview["plan"]).decode("utf-8"), canonical(preview["binding"]).decode("utf-8"),
                 canonical(snapshot).decode("utf-8"), now, now),
            )
            for step in preview["plan"]["steps"]:
                attempt_id = uuid.uuid5(uuid.NAMESPACE_URL, pipeline_id + step["step_id"] + ":1").hex
                directive = {
                    "contract": "HandlerDirective", "pipeline_id": pipeline_id,
                    "step_id": step["step_id"], "attempt_id": attempt_id,
                    "generation": 1, "milestone": step["milestone"], "operation": "execute",
                    "input_hash": snapshot["input_hash"], "plan_hash": preview["plan"]["plan_hash"],
                }
                connection.execute("""INSERT INTO analysis_step_attempts
                    (attempt_id,pipeline_id,step_id,milestone,generation,attempt,status,directive_json,updated_at)
                    VALUES (?,?,?,?,?,1,'planned',?,?)""",
                    (attempt_id, pipeline_id, step["step_id"], step["milestone"], 1,
                     canonical(directive).decode("utf-8"), now),
                )
            for target in EFFECTIVE_PUBLICATION_WRITERS:
                connection.execute("""INSERT INTO analysis_pipeline_publications
                    (pipeline_id,target_role,status,updated_at) VALUES (?,?,'pending',?)""",
                    (pipeline_id, target, now),
                )
                if not preview["plan"]["publication_targets"]:
                    _transition_state(connection, "publication", (pipeline_id, target), "not_selected", generation=1)
            self._event(connection, pipeline_id, "pipeline_accepted", {
                "plan_hash": preview["plan"]["plan_hash"], "input_hash": snapshot["input_hash"]})
        self._schedule(pipeline_id, app_url)
        return self.status(item_id, pipeline_id, ensure_running=False), 202

    def _event(self, connection: sqlite3.Connection, pipeline_id: str, kind: str, payload: dict[str, Any]) -> None:
        _event(connection, pipeline_id, kind, payload)

    def _schedule(self, pipeline_id: str, app_url: str) -> None:
        key = self.runtime_key + ":" + pipeline_id
        with RUNTIME_LOCK:
            row = self._pipeline_row(pipeline_id, columns="status,generation")
            if row["status"] != "accepted":
                return
            generation = row["generation"]
            current = RUNTIMES.get(key)
            if current and current.is_alive() and getattr(current, "pipeline_generation", None) == generation:
                return
            thread = threading.Thread(
                target=self._run_guarded, args=(pipeline_id, app_url, key, generation),
                name=f"analysis-pipeline-{pipeline_id[:8]}-{generation}", daemon=True,
            )
            thread.pipeline_generation = generation
            RUNTIMES[key] = thread
            thread.start()

    def _run_guarded(self, pipeline_id: str, app_url: str, runtime_key: str,
                     generation: int | None = None) -> None:
        if generation is None:
            generation = self._pipeline_row(pipeline_id, columns="generation")["generation"]
        try:
            self._run(pipeline_id, app_url, generation=generation)
        except Exception as exc:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT pipeline_id,plan_hash,generation,status,cancel_requested FROM analysis_pipeline_requests WHERE pipeline_id=?", (pipeline_id,)).fetchone()
                if row and row["generation"] == generation and row["status"] not in {"completed", "cancelled", "failed"}:
                    decision = core.decide_failure([{"code": getattr(exc, "code", "execution_failed")}],
                        cancelled=bool(row["cancel_requested"]), context=dict(row), unexpected=True)
                    _record_decision(connection, pipeline_id, decision)
                    cancelled = decision["decision"]["action"] == "cancel"
                    if cancelled:
                        self._finish_cancelled(connection, pipeline_id, generation)
                        return
                    _transition_state(connection, "pipeline", (pipeline_id,), "failed", generation=generation,
                                      changes={"error": str(exc)[:1000]})
                    self._event(connection, pipeline_id, "pipeline_failed", {"error": str(exc)[:1000], "generation": generation})
        finally:
            with RUNTIME_LOCK:
                if RUNTIMES.get(runtime_key) is threading.current_thread():
                    RUNTIMES.pop(runtime_key, None)

    @staticmethod
    def _assert_current(connection: sqlite3.Connection, pipeline_id: str, generation: int,
                        *, allow_cancel: bool = False, attempt_id: str | None = None) -> None:
        row = connection.execute("SELECT generation,status,cancel_requested FROM analysis_pipeline_requests WHERE pipeline_id=?", (pipeline_id,)).fetchone()
        if row is None or row["generation"] != generation or row["status"] not in {"accepted", "running", "cancelling"}:
            raise AnalysisContractError("旧世代の実行結果は採用しません。", code="stale_generation")
        if not allow_cancel and row["cancel_requested"]:
            raise AnalysisContractError("保存確定前に取り消されました。", code="cancelled")
        if attempt_id is not None:
            step = connection.execute("SELECT step_id,generation,status FROM analysis_step_attempts WHERE attempt_id=? AND pipeline_id=?", (attempt_id, pipeline_id)).fetchone()
            latest = connection.execute("SELECT attempt_id FROM analysis_step_attempts WHERE pipeline_id=? AND step_id=? ORDER BY attempt DESC LIMIT 1",
                                        (pipeline_id, step["step_id"] if step else "")).fetchone()
            if (step is None or step["generation"] != generation or latest is None or latest["attempt_id"] != attempt_id
                    or step["status"] in TERMINAL_SUCCESS | {"failed", "cancelled", "interrupted"}):
                raise AnalysisContractError("旧試行の実行結果は採用しません。", code="stale_attempt")

    @contextmanager
    def _worker_transaction(self, pipeline_id: str, generation: int, *, allow_cancel: bool = False):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_current(connection, pipeline_id, generation, allow_cancel=allow_cancel)
            yield connection

    def _pipeline_row(self, pipeline_id: str, *, columns: str = (
        "pipeline_id,item_id,source_revision,analysis_revision,input_hash,plan_hash,"
        "status,generation,result_run_id"
    )) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT {columns} FROM analysis_pipeline_requests WHERE pipeline_id=?", (pipeline_id,)
            ).fetchone()
        if row is None:
            raise LookupError("分析pipelineが見つかりません。")
        return dict(row)

    def _cancelled(self, pipeline_id: str, generation: int) -> bool:
        row = self._pipeline_row(pipeline_id, columns="cancel_requested,generation")
        return bool(row["cancel_requested"]) or int(row["generation"]) != int(generation)

    def _cancel_attempt(self, connection: sqlite3.Connection, step: dict[str, Any],
                        generation: int, *, artifact: Any = None) -> None:
        """Record cancellation after the worker settles, preserving prior success."""
        if step["status"] in TERMINAL_SUCCESS | {"failed", "cancelled", "interrupted"}:
            return
        self._assert_current(connection, step["pipeline_id"], generation,
                             allow_cancel=True, attempt_id=step["attempt_id"])
        context = dict(connection.execute("SELECT pipeline_id,plan_hash,generation FROM analysis_pipeline_requests WHERE pipeline_id=?",
                                          (step["pipeline_id"],)).fetchone())
        decision = core.decide_cancel_step(step, context)
        _record_decision(connection, step["pipeline_id"], decision)
        now = utc_now()
        changes = {"error_code": "cancelled", "error": "取り消されました。確定済み成果は保持しています。", "ended_at": now}
        if artifact is not None:
            changes["artifact_json"] = canonical(artifact).decode("utf-8")
        for effect in decision["transitions"]:
            _transition_state(connection, "step", (step["attempt_id"],), effect["to"], generation=generation,
                guard_id=effect["guard_id"], changes=changes if effect == decision["transitions"][-1] else {})

    def _finish_cancelled(self, connection: sqlite3.Connection, pipeline_id: str,
                          generation: int, *, milestone: str | None = None) -> None:
        """Finalize only this generation, once all of its workers have settled."""
        self._assert_current(connection, pipeline_id, generation, allow_cancel=True)
        for step in _latest_steps(connection, pipeline_id):
            if step["generation"] == generation:
                self._cancel_attempt(connection, step, generation)
        # A terminal pipeline cannot truthfully claim an unobserved write is ongoing.
        for row in connection.execute("SELECT target_role FROM analysis_pipeline_publications WHERE pipeline_id=? AND status='publishing'", (pipeline_id,)).fetchall():
            _transition_state(connection, "publication", (pipeline_id, row["target_role"]), "unknown", generation=generation,
                              changes={"error": "取消時点の公開結果を確認できません。"})
        row = dict(connection.execute("SELECT pipeline_id,plan_hash,status,generation,cancel_requested FROM analysis_pipeline_requests WHERE pipeline_id=?", (pipeline_id,)).fetchone())
        decision = core.decide_cancel_pipeline(row)
        _record_decision(connection, pipeline_id, decision)
        changes = {"wait_reason": "", "error": ""}
        if milestone is not None:
            changes["current_milestone"] = milestone
        for effect in decision["transitions"]:
            _transition_state(connection, "pipeline", (pipeline_id,), effect["to"], generation=generation,
                guard_id=effect["guard_id"], changes=changes if effect == decision["transitions"][-1] else {})
        self._event(connection, pipeline_id, "pipeline_cancelled", {"generation": generation, "milestone": milestone})

    def _cancel_step(self, attempt_id: str, generation: int, *, artifact: Any = None) -> None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            step = connection.execute("SELECT * FROM analysis_step_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if step is None:
                raise AnalysisContractError("試行がありません。", code="stale_attempt")
            self._cancel_attempt(connection, dict(step), generation, artifact=artifact)

    def _fail_attempt(self, pipeline_id: str, attempt_id: str, generation: int, exc: Exception) -> None:
        with self._worker_transaction(pipeline_id, generation, allow_cancel=True) as connection:
            self._assert_current(connection, pipeline_id, generation, allow_cancel=True, attempt_id=attempt_id)
            context = dict(connection.execute("SELECT pipeline_id,plan_hash,generation,status,cancel_requested FROM analysis_pipeline_requests WHERE pipeline_id=?", (pipeline_id,)).fetchone())
            step = dict(connection.execute("SELECT * FROM analysis_step_attempts WHERE attempt_id=?", (attempt_id,)).fetchone())
            code = getattr(exc, "code", "execution_failed")
            decision = core.decide_failed_attempt(step, error_code=code, cancelled=bool(context["cancel_requested"]), context=context)
            if decision["decision"]["action"] == "cancel":
                self._cancel_attempt(connection, step, generation)
                return
            _record_decision(connection, pipeline_id, decision)
            effect = decision["transitions"][0]
            _transition_state(connection, "step", (attempt_id,), effect["to"], generation=generation,
                guard_id=effect["guard_id"], changes={"error_code": code, "error": str(exc)[:1000], "ended_at": utc_now()})

    def _set_step(self, attempt_id: str, status: str | tuple[str, ...], *, artifact: Any = None,
                  report: Any = None, error_code: str = "", error: str = "", generation: int,
                  decision: dict[str, Any] | None = None, reuse_key: str = "") -> None:
        now = utc_now()
        statuses = (status,) if isinstance(status, str) else status
        changes = {"error_code": error_code, "error": error}
        if statuses[-1] in TERMINAL_SUCCESS | {"failed", "cancelled", "interrupted"}:
            changes["ended_at"] = now
        if artifact is not None:
            changes["artifact_json"] = canonical(artifact).decode("utf-8")
            if statuses[-1] == "committed":
                changes.update(artifact_hash=fingerprint(artifact), reuse_key=reuse_key)
        if report is not None:
            changes["report_json"] = canonical(report).decode("utf-8")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            step = connection.execute("SELECT * FROM analysis_step_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if step is None:
                raise AnalysisContractError("試行がありません。", code="stale_attempt")
            self._assert_current(connection, step["pipeline_id"], generation,
                                 allow_cancel=statuses[-1] in {"cancelled", "failed"}, attempt_id=attempt_id)
            if decision:
                _record_decision(connection, step["pipeline_id"], decision)
                if "reuse_decision" in decision:
                    _record_decision(connection, step["pipeline_id"], decision["reuse_decision"])
            for target in statuses:
                metadata = changes if target == statuses[-1] else {}
                if target == "running" and not step["started_at"]:
                    metadata = {**metadata, "started_at": now}
                _transition_state(connection, "step", (attempt_id,), target, generation=generation, changes=metadata)

    def _execute_step(self, pipeline: dict[str, Any], step: dict[str, Any], snapshot: dict[str, Any],
                      definitions: list[dict[str, Any]], app_url: str, *,
                      dispatch_decision: dict[str, Any] | None = None) -> dict[str, Any]:
        attempt_id = step["attempt_id"]
        generation = int(step["generation"])
        if self._cancelled(pipeline["pipeline_id"], generation):
            self._cancel_step(attempt_id, generation)
            return {"status": "cancelled"}
        self._set_step(attempt_id, generation=generation, status="checking", decision=dispatch_decision)
        plan_steps = {value["step_id"]: value for value in json.loads(pipeline["plan_json"])["steps"]}
        spec = plan_steps[step["step_id"]]
        decision = core.decide_applicability(step["step_id"], spec, has_definitions=bool(definitions),
            has_targets=bool(json.loads(pipeline["plan_json"])["publication_targets"]), context=pipeline)
        if decision["decision"]["action"] == "mark_not_applicable":
            artifact = {"reason_code": "not_selected", "rule_version": "analysis-core-1", "verified_by": "analysis_core"}
            self._set_step(attempt_id, generation=generation, status="not_applicable", artifact=artifact,
                           report={"status": "not_applicable"}, decision=decision)
            return {"status": "not_applicable", "artifact": artifact}
        reuse_key = pipeline.get("_reuse_keys", {}).get(step["step_id"], "")
        if reuse_key:
            reuse_decision = core.decide_reuse(step["step_id"], reuse_key, pipeline.get("_reuse_candidates", []),
                mode=json.loads(pipeline["plan_json"]).get("reuse", "auto"), context=pipeline)
            if reuse_decision["decision"]["action"] == "reuse":
                source = reuse_decision["candidate"]
                artifact = json.loads(source["artifact_json"])
                with self._worker_transaction(pipeline["pipeline_id"], generation) as connection:
                    self._assert_current(connection, pipeline["pipeline_id"], generation, attempt_id=attempt_id)
                    _record_decision(connection, pipeline["pipeline_id"], decision)
                    _record_decision(connection, pipeline["pipeline_id"], reuse_decision)
                    _transition_state(connection, "step", (attempt_id,), "reused", generation=generation,
                        guard_id=reuse_decision["transitions"][0]["guard_id"], changes={
                            "artifact_json": source["artifact_json"], "artifact_hash": source["artifact_hash"],
                            "reuse_key": reuse_key, "reused_from": source["attempt_id"], "reused_at": source["ended_at"],
                            "ended_at": utc_now(), "report_json": canonical({"status": "reused",
                                "reused_from": source["attempt_id"], "artifact_hash": source["artifact_hash"]}).decode("utf-8")})
                    self._event(connection, pipeline["pipeline_id"], "step_reused", {
                        "step_id": step["step_id"], "attempt_id": attempt_id, "reused_from": source["attempt_id"],
                        "artifact_hash": source["artifact_hash"], "reuse_key": reuse_key, "generation": generation})
                return {"status": "reused", "artifact": artifact}
            # Both judgments belong to the existing dispatch transaction.
            decision = {**decision, "reuse_decision": reuse_decision}
        self._set_step(attempt_id, generation=generation, status=("ready", "running"), decision=decision)
        step_id = step["step_id"]
        if step_id == "freeze_input":
            artifact = {"input_hash": snapshot["input_hash"], "source_revision": pipeline["source_revision"],
                        "analysis_revision": pipeline["analysis_revision"]}
        elif step_id in {"participation", "conversation_dynamics"}:
            artifact = self.method_runner(step_id, copy.deepcopy(snapshot))
        elif step_id == "chart_specs":
            artifact = {"chart_specs": self._chart_specs(pipeline["pipeline_id"])}
        elif step_id == "execution_binding":
            artifact = json.loads(pipeline["binding_json"])
        elif step_id == "manual_measurement":
            rows = measure_segments(snapshot["analysis"], definitions)
            method, datasets = _manual_method(definitions, rows)
            artifact = {"method": method, "datasets": {name: {"fields": value[0], "rows": value[1]} for name, value in datasets.items()}}
        elif step_id == "save_result":
            if self._cancelled(pipeline["pipeline_id"], generation):
                raise AnalysisContractError("保存確定前に取り消されました。", code="cancelled")
            artifact = self._save_package(pipeline, snapshot, definitions, app_url, step=step)
        elif step_id == "publish_result":
            artifact = self._publish_package(pipeline, step=step)
            if any(value["status"] != "published" for value in artifact["outcomes"].values()
                   if value["status"] != "not_selected"):
                raise AnalysisContractError("選択したVaultへの公開を完了できませんでした。", code="publication_failed")
        else:
            raise AnalysisContractError("未対応のstepです。", code="step_unavailable")
        if self._cancelled(pipeline["pipeline_id"], generation):
            self._cancel_step(attempt_id, generation, artifact=artifact)
            return {"status": "cancelled", "artifact": artifact}
        self._set_step(attempt_id, generation=generation, status="validating")
        canonical(artifact)  # JSON/NaN validation before persistence
        self._set_step(attempt_id, generation=generation, status="persisting")
        report = {
            "contract": "HandlerReport", "pipeline_id": pipeline["pipeline_id"],
            "step_id": step_id, "attempt_id": attempt_id, "generation": generation,
            "status": "completed", "input_hash": pipeline["input_hash"],
        }
        self._set_step(attempt_id, generation=generation, status="committed", artifact=artifact, report=report, reuse_key=reuse_key)
        return {"status": "committed", "artifact": artifact}

    def _chart_specs(self, pipeline_id: str) -> list[dict[str, Any]]:
        artifacts = self._artifacts(pipeline_id)
        specs = []
        for method_id in ("participation", "conversation_dynamics"):
            artifact = artifacts.get(method_id, {})
            for dataset, table in artifact.get("datasets", {}).items():
                fields = table.get("fields", [])
                specs.append({
                    "chart_id": f"{pipeline_id}:{dataset}", "visual_id": f"V-{dataset}",
                    "dataset_ref": dataset, "source_hash": fingerprint(table.get("rows", [])),
                    "grain": "speaker" if dataset == "speakers" else "conversation_event",
                    "filters": [], "encodings": {"fields": fields}, "category_order": [],
                    "palette": "gurumoji-default", "value_format": "auto",
                    "denominator": "fixed_dataset", "missing_policy": "show",
                    "evidence_ref": "input_snapshot", "layout_ref": "table-or-deterministic-svg",
                    "title": dataset, "captions": {"unit": "dataset rows", "n": len(table.get("rows", []))},
                    "size": {"width": 960, "height": 540}, "font": "system-ui",
                })
        return specs

    def _artifacts(self, pipeline_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            steps = _latest_steps(connection, pipeline_id)
        values = {}
        for step in steps:
            if step["artifact_json"]:
                try:
                    values[step["step_id"]] = json.loads(step["artifact_json"])
                except json.JSONDecodeError:
                    continue
        return values

    def _save_package(self, pipeline: dict[str, Any], snapshot: dict[str, Any],
                      definitions: list[dict[str, Any]], app_url: str, *, step: dict[str, Any]) -> dict[str, Any]:
        artifacts = self._artifacts(pipeline["pipeline_id"])
        methods = []
        datasets: dict[str, tuple[list[str], list[dict[str, Any]]]] = {}
        for step_id in ("participation", "conversation_dynamics", "manual_measurement"):
            value = artifacts.get(step_id, {})
            if value.get("method"):
                methods.append(value["method"])
            for name, table in value.get("datasets", {}).items():
                datasets[name] = (table["fields"], table["rows"])
        plan = json.loads(pipeline["plan_json"])
        parameters = {
            "pipeline_id": pipeline["pipeline_id"], "plan_hash": pipeline["plan_hash"],
            "binding": json.loads(pipeline["binding_json"]), "definitions": definitions,
            "research_protocol": plan["research_protocol"],
            "publication_targets": validate_publication_targets(plan["publication_targets"]),
            "reused_steps": [],
        }
        with self.connect() as connection:
            parameters["reused_steps"] = [{key: value[key] for key in ("step_id", "reused_from", "artifact_hash")}
                for value in _latest_steps(connection, pipeline["pipeline_id"]) if value["status"] == "reused"]
        if "planning_proposal" in plan:
            parameters["planning_proposal"] = plan["planning_proposal"]
        result = {
            "schema_version": 1,
            "parameters": parameters,
            "algorithms": {"analysis_pipeline": core.PIPELINE_VERSION,
                           "automatic": snapshot.get("analysis", {}).get("algorithm_version")},
            "methods": methods, "chart_specs": artifacts.get("chart_specs", {}).get("chart_specs", []),
        }
        request_id = "pipeline-result-" + pipeline["pipeline_id"]
        run = self.save_result(
            item_id=pipeline["item_id"], kind="milestone_analysis",
            snapshot=snapshot["archive_snapshot"], result=result, datasets=datasets,
            request_id=request_id, input_fingerprint=pipeline["input_hash"],
            source_revision=pipeline["source_revision"], analysis_revision=pipeline["analysis_revision"],
            app_url=app_url, publish=False,
            commit_guard=lambda connection: self._assert_current(connection, pipeline["pipeline_id"], step["generation"], attempt_id=step["attempt_id"]),
        )
        current_item = self.find_item(pipeline["item_id"])
        if current_item is None or self.source_fingerprint(current_item) != pipeline["input_hash"]:
            with self.connect() as connection:
                connection.execute("UPDATE analysis_runs SET stale=1 WHERE id=?", (run["id"],))
            run = {**run, "stale": 1}
        package_hash = str(run.get("fingerprint") or fingerprint({"run_id": run["id"], "methods": methods}))
        with self._worker_transaction(pipeline["pipeline_id"], step["generation"], allow_cancel=True) as connection:
            self._assert_current(connection, pipeline["pipeline_id"], step["generation"], allow_cancel=True, attempt_id=step["attempt_id"])
            connection.execute(
                "UPDATE analysis_pipeline_requests SET result_run_id=?,updated_at=? WHERE pipeline_id=?",
                (run["id"], utc_now(), pipeline["pipeline_id"]),
            )
            connection.execute(
                "UPDATE analysis_pipeline_publications SET result_run_id=?,package_hash=?,updated_at=? WHERE pipeline_id=?",
                (run["id"], package_hash, utc_now(), pipeline["pipeline_id"]),
            )
        return {"result_run_id": run["id"], "package_hash": package_hash, "status": run["status"]}

    def _publish_package(self, pipeline: dict[str, Any], *, step: dict[str, Any]) -> dict[str, Any]:
        current = self._pipeline_row(pipeline["pipeline_id"], columns="pipeline_id,result_run_id,plan_json")
        run_id = current["result_run_id"]
        if not run_id:
            raise AnalysisContractError("保存済みresult_runがありません。", code="publication_failed")
        selected = validate_publication_targets(json.loads(current["plan_json"])["publication_targets"])
        effective = list(EFFECTIVE_PUBLICATION_WRITERS) if selected else []
        if not effective:
            return {"result_run_id": run_id, "outcomes": {kind: {"status": "not_selected"} for kind in EFFECTIVE_PUBLICATION_WRITERS}}
        with self._worker_transaction(current["pipeline_id"], step["generation"]) as connection:
            self._assert_current(connection, current["pipeline_id"], step["generation"], attempt_id=step["attempt_id"])
            for kind in effective:
                _transition_state(connection, "publication", (current["pipeline_id"], kind), "publishing",
                    generation=step["generation"], changes={"result_run_id": run_id, "error": "",
                    "attempt_id": step["attempt_id"], "generation": step["generation"]})
        publication_error = ""
        try:
            self.publish_result(run_id, targets=selected, commit_guard=lambda connection: self._assert_current(
                connection, current["pipeline_id"], step["generation"], attempt_id=step["attempt_id"]))
        except Exception as exc:
            publication_error = str(exc)[:1000]
        # Read-only reconciliation is permitted after cancellation: an exception
        # is not proof that already completed filesystem writes were rolled back.
        try:
            reported = self.publication_outcomes(run_id)
        except Exception as exc:
            reported = {}
            publication_error = publication_error or str(exc)[:1000]
        outcomes = {}
        for kind in effective:
            value = reported.get(kind, {})
            outcomes[kind] = (value if value.get("status") in {"published", "failed", "conflict", "unknown"}
                              else {"status": "unknown", "error": publication_error or "公開結果を確認できません。"})
        with self._worker_transaction(current["pipeline_id"], step["generation"], allow_cancel=True) as connection:
            self._assert_current(connection, current["pipeline_id"], step["generation"], allow_cancel=True, attempt_id=step["attempt_id"])
            for target, value in outcomes.items():
                _transition_state(connection, "publication", (current["pipeline_id"], target), value["status"],
                    generation=step["generation"], changes={"error": str(value.get("error") or "")})
        return {"result_run_id": run_id, "outcomes": outcomes}

    def _run(self, pipeline_id: str, app_url: str, *, generation: int | None = None) -> None:
        pipeline = self._pipeline_row(pipeline_id, columns=(
            "pipeline_id,item_id,source_revision,analysis_revision,input_hash,plan_hash,"
            "status,generation,result_run_id,snapshot_json,plan_json,binding_json"
        ))
        if pipeline["status"] != "accepted" or (generation is not None and generation != pipeline["generation"]):
            return
        generation = pipeline["generation"]
        definitions = self._bound_definitions(pipeline)
        snapshot = json.loads(pipeline["snapshot_json"])
        if snapshot.get("input_hash") != pipeline["input_hash"]:
            raise AnalysisContractError("固定入力のhashが一致しません。", code="binding_conflict")
        from .services.analysis_pipeline_adapters import validate_pipeline_snapshot
        validate_pipeline_snapshot(snapshot)
        plan = json.loads(pipeline["plan_json"])
        binding = json.loads(pipeline["binding_json"])
        analysis_hash = core.reuse_analysis_hash(snapshot["analysis"])
        definition_hashes = [s["definition_hash"] for s in binding.get("resolved", [])]
        pipeline["_reuse_keys"] = {spec["step_id"]: core.step_reuse_key(
            library=self.runtime_key, item_id=pipeline["item_id"], spec=spec,
            analysis_hash=analysis_hash,
            registry_version=REGISTRY_VERSION, algorithm_version=snapshot["analysis"].get("algorithm_version"),
            definition_hashes=definition_hashes) for spec in plan["steps"]}
        keys = [key for key in pipeline["_reuse_keys"].values() if key]
        pipeline["_reuse_candidates"] = []
        if keys and plan.get("reuse", "auto") == "auto":
            with self.connect() as connection:
                pipeline["_reuse_candidates"] = [dict(row) for row in connection.execute(
                    "SELECT attempt_id,step_id,status,reuse_key,artifact_hash,artifact_json,ended_at "
                    "FROM analysis_step_attempts WHERE reuse_key IN (" + ",".join("?" for _ in keys) + ") "
                    "AND status='committed' AND artifact_hash<>'' AND pipeline_id<>? ORDER BY ended_at DESC,attempt_id",
                    (*keys, pipeline_id)).fetchall()]
        # Previously accepted snapshots must meet the same effective-input gate.
        segment_count = len(_included_segments(snapshot["analysis"]))
        if eligibility_assessment(definitions, segment_count=segment_count)["execution"] != "allowed":
            raise AnalysisContractError(
                "必須の適用性検査に合格していません。" if segment_count else "分析できる発話がありません。",
                code="ineligible" if segment_count else "no_valid_input",
            )
        with self._worker_transaction(pipeline_id, generation) as connection:
            if connection.execute("SELECT status FROM analysis_pipeline_requests WHERE pipeline_id=?", (pipeline_id,)).fetchone()[0] != "accepted":
                return
            _transition_state(connection, "pipeline", (pipeline_id,), "running", generation=generation,
                              changes={"wait_reason": "", "error": ""})
            self._event(connection, pipeline_id, "pipeline_running", {"generation": generation})
        for milestone in MILESTONES:
            pipeline.update(self._pipeline_row(pipeline_id))
            if self._cancelled(pipeline_id, generation):
                with self._worker_transaction(pipeline_id, generation, allow_cancel=True) as connection:
                    self._finish_cancelled(connection, pipeline_id, generation, milestone=milestone)
                return
            plan_steps = {
                value["step_id"]: value
                for value in json.loads(pipeline["plan_json"])["steps"]
            }
            with self._worker_transaction(pipeline_id, generation) as connection:
                connection.execute(
                    "UPDATE analysis_pipeline_requests SET current_milestone=?,updated_at=? WHERE pipeline_id=?",
                    (milestone, utc_now(), pipeline_id),
                )
                self._event(connection, pipeline_id, "milestone_started", {"milestone": milestone})
            while True:
                with self._worker_transaction(pipeline_id, generation) as connection:
                    all_steps = _latest_steps(connection, pipeline_id)
                    dispatch = core.decide_dispatch(all_steps, plan_steps, milestone, pipeline)
                if dispatch["decision"]["action"] == "release_gate":
                    break
                ready = [s for s in all_steps if s["step_id"] in dispatch["decision"]["affected_steps"]]
                if dispatch["decision"]["action"] == "fail":
                    raise AnalysisContractError(
                        "親stepが未確定のため段階を進められません。", code="parent_incomplete"
                    )
                # M2 has two independent adapters and is observably concurrent.
                # Parent-dependent M7 publication is selected only after save_result.
                with ThreadPoolExecutor(max_workers=max(1, min(2, len(ready))),
                                        thread_name_prefix=f"{milestone}-analysis") as executor:
                    futures = {
                        executor.submit(self._execute_step, pipeline, step, snapshot, definitions, app_url,
                                        dispatch_decision=dispatch): step
                        for step in ready
                    }
                    failed: list[tuple[dict[str, Any], Exception]] = []
                    for future in as_completed(futures):
                        step = futures[future]
                        try:
                            future.result()
                        except Exception as exc:
                            try:
                                self._fail_attempt(pipeline_id, step["attempt_id"], generation, exc)
                            except AnalysisContractError as stale:
                                if stale.code not in {"stale_generation", "stale_attempt"}:
                                    raise
                            failed.append((step, exc))
                    if self._cancelled(pipeline_id, generation):
                        with self._worker_transaction(pipeline_id, generation, allow_cancel=True) as connection:
                            self._finish_cancelled(connection, pipeline_id, generation, milestone=milestone)
                        return
                    if failed:
                        decision = core.decide_failure([{"step_id": s["step_id"], "code": getattr(exc, "code", "execution_failed")}
                            for s, exc in failed], cancelled=False, context=pipeline)
                        reason = decision["wait_reason"]
                        with self._worker_transaction(pipeline_id, generation) as connection:
                            _record_decision(connection, pipeline_id, decision)
                            _transition_state(connection, "pipeline", (pipeline_id,), "waiting", generation=generation,
                                changes={"wait_reason": reason, "error": str(failed[0][1])[:1000]})
                            self._event(connection, pipeline_id, "milestone_waiting", {
                                "milestone": milestone, "reason": reason,
                                "failed_steps": [value[0]["step_id"] for value in failed]})
                        return
            with self._worker_transaction(pipeline_id, generation) as connection:
                final_steps = [step for step in _latest_steps(connection, pipeline_id) if step["milestone"] == milestone]
                if core.derive_milestone_status(final_steps) != "committed":
                    raise AnalysisContractError("段階の必須stepが未確定です。", code="gate_incomplete")
                _record_decision(connection, pipeline_id, dispatch)
                self._event(connection, pipeline_id, "milestone_committed", {"milestone": milestone})
        current = self._pipeline_row(pipeline_id, columns="result_run_id")
        with self._worker_transaction(pipeline_id, generation) as connection:
            publications = connection.execute(
                "SELECT * FROM analysis_pipeline_publications WHERE pipeline_id=?", (pipeline_id,)
            ).fetchall()
            decision = core.decide_completion([dict(row) for row in publications], pipeline)
            _record_decision(connection, pipeline_id, decision)
            if decision["decision"]["action"] != "commit":
                _transition_state(connection, "pipeline", (pipeline_id,), "waiting", generation=generation,
                                  changes={"wait_reason": "publication"})
                return
            _transition_state(connection, "pipeline", (pipeline_id,), "completed", generation=generation,
                              changes={"wait_reason": "", "error": "", "current_milestone": "M7"})
            self._event(connection, pipeline_id, "pipeline_completed", {"result_run_id": current["result_run_id"]})

    def status(self, item_id: str, pipeline_id: str, *, ensure_running: bool = True) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("BEGIN")
            row = connection.execute("""SELECT request_id,status,generation,current_milestone,wait_reason,
                cancel_requested,result_run_id,error,plan_hash,input_hash,
                json_extract(plan_json,'$.planning_proposal') AS planning_proposal_json
                FROM analysis_pipeline_requests WHERE pipeline_id=? AND item_id=?""", (pipeline_id, item_id)).fetchone()
            if row is None:
                raise LookupError("分析pipelineが見つかりません。")
            row = dict(row)
            steps = _latest_steps(connection, pipeline_id, include_payload=False)
            publications = [dict(value) for value in connection.execute(
                "SELECT target_role,status,error,result_run_id,package_hash FROM analysis_pipeline_publications WHERE pipeline_id=? ORDER BY target_role",
                (pipeline_id,),
            ).fetchall()]
            restart_pending = _has_restart_event(connection, pipeline_id, row["generation"])
            # New decision records must not evict the existing 80-event progress
            # history. Bound each stream separately and retain sequence order.
            events = [dict(value) for value in connection.execute(
                """WITH progress AS (
                    SELECT sequence,event_type,payload_json,created_at FROM analysis_pipeline_events
                    WHERE pipeline_id=? AND event_type<>'core_decision' ORDER BY sequence DESC LIMIT 80),
                decisions AS (
                    SELECT sequence,event_type,payload_json,created_at FROM analysis_pipeline_events
                    WHERE pipeline_id=? AND event_type='core_decision' ORDER BY sequence DESC LIMIT 80)
                SELECT * FROM progress UNION ALL SELECT * FROM decisions ORDER BY sequence""",
                (pipeline_id,pipeline_id),
            ).fetchall()]
        # ensure_running is retained for callers of the old API; GET never writes.
        restart_pending = bool(restart_pending and row["status"] == "waiting"
                               and row["wait_reason"] == "retry" and not row["cancel_requested"])
        recovery_error = core.recovery_error(steps) if restart_pending else ""
        milestones = []
        for milestone in MILESTONES:
            values = [step for step in steps if step["milestone"] == milestone]
            status = core.derive_milestone_status(values)
            milestones.append({"id": milestone, "status": status, "steps": [self._public_step(value) for value in values]})
        result_run = None
        if row["result_run_id"]:
            try:
                result_run = self.public_run({"id": row["result_run_id"]})
            except (LookupError, KeyError, TypeError):
                result_run = {"id": row["result_run_id"]}
        completed = sum(step["status"] in TERMINAL_SUCCESS for step in steps)
        proposal = json.loads(row["planning_proposal_json"]) if row["planning_proposal_json"] else None
        planning = ({key: proposal[key] for key in
                     ("objective", "provider", "model", "primary_method")}
                    if isinstance(proposal, dict) else None)
        return {
            "contract": "AnalysisResponse", "pipeline_id": pipeline_id,
            "request_id": row["request_id"], "item_id": item_id, "status": row["status"], "generation": row["generation"],
            "current_milestone": row["current_milestone"], "wait_reason": row["wait_reason"],
            "error": row["error"], "plan_hash": row["plan_hash"], "input_hash": row["input_hash"],
            "progress": round(100 * completed / len(steps)) if steps else 0,
            "planning": planning,
            "recovery": {"pending": restart_pending, "mode": "blocked" if recovery_error else
                         "manual" if restart_pending else "none",
                         "reason_code": recovery_error},
            "milestones": milestones,
            "publications": [{key: value[key] for key in ("target_role", "status", "error", "result_run_id", "package_hash")} for value in publications],
            "events": [{"sequence": value["sequence"], "type": value["event_type"],
                        "payload": json.loads(value["payload_json"]), "created_at": value["created_at"]} for value in events],
            "result_run": result_run,
            "allowed_actions": core.derive_allowed_actions(row, steps, restart_pending=restart_pending),
            "summary": {"completed": completed, "total": len(steps),
                        "failed": sum(step["status"] == "failed" for step in steps),
                        "not_applicable": sum(step["status"] == "not_applicable" for step in steps)},
        }

    @staticmethod
    def _public_step(value: dict[str, Any]) -> dict[str, Any]:
        return {key: value[key] for key in (
            "step_id", "attempt_id", "attempt", "status", "error_code", "error",
            "started_at", "updated_at", "ended_at",
            "reused_from", "reused_at",
        )}

    @staticmethod
    def _allowed_actions(row: dict[str, Any], steps: list[dict[str, Any]]) -> list[str]:
        return core.derive_allowed_actions(row, steps)

    def cancel(self, item_id: str, pipeline_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM analysis_pipeline_requests WHERE pipeline_id=? AND item_id=?", (pipeline_id, item_id)).fetchone()
            if row is None:
                raise LookupError("分析pipelineが見つかりません。")
            if row["status"] not in {"completed", "failed", "cancelled"}:
                if row["status"] != "cancelling":
                    _transition_state(connection, "pipeline", (pipeline_id,), "cancelling", generation=row["generation"],
                                      changes={"cancel_requested": 1})
                    self._event(connection, pipeline_id, "cancel_requested", {"generation": row["generation"]})
                if row["status"] in {"accepted", "waiting"}:
                    self._finish_cancelled(connection, pipeline_id, row["generation"])
        return self.status(item_id, pipeline_id, ensure_running=False)

    def retry(self, item_id: str, pipeline_id: str, payload: dict[str, Any], *, app_url: str) -> dict[str, Any]:
        return self._retry(item_id, pipeline_id, payload, app_url=app_url, resuming=False)

    def resume(self, item_id: str, pipeline_id: str, payload: dict[str, Any], *, app_url: str) -> dict[str, Any]:
        return self._retry(item_id, pipeline_id, payload, app_url=app_url, resuming=True)

    def _retry(self, item_id: str, pipeline_id: str, payload: dict[str, Any], *, app_url: str,
               resuming: bool) -> dict[str, Any]:
        target = payload.get("step_id")
        if resuming and target:
            raise AnalysisContractError("再開では残る全stepを対象とします。step_idは指定できません。", code="invalid_resume")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM analysis_pipeline_requests WHERE pipeline_id=? AND item_id=?", (pipeline_id, item_id)).fetchone()
            if row is None:
                raise LookupError("分析pipelineが見つかりません。")
            if row["status"] in {"cancelled", "failed"}:
                raise AnalysisContractError("この分析は終了しています。新しいrequest_idで分析を開始してください。", code="pipeline_terminal")
            if row["status"] in {"accepted", "running", "cancelling"}:
                raise AnalysisContractError("実行または中止処理の完了を待ってから再試行してください。", code="retry_in_progress")
            if row["status"] == "completed":
                if resuming:
                    raise AnalysisContractError("この分析は終了しています。", code="pipeline_terminal")
                return self.status(item_id, pipeline_id, ensure_running=False)
            restart_pending = _has_restart_event(connection, pipeline_id, row["generation"])
            if resuming and not restart_pending:
                raise AnalysisContractError("再起動後の再開待ちではありません。", code="nothing_to_resume")
            if not resuming and restart_pending:
                raise AnalysisContractError("再起動後は再開操作を使用してください。", code="resume_required")
            if resuming:
                self._validate_resume(dict(row))
            if "publication_targets" in payload and validate_publication_targets(payload["publication_targets"]) != json.loads(row["plan_json"])["publication_targets"]:
                raise AnalysisContractError("再試行で公開範囲を変更できません。", code="publication_scope_conflict")
            if "result_run_id" in payload and payload["result_run_id"] != row["result_run_id"]:
                raise AnalysisContractError("再試行で固定packageを変更できません。", code="publication_scope_conflict")
            steps = _latest_steps(connection, pipeline_id)
            decision = core.decide_retry(steps, dict(row), target=target, restart_pending=restart_pending)
            if decision["error_code"]:
                messages = {"retry_in_progress": "未確定の試行が残っています。",
                            "nothing_to_retry": "再試行できるstepがありません。",
                            "retry_limit_reached": "再試行上限に達しました。完了済み成果を保持して停止します。"}
                raise AnalysisContractError(messages[decision["error_code"]], code=decision["error_code"])
            _record_decision(connection, pipeline_id, decision)
            candidates = [s for s in steps if s["step_id"] in decision["decision"]["affected_steps"]]
            generation = int(row["generation"]) + 1
            candidate_ids = {value["step_id"] for value in candidates}
            for old in candidates:
                attempt = int(old["attempt"]) + 1
                attempt_id = uuid.uuid5(uuid.NAMESPACE_URL, pipeline_id + old["step_id"] + f":{attempt}").hex
                directive = json.loads(old["directive_json"])
                directive.update(attempt_id=attempt_id, generation=generation)
                connection.execute("""INSERT INTO analysis_step_attempts
                    (attempt_id,pipeline_id,step_id,milestone,generation,attempt,status,directive_json,updated_at)
                    VALUES (?,?,?,?,?,?, 'planned',?,?)""",
                    (attempt_id, pipeline_id, old["step_id"], old["milestone"], generation, attempt,
                     canonical(directive).decode("utf-8"), utc_now()),
                )
            for future in steps:
                if future["status"] != "planned" or future["step_id"] in candidate_ids:
                    continue
                directive = json.loads(future["directive_json"] or "{}")
                directive["generation"] = generation
                connection.execute(
                    "UPDATE analysis_step_attempts SET generation=?,directive_json=?,updated_at=? WHERE attempt_id=?",
                    (generation, canonical(directive).decode("utf-8"), utc_now(), future["attempt_id"]),
                )
            _transition_state(connection, "pipeline", (pipeline_id,), "accepted", generation=row["generation"],
                changes={"wait_reason": "", "error": "", "cancel_requested": 0, "generation": generation})
            self._event(connection, pipeline_id, "resume_accepted" if resuming else "retry_accepted",
                        {"steps": [value["step_id"] for value in candidates], "generation": generation})
        self._schedule(pipeline_id, app_url)
        return self.status(item_id, pipeline_id, ensure_running=False)

    def _validate_resume(self, row: dict[str, Any]) -> None:
        """Revalidate fixed input, policy and binding; attempt budget is checked in _retry."""
        item = self.find_item(row["item_id"])
        if item is None:
            raise LookupError("対象の会話が見つかりません。")
        if (item["revision_count"] != row["source_revision"] or item["analysis_revision"] != row["analysis_revision"]
                or self.source_fingerprint(item) != row["input_hash"]):
            raise AnalysisContractError("入力版が更新されています。新しい分析を開始してください。", code="revision_conflict")
        plan = json.loads(row["plan_json"])
        snapshot = json.loads(row["snapshot_json"])
        if (snapshot.get("input_hash") != row["input_hash"] or plan.get("input_hash") != row["input_hash"]
                or plan.get("plan_hash") != row["plan_hash"]
                or fingerprint({key: value for key, value in plan.items() if key != "plan_hash"}) != row["plan_hash"]):
            raise AnalysisContractError("固定入力・計画のhashが一致しません。", code="binding_conflict")
        from .services.analysis_pipeline_adapters import validate_pipeline_snapshot
        validate_pipeline_snapshot(snapshot)
        definitions = self._bound_definitions(row)
        checked = build_plan_envelope(item_id=row["item_id"], source_revision=row["source_revision"],
            analysis_revision=row["analysis_revision"], input_fingerprint=row["input_hash"], payload=plan,
            definitions=definitions, segment_count=len(_included_segments(snapshot["analysis"])))
        if checked["eligibility"]["execution"] != "allowed":
            raise AnalysisContractError("分析できる発話がありません。", code="no_valid_input")
