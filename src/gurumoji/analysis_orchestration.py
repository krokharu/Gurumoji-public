"""Durable, evidence-linked exploratory Core/Handler orchestration.

The Handler is the only execution authority. Injected agents return data (intents,
results and decisions); they never receive executors or mutable application state.
SQLite is the source of truth. An interrupted external call is explicitly uncertain,
not retried: recovery may adopt an already-received raw response or abandon a call.
This module does not send data, publish notes, or change source annotations itself.
"""
from __future__ import annotations

import copy
from difflib import SequenceMatcher
import json
import hashlib
import math
import sqlite3
import threading
import time
import uuid
import unicodedata
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable

from .analysis_core import (AnalysisContractError, canonical, fingerprint,
                            validate_publication_targets, validate_label_definitions, EFFECTIVE_PUBLICATION_WRITERS)
from .services import artifact_review
from .orchestration_initial import (initialize_initial_checkpoints, create_initial_checkpoints,
    read_initial_checkpoints, stage_input_hash, write_stage, initial_progress, recover_initial_checkpoints)

SCHEMA_VERSION = 1
ROLES = {"core": "Core", "handler": "Handler", "interpretation": "会話解釈",
         "statistics": "数量・統計", "verification": "独立検証", "critic": "批判者",
         "orchestrator": "専門オーケストレータ"}
AI_ROLES = frozenset({"core", "interpretation", "verification", "critic", "orchestrator"})
INITIAL_SECTIONS = frozenset({"segments", "annotations", "automatic", "manual", "research", "config", "cautions", "classification"})
LABEL_FIELDS = frozenset({"code", "codes", "theme", "sentiment", "dialogue_act", "importance", "review", "category"})
METHODS = frozenset({"participation", "conversation_dynamics", "label_frequency"})
TERMINAL = frozenset({"completed", "stopped", "cancelled", "failed"})
IMPORTANCE = {"low": 1, "medium": 2, "high": 3}


def _id(prefix: str) -> str:
    return prefix + "_" + uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return canonical(value).decode("utf-8")


def _error(message: str, code: str = "invalid_request", field: str = "") -> AnalysisContractError:
    return AnalysisContractError(message, code=code, field=field)


def _scope(intent):
    value = intent.get("scope")
    return value if isinstance(value, dict) else {}


def initialize_orchestration_store(connection: sqlite3.Connection) -> None:
    """Additive schema only; initialization never modifies an active execution."""
    schema = """
    CREATE TABLE IF NOT EXISTS orchestration_initials (
      initial_id TEXT PRIMARY KEY, identity TEXT NOT NULL UNIQUE, item_id TEXT NOT NULL,
      status TEXT NOT NULL, snapshot_json TEXT, snapshot_hash TEXT, error TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orchestration_runs (
      run_id TEXT PRIMARY KEY, item_id TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE,
      request_hash TEXT NOT NULL, initial_id TEXT NOT NULL, state_json TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS orchestration_runs_item ON orchestration_runs(item_id);
    CREATE TABLE IF NOT EXISTS orchestration_tasks (
      task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
      state_json TEXT NOT NULL, UNIQUE(run_id,idempotency_key));
    CREATE TABLE IF NOT EXISTS orchestration_results (
      result_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL UNIQUE,
      raw_json TEXT NOT NULL, state_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orchestration_events (
      seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, payload_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orchestration_decisions (
      decision_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, result_id TEXT NOT NULL UNIQUE,
      payload_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orchestration_issues (
      issue_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, issue_key TEXT NOT NULL,
      target_id TEXT NOT NULL, target_version TEXT NOT NULL, evidence_version TEXT NOT NULL,
      payload_json TEXT NOT NULL, UNIQUE(run_id,issue_key,target_id,target_version,evidence_version));
    CREATE TABLE IF NOT EXISTS orchestration_responses (
      response_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, issue_id TEXT NOT NULL,
      decision_id TEXT NOT NULL, payload_json TEXT NOT NULL, UNIQUE(issue_id,decision_id));
    CREATE TABLE IF NOT EXISTS orchestration_label_versions (
      run_id TEXT NOT NULL, annotation_version INTEGER NOT NULL, payload_json TEXT NOT NULL,
      PRIMARY KEY(run_id,annotation_version));
    CREATE TABLE IF NOT EXISTS orchestration_label_proposals (
      proposal_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, result_id TEXT NOT NULL,
      payload_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orchestration_label_audit (
      event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, proposal_id TEXT NOT NULL,
      payload_json TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS orchestration_label_audit_run ON orchestration_label_audit(run_id,proposal_id);
    CREATE TABLE IF NOT EXISTS orchestration_usage (
      usage_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL, payload_json TEXT NOT NULL);
    """
    initialize_initial_checkpoints(connection)
    for statement in schema.split(";"):
        if statement.strip():
            connection.execute(statement)
    # This ledger has no mutable status: each proposal and disposition is a new
    # row. Protect accidental rewrites even outside the orchestration service.
    for action in ("UPDATE", "DELETE"):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS orchestration_label_audit_no_{action.lower()}
            BEFORE {action} ON orchestration_label_audit BEGIN
            SELECT RAISE(ABORT, 'label audit is append-only'); END""")


def recover_orchestration_runs(connection: sqlite3.Connection) -> None:
    """Startup-only recovery marker. Never invoke while this process runs jobs.

    Recovery preserves received results and makes uncertain calls explicit. It
    never launches workers and never promises exactly-once provider execution.
    """
    recover_initial_checkpoints(connection)
    rows = connection.execute("SELECT run_id,state_json FROM orchestration_runs").fetchall()
    for row in rows:
        run_id, encoded = row[0], row[1]
        run = json.loads(encoded)
        if run["status"] not in {"running", "queued"}:
            continue
        for task_row in connection.execute("SELECT task_id,state_json FROM orchestration_tasks WHERE run_id=?", (run_id,)).fetchall():
            task = json.loads(task_row[1])
            if task["status"] in {"running", "cancel_requested"}:
                received = connection.execute("SELECT 1 FROM orchestration_results WHERE task_id=?", (task_row[0],)).fetchone()
                task.update(status="received" if received else "uncertain", error="" if received else "execution_outcome_unknown")
                connection.execute("UPDATE orchestration_tasks SET state_json=? WHERE task_id=?", (_json(task), task_row[0]))
        run.update(status="recovery_required", error="実行環境が再起動しました。保存状態を確認して明示的に再開してください。", updated_at=_now())
        connection.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (_json(run), run_id))


def validate_orchestration_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _error("分析設定はオブジェクトで指定してください。")
    if payload.get("research_mode", payload.get("research_protocol", "exploratory")) != "exploratory":
        raise _error("この実装は探索分析専用です。隔離検証データを伴う確認分析には未対応です。", "confirmatory_unavailable")
    question = payload.get("question", payload.get("objective", "会話の特徴と代替説明を根拠付きで分析する"))
    if not isinstance(question, str) or not question.strip() or len(question) > 8000:
        raise _error("分析する問いを指定してください。", field="question")
    mode = payload.get("stop_mode", "auto")
    if mode not in {"time", "iterations", "importance", "auto"}:
        raise _error("終了モードが正しくありません。", field="stop_mode")
    config = {"question": question.strip(), "stop_mode": mode, "research_mode": "exploratory",
              "provider": payload.get("provider", "lmstudio"), "model": payload.get("model", ""),
              "provider_policy": payload.get("provider_policy", "local_only"),
              "cloud_consent": payload.get("cloud_consent") is True,
              "adapter_version": payload.get("adapter_version", "core-handler-prompts-1"),
              "core_progress_version": payload.get("core_progress_version", 0),
              "initial_label_definitions_version": payload.get("initial_label_definitions_version", 0),
              "initial_specialist_analysis_version": payload.get("initial_specialist_analysis_version", 0),
              "model_context_version": payload.get("model_context_version", 0),
              "context_reference_version": payload.get("context_reference_version", 0),
              "specialist_orchestration_version": payload.get("specialist_orchestration_version", 0),
              "expert_step_ids": payload.get("expert_step_ids"),
              "template_version": payload.get("template_version", "existing-analysis-v1"),
              "template_config": payload.get("template_config", {}), "roles": payload.get("roles", {}),
              "importance_threshold": payload.get("importance_threshold", "medium"),
              "min_iterations": 3 if mode == "auto" and not payload.get("specialist_orchestration_version") else 0,
              "max_iterations": payload.get("max_iterations", None if mode == "auto" else 5),
              "time_limit_seconds": payload.get("time_limit_seconds", None if mode == "auto" else 300),
              "max_calls": payload.get("max_calls", 24), "max_tasks": payload.get("max_tasks", 40),
              "concurrency": payload.get("concurrency", 2),
              "call_timeout_seconds": payload.get("call_timeout_seconds", 120),
              "max_result_bytes": payload.get("max_result_bytes", 2_000_000),
              "max_cost": payload.get("max_cost"),
              "context_index_limit": payload.get("context_index_limit", 0),
              "context_evidence_limit": payload.get("context_evidence_limit", 120),
              "context_text_limit": payload.get("context_text_limit", 60000)}
    config["analysis_interval_version"] = payload.get("analysis_interval_version", 0)
    config["artifact_review_version"] = payload.get("artifact_review_version", 0)
    if config["artifact_review_version"] and not (config["analysis_interval_version"] == 1
            and config["specialist_orchestration_version"] == 1):
        raise _error("先行所見の点検には固定区間と専門側の判断が必要です。", "artifact_input_invalid")
    if config["artifact_review_version"]:
        from .method_experts import counterexample_review_procedure
        procedure = counterexample_review_procedure()
        config["artifact_procedure"] = {k: procedure[k] for k in ("procedure_id", "version", "sha256")}
    config["analysis_interval_seconds"] = payload.get("analysis_interval_seconds", 300)
    for key, low, high in (("max_calls", 1, 10000), ("max_tasks", 1, 20000), ("concurrency", 1, 4),
                           ("core_progress_version", 0, 1),
                           ("analysis_interval_version", 0, 1), ("analysis_interval_seconds", 1, 86400),
                           ("artifact_review_version", 0, 1),
                           ("initial_label_definitions_version", 0, 1),
                            ("initial_specialist_analysis_version", 0, 1),
                            ("model_context_version", 0, 1),
                            ("context_reference_version", 0, 1),
                            ("specialist_orchestration_version", 0, 1),
                           ("call_timeout_seconds", 1, 3600), ("max_result_bytes", 1000, 20_000_000),
                           ("context_evidence_limit", 1, 120), ("context_text_limit", 1, 60000)):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise _error(f"{key}は{low}〜{high}の整数です。", field=key)
    steps = config["expert_step_ids"]
    if steps is not None and (not isinstance(steps, list) or not 0 < len(steps) <= 30 or any(not isinstance(step, str) or not step for step in steps) or len(set(steps)) != len(steps)):
        raise _error("専門家の手順IDを重複のない配列で指定してください。", field="expert_step_ids")
    if type(config["context_index_limit"]) is not int or not 0 <= config["context_index_limit"] <= 120:
        raise _error("context_index_limitは0〜120の整数です。0は索引の省略なしです。", field="context_index_limit")
    for key in ("max_iterations", "time_limit_seconds"):
        value = config[key]
        if value is not None and (type(value) is not int or value < 1 or value > 864000):
            raise _error(f"{key}は正の整数またはnullです。", field=key)
    if mode == "time" and config["time_limit_seconds"] is None:
        raise _error("時間モードには時間上限が必要です。", field="time_limit_seconds")
    if mode == "iterations" and config["max_iterations"] is None:
        raise _error("回数モードには回数上限が必要です。", field="max_iterations")
    if mode == "auto" and config["max_iterations"] is not None and config["max_iterations"] < config["min_iterations"]:
        raise _error("AIお任せの回数上限は最低3回以上にしてください。", field="max_iterations")
    if config["importance_threshold"] not in IMPORTANCE:
        raise _error("重要度閾値が正しくありません。", field="importance_threshold")
    if not isinstance(config["template_version"], str) or not config["template_version"]:
        raise _error("テンプレート版を指定してください。", field="template_version")
    if not isinstance(config["template_config"], dict) or not isinstance(config["roles"], dict):
        raise _error("テンプレート設定と役割設定はオブジェクトで指定してください。")
    if config["max_cost"] is not None and (type(config["max_cost"]) not in {int, float}
            or not math.isfinite(config["max_cost"]) or config["max_cost"] <= 0):
        raise _error("費用上限は正の数です。", field="max_cost")
    if config["max_cost"] is not None:
        raise _error("実費用を確実に取得できないため金額上限には未対応です。呼出し数・タスク数上限を指定してください。", "cost_budget_unavailable")
    if config["provider_policy"] not in {"local_only", "cloud_allowed"}:
        raise _error("送信方針が正しくありません。", "provider_unavailable")
    for role in AI_ROLES:
        options = config["roles"].get(role, {})
        if not isinstance(options, dict):
            raise _error("役割設定が正しくありません。", field="roles")
        provider = options.get("provider", config["provider"])
        model = options.get("model", config["model"])
        if provider not in {"lmstudio", "openai", "google"}:
            raise _error("対応するLLMを選択してください。", "provider_unavailable")
        if provider != "lmstudio" and (config["provider_policy"] != "cloud_allowed" or not config["cloud_consent"]):
            raise _error("外部LLMの利用にはcloud_allowedが必要です。", "provider_unavailable")
        if not isinstance(model, str) or not model.strip() or len(model) > 200 or "\n" in model or "\r" in model:
            raise _error("実際に利用するモデル名を指定してください。", "provider_unavailable")
        config["roles"][role] = {"provider": provider, "model": model.strip()}
    config["publication_targets"] = validate_publication_targets(payload.get("publication_targets", []))
    config["effective_publication_writers"] = list(EFFECTIVE_PUBLICATION_WRITERS) if config["publication_targets"] else []
    canonical(config)
    if config["initial_specialist_analysis_version"] and not (config["initial_label_definitions_version"] and config["core_progress_version"]):
        raise _error("初回の全専門家分析には尺度出力と結果評価の契約が必要です。", "invalid_initial_contract")
    return copy.deepcopy(config)


class ExecutionStopped(Exception):
    """A cooperative cancellation/deadline signal, never an agent result."""


class AnalysisOrchestrationService:
    def __init__(self, *, connect: Callable[[], sqlite3.Connection] | None = None,
                 database_connection: Callable[[], sqlite3.Connection] | None = None,
                 find_item: Callable[[str], Any], snapshot_builder: Callable[[Any], dict[str, Any]],
                 agent_runner: Callable[..., Any], method_runner: Callable[..., Any],
                 source_fingerprint: Callable[[Any], str] | None = None,
                 write_lock: Any = None, schedule: bool = True, adapter_version: str = "core-handler-prompts-1",
                 initial_builder: Any = None, on_complete: Callable[[str, str], Any] | None = None,
                 outline_builder: Callable[..., Any] | None = None):
        self.connect = connect or database_connection
        if self.connect is None:
            raise TypeError("connect is required")
        self.find_item, self.snapshot_builder = find_item, snapshot_builder
        self.agent_runner, self.method_runner = agent_runner, method_runner
        self.source_fingerprint, self.schedule = source_fingerprint, schedule
        self.adapter_version = adapter_version
        self.initial_builder, self.on_complete = initial_builder, on_complete
        self.outline_builder = outline_builder
        if initial_builder is not None and source_fingerprint is None:
            raise TypeError("staged initial analysis requires source_fingerprint")
        self._driving: set[str] = set()
        self.lock = write_lock or threading.RLock()
        self._workers: dict[str, threading.Thread] = {}
        self._worker_lock = threading.Lock()
        with self._db() as db:
            initialize_orchestration_store(db)

    @contextmanager
    def _db(self):
        with self.lock:
            connection = self.connect()
            try:
                with connection as db:
                    db.row_factory = sqlite3.Row
                    if not db.in_transaction:
                        db.execute("BEGIN IMMEDIATE")
                    yield db
            finally:
                # sqlite3.Connection's context manager commits but does not
                # close. Factories returning context managers close themselves.
                if isinstance(connection, sqlite3.Connection):
                    connection.close()

    def _check_version(self, run):
        if run.get("analysis_partition"):
            from .services.analysis_intervals import check_partition
            check_partition(run["analysis_partition"], run["config"], run["input_hash"])
        if run.get("schema_version") != SCHEMA_VERSION:
            raise _error("保存されたrunの形式版が異なります。元の版で復旧してください。", "schema_version_conflict")
        if run["config"].get("adapter_version") != self.adapter_version:
            raise _error("モデル指示の版が変わりました。新しいrunを開始してください。", "adapter_version_conflict")
        if run["config"].get("artifact_review_version"):
            from .method_experts import counterexample_review_procedure
            procedure = counterexample_review_procedure()
            if run["config"].get("artifact_procedure") != {k: procedure[k] for k in ("procedure_id", "version", "sha256")}:
                raise _error("反例点検の手順版が変わりました。", "artifact_input_invalid")

    def _read_run(self, db, run_id: str, item_id: str | None = None) -> dict:
        row = db.execute("SELECT * FROM orchestration_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None or (item_id is not None and row["item_id"] != item_id):
            raise LookupError("自律分析runが見つかりません。")
        return json.loads(row["state_json"])

    def _write_run(self, db, run: dict) -> None:
        run["updated_at"] = _now()
        db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (_json(run), run["run_id"]))

    def _event(self, db, run_id: str, event_type: str, message: str, *, source="handler", target="", task_id="", **extra):
        event = {"type": event_type, "from": source, "to": target, "task_id": task_id,
                 "message": message, "created_at": _now(), **extra}
        db.execute("INSERT INTO orchestration_events(run_id,payload_json) VALUES (?,?)", (run_id, _json(event)))

    def _tasks(self, db, run_id):
        return [json.loads(row[0]) for row in db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=? ORDER BY rowid", (run_id,))]

    def _write_task(self, db, task):
        db.execute("UPDATE orchestration_tasks SET state_json=? WHERE task_id=?", (_json(task), task["task_id"]))

    def _initial(self, db, initial_id):
        row = db.execute("SELECT * FROM orchestration_initials WHERE initial_id=?", (initial_id,)).fetchone()
        if row is None or row["status"] != "ready":
            raise _error("初期分析の固定版が利用できません。", "initial_unavailable")
        value = json.loads(row["snapshot_json"])
        if fingerprint(value) != row["snapshot_hash"]:
            raise _error("初期分析の保存hashが一致しません。AI実行を停止します。", "initial_hash_mismatch")
        return value

    def start(self, item_id: str, payload: dict, app_url: str = "") -> dict:
        config = validate_orchestration_payload(payload)
        request_id = payload.get("request_id") or _id("request")
        if not isinstance(request_id, str) or len(request_id) > 200:
            raise _error("request_idが正しくありません。")
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        request_hash = fingerprint({"item_id": item_id, "config": config,
                                    "source_revision": payload.get("source_revision"),
                                    "analysis_revision": payload.get("analysis_revision"),
                                    "input_hash": payload.get("input_hash")})
        with self._db() as db:
            existing = db.execute("SELECT * FROM orchestration_runs WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                matches = existing["request_hash"] == request_hash
                saved_config = json.loads(existing["state_json"])["config"]
                if not matches and "publication_targets" not in saved_config and not config["publication_targets"]:
                    legacy_config = {key: value for key, value in config.items()
                                     if key not in {"publication_targets", "effective_publication_writers"}}
                    matches = existing["request_hash"] == fingerprint({"item_id": item_id, "config": legacy_config,
                        "source_revision": payload.get("source_revision"), "analysis_revision": payload.get("analysis_revision"),
                        "input_hash": payload.get("input_hash")})
                if existing["item_id"] != item_id or not matches:
                    raise _error("同じrequest_idに異なる設定は使えません。", "request_conflict")
                return self._public(db, json.loads(existing["state_json"]))
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("会話が見つかりません。")
        current_item = dict(item)
        for supplied, actual in (("source_revision", "revision_count"), ("analysis_revision", "analysis_revision")):
            if supplied in payload and (type(payload[supplied]) is not int or payload[supplied] != int(current_item.get(actual, 0) or 0)):
                raise _error("確認した入力版が更新されています。", "revision_conflict", supplied)
        # A source fingerprint permits cache lookup before the expensive fixed analysis.
        before = self.source_fingerprint(item) if self.source_fingerprint else None
        if self.initial_builder is not None:
            return self._start_staged(item_id, payload, config, request_id, request_hash, app_url, item, before)
        snapshot = None
        if before is None:
            snapshot = self.snapshot_builder(item)
            before = snapshot.get("input_hash")
        if payload.get("input_hash") is not None and payload["input_hash"] != before:
            raise _error("確認した入力hashが更新されています。", "revision_conflict", "input_hash")
        identity = fingerprint({"item_id": item_id, "dataset_version": before,
                                "template_version": config["template_version"], "config": config["template_config"]})
        build = False
        with self._db() as db:
            initial = db.execute("SELECT * FROM orchestration_initials WHERE identity=?", (identity,)).fetchone()
            if initial is None:
                initial_id = _id("initial")
                db.execute("INSERT INTO orchestration_initials(initial_id,identity,item_id,status,created_at) VALUES (?,?,?,?,?)",
                           (initial_id, identity, item_id, "building", _now()))
                build = True
            elif initial["status"] != "ready":
                raise _error("同じ初期分析が作成中、または復旧確認待ちです。自動再実行しません。", "initial_recovery_required")
            else:
                initial_id = initial["initial_id"]
                snapshot = self._initial(db, initial_id)
        if build:
            try:
                snapshot = snapshot if snapshot is not None else self.snapshot_builder(item)
                if not isinstance(snapshot, dict) or not isinstance(snapshot.get("analysis"), dict) or not snapshot.get("input_hash"):
                    raise _error("初期分析スナップショットの形式が正しくありません。", "invalid_snapshot")
                latest = self.find_item(item_id)
                if snapshot["input_hash"] != before or (self.source_fingerprint and (latest is None or self.source_fingerprint(latest) != before)):
                    raise _error("入力固定中に会話が変更されました。", "revision_conflict")
                snapshot = copy.deepcopy(snapshot)
                snapshot["evidence"] = self._evidence(snapshot)
                if not any(not e["excluded"] and e["text"].strip() for e in snapshot["evidence"]):
                    raise _error("分析できる発話がありません。", "no_valid_input")
                with self._db() as db:
                    db.execute("UPDATE orchestration_initials SET status='ready',snapshot_json=?,snapshot_hash=? WHERE initial_id=? AND status='building'",
                               (_json(snapshot), fingerprint(snapshot), initial_id))
            except Exception as exc:
                with self._db() as db:
                    db.execute("UPDATE orchestration_initials SET status='failed',error=? WHERE initial_id=?", (type(exc).__name__, initial_id))
                raise
        run_id = _id("run")
        run = {"schema_version": SCHEMA_VERSION, "label_audit_version": 1, "run_id": run_id, "item_id": item_id, "request_id": request_id,
               "initial_id": initial_id, "input_hash": snapshot["input_hash"],
               "source_revision": snapshot.get("source_revision", 0), "analysis_revision": snapshot.get("analysis_revision", 0),
               "config": config, "app_url": app_url.rstrip("/"), "status": "queued", "phase": "core",
               "iteration": 0, "stop_reason": "", "created_at": _now(), "started_at": None,
               "updated_at": _now(), "ended_at": None, "deadline": None, "cancel_requested": False,
               "generation": 1, "calls_started": 0, "code_executions": 0, "annotation_version": 0,
               "codebook_version": int(snapshot["analysis"].get("manual", {}).get("codebook_version",
                       snapshot["analysis"].get("config", {}).get("codebook_version", 1))), "view_version": 0, "current_view": {}, "pending_stop": None,
               "reviewed_stop_versions": [], "last_decision_id": None, "error": "", "stale": False,
               "review_status": "not_requested", "publication_status": "not_requested"}
        labels = self._source_labels(snapshot)
        with self._db() as db:
            # Recheck a concurrent identical start after initial capture.
            existing = db.execute("SELECT * FROM orchestration_runs WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise _error("request_idが競合しました。", "request_conflict")
                return self._public(db, json.loads(existing["state_json"]))
            db.execute("INSERT INTO orchestration_runs VALUES (?,?,?,?,?,?)", (run_id, item_id, request_id, request_hash, initial_id, _json(run)))
            db.execute("INSERT INTO orchestration_label_versions VALUES (?,?,?)", (run_id, 0, _json(labels)))
            self._event(db, run_id, "initial_saved", "初期分析の全結果を不変の版として固定しました。", initial_id=initial_id)
        if self.schedule:
            self._schedule(run_id)
        return self.status(item_id, run_id)

    def _validate_initial_source(self, run):
        item = self.find_item(run["item_id"])
        if item is None or self.source_fingerprint(item) != run["input_hash"]:
            raise _error("初期分析の入力版が更新されています。新しいrunを開始してください。", "revision_conflict")
        row = dict(item)
        for key, column in (("source_revision", "revision_count"), ("analysis_revision", "analysis_revision")):
            if int(row.get(column, 0) or 0) != run[key]:
                raise _error("初期分析の入力版が更新されています。", "revision_conflict")

    def _start_staged(self, item_id, payload, config, request_id, request_hash, app_url, item, before):
        if payload.get("input_hash") is not None and payload["input_hash"] != before:
            raise _error("確認した入力hashが更新されています。", "revision_conflict", "input_hash")
        identity = fingerprint({"item_id": item_id, "dataset_version": before,
                                "template_version": config["template_version"], "config": config["template_config"]})
        run_id = _id("run")
        snapshot = None
        with self._db() as db:
            existing = db.execute("SELECT * FROM orchestration_runs WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing["item_id"] != item_id or existing["request_hash"] != request_hash:
                    raise _error("request_idが競合しました。", "request_conflict")
                return self._public(db, json.loads(existing["state_json"]))
            initial = db.execute("SELECT * FROM orchestration_initials WHERE identity=?", (identity,)).fetchone()
            if initial is None:
                initial_id = _id("initial")
                # Freeze row JSON before expensive work and before returning the run.
                frozen = self.initial_builder.freeze(item)
                db.execute("INSERT INTO orchestration_initials(initial_id,identity,item_id,status,created_at) VALUES (?,?,?,?,?)",
                           (initial_id, identity, item_id, "building", _now()))
                create_initial_checkpoints(db, initial_id, self.initial_builder, frozen, before, run_id)
            else:
                initial_id = initial["initial_id"]
                if initial["status"] == "ready":
                    snapshot = self._initial(db, initial_id)
                else:
                    build, _, states, _, _ = read_initial_checkpoints(db, initial_id, self.initial_builder)
                    owner = self._read_run(db, build["owner_run_id"])
                    if owner["status"] not in TERMINAL or any(s["status"] == "running" for s in states):
                        raise _error("同じ初期分析の保存済みrunを再開してください。", "initial_recovery_required")
                    # A new explicit start after cancellation can reuse committed
                    # deterministic outputs, but it cannot revive the old run.
                    db.execute("UPDATE orchestration_initial_builds SET owner_run_id=? WHERE initial_id=?", (run_id, initial_id))
            row = dict(item)
            run = {"schema_version": SCHEMA_VERSION, "label_audit_version": 1, "run_id": run_id, "item_id": item_id, "request_id": request_id,
                   "initial_id": initial_id, "input_hash": before,
                   "source_revision": int(row.get("revision_count", 0) or 0),
                   "analysis_revision": int(row.get("analysis_revision", 0) or 0),
                   "config": config, "app_url": app_url.rstrip("/"), "status": "queued",
                   "phase": "core" if snapshot is not None else "initial", "iteration": 0,
                   "stop_reason": "", "created_at": _now(), "started_at": None, "updated_at": _now(),
                   "ended_at": None, "deadline": None, "cancel_requested": False, "generation": 1,
                   "calls_started": 0, "code_executions": 0, "annotation_version": 0,
                   "codebook_version": 1, "view_version": 0, "current_view": {}, "pending_stop": None,
                   "reviewed_stop_versions": [], "last_decision_id": None, "error": "", "stale": False,
                   "review_status": "not_requested", "publication_status": "not_requested"}
            self._validate_initial_source(run)
            if snapshot is not None:
                run["source_revision"] = snapshot.get("source_revision", run["source_revision"])
                run["analysis_revision"] = snapshot.get("analysis_revision", run["analysis_revision"])
                run["codebook_version"] = int(snapshot["analysis"].get("manual", {}).get("codebook_version", snapshot["analysis"].get("config", {}).get("codebook_version", 1)))
            db.execute("INSERT INTO orchestration_runs VALUES (?,?,?,?,?,?)", (run_id, item_id, request_id, request_hash, initial_id, _json(run)))
            if snapshot is not None:
                db.execute("INSERT INTO orchestration_label_versions VALUES (?,?,?)", (run_id, 0, _json(self._source_labels(snapshot))))
            self._event(db, run_id, "initial_saved" if snapshot is not None else "initial_queued",
                        "初期分析の保存済み全結果を再利用します。" if snapshot is not None else "初期分析の入力を固定しました。段階ごとに保存して実行します。", initial_id=initial_id)
        if self.schedule:
            self._schedule(run_id)
        return self.status(item_id, run_id)

    def _build_initial(self, run_id):
        """Commit each deterministic output before advancing to the next stage."""
        stage_id = None
        attempt_id = None
        try:
            while True:
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    if run["status"] in TERMINAL or run["status"] == "recovery_required":
                        return False
                    if run["phase"] != "initial":
                        return True
                    if run["started_at"] is None:
                        run["started_at"] = _now()
                        seconds = run["config"]["time_limit_seconds"]
                        run["deadline"] = time.time() + seconds if seconds is not None else None
                        self._write_run(db, run)
                    limit = self._limit(db, run)
                    if limit:
                        self._stop(db, run, limit)
                        return False
                    self._check_version(run)
                    self._validate_initial_source(run)
                    if self.initial_builder is None:
                        raise _error("初期分析の実装が利用できません。", "initial_version_conflict")
                    build, frozen, states, outputs, hashes = read_initial_checkpoints(db, run["initial_id"], self.initial_builder)
                    if build["source_hash"] != run["input_hash"] or build["owner_run_id"] != run_id:
                        raise _error("初期分析の入力または実行主体が一致しません。", "initial_hash_mismatch")
                    pending = next((s for s in states if s["status"] != "completed"), None)
                    if pending is None:
                        snapshot = copy.deepcopy(outputs[self.initial_builder.stages[-1].stage_id])
                        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("analysis"), dict) or snapshot.get("input_hash") != run["input_hash"]:
                            raise _error("初期分析スナップショットの形式が正しくありません。", "invalid_snapshot")
                        if any(snapshot.get(key, 0) != run[key] for key in ("source_revision", "analysis_revision")):
                            raise _error("初期分析の入力版が一致しません。", "revision_conflict")
                        snapshot["evidence"] = self._evidence(snapshot)
                        if not any(not e["excluded"] and e["text"].strip() for e in snapshot["evidence"]):
                            raise _error("分析できる発話がありません。", "no_valid_input")
                        db.execute("UPDATE orchestration_initials SET status='ready',snapshot_json=?,snapshot_hash=?,error='' WHERE initial_id=?",
                                   (_json(snapshot), fingerprint(snapshot), run["initial_id"]))
                        db.execute("INSERT OR IGNORE INTO orchestration_label_versions VALUES (?,?,?)", (run_id, 0, _json(self._source_labels(snapshot))))
                        run.update(phase="core", error="", codebook_version=int(snapshot["analysis"].get("manual", {}).get("codebook_version", snapshot["analysis"].get("config", {}).get("codebook_version", 1))))
                        self._write_run(db, run)
                        self._event(db, run_id, "initial_saved", "初期分析の全段階を不変の版として固定しました。", initial_id=run["initial_id"])
                        return True
                    if pending["status"] == "running":
                        # Another live driver owns this stage. Startup recovery
                        # explicitly releases crashed deterministic attempts.
                        return False
                    stage_id, attempt_id = pending["stage_id"], _id("initial_attempt")
                    pending.update(status="running", attempt_count=pending["attempt_count"] + 1,
                                   attempt_id=attempt_id, started_at=_now(), completed_at=None, error="",
                                   input_hash=stage_input_hash(build, pending, hashes))
                    write_stage(db, run["initial_id"], pending)
                    db.execute("UPDATE orchestration_initials SET status='building',error='' WHERE initial_id=?", (run["initial_id"],))
                    run.update(status="running", error="")
                    self._write_run(db, run)
                    self._event(db, run_id, "initial_stage_started", pending["label"], stage_id=stage_id)
                # All expensive work is outside SQLite transactions and receives
                # frozen data, never current mutable row values.
                output = self.initial_builder.run_stage(stage_id, copy.deepcopy(frozen), copy.deepcopy(outputs))
                encoded = _json(output)
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    self._validate_initial_source(run)
                    build, _, states, _, _ = read_initial_checkpoints(db, run["initial_id"], self.initial_builder)
                    state = next(s for s in states if s["stage_id"] == stage_id)
                    if state.get("attempt_id") != attempt_id or state["status"] != "running" or build["owner_run_id"] != run_id:
                        raise _error("初期分析段階の実行世代が変わりました。", "initial_attempt_conflict")
                    state.update(status="completed", output_hash=fingerprint(json.loads(encoded)), completed_at=_now(), error="")
                    write_stage(db, run["initial_id"], state, json.loads(encoded))
                    self._event(db, run_id, "initial_stage_completed", state["label"], stage_id=stage_id, output_hash=state["output_hash"])
                    # Cancellation permits retaining this deterministic output;
                    # the next loop fences adoption and all later stages/AI.
                stage_id, attempt_id = None, None
        except Exception as exc:
            with self._db() as db:
                run = self._read_run(db, run_id)
                error = getattr(exc, "code", type(exc).__name__)
                if stage_id:
                    row = db.execute("SELECT state_json FROM orchestration_initial_stages WHERE initial_id=? AND stage_id=?", (run["initial_id"], stage_id)).fetchone()
                    if row:
                        state = json.loads(row[0])
                        if state["status"] == "running" and state.get("attempt_id") == attempt_id:
                            state.update(status="failed", error=error)
                            write_stage(db, run["initial_id"], state)
                db.execute("UPDATE orchestration_initials SET status='failed',error=? WHERE initial_id=? AND status!='ready'", (error, run["initial_id"]))
                if run["status"] not in TERMINAL:
                    run.update(status="recovery_required", error=error, stale=run["stale"] or error == "revision_conflict")
                    self._write_run(db, run)
                    self._event(db, run_id, "initial_recovery_required", "初期分析は未完了です。完了済み段階を保持しています。", error=error)
            return False

    def _notify_completed(self, run_id):
        if self.on_complete is None:
            return
        with self._db() as db:
            run = self._read_run(db, run_id)
            if run["status"] != "completed" or run.get("completion_callback_status"):
                return
            run["completion_callback_status"] = "running"
            self._write_run(db, run)
            item_id = run["item_id"]
        try:
            self.on_complete(item_id, run_id)
        except Exception as exc:
            with self._db() as db:
                run = self._read_run(db, run_id)
                run.update(completion_callback_status="failed", publication_error=getattr(exc, "code", type(exc).__name__))
                self._write_run(db, run)
                self._event(db, run_id, "publication_failed", "分析は完了しています。結果保存・公開処理を確認してください。", error=run["publication_error"])
        else:
            with self._db() as db:
                run = self._read_run(db, run_id)
                run["completion_callback_status"] = "completed"
                self._write_run(db, run)

    @staticmethod
    def _evidence(snapshot: dict) -> list[dict]:
        evidence = []
        for index, segment in enumerate(snapshot["analysis"].get("segments", [])):
            utterance_id = str(segment.get("id", segment.get("segment_id", index)))
            text = str(segment.get("text", ""))
            evidence_id = "ev_" + fingerprint({"dataset": snapshot["input_hash"], "utterance": utterance_id, "text": text})[7:31]
            evidence.append({"id": evidence_id, "evidence_id": evidence_id, "utterance_id": utterance_id,
                             "dataset_version": snapshot["input_hash"], "source_hash": fingerprint(text),
                             "text": text, "speaker": segment.get("speaker"), "start": segment.get("start"),
                             "end": segment.get("end"), "excluded": bool(segment.get("excluded"))})
        if len({row["utterance_id"] for row in evidence}) != len(evidence):
            raise _error("発話IDが重複しています。", "invalid_snapshot")
        return evidence

    @staticmethod
    def _source_labels(snapshot):
        return {str(s.get("id", s.get("segment_id", i))): copy.deepcopy(s.get("annotation", s.get("labels", snapshot["analysis"].get("annotations", {}).get(str(s.get("id", s.get("segment_id", i))), {}))))
                for i, s in enumerate(snapshot["analysis"].get("segments", []))}

    def _schedule(self, run_id):
        with self._worker_lock:
            old = self._workers.get(run_id)
            if old and old.is_alive():
                return
            thread = threading.Thread(target=self.run, args=(run_id,), daemon=True, name="analysis-" + run_id[-8:])
            self._workers[run_id] = thread
            thread.start()

    def _usage(self, db, run):
        records = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_usage WHERE run_id=?", (run["run_id"],))]
        def total(key):
            values = [r[key] for r in records if type(r.get(key)) in {int, float}]
            return sum(values) if values else None
        return {"calls": run["calls_started"], "code_executions": run["code_executions"],
                "input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"),
                "total_tokens": total("total_tokens"), "cost": total("cost"),
                "currency": "USD" if any(r.get("currency") == "USD" for r in records) else None,
                "measured_calls": len({r.get("task_id") for r in records}),
                "measurement_status": "reported" if records else "unavailable"}

    def _public(self, db, run):
        result = copy.deepcopy(run)
        result["config"].setdefault("publication_targets", [])
        result["config"]["effective_publication_writers"] = list(EFFECTIVE_PUBLICATION_WRITERS) if result["config"]["publication_targets"] else []
        result["initial"] = initial_progress(db, run["initial_id"])
        result["initial_stages"] = result["initial"]["stages"]
        tasks = self._tasks(db, run["run_id"])
        result["tasks"] = tasks
        if run.get("analysis_partition"):
            from .services.analysis_intervals import progress
            result["interval_progress"] = progress(run["analysis_partition"], tasks)
        result["completed_core_iterations"] = self._completed_core_iterations(db, run)
        if run["config"].get("initial_label_definitions_version"):
            try:
                result["initial_label_catalog"] = self._initial_label_catalog(db, run)
            except AnalysisContractError as exc:
                result["initial_label_catalog"] = None
                result["initial_label_error"] = exc.code
        if run.get("initial_analysis_report"):
            result["initial_analysis_report"] = copy.deepcopy(run["initial_analysis_report"])
        result["events"] = [{"seq": row[0], **json.loads(row[1])} for row in db.execute(
            "SELECT seq,payload_json FROM orchestration_events WHERE run_id=? ORDER BY seq", (run["run_id"],))]
        result["usage"] = self._usage(db, run)
        result["roles"] = []
        for role, label in ROLES.items():
            assigned = [task for task in tasks if task["role"] == role]
            running = [task for task in assigned if task["status"] in {"running", "cancel_requested"}]
            options = run["config"]["roles"].get(role, {})
            result["roles"].append({"id": role, "label": label, "kind": "ai" if role in AI_ROLES else "code",
                "provider": options.get("provider", "python"), "model": options.get("model", "deterministic"),
                "status": "running" if running else ("idle" if run["status"] not in TERMINAL else run["status"]),
                "assigned": len(assigned), "completed": sum(t["status"] == "succeeded" for t in assigned),
                "failed": sum(t["status"] in {"failed", "quarantined", "uncertain"} for t in assigned),
                "current_task": running[0]["title"] if running else ""})
        result["results"] = [json.loads(r[0]) for r in db.execute("SELECT state_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        result["issues"] = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_issues WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        result["critique_responses"] = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_responses WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        result["label_proposals"] = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_label_proposals WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        result["unresolved_issues"] = [issue for issue in result["issues"] if issue.get("status") != "resolved"]
        uncertain = [t["task_id"] for t in tasks if t["status"] in {"running", "uncertain", "cancel_requested"}]
        result["can_resume"] = run["status"] in {"queued", "recovery_required"} and not uncertain
        if run["phase"] == "initial":
            result["can_resume"] = result["can_resume"] and not run["stale"]
            try:
                if self.initial_builder is None:
                    raise _error("初期分析の実装が利用できません。", "initial_version_conflict")
                build, _, stages, _, _ = read_initial_checkpoints(db, run["initial_id"], self.initial_builder)
                if build["source_hash"] != run["input_hash"] or build["owner_run_id"] != run["run_id"]:
                    raise _error("初期分析の入力または実行主体が一致しません。", "initial_hash_mismatch")
                result["can_resume"] = result["can_resume"] and not any(s["status"] == "running" for s in stages)
            except (AnalysisContractError, ValueError, TypeError, KeyError) as exc:
                result["can_resume"] = False
                result["initial"]["recovery_error"] = getattr(exc, "code", "initial_checkpoint_invalid")
        result["allowed_actions"] = (["resume"] if result["can_resume"] else []) + (["cancel"] if run["status"] not in TERMINAL else [])
        result["uncertain_tasks"] = uncertain
        result["in_flight_count"] = sum(t["status"] in {"running", "cancel_requested", "uncertain"} for t in tasks)
        return result

    def status(self, item_id: str, run_id: str) -> dict:
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("会話が見つかりません。")
        with self._db() as db:
            run = self._read_run(db, run_id, item_id)
            if self.source_fingerprint and (item is None or self.source_fingerprint(item) != run["input_hash"]):
                run["stale"] = True
                self._write_run(db, run)
            return self._public(db, run)

    def history(self, item_id: str) -> list[dict]:
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self._db() as db:
            return [self._public(db, json.loads(row[0])) for row in db.execute(
                "SELECT state_json FROM orchestration_runs WHERE item_id=? ORDER BY rowid DESC", (item_id,)).fetchall()]

    def result(self, item_id: str, run_id: str, result_id: str | None = None) -> dict:
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self._db() as db:
            return self.result_locked(db, item_id, run_id, result_id)

    def result_locked(self, db, item_id: str, run_id: str, result_id: str | None = None) -> dict:
        """Serialize an export inside the caller's transaction, without nesting."""
        run = self._read_run(db, run_id, item_id)
        if result_id:
            row = db.execute("SELECT * FROM orchestration_results WHERE result_id=? AND run_id=?", (result_id, run_id)).fetchone()
            if row is None:
                raise LookupError("結果が見つかりません。")
            return {**json.loads(row["state_json"]), "raw": json.loads(row["raw_json"])}
        initial = db.execute("SELECT * FROM orchestration_initials WHERE initial_id=?", (run["initial_id"],)).fetchone()
        return {"run": self._public(db, run), "initial": {"initial_id": initial["initial_id"],
            "hash": initial["snapshot_hash"], "snapshot": json.loads(initial["snapshot_json"]) if initial["snapshot_json"] else None},
            "raw_results": [{**json.loads(r[0]), "raw": json.loads(r[1])} for r in db.execute("SELECT state_json,raw_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run_id,))],
            "decisions": [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run_id,))],
            "label_audit": [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_label_audit WHERE run_id=? ORDER BY rowid", (run_id,))],
            "label_versions": [{"annotation_version": r[0], "labels": json.loads(r[1])} for r in db.execute(
                "SELECT annotation_version,payload_json FROM orchestration_label_versions WHERE run_id=? ORDER BY annotation_version", (run_id,))],
            "usage_records": [{"usage_id": r[0], "task_id": r[1], "payload": json.loads(r[2])} for r in db.execute(
                "SELECT usage_id,task_id,payload_json FROM orchestration_usage WHERE run_id=? ORDER BY rowid", (run_id,))]}

    def _stop(self, db, run, reason, *, completed=False):
        if run["status"] in TERMINAL:
            return
        run.update(status="completed" if completed else ("cancelled" if reason == "user_stop" else "stopped"),
                   phase="stopped", stop_reason=reason, ended_at=_now(), generation=run["generation"] + 1)
        for task in self._tasks(db, run["run_id"]):
            if task["status"] == "queued":
                task.update(status="cancelled", error=reason)
                self._write_task(db, task)
            elif task["status"] == "running":
                task.update(status="cancel_requested", error=reason)
                self._write_task(db, task)
        if run["pending_stop"] and run["review_status"] not in {"reviewed", "unavailable"}:
            run["review_status"] = "incomplete"
        self._write_run(db, run)
        self._event(db, run["run_id"], "stopped", reason)

    def cancel(self, item_id: str, run_id: str) -> dict:
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self._db() as db:
            run = self._read_run(db, run_id, item_id)
            if run["status"] not in TERMINAL:
                run["cancel_requested"] = True
                self._stop(db, run, "user_stop")
            return self._public(db, run)

    def resume(self, item_id: str, run_id: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self._worker_lock:
            worker = self._workers.get(run_id)
            if worker and worker.is_alive():
                return self.status(item_id, run_id)
        with self._db() as db:
            run = self._read_run(db, run_id, item_id)
            self._check_version(run)
            if "publication_targets" in payload and validate_publication_targets(payload["publication_targets"]) != run["config"].get("publication_targets", []):
                raise _error("再開時に公開先を変更できません。新しいrunを開始してください。", "publication_scope_conflict")
            if run["phase"] == "initial":
                self._validate_initial_source(run)
                if self.initial_builder is None:
                    raise _error("初期分析の実装が利用できません。", "initial_version_conflict")
                read_initial_checkpoints(db, run["initial_id"], self.initial_builder)
            if run["status"] in TERMINAL:
                raise _error("終了済みrunは再実行しません。新しいrunを開始してください。", "run_terminal")
            uncertain = []
            for task in self._tasks(db, run_id):
                if task.get("input_artifacts"):
                    self._recheck_review_binding(db, run, task)
                if task["status"] in {"running", "uncertain", "cancel_requested"}:
                    row = db.execute("SELECT state_json FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
                    if row:
                        task["status"] = "received"
                    elif payload.get("recovery", {}).get(task["task_id"]) == "abandon":
                        task.update(status="failed", error="explicitly_abandoned_uncertain_execution")
                        self._event(db, run_id, "recovery_abandoned", "実行結果不明の呼出しを明示的に放棄しました。再発注しません。", task_id=task["task_id"])
                    else:
                        task.update(status="uncertain", error="execution_outcome_unknown")
                        uncertain.append(task["task_id"])
                    self._write_task(db, task)
            if uncertain:
                run.update(status="recovery_required", error="実行済みか不明な呼出しがあります。結果を照合するか、明示的に放棄してください。")
                self._write_run(db, run)
                self._event(db, run_id, "recovery_required", run["error"], task_ids=uncertain)
                return self._public(db, run)
            run.update(status="queued", error="", generation=run["generation"] + 1)
            self._write_run(db, run)
        if self.schedule:
            self._schedule(run_id)
        return self.status(item_id, run_id)

    def _limit(self, db, run, *, new_round=False):
        if run["cancel_requested"]:
            return "user_stop"
        if run["deadline"] is not None and time.time() >= run["deadline"]:
            return "time_limit"
        if new_round and run["config"]["max_iterations"] is not None and run["iteration"] >= run["config"]["max_iterations"]:
            return "iteration_limit"
        usage = self._usage(db, run)
        if run["config"]["max_cost"] is not None and usage["cost"] is not None and usage["cost"] >= run["config"]["max_cost"]:
            return "budget_limit"
        return None

    def _completed_core_iterations(self, db, run):
        # Count adopted decisions, never queued attempts or quarantined results.
        return sum(json.loads(row[0]).get("phase") != "initial_routing" and json.loads(row[0]).get("role", "core") == "core" for row in db.execute(
            "SELECT payload_json FROM orchestration_decisions WHERE run_id=?", (run["run_id"],)))

    def _pending_result_assessments(self, db, run):
        assessed = {entry["result_id"] for row in db.execute(
            "SELECT payload_json FROM orchestration_decisions WHERE run_id=?", (run["run_id"],))
            for entry in json.loads(row[0]).get("result_assessments", [])}
        return [meta["result_id"] for row in db.execute(
            "SELECT state_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run["run_id"],))
            if (meta := json.loads(row[0]))["role"] not in {"core", "orchestrator"}
            and meta["validation_status"] == "valid" and not meta.get("stale")
            and meta["result_id"] not in assessed]

    def _review_pending(self, db, run, task):
        pending = self._pending_result_assessments(db, run)
        if task["role"] != "orchestrator":
            return pending
        domain = task["intent"]["scope"]["domain"]
        return [rid for rid in pending if self._result_domain(db, rid) == domain]

    @staticmethod
    def _result_domain(db, result_id):
        row = db.execute("SELECT t.state_json,r.raw_json FROM orchestration_tasks t JOIN orchestration_results r ON r.task_id=t.task_id WHERE r.result_id=?", (result_id,)).fetchone()
        task = json.loads(row[0])
        return "labels" if task["phase"] == "initial_labels" or task.get("intent", {}).get("scope") == "label_review" or json.loads(row[1]).get("label_patches") else task["role"]

    def _domain_reports(self, db, run):
        reports = []
        events = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_events WHERE run_id=?", (run["run_id"],))]
        followups = self._tasks(db, run["run_id"])
        for (encoded,) in db.execute("SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run["run_id"],)):
            decision = json.loads(encoded)
            if decision.get("role") != "orchestrator":
                continue
            row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=?", (decision["result_id"],)).fetchone()
            meta = json.loads(row[1])
            if meta["validation_status"] != "valid" or fingerprint(json.loads(row[0])) != meta["raw_hash"]:
                raise _error("専門オーケストレータ報告の整合性を確認できません。", "result_integrity_mismatch")
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (meta["task_id"],)).fetchone()[0])
            self._check_input_manifest(run, task, meta)
            reports.append({"domain": decision["domain"], "task_id": meta["task_id"], "result_id": meta["result_id"], "raw_hash": meta["raw_hash"],
                "source_result_ids": [a["result_id"] for a in decision["result_assessments"]],
                "summary": decision["summary"], "claims": decision.get("claims", []),
                "alternatives": decision.get("alternatives", []), "unresolved": decision.get("unresolved", []),
                "dispositions": {value: sum(a["disposition"] == value for a in decision["result_assessments"]) for value in ("adopt", "reject", "defer")},
                "annotation_version": decision["annotation_version"], "status": "ai_draft", "read_scope": "specialist_result_review"})
            if decision.get("topic_sources"):
                reports[-1]["topic_sources"] = copy.deepcopy(decision["topic_sources"])
            if run["config"].get("artifact_review_version"):
                reports[-1]["artifact_decisions"] = copy.deepcopy(decision.get("artifact_decisions", []))
                reports[-1]["review_results"] = copy.deepcopy(decision.get("review_results", []))
                reports[-1]["independent_support_count"] = None
                reports[-1]["review_limit"] = "派生レビューは先行所見と独立した裏付けではない。範囲内未検出は真実性の確認ではない。"
            reports[-1]["deferred_followup_count"] = sum(e["type"] == "intent_deferred" and e.get("review_result_id") == meta["result_id"] for e in events)
            statuses = [t["status"] for t in followups if t.get("parent_task_id") == task["task_id"]]
            reports[-1]["followup_status_counts"] = {status: statuses.count(status) for status in sorted(set(statuses))}
        return reports

    @staticmethod
    def _core_progress_signature(raw):
        # IDs, order, punctuation and summary-only paraphrases do not add evidence.
        def text(value):
            # Preserve internal punctuation, signs and word boundaries: -1 and
            # 1 or 1.2 and 12 must never be collapsed into the same assertion.
            return " ".join(unicodedata.normalize("NFKC", value).casefold().split()).rstrip("。.!?！？")
        def items(values):
            return sorted({_json(value) for value in values})
        return fingerprint({
            "claims": items({"text": text(claim["text"]), "kind": claim["kind"],
                              "evidence_ids": sorted(set(claim["evidence_ids"]))}
                             for claim in raw.get("claims", [])),
            "alternatives": sorted({text(value) for value in raw.get("alternatives", [])}),
            "unresolved": sorted({text(value) for value in raw.get("unresolved", [])}),
            "intents": items({**{key: intent.get(key) for key in (
                "role", "kind", "result_id", "method_id", "label_field", "scope", "label_dependent", "replicate_id")},
                "question": text(intent["question"]), "evidence_ids": sorted(set(intent.get("evidence_ids", []))),
                "initial_sections": sorted(set(intent.get("initial_sections", [])))}
                for intent in raw.get("intents", [])),
        })

    def _new_result_basis(self, db, run, history, assessments):
        def basis(result_id):
            row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE run_id=? AND result_id=?",
                             (run["run_id"], result_id)).fetchone()
            metadata = json.loads(row[1])
            if fingerprint(json.loads(row[0])) != metadata["raw_hash"]:
                raise _error("専門家結果のhashが一致しません。", "result_integrity_mismatch")
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",
                                        (metadata["task_id"], run["run_id"])).fetchone()[0])
            if task.get("input_artifacts"):
                return None
            return fingerprint({"role": metadata["role"], "raw_hash": metadata["raw_hash"],
                "data_version": metadata["dataset_version"], "annotation_version": metadata["annotation_version"],
                "scope": task["intent"].get("scope"), "target_version": task["intent"].get("target_version"),
                "evidence_ids": sorted(set(task["intent"].get("evidence_ids", [])))})
        seen = {basis(entry["result_id"]) for decision in history for entry in decision.get("result_assessments", [])}
        fresh = []
        for result_id in assessments:
            key = basis(result_id)
            if key is not None and key not in seen:
                fresh.append(result_id)
                seen.add(key)
        return fresh

    def _new_review_checks(self, db, run, previous_ids, assessed_ids):
        def signature(rid):
            row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?", (rid, run["run_id"])).fetchone()
            raw, meta = json.loads(row[0]), json.loads(row[1])
            if not meta.get("derived_from"):
                return None
            if fingerprint(raw) != meta["raw_hash"]:
                artifact_review.reject("派生レビューの保存hashが一致しません。")
            return artifact_review.review_progress(raw)
        seen = {signature(rid) for rid in previous_ids}
        fresh = []
        for rid in assessed_ids:
            key = signature(rid)
            if key is not None and key not in seen:
                fresh.append(rid)
                seen.add(key)
        return fresh

    def _continue_minimum_iterations(self, db, run, reason):
        minimum = run["config"].get("min_iterations", 0)
        completed = self._completed_core_iterations(db, run)
        if completed >= minimum:
            return False
        limit = self._limit(db, run, new_round=True)
        if limit:
            self._stop(db, run, limit)
        else:
            run["phase"] = "core"
            self._event(db, run["run_id"], "minimum_iterations_continued",
                        f"Core判断は{completed}/{minimum}回です。根拠・批判・未解決点を再検討して次の判断へ進みます。",
                        proposed_stop_reason=reason, completed_core_iterations=completed,
                        min_iterations=minimum)
            self._write_run(db, run)
        return True

    def _source_review_binding(self, db, run, result_id, scope=None):
        from .method_experts import counterexample_review_procedure
        row = db.execute("SELECT raw_json,state_json,task_id FROM orchestration_results WHERE result_id=? AND run_id=?",
                         (result_id, run["run_id"])).fetchone()
        if row is None:
            artifact_review.reject("同じrunの先行所見が見つかりません。")
        raw, meta = json.loads(row[0]), json.loads(row[1])
        source = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",
                            (row[2], run["run_id"])).fetchone()
        if source is None:
            artifact_review.reject("先行所見の生成タスクが見つかりません。")
        task = json.loads(source[0])
        scope = copy.deepcopy(scope if scope is not None else _scope(task["intent"]))
        from .services.analysis_intervals import interval_scope
        intervals = run.get("analysis_partition", {}).get("intervals", []) + run.get("interval_refinements", [])
        interval = next((i for i in intervals if i["interval_id"] == scope.get("interval_id")), None)
        if interval is None or interval_scope(interval) != scope:
            artifact_review.reject("先行所見の固定区間が不正です。")
        self._check_input_manifest(run, task, meta)
        binding = artifact_review.validate_source(run, task, meta, raw, scope, counterexample_review_procedure())
        return binding, raw, meta

    def _artifact_history(self, db, run, domain):
        return [{**entry, "decision_id": d["decision_id"]}
                for (encoded,) in db.execute("SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run["run_id"],))
                if (d := json.loads(encoded)).get("role") == "orchestrator" and d.get("domain") == domain
                for entry in d.get("artifact_decisions", [])]

    def _artifact_candidates(self, db, run, domain):
        history = self._artifact_history(db, run, domain)
        latest = {r["result_id"]: r for r in history}
        candidates = []
        # Stable insertion order and complete index units. No result body here.
        information = fingerprint({"annotation_version": run["annotation_version"],
            "results": [m["raw_hash"] for (s,) in db.execute("SELECT state_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run["run_id"],))
                        if (m := json.loads(s)).get("role") not in {"core", "orchestrator"}
                        and m.get("validation_status") == "valid"]})
        for (rid,) in db.execute("SELECT result_id FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run["run_id"],)).fetchall():
            old = latest.get(rid)
            if old and old["disposition"] != "defer":
                continue
            try:
                binding, _, meta = self._source_review_binding(db, run, rid)
            except AnalysisContractError:
                continue
            candidates.append({"result_id": rid, "raw_hash": binding["raw_hash"], "run_id": run["run_id"],
                "task_id": binding["task_id"], "created_by": "interpretation", "interval_id": binding["interval"]["interval_id"],
                "dataset_version": binding["dataset_version"], "schema_version": binding["schema_version"],
                "codebook_version": binding["codebook_version"], "annotation_version": binding["annotation_version"],
                "scope": binding["interval"], "provided_evidence_ids": binding["source_provided_evidence_ids"],
                "claim_count": len(binding["claim_ids"]), "content_status": meta.get("content_status", "unreviewed"),
                "coverage": next(t["context_manifest"]["coverage"] for t in self._tasks(db, run["run_id"]) if t["task_id"] == binding["task_id"]),
                "information_hash": fingerprint([binding, information]),
                "previous_decision_id": old.get("decision_id", "") if old else ""})
        return candidates[:6], len(candidates) - min(6, len(candidates))

    def resolve_review_input(self, db, run, intent):
        if (run["config"].get("artifact_review_version") != 1 or intent.get("role") != "interpretation"
                or intent.get("artifact_purpose") != artifact_review.PURPOSE or intent.get("label_dependent")
                or intent.get("result_id") or intent.get("initial_sections") or intent.get("method_id")):
            artifact_review.reject("専用の解釈役レビュー依頼だけが先行所見を利用できます。")
        row = db.execute("SELECT payload_json FROM orchestration_decisions WHERE decision_id=? AND run_id=?",
                         (intent.get("artifact_decision_id"), run["run_id"])).fetchone()
        decision = json.loads(row[0]) if row else {}
        rid = intent.get("review_target_result_id")
        choice = next((r for r in decision.get("artifact_decisions", []) if r["result_id"] == rid and r["disposition"] == "use"), None)
        if decision.get("role") != "orchestrator" or choice is None or intent.get("interval_ids") != [choice["interval_id"]]:
            artifact_review.reject("提示候補のuse判断に結び付いた依頼が必要です。")
        binding, _, _ = self._source_review_binding(db, run, rid)
        if choice.get("raw_hash") != binding["raw_hash"]:
            artifact_review.reject("提示した先行所見の版が変わりました。")
        return binding

    def _recheck_review_binding(self, db, run, task):
        if task.get("role") != "interpretation" or task.get("intent", {}).get("kind") != "finding_review":
            artifact_review.reject("この役割へ先行所見を配送できません。")
        bindings = task.get("input_artifacts", [])
        if not isinstance(bindings, list) or len(bindings) != 1:
            artifact_review.reject("先行所見の束縛は1件です。")
        current, raw, _ = self._source_review_binding(db, run, bindings[0]["result_id"], _scope(task["intent"]))
        if current != bindings[0] or self.resolve_review_input(db, run, task["intent"]) != current:
            artifact_review.reject("固定した先行所見の入力版・hash・手順が変わりました。")
        return current, raw

    def _register(self, db, run, intent: dict, *, phase: str, automatic=False) -> dict | None:
        binding = None
        if intent.get("input_artifacts"):
            artifact_review.reject("入力束縛はHandlerだけが作成します。")
        if intent.get("kind") == "finding_review":
            binding = self.resolve_review_input(db, run, intent)
            if any(d != binding["task_id"] for d in intent.get("dependencies", [])):
                artifact_review.reject("初期レビューの依存は生成済みの先行所見1件だけです。")
            intent = {**copy.deepcopy(intent), "scope": copy.deepcopy(binding["interval"]),
                      "dependencies": [binding["task_id"]]}
        elif intent.get("review_target_result_id") or intent.get("artifact_purpose"):
            artifact_review.reject("先行所見の指定は専用レビュー依頼だけに許可されます。")
        if run["config"].get("analysis_interval_version") and _scope(intent).get("interval_id"):
            from .services.analysis_intervals import interval_scope
            supplied = intent["scope"]
            known_intervals = run["analysis_partition"]["intervals"] + run.get("interval_refinements", [])
            interval = next((i for i in known_intervals if i["interval_id"] == supplied["interval_id"]), None)
            canonical_scope = interval_scope(interval, blind=intent["role"] == "verification") if interval else None
            if supplied != canonical_scope:
                raise _error("タスクの区間と固定所属が一致しません。", "interval_scope_invalid")
            intent = copy.deepcopy(intent)
            intent["evidence_ids"] = supplied["owned_evidence_ids"] + supplied["boundary_evidence_ids"]
        if (run["config"].get("analysis_interval_version") and intent.get("role") in {"interpretation", "verification", "critic"}
                and intent.get("kind", "analysis") != "clarification"
                and phase not in {"initial_labels", "label_review", "stop_review"}
                and not _scope(intent).get("interval_id")):
            from .services.analysis_intervals import check_partition, interval_scope
            partition = run.get("analysis_partition")
            if not partition:
                raise _error("原文の区間が確定していません。", "interval_missing")
            check_partition(partition, run["config"], run["input_hash"])
            selected = set(intent.get("evidence_ids", []))
            requested = intent.get("interval_ids", _scope(intent).get("interval_ids", []))
            available = {i["interval_id"] for i in partition["intervals"]}
            if not isinstance(requested, list) or any(i not in available for i in requested):
                raise _error("存在する区間IDを指定してください。", "interval_missing")
            # A cited row selects its owning interval, never just the citation.
            intervals = [i for i in partition["intervals"] if (not requested or i["interval_id"] in requested)
                         and (not selected or selected.intersection(i["owned_evidence_ids"]))]
            if not intervals:
                raise _error("対象区間がありません。", "interval_missing")
            first_task = None
            for interval in intervals:
                if interval["status"] != "ready":
                    self._stop(db, run, "interval_unprocessable")
                    return first_task
                child = copy.deepcopy(intent)
                scope = interval_scope(interval, blind=intent["role"] == "verification")
                child.update(scope=scope, evidence_ids=scope["owned_evidence_ids"] + scope["boundary_evidence_ids"])
                task = self._register(db, run, child, phase=phase, automatic=automatic)
                first_task = first_task or task
                if run["status"] in TERMINAL:
                    break
            return first_task
        role = intent.get("role")
        if role not in AI_ROLES | {"statistics"}:
            raise _error("未対応の専門家です。", "invalid_intent")
        method = intent.get("method_id") or ("participation" if role == "statistics" else "agent-v1")
        if role == "statistics" and method != "label_frequency" and (intent.get("evidence_ids") or intent.get("scope") or intent.get("label_dependent")):
            raise _error("既存コード計算は初期版の全範囲専用です。部分範囲・ラベル再計算は未対応です。", "method_scope_unavailable")
        if method == "label_frequency" and (role != "statistics" or intent.get("label_field", "codes") not in LABEL_FIELDS):
            raise _error("対応するラベル集計列を指定してください。", "label_field_unavailable")
        if role == "statistics" and method not in METHODS:
            raise _error("未対応のコード計算です。", "method_unavailable")
        initial = self._initial(db, run["initial_id"])
        valid_evidence = {e["evidence_id"] for e in initial["evidence"] if not e["excluded"]}
        evidence_ids = intent.get("evidence_ids", [])
        if not isinstance(evidence_ids, list) or any(e not in valid_evidence for e in evidence_ids):
            raise _error("タスクが存在しない根拠を参照しています。", "evidence_missing")
        question = intent.get("question", run["config"]["question"])
        if not isinstance(question, str) or not question.strip():
            raise _error("タスクの問いがありません。", "invalid_intent")
        if not automatic and (not intent.get("why_now") or not intent.get("success_criteria")):
            raise _error("追加タスクには理由と採用基準が必要です。", "invalid_intent")
        if intent.get("kind", "analysis") not in {"analysis", "clarification", "finding_review", ""}:
            raise _error("未対応のタスク種別です。", "invalid_intent")
        if intent.get("kind") == "clarification":
            target = db.execute("SELECT state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                (intent.get("result_id"), run["run_id"])).fetchone()
            is_initial = intent.get("result_id") == run["initial_id"]
            if role not in {"interpretation", "critic", "verification"} or (not is_initial and (target is None or json.loads(target[0])["validation_status"] != "valid")):
                raise _error("説明対象の保存済み結果を指定してください。", "clarification_target_missing")
            if role == "verification" and (is_initial or target is None or json.loads(target[0]).get("role") != "verification"):
                raise _error("独立検証への説明依頼は、その独立検証の保存済み結果だけを対象にしてください。", "clarification_target_mismatch")
            if is_initial:
                sections = intent.get("initial_sections", [])
                if not isinstance(sections, list) or not sections or len(sections) > 6 or any(section not in initial["analysis"] or section not in INITIAL_SECTIONS for section in sections):
                    raise _error("初期版の存在する節を1〜6件指定してください。", "initial_section_missing")
        dependencies = intent.get("dependencies", [])
        tasks = self._tasks(db, run["run_id"])
        known = {task["task_id"]: task for task in tasks}
        if not isinstance(dependencies, list) or any(d not in known for d in dependencies):
            raise _error("タスク依存関係が存在しません。", "dependency_missing")
        label_dependent = bool(intent.get("label_dependent", False)) if role != "statistics" else method == "label_frequency"
        identity = {"input": run["input_hash"], "annotation_version": run["annotation_version"] if label_dependent else None,
                    "role": role, "method": method, "question": question.strip(), "evidence_ids": sorted(evidence_ids),
                    "scope": intent.get("scope"), "label_field": intent.get("label_field", "codes") if method == "label_frequency" else None, "target_id": intent.get("target_id"), "target_version": intent.get("target_version"),
                    "evidence_version": fingerprint([run["input_hash"], run["annotation_version"]]) if role == "critic" else intent.get("evidence_version", run["input_hash"]), "replicate_id": intent.get("replicate_id") or None,
                    "round": run["iteration"] if role == "core" else None, "options": run["config"]["roles"].get(role), "kind": intent.get("kind", "analysis"), "result_id": intent.get("result_id"), "initial_sections": intent.get("initial_sections", []),
                    "dependencies": sorted(dependencies)}
        key = fingerprint(identity)
        if binding:
            identity["input_artifacts"] = [binding]
            key = fingerprint(identity)
        existing = db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=? AND idempotency_key=?", (run["run_id"], key)).fetchone()
        if existing:
            task = json.loads(existing[0])
            self._event(db, run["run_id"], "duplicate_suppressed", "同じ入力・目的・対象版のタスクを再発注しません。", task_id=task["task_id"])
            return None
        if run["config"].get("specialist_orchestration_version") and role == "statistics" and method in {"participation", "conversation_dynamics"} and phase != "initial_analysis":
            reusable = next((t for t in tasks if t["role"] == "statistics" and t["method_id"] == method and t["status"] == "succeeded" and t["dataset_version"] == run["input_hash"]), None)
            if reusable:
                self._event(db, run["run_id"], "duplicate_suppressed", "固定入力の同じ全件集計は保存済み結果を参照し、再計算しません。", task_id=reusable["task_id"], result_id=reusable["result_id"])
                return None
        if len(tasks) >= run["config"]["max_tasks"]:
            self._stop(db, run, "task_budget_limit")
            return None
        queued_calls = sum(t["kind"] == "ai" and t["status"] == "queued" for t in tasks)
        if role in AI_ROLES and run["calls_started"] + queued_calls >= run["config"]["max_calls"]:
            self._stop(db, run, "call_budget_limit")
            return None
        options = run["config"]["roles"].get(role, {"provider": "python", "model": method})
        task = {"task_id": _id("task"), "run_id": run["run_id"], "intent_id": intent.get("intent_id") or _id("intent"),
                "parent_task_id": intent.get("parent_task_id"), "attempt_id": _id("attempt"),
                "idempotency_key": key, "role": role, "kind": "ai" if role in AI_ROLES else "code",
                "provider": options["provider"], "model": options["model"], "method_id": method,
                "title": question.strip(), "intent": copy.deepcopy(intent), "phase": phase, "iteration": run["iteration"],
                "dataset_version": run["input_hash"], "annotation_version": run["annotation_version"],
                "codebook_version": run["codebook_version"], "label_dependent": label_dependent,
                "dependencies": dependencies, "status": "queued", "validation_status": "pending", "stale": False,
                "created_at": _now(), "started_at": None, "ended_at": None, "error": ""}
        if binding:
            task["input_artifacts"] = [copy.deepcopy(binding)]
        db.execute("INSERT INTO orchestration_tasks VALUES (?,?,?,?)", (task["task_id"], run["run_id"], key, _json(task)))
        self._event(db, run["run_id"], "task_registered", task["title"], target=role, task_id=task["task_id"])
        return task

    @staticmethod
    def _safe_section(value, evidence):
        """Filter excluded IDs, referenced rows/maps and verbatim excluded text.

        Complete original sections remain available through the owner-only result
        export. This bounded AI view is deliberately allowed to omit more data.
        """
        excluded = {e["utterance_id"] for e in evidence if e["excluded"]}
        texts = [e["text"] for e in evidence if e["excluded"] and e["text"]]
        omitted = object()
        def clean(node):
            if isinstance(node, str):
                return omitted if node in excluded or any(text in node for text in texts) else node
            if isinstance(node, list):
                children = [clean(child) for child in node]
                return [child for child in children if child is not omitted]
            if isinstance(node, dict):
                if node.get("excluded") is True:
                    return omitted
                for key, child in node.items():
                    if (key in {"id", "segment_id", "utterance_id"} or key.endswith(("_segment_id", "_utterance_id"))) and str(child) in excluded:
                        return omitted
                    if key.endswith(("segment_ids", "utterance_ids")) and isinstance(child, list) and any(str(v) in excluded for v in child):
                        return omitted
                result = {}
                for key, child in node.items():
                    if str(key) in excluded:
                        continue
                    fixed = clean(child)
                    if fixed is not omitted:
                        result[key] = fixed
                return result
            return copy.deepcopy(node)
        result = clean(value)
        return None if result is omitted else result

    def build_review_resources(self, db, run, task, context):
        from .method_experts import counterexample_review_procedure
        binding, raw = self._recheck_review_binding(db, run, task)
        delivered = [r["evidence_id"] for r in context["raw_evidence"]]
        expected = binding["interval"]["owned_evidence_ids"] + binding["interval"]["boundary_evidence_ids"]
        if set(delivered) != set(expected):
            artifact_review.reject("原文の担当区間と文脈を完全に配送する必要があります。")
        packet = {"result_id": binding["result_id"], "raw_hash": binding["raw_hash"],
            "claims": copy.deepcopy(raw["claims"]), "summary": raw.get("summary", ""),
            "coverage": copy.deepcopy(next(t["context_manifest"]["coverage"] for t in self._tasks(db, run["run_id"])
                                         if t["task_id"] == binding["task_id"])),
            "limitations": raw.get("limitations", ""), "unresolved": raw.get("unresolved", []),
            "content_status": self._source_review_binding(db, run, binding["result_id"])[2].get("content_status", "unreviewed")}
        if binding["annotation_version"] is not None:
            definitions = self._initial_label_catalog(db, run)
            if not definitions:
                artifact_review.reject("先行所見に必要な定義がありません。")
            packet["definitions"] = definitions
            packet["labels"] = copy.deepcopy(context.get("labels", {}))
        return {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task), "question": task["title"],
            "data_version": run["input_hash"], "annotation_version": task["annotation_version"],
            "raw_evidence": context["raw_evidence"], "coverage": context["coverage"],
            "input_artifacts": [binding], "finding_resource": packet,
            "review_procedure": counterexample_review_procedure(), "research_mode": "exploratory",
            "execution_allowed": False, "blind_first": False,
            "resources_origin": {"run_id": run["run_id"], "initial_id": run["initial_id"]}}

    def _context(self, db, run, task):
        if task.get("input_artifacts") or task["intent"].get("kind") == "finding_review":
            self._recheck_review_binding(db, run, task)
        context = self._base_context(db, run, task)
        if task["intent"].get("kind") == "finding_review":
            context = self.build_review_resources(db, run, task, context)
        if run["config"].get("artifact_review_version"):
            context["artifact_review_version"] = artifact_review.VERSION
            if task["role"] == "orchestrator":
                domain = task["intent"]["scope"]["domain"]
                candidates, omitted = self._artifact_candidates(db, run, domain)
                context["artifact_candidates"] = candidates
                context["artifact_candidate_scope"] = {"omitted_count": omitted, "ordering": "result_insertion"}
                latest = {r["result_id"]: r for r in self._artifact_history(db, run, domain)}
                context["unresolved_artifact_decisions"] = [r for r in latest.values() if r["disposition"] == "defer"]
        return context

    def _base_context(self, db, run, task):
        initial = self._initial(db, run["initial_id"])
        raw = [e for e in initial["evidence"] if not e["excluded"]]
        selected = task["intent"].get("evidence_ids", [])
        if run["config"].get("specialist_orchestration_version") and task["role"] == "critic" and task["phase"] == "stop_review":
            selected = sorted({ref for claim in run["current_view"].get("claims", []) for ref in claim["evidence_ids"]})
        if selected:
            raw = [e for e in raw if e["evidence_id"] in selected]
        available_count = len(raw)
        bounded, size = [], 0
        for evidence in raw:
            page = task["kind"] == "ai" and (run["config"].get("model_context_version") and task["phase"] == "initial_analysis"
                    or _scope(task["intent"]).get("interval_id"))
            if not page and (len(bounded) >= run["config"]["context_evidence_limit"] or size + len(evidence["text"]) > run["config"]["context_text_limit"]):
                break
            bounded.append(evidence); size += len(evidence["text"])
        raw = bounded
        # The immutable snapshot retains per-row hashes and versions.
        raw = [{key: entry[key] for key in ("evidence_id", "utterance_id", "text", "speaker", "start", "end")}
               for entry in raw]
        evidence_index = [{"evidence_id": e["evidence_id"], "utterance_id": e["utterance_id"]}
                          for e in initial["evidence"] if not e["excluded"]]
        index_count = len(evidence_index)
        index_limit = run["config"].get("context_index_limit", 0)
        if index_limit:
            evidence_index = evidence_index[:index_limit]
        coverage = {"available_count": available_count, "provided_count": len(raw), "omitted_count": available_count - len(raw),
                    "complete": len(raw) == available_count, "scope": "selected" if selected else "dataset",
                    "evidence_index": evidence_index, "index_available_count": index_count,
                    "index_provided_count": len(evidence_index), "index_omitted_count": index_count - len(evidence_index)}
        initial_report = copy.deepcopy(run.get("initial_analysis_report"))
        scope = _scope(task["intent"])
        if run["config"].get("model_context_version") and initial_report and "requirement_keys" in scope:
            initial_report["full_report_hash"] = fingerprint(initial_report)
            initial_report["label_requirements"] = [entry for entry in initial_report["label_requirements"] if fingerprint(entry) in scope["requirement_keys"]]
            source_results = {source["result_id"] for entry in initial_report["label_requirements"] for source in entry["sources"]}
            initial_report["reports"] = [report for report in initial_report["reports"] if report["result_id"] in source_results]
            initial_report["requirement_scope"] = "selected; remaining requirements have separate Handler tasks"
        if isinstance(task["intent"].get("scope"), dict) and task["intent"]["scope"].get("owned_evidence_ids"):
            coverage["page"] = copy.deepcopy(task["intent"]["scope"])
            if task["role"] == "verification":
                coverage["page"].pop("title", None)
            coverage["owned_count"] = len(coverage["page"]["owned_evidence_ids"])
            coverage["boundary_count"] = len(coverage["page"].get("boundary_evidence_ids", []))
        if task["role"] == "interpretation" and task["phase"] == "initial_labels" and task["method_id"] == "label-design-v1":
            return {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task),
                    "question": run["config"]["question"], "data_version": run["input_hash"],
                    "annotation_version": task["annotation_version"], "raw_evidence": copy.deepcopy(raw),
                    "coverage": coverage, "research_mode": "exploratory", "execution_allowed": False,
                    "initial_analysis_report": initial_report,
                    "routing_instruction": copy.deepcopy(task["intent"]),
                    "budget": {"iteration": run["iteration"], "completed_core_iterations": self._completed_core_iterations(db, run)}}
        if task["phase"] == "initial_analysis" and task["role"] in {"interpretation", "critic"}:
            # Initial specialists inspect the same source independently, even
            # when a faster worker has already reported to the Handler.
            context = {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task),
                       "question": run["config"]["question"], "data_version": run["input_hash"],
                       "annotation_version": task["annotation_version"], "raw_evidence": copy.deepcopy(raw),
                       "coverage": coverage, "research_mode": "exploratory", "execution_allowed": False}
            if task["role"] == "critic":
                context["review_target"] = {"target_id": task["intent"]["target_id"],
                    "target_version": task["intent"]["target_version"],
                    "view": {"question": run["config"]["question"], "scope": "initial_analysis_plan"}}
            return context
        # Deliberately construct the blind packet from an allowlist. Even the
        # Core-written question/success criteria may disclose its expected answer.
        if task["role"] == "verification" and task["intent"].get("kind") == "clarification":
            target = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                (task["intent"].get("result_id"), run["run_id"])).fetchone()
            if target is None:
                raise _error("説明対象が見つかりません。", "clarification_target_missing")
            content, metadata = json.loads(target[0]), json.loads(target[1])
            if metadata.get("role") != "verification" or metadata.get("validation_status") != "valid":
                raise _error("独立検証以外の結果はこの対話に渡せません。", "clarification_target_mismatch")
            if fingerprint(content) != metadata["raw_hash"]:
                raise _error("保存済み結果のhashが一致しません。", "result_integrity_mismatch")
            references = {ref for claim in content.get("claims", []) for ref in claim.get("evidence_ids", [])}
            relevant = [e for e in initial["evidence"] if not e["excluded"] and e["evidence_id"] in references]
            provided, size = [], 0
            for evidence in relevant:
                if len(provided) >= run["config"]["context_evidence_limit"] or size + len(evidence["text"]) > run["config"]["context_text_limit"]:
                    break
                provided.append(evidence); size += len(evidence["text"])
            return {"schema_version": SCHEMA_VERSION, "task": {"task_id": task["task_id"], "role": "verification"},
                    "question": task["title"], "data_version": metadata["dataset_version"],
                    "annotation_version": metadata["annotation_version"], "raw_evidence": [
                        {key: row[key] for key in ("evidence_id", "utterance_id", "text", "speaker", "start", "end")}
                        for row in provided],
                    "coverage": {"available_count": len(relevant), "provided_count": len(provided),
                                 "omitted_count": len(relevant) - len(provided), "complete": len(relevant) == len(provided),
                                 "scope": "saved_verification_result"},
                    "clarification_target": {"metadata": metadata,
                        "content": content if len(target[0]) <= 16000 else {"content_excerpt": target[0][:16000], "truncated": True}},
                    "blind_first": False, "execution_allowed": False, "research_mode": "exploratory"}
        if task["role"] == "verification":
            return {"schema_version": SCHEMA_VERSION, "task": {"task_id": task["task_id"], "role": "verification",
                    **({"phase": "initial_analysis"} if task["phase"] == "initial_analysis" else {})},
                    "question": run["config"]["question"] if task["phase"] == "initial_analysis" else "原文から観察事実、矛盾、判断できない点を独立に確認してください。",
                    "data_version": run["input_hash"], "annotation_version": task["annotation_version"],
                    "raw_evidence": copy.deepcopy(raw), "coverage": coverage, "blind_first": True,
                    "research_mode": "exploratory"}
        if task["phase"] == "label_review":
            return {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task),
                    "question": task["title"], "data_version": run["input_hash"],
                    "annotation_version": task["annotation_version"], "raw_evidence": copy.deepcopy(raw),
                    "coverage": coverage, "initial_label_catalog": self._initial_label_catalog(db, run),
                    "review_target": {"target_id": task["intent"]["target_id"], "target_version": task["intent"]["target_version"]},
                    "research_mode": "exploratory"}
        public = self._public(db, run)
        accepted = []
        for result in public["results"]:
            if result["validation_status"] == "valid":
                row = db.execute("SELECT raw_json FROM orchestration_results WHERE result_id=?", (result["result_id"],)).fetchone()
                content = json.loads(row[0])
                if fingerprint(content) != result["raw_hash"]:
                    raise _error("保存済み結果のhashが一致しません。", "result_integrity_mismatch")
                if result["result_id"] in run.get("initial_label_result_ids", [run.get("initial_label_result_id")]):
                    content = {"summary": content.get("summary", ""), "claims": content.get("claims", []),
                               "label_definitions_ref": "initial_label_catalog"}
                elif len(row[0]) > 16000 and not result.get("derived_from"):
                    content = {"summary": content.get("summary", ""), "claims": content.get("claims", [])[:24], "omitted_full_result": True}
                accepted.append({**result, "content": content})
        pending_results = self._review_pending(db, run, task) if run["config"].get("core_progress_version") else []
        pending_batch = pending_results[:20]
        if task["role"] in {"core", "orchestrator"} and run["config"].get("core_progress_version"):
            batch = [result for result in accepted if result["result_id"] in pending_batch]
            previous = [result for result in accepted if result["result_id"] not in pending_batch]
            accepted = batch + (previous[-(20 - len(batch)):] if len(batch) < 20 else [])
        else:
            accepted = accepted[-20:]
        context = {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task), "question": run["config"]["question"],
                   "data_version": run["input_hash"], "annotation_version": task["annotation_version"],
                   "raw_evidence": copy.deepcopy(raw), "coverage": coverage, "research_mode": "exploratory",
                   "current_view": run["current_view"], "view_version": run["view_version"],
                   "initial": {"initial_id": run["initial_id"], "available_sections": [section for section in initial["analysis"] if section in INITIAL_SECTIONS],
                               "full_results_preserved": True, "read_scope": "index_only"},
                   "results": accepted, "issues": public["issues"], "critique_responses": public["critique_responses"],
                   "dependency_task_ids": [entry["task_id"] for entry in public["tasks"] if entry["status"] == "succeeded"],
                   "label_proposals": public["label_proposals"], "usage": public["usage"],
                   "budget": {"remaining_calls": run["config"]["max_calls"] - run["calls_started"],
                              "remaining_tasks": run["config"]["max_tasks"] - len(public["tasks"]),
                              "max_iterations": run["config"]["max_iterations"], "iteration": run["iteration"],
                              "min_iterations": run["config"].get("min_iterations", 0),
                              "completed_core_iterations": self._completed_core_iterations(db, run),
                              "deadline": run["deadline"]}, "stop_proposal": run["pending_stop"]}
        if run.get("analysis_partition") and task["role"] in {"core", "orchestrator"}:
            context["analysis_interval_index"] = [{k: i[k] for k in ("interval_id", "parent_topic_id", "start", "end")}
                for i in run["analysis_partition"]["intervals"]]
        if run["config"].get("initial_label_definitions_version"):
            context["initial_label_catalog"] = self._initial_label_catalog(db, run)
            if task["role"] == "core" and task["phase"] != "initial_routing" and not context["initial_label_catalog"]:
                raise _error("初回の専門家によるラベル・尺度出力が必要です。", "initial_labels_missing")
        if run.get("initial_analysis_report"):
            context["initial_analysis_report"] = initial_report
        if task["role"] in {"core", "orchestrator"} and run["config"].get("core_progress_version"):
            context["iteration_review"] = {
                "previous_decision_id": run["last_decision_id"],
                "pending_result_ids": pending_batch,
                "omitted_pending_result_count": len(pending_results) - len(pending_batch),
                "progress_required": True,
            }
            if task["phase"] == "initial_routing":
                context["iteration_review"].update(pending_result_ids=[], omitted_pending_result_count=0, progress_required=False)
            if run["config"].get("model_context_version"):
                unread = set(pending_results) - set(pending_batch)
                all_issues = context["issues"]
                context["issues"] = [issue for issue in all_issues if issue["status"] == "open" and issue["result_id"] not in unread]
                context["issue_scope"] = {"unread_result_issue_count": sum(issue["status"] == "open" and issue["result_id"] in unread for issue in all_issues),
                    "resolved_issue_count": sum(issue["status"] != "open" for issue in all_issues), "full_issue_index_hash": fingerprint(all_issues)}
        context["labels"] = json.loads(db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                                                    (run["run_id"], task["annotation_version"])).fetchone()[0])
        included_ids = {e["utterance_id"] for e in raw}
        context["labels"] = {key: value for key, value in context["labels"].items() if key in included_ids}
        if run["config"].get("initial_label_definitions_version"):
            context["labels"] = {key: {field: item for field, item in value.items() if field in LABEL_FIELDS}
                                 for key, value in context["labels"].items() if isinstance(value, dict)}
        if run["config"].get("specialist_orchestration_version"):
            if task["role"] == "orchestrator":
                context["review_domain"] = task["intent"]["scope"]["domain"]
                context["prior_domain_reports"] = [r for r in self._domain_reports(db, run)
                    if r["domain"] == context["review_domain"] and r["annotation_version"] == task["annotation_version"]]
                context.pop("initial_analysis_report", None)
                context.pop("current_view", None)
                context.pop("stop_proposal", None)
                context.pop("critique_responses", None)
                context["results"] = [r for r in accepted if r["result_id"] in pending_batch]
                context["issues"] = [i for i in context["issues"] if i["result_id"] in pending_batch]
                context["label_proposals"] = [p for p in context["label_proposals"] if p["result_id"] in pending_batch]
                if context["review_domain"] != "labels":
                    context["label_proposals"] = []
                    context.pop("initial_label_catalog", None)
                context["dependency_task_ids"] = [r["task_id"] for r in context["results"]]
            elif task["role"] == "core" and task["phase"] != "initial_routing":
                context["domain_reports"] = self._domain_reports(db, run)
                context["results"] = []
                context["issues"] = []
                context["label_proposals"] = []
                context["review_scope"] = "specialist_reports_not_full_raw_results"
            elif task["role"] in {"interpretation", "critic"} and task["phase"] != "initial_analysis":
                # New analysis reads its scoped source. Saved-result dialogue is
                # supplied separately by the clarification contract below.
                context.pop("initial_analysis_report", None)
                context["results"] = []
                context["issues"] = []
                context["critique_responses"] = []
                context["label_proposals"] = []
                context["dependency_task_ids"] = task["dependencies"]
                if not task["label_dependent"]:
                    context.pop("initial_label_catalog", None)
                if task["role"] == "interpretation":
                    context.pop("current_view", None)
                    context.pop("stop_proposal", None)
        if task["intent"].get("kind") == "clarification":
            target = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                (task["intent"].get("result_id"), run["run_id"])).fetchone()
            if task["intent"].get("result_id") == run["initial_id"]:
                sections = {}
                remaining = 16000
                eligible = {e["utterance_id"] for e in initial["evidence"] if not e["excluded"]}
                for section in task["intent"].get("initial_sections", []):
                    value = self._safe_section(initial["analysis"][section], initial["evidence"])
                    if section == "segments":
                        value = [s for s in (value or []) if str(s.get("id", s.get("segment_id"))) in eligible]
                    elif section == "annotations":
                        value = {k: v for k, v in (value or {}).items() if k in eligible}
                    encoded = _json(value)
                    sections[section] = value if len(encoded) <= remaining else {"content_excerpt": encoded[:remaining], "truncated": True}
                    remaining = max(0, remaining - len(encoded))
                context["clarification_target"] = {"initial_id": run["initial_id"], "sections": sections, "read_only": True}
            else:
                encoded = target[0]
                content = json.loads(encoded) if len(encoded) <= 16000 else {"content_excerpt": encoded[:16000], "truncated": True}
                context["clarification_target"] = {"metadata": json.loads(target[1]), "content": content}
            context["execution_allowed"] = False
        if task["role"] == "critic":
            context["review_target"] = {"target_id": task["intent"]["target_id"], "target_version": task["intent"]["target_version"],
                                        "evidence_version": fingerprint([run["input_hash"], run["annotation_version"]]), "view": run["current_view"], "stop": run["pending_stop"]}
        return copy.deepcopy(context)

    def _check(self, run_id, generation, task_id=None):
        with self._db() as db:
            run = self._read_run(db, run_id)
            limit = "source_deleted" if self.find_item(run["item_id"]) is None else self._limit(db, run)
            if limit and run["status"] not in TERMINAL:
                self._stop(db, run, limit)
            if limit or run["status"] in TERMINAL or run["generation"] != generation:
                raise ExecutionStopped(run["stop_reason"] or "stopped")
            if task_id:
                row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()
                task = json.loads(row[0])
                if task.get("started_epoch") and time.time() - task["started_epoch"] > run["config"]["call_timeout_seconds"]:
                    self._stop(db, run, "call_timeout")
                    raise ExecutionStopped("call_timeout")

    def _record_usage(self, run_id, task_id, usage=None, **values):
        data = dict(usage or {}, **values)
        if "context_manifest" in data:
            manifest = copy.deepcopy(data["context_manifest"])
            with self._db() as db:
                run = self._read_run(db, run_id)
                task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",
                                             (task_id, run_id)).fetchone()[0])
                if manifest.get("version") != (artifact_review.MANIFEST_VERSION if run["config"].get("artifact_review_version") else 1) or manifest.get("dataset_version") != run["input_hash"]:
                    raise _error("入力パケットの版が一致しません。", "context_manifest_invalid")
                scope = _scope(task["intent"])
                if scope.get("interval_id") and (manifest.get("analysis_interval") != scope or
                        set(scope["owned_evidence_ids"] + scope["boundary_evidence_ids"]) != set(manifest.get("provided_evidence_ids", []))):
                    raise _error("担当原文または文脈原文が入力から欠落しています。", "context_manifest_invalid")
                if manifest.get("evidence_transport_version") == 1:
                    from .services.model_context import digest
                    mapping = manifest.get("reference_map")
                    if not isinstance(mapping, dict) or digest(mapping) != manifest.get("reference_map_sha256"):
                        raise _error("根拠対応表のhashが一致しません。", "context_manifest_invalid")
                pending = self._review_pending(db, run, task)
                if task.get("input_artifacts"):
                    binding, _ = self._recheck_review_binding(db, run, task)
                    from .services.model_context import digest, transform_references
                    packet = self.build_review_resources(db, run, task, self._base_context(db, run, task))["finding_resource"]
                    mapping = manifest.get("reference_map")
                    packet_hash = digest(transform_references(packet, mapping)) if mapping is not None else digest(packet)
                    if (manifest.get("input_artifacts") != [binding]
                            or manifest.get("finding_packet_sha256") != packet_hash or manifest.get("review_procedure") != binding["procedure"]):
                        artifact_review.reject("資料packetと入力manifestの束縛が不正です。", "context_manifest_invalid")
                if run["config"].get("artifact_review_version") and task["role"] == "orchestrator":
                    candidates, omitted = self._artifact_candidates(db, run, task["intent"]["scope"]["domain"])
                    presented = manifest.get("artifact_candidates", [])
                    expected_omitted = omitted + len(candidates) - len(presented)
                    if (presented != candidates[:len(presented)] or candidates and not presented
                            or manifest.get("artifact_candidate_scope", {}).get("omitted_count") != expected_omitted):
                        artifact_review.reject("候補の提示範囲と未提示件数が不正です。", "context_manifest_invalid")
                requested = manifest.get("requested_result_ids", [])
                if task["role"] in {"core", "orchestrator"} and task["phase"] != "initial_routing" and (requested != pending[:len(requested)] or pending and not requested):
                    raise _error("未評価結果の先頭から順に処理してください。", "context_manifest_invalid")
                task["context_manifest"] = manifest
                task["context_manifest_hash"] = fingerprint(manifest)
                self._write_task(db, task)
                self._event(db, run_id, "context_prepared", "入力範囲とモデルの予算を保存しました。",
                            task_id=task_id, context_manifest_hash=task["context_manifest_hash"])
            return
        if data.get("reported") is False:
            return
        record = {"task_id": task_id, "reported_at": _now()}
        for key in ("input_tokens", "output_tokens", "total_tokens", "cost"):
            value = data.get(key)
            if type(value) in {int, float} and math.isfinite(value) and value >= 0:
                record[key] = value
        if not any(k in record for k in ("input_tokens", "output_tokens", "total_tokens", "cost")):
            return
        if data.get("currency") == "USD":
            record["currency"] = "USD"
        usage_id = str(data.get("usage_id") or task_id + ":response")
        with self._db() as db:
            db.execute("INSERT OR IGNORE INTO orchestration_usage VALUES (?,?,?,?)", (run_id + ":" + usage_id, run_id, task_id, _json(record)))

    def _execute(self, run_id: str, task_id: str):
        with self._db() as db:
            run = self._read_run(db, run_id)
            row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()
            task = json.loads(row[0])
            if task["status"] != "queued" or run["status"] in TERMINAL:
                return
            self._check_version(run)
            if task.get("input_artifacts"):
                try:
                    self._recheck_review_binding(db, run, task)
                except AnalysisContractError as exc:
                    task.update(status="failed", validation_status="rejected", error=exc.code, ended_at=_now())
                    self._write_task(db, task)
                    self._event(db, run_id, "preflight_rejected", exc.code, task_id=task_id)
                    run["error"] = exc.code
                    self._stop(db, run, "execution_failure")
                    return
            limit = self._limit(db, run)
            if limit:
                self._stop(db, run, limit)
                return
            task.update(status="running", started_at=_now(), started_epoch=time.time(), generation=run["generation"])
            run["calls_started" if task["kind"] == "ai" else "code_executions"] += 1
            self._write_task(db, task)
            self._write_run(db, run)
            self._event(db, run_id, "task_started", task["title"], target=task["role"], task_id=task_id)
            context = self._context(db, run, task)
            ai_snapshot = self._initial(db, run["initial_id"]) if task["kind"] == "ai" else None
            experts = ai_snapshot["analysis"].get("experts") if ai_snapshot and run["config"].get("model_context_version") and task["role"] == "interpretation" else None
            snapshot = self._initial(db, run["initial_id"]) if task["kind"] == "code" else None
            if snapshot is not None:
                snapshot["orchestration_task"] = copy.deepcopy(task)
                snapshot["orchestration_labels"] = json.loads(db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                    (run_id, task["annotation_version"])).fetchone()[0])
        check = lambda: self._check(run_id, task["generation"], task_id)
        try:
            check()
            if task["kind"] == "code":
                raw = self.method_runner(task["method_id"], snapshot)
                if task["phase"] == "initial_analysis":
                    # Existing code methods use saved participation/time/label
                    # fields; they do not invent new research scales.
                    raw = {**raw, "label_requirements": [],
                           "requirement_scope": "既存の入力項目による集計。研究概念の尺度設計は専門家の報告を参照する。"}
                    if (task["method_id"] == "label_frequency" and raw.get("denominator", 0) > 0
                            and raw.get("missing_count") == raw["denominator"] and context["raw_evidence"]):
                        raw["label_requirements"] = [{"requirement_id": "codes_for_frequency", "kind": "label",
                            "name": "研究質問に対応する分類ラベル", "analysis": "研究質問に対応する分類別の度数集計",
                            "reason": f"既存codesは対象{raw['denominator']}発話の全件が欠測で、分類別集計ができない。原文に基づく定義と、その後の発話への付与が必要。",
                            "evidence_ids": [context["raw_evidence"][0]["evidence_id"]]}]
            else:
                references = run["config"].get("context_reference_version") == 1
                brief = None
                if run["config"].get("model_context_version") and task["role"] == "interpretation" and not task.get("input_artifacts") and (references or task["phase"] != "initial_labels"):
                    from . import method_experts
                    if method_experts.ai_block_reason(experts):
                        raise _error("選択した専門家のAI補助条件が未成立です。", "expert_knowledge_unavailable")
                    try:
                        brief = method_experts.ai_context(experts, step_ids=run["config"].get("expert_step_ids"))
                    except method_experts.ExpertDefinitionError:
                        raise _error("専門家の定義・知識・許可手順を再確認してください。", "expert_knowledge_unavailable") from None
                    context["expert_knowledge"] = {"version": 1, "stage": task["phase"],
                        "status": "method_brief" if brief else "generic", "brief": brief}
                if references and not task.get("input_artifacts"):
                    from . import method_experts
                    try:
                        context["expert_knowledge"] = method_experts.orchestration_context(stage=task["phase"], brief=brief)
                    except method_experts.ExpertDefinitionError:
                        raise _error("参照するObsidian知識のID・状態・必須節・入力上限を確認してください。", "expert_knowledge_unavailable") from None
                    context["resources_origin"] = {"initial_id": run["initial_id"], "run_id": run["run_id"]}
                options = {**copy.deepcopy(run["config"]), **run["config"]["roles"][task["role"]], "timeout_seconds": run["config"]["call_timeout_seconds"],
                           "deadline": run["deadline"], "research_mode": "exploratory", "provider_policy": run["config"]["provider_policy"]}
                options["_reference_evidence"] = [
                    {key: row[key] for key in ("evidence_id", "utterance_id")}
                    for row in ai_snapshot["evidence"] if not row["excluded"]]
                if (run["config"].get("model_context_version") or run["config"].get("analysis_interval_version")) and task["role"] in {"core", "orchestrator"} and task["phase"] != "initial_routing":
                    options["_source_evidence"] = [{key: row[key] for key in ("evidence_id", "utterance_id", "text", "speaker", "start", "end")}
                        for row in ai_snapshot["evidence"] if not row["excluded"]]
                from .services.model_context import ReferenceResponseError
                reference_error = ""
                try:
                    raw = self.agent_runner(task["role"], context, options, check,
                                            lambda usage=None, **kw: self._record_usage(run_id, task_id, usage, **kw))
                except ReferenceResponseError as exc:
                    raw, reference_error = exc.response, exc.code
            # Raw response commits before semantic validation, including a late response.
            raw_json = _json(raw)
            with self._db() as db:
                latest = self._read_run(db, run_id)
                if self.find_item(latest["item_id"]) is None and latest["status"] not in TERMINAL:
                    self._stop(db, latest, "source_deleted")
                limit = self._limit(db, latest)
                if not limit and time.time() - task["started_epoch"] > latest["config"]["call_timeout_seconds"]:
                    limit = "call_timeout"
                if limit and latest["status"] not in TERMINAL:
                    self._stop(db, latest, limit)
                late = latest["status"] in TERMINAL or latest["generation"] != task["generation"]
                metadata = {"result_id": _id("result"), "run_id": run_id, "task_id": task_id, "role": task["role"],
                            "attempt_id": task["attempt_id"], "received_at": _now(), "raw_hash": fingerprint(raw),
                            "dataset_version": task["dataset_version"], "annotation_version": task["annotation_version"],
                            "validation_status": "quarantined" if late else "received", "content_status": "unreviewed",
                            "error": "late_response_after_stop" if late else "", "stale": False}
                scope = _scope(task["intent"])
                if scope.get("interval_id"):
                    metadata["interval_lineage"] = {k: scope.get(k) for k in
                        ("interval_id", "parent_interval_id", "parent_topic_id", "dataset_version", "ownership_sha256")}
                if task["kind"] == "ai" and reference_error:
                    metadata["reference_error"] = reference_error
                if task.get("input_artifacts"):
                    metadata["derived_from"] = copy.deepcopy(task["input_artifacts"])
                    metadata["independent_verification"] = False
                if (latest["config"].get("model_context_version") or latest["config"].get("analysis_interval_version")) and task["kind"] == "ai":
                    stored_task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                    metadata["context_manifest_hash"] = stored_task.get("context_manifest_hash")
                db.execute("INSERT OR IGNORE INTO orchestration_results VALUES (?,?,?,?,?)", (metadata["result_id"], run_id, task_id, raw_json, _json(metadata)))
                current_task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                current_task.update(status="quarantined" if late else "received", ended_at=_now(), result_id=metadata["result_id"],
                                    validation_status=metadata["validation_status"], error=metadata["error"])
                self._write_task(db, current_task)
                self._event(db, run_id, "raw_received", "原結果を保存しました。", source=task["role"], target="handler", task_id=task_id)
            if not late:
                self._validate_received(run_id, task_id)
        except ExecutionStopped:
            with self._db() as db:
                current = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                if current["status"] in {"running", "cancel_requested"}:
                    current.update(status="cancelled", ended_at=_now(), error="cooperative_stop")
                    self._write_task(db, current)
        except Exception as exc:
            with self._db() as db:
                current = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                # Transport errors may have consumed external work. Never retry blind.
                before_dispatch = getattr(exc, "code", "") in {"context_budget_exceeded", "context_budget_unavailable", "context_manifest_invalid", "expert_knowledge_unavailable", "artifact_input_invalid", "result_integrity_mismatch", "provider_unavailable"}
                owned = current["intent"].get("scope", {}).get("owned_evidence_ids", []) if isinstance(current["intent"].get("scope"), dict) else []
                latest = self._read_run(db, run_id)
                if (getattr(exc, "code", "") == "context_budget_exceeded" and current["phase"] in {"initial_routing", "initial_labels"}
                        and latest["config"].get("model_context_version") and latest["status"] not in TERMINAL):
                    selected_keys = _scope(current["intent"]).get("requirement_keys")
                    if selected_keys is None:
                        selected_keys = [fingerprint(entry) for entry in latest["initial_analysis_report"]["label_requirements"]]
                    if len(selected_keys) > 1:
                        child_phase = current["phase"]
                        current.update(status="blocked", phase=child_phase + "_split", ended_at=_now(), error="context_requirement_split")
                        self._write_task(db, current)
                        latest["calls_started"] -= 1
                        for keys in (selected_keys[:len(selected_keys) // 2], selected_keys[len(selected_keys) // 2:]):
                            intent = copy.deepcopy(current["intent"])
                            intent.update(parent_task_id=task_id, scope={"requirement_keys": keys, "split_from_task_id": task_id})
                            if child_phase == "initial_labels":
                                requirements = [entry for entry in latest["initial_analysis_report"]["label_requirements"] if fingerprint(entry) in keys]
                                intent["evidence_ids"] = sorted({ref for entry in requirements for ref in entry["evidence_ids"]})
                            self._register(db, latest, intent, phase=child_phase, automatic=True)
                        self._write_run(db, latest)
                        self._event(db, run_id, "context_requirement_split", "必須要件を保持したまま、Coreへの報告を分割して保存しました。", task_id=task_id)
                        return
                if (getattr(exc, "code", "") == "context_budget_exceeded" and not current.get("input_artifacts") and (current["phase"] == "initial_analysis" or
                        _scope(current["intent"]).get("interval_id"))
                        and len(owned) > 1 and latest["status"] not in TERMINAL):
                    child_phase = current["phase"]
                    current.update(status="blocked", phase=child_phase + "_split", ended_at=_now(), error="context_page_split")
                    self._write_task(db, current)
                    rows = [e["evidence_id"] for e in self._initial(db, latest["initial_id"])["evidence"] if not e["excluded"]]
                    latest["calls_started"] -= 1  # This attempt never reached inference.
                    for part in (owned[:len(owned) // 2], owned[len(owned) // 2:]):
                        first, last = rows.index(part[0]), rows.index(part[-1]) + 1
                        visible = rows[max(0, first - 1):min(len(rows), last + 1)]
                        intent = copy.deepcopy(current["intent"])
                        intent.update(evidence_ids=visible, parent_task_id=task_id,
                            scope={"owned_evidence_ids": part, "boundary_evidence_ids": [ref for ref in visible if ref not in part],
                                   "split_from_task_id": task_id})
                        if latest["config"].get("analysis_interval_version"):
                            from .services.analysis_intervals import make_interval, interval_scope
                            pool = [e for e in self._initial(db, latest["initial_id"])["evidence"] if not e["excluded"]]
                            parent = current["intent"]["scope"]
                            source_interval = next(i for i in latest["analysis_partition"]["intervals"] + latest.get("interval_refinements", [])
                                                   if i["interval_id"] == parent["interval_id"])
                            interval = make_interval(pool, first, last, dataset_version=latest["input_hash"],
                                parent_topic_id=parent["parent_topic_id"], title=source_interval.get("title", ""),
                                method="budget_split", parent_interval_id=parent["interval_id"])
                            refinements = latest.setdefault("interval_refinements", [])
                            if not any(i["interval_id"] == interval["interval_id"] for i in refinements):
                                refinements.append(interval)
                            intent["scope"] = interval_scope(interval, blind=current["role"] == "verification")
                        self._register(db, latest, intent, phase=child_phase, automatic=True)
                    self._write_run(db, latest)
                    self._event(db, run_id, "context_page_split", "未送信の範囲を分割し、次の専門家タスクとして保存しました。", task_id=task_id)
                    return
                current.update(status="uncertain" if task["kind"] == "ai" and not before_dispatch else "failed", ended_at=_now(), error=getattr(exc, "code", type(exc).__name__))
                self._write_task(db, current)
                if before_dispatch:
                    latest["calls_started"] -= 1
                    self._write_run(db, latest)
                if latest["status"] not in TERMINAL and task["kind"] == "ai" and not before_dispatch:
                    latest.update(status="recovery_required", error="外部呼出しの実行結果が不明です。自動再試行しません。")
                    self._write_run(db, latest)
                event = "preflight_rejected" if before_dispatch else "execution_uncertain" if task["kind"] == "ai" else "task_failed"
                self._event(db, run_id, event, getattr(exc, "code", type(exc).__name__), task_id=task_id)

    def _validate_received(self, run_id, task_id):
        with self._db() as db:
            run = self._read_run(db, run_id)
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
            row = db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (task_id,)).fetchone()
            meta, raw = json.loads(row["state_json"]), json.loads(row["raw_json"])
            if (fingerprint(raw) != meta["raw_hash"] or meta.get("task_id") != task_id
                    or meta.get("run_id") != run_id or meta.get("result_id") != row["result_id"]
                    or meta.get("attempt_id") != task["attempt_id"]):
                meta.update(validation_status="quarantined", error="result_integrity_mismatch")
                task.update(status="quarantined", validation_status="quarantined", error="result_integrity_mismatch")
                db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), row["result_id"]))
                self._write_task(db, task)
                self._event(db, run_id, "result_quarantined", "result_integrity_mismatch", task_id=task_id)
                return
            if meta["validation_status"] != "received":
                if task["status"] == "received":
                    task.update(status="succeeded" if meta["validation_status"] == "valid" else "quarantined",
                                validation_status=meta["validation_status"], result_id=meta["result_id"])
                    self._write_task(db, task)
                return
            try:
                self._check_input_manifest(run, task, meta)
                if meta.get("reference_error"):
                    raise _error("対応表にない根拠参照です。", "evidence_missing")
                if len(row["raw_json"].encode("utf-8")) > run["config"]["max_result_bytes"]:
                    raise _error("結果が保存上限を超えています。", "result_size_limit")
                if run["status"] in TERMINAL:
                    raise _error("停止後の結果は採用しません。", "late_response_after_stop")
                self._validate_result(db, run, task, raw)
                meta.update(validation_status="valid", error="")
                task.update(status="succeeded", validation_status="valid", error="")
                if task.get("input_artifacts"):
                    scope = task["input_artifacts"][0]["interval"]
                    meta["review_status"] = "insufficient" if any(r["verdict"] == "insufficient" for r in raw["claim_verdicts"]) else "checked_in_scope"
                    meta["claim_evidence_scope"] = [{"claim_id": r["claim_id"],
                        "owned_evidence_ids": [e for e in r["evidence_ids"] if e in scope["owned_evidence_ids"]],
                        "boundary_evidence_ids": [e for e in r["evidence_ids"] if e in scope["boundary_evidence_ids"]]}
                        for r in raw["claim_verdicts"]]
                if task["role"] == "critic":
                    self._save_issues(db, run, task, raw, meta)
                for patch in raw.get("label_patches", []):
                    self._save_patch(db, run, task, patch, meta)
                delegated = run["config"].get("specialist_orchestration_version") and task["role"] not in {"core", "orchestrator"}
                self._event(db, run_id, "result_validated", "保存済み・形式確認済みとして専門側へ渡します。" if delegated else "保存済み・内容未検証としてCoreへ渡します。",
                            source="handler", target="orchestrator" if delegated else "core", task_id=task_id)
                if task["phase"] == "initial_analysis":
                    self._event(db, run_id, "initial_requirements_reported", "初回分析の結果とラベル・尺度の必要性をハンドラーが受領しました。",
                                source=task["role"], target="handler", task_id=task_id,
                                result_id=meta["result_id"], raw_hash=meta["raw_hash"],
                                requirement_count=len(raw["label_requirements"]))
            except (AnalysisContractError, ValueError, TypeError, KeyError) as exc:
                code = getattr(exc, "code", "invalid_result")
                meta.update(validation_status="quarantined", error=code)
                task.update(status="quarantined", validation_status="quarantined", error=code)
                self._event(db, run_id, "result_quarantined", code, task_id=task_id)
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), meta["result_id"]))
            self._write_task(db, task)

    def _label_design_evidence_ids(self, db, run, task=None):
        if task and (run["config"].get("model_context_version") or run["config"].get("analysis_interval_version")):
            manifest = task.get("context_manifest")
            if manifest:
                if fingerprint(manifest) != task.get("context_manifest_hash"):
                    raise _error("入力記録のhashが一致しません。", "context_manifest_invalid")
                return set(manifest["provided_evidence_ids"])
            if task["intent"].get("evidence_ids"):
                return set(task["intent"]["evidence_ids"])
        included, size = set(), 0
        for entry in self._initial(db, run["initial_id"])["evidence"]:
            if entry["excluded"]:
                continue
            if len(included) >= run["config"]["context_evidence_limit"] or size + len(entry["text"]) > run["config"]["context_text_limit"]:
                break
            included.add(entry["evidence_id"])
            size += len(entry["text"])
        return included

    def _collect_initial_analysis(self, db, run):
        reports, requirements = [], {}
        tasks = [task for task in self._tasks(db, run["run_id"]) if task["phase"] == "initial_analysis"]
        expected = {("interpretation", "agent-v1"), ("verification", "agent-v1"), ("critic", "agent-v1"),
                    *(("statistics", method) for method in METHODS)}
        paged = run["config"].get("model_context_version") or run["config"].get("analysis_interval_version")
        if {(task["role"], task["method_id"]) for task in tasks} != expected or not paged and len(tasks) != len(expected):
            raise _error("初回分析の担当が揃っていません。", "initial_analysis_incomplete")
        if paged:
            all_ids = {e["evidence_id"] for e in self._initial(db, run["initial_id"])["evidence"] if not e["excluded"]}
            for role in ("interpretation", "verification", "critic"):
                owned = [ref for task in tasks if task["role"] == role
                         for ref in task["intent"].get("scope", {}).get("owned_evidence_ids", [])]
                if len(owned) != len(set(owned)) or set(owned) != all_ids:
                    raise _error("初回分析の分割範囲に欠落または重複があります。", "initial_analysis_incomplete")
                for task in tasks:
                    if task["role"] == role and not set(task["intent"]["scope"]["owned_evidence_ids"]).issubset(self._label_design_evidence_ids(db, run, task)):
                        raise _error("担当範囲に未読の発話が残っています。", "initial_analysis_incomplete")
        for task in tasks:
            row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
            if task["status"] != "succeeded" or row is None:
                raise _error("初回分析に未実行または失敗した担当があります。", "initial_analysis_incomplete")
            raw, meta = json.loads(row[0]), json.loads(row[1])
            if (fingerprint(raw) != meta.get("raw_hash") or meta.get("validation_status") != "valid"
                    or meta.get("task_id") != task["task_id"] or meta.get("attempt_id") != task["attempt_id"]
                    or meta.get("run_id") != run["run_id"] or meta.get("dataset_version") != run["input_hash"]):
                raise _error("初回分析結果の保存hashまたは版が不正です。", "result_integrity_mismatch")
            self._validate_result(db, run, task, raw)
            self._check_input_manifest(run, task, meta)
            source = {"role": task["role"], "method_id": task["method_id"], "task_id": task["task_id"],
                      "result_id": meta["result_id"], "raw_hash": meta["raw_hash"]}
            if _scope(task["intent"]).get("interval_id"):
                source.update(interval_id=task["intent"]["scope"]["interval_id"],
                              parent_topic_id=task["intent"]["scope"]["parent_topic_id"],
                              ownership_sha256=task["intent"]["scope"]["ownership_sha256"])
            reports.append({**source, "summary": raw.get("summary", ""),
                            "requirement_count": len(raw["label_requirements"])})
            for entry in raw["label_requirements"]:
                key = fingerprint({k: v for k, v in entry.items() if k != "requirement_id"})
                aggregate = requirements.setdefault(key, {**copy.deepcopy(entry), "sources": []})
                aggregate["sources"].append({**source, "requirement_id": entry["requirement_id"]})
        return {"status": "ai_draft", "dataset_version": run["input_hash"], "reports": reports,
                "label_requirements": list(requirements.values()), "all_roles_reported": True,
                "full_evidence_coverage": bool(paged)}

    def _apply_initial_routing(self, db, run, task):
        row = db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
        raw, meta = json.loads(row["raw_json"]), json.loads(row["state_json"])
        if fingerprint(raw) != meta.get("raw_hash") or meta.get("validation_status") != "valid":
            raise _error("担当指示の保存結果が不正です。", "result_integrity_mismatch")
        self._validate_result(db, run, task, raw)
        self._check_input_manifest(run, task, meta)
        decision = {**copy.deepcopy(raw), "decision_id": _id("decision"), "result_id": meta["result_id"],
                    "task_id": task["task_id"], "phase": "initial_routing", "iteration": 0,
                    "role": "core", "created_at": _now(), "annotation_version": run["annotation_version"],
                    "before_annotation_version": run["annotation_version"], "after_annotation_version": run["annotation_version"]}
        db.execute("INSERT OR IGNORE INTO orchestration_decisions VALUES (?,?,?,?)",
                   (decision["decision_id"], run["run_id"], meta["result_id"], _json(decision)))
        instruction = copy.deepcopy(raw["intents"][0])
        if run["config"].get("model_context_version"):
            scope = _scope(task["intent"])
            instruction["scope"] = {"requirement_keys": scope.get("requirement_keys",
                [fingerprint(entry) for entry in run["initial_analysis_report"]["label_requirements"]])}
            requirements = [entry for entry in run["initial_analysis_report"]["label_requirements"] if fingerprint(entry) in instruction["scope"]["requirement_keys"]]
            instruction["evidence_ids"] = sorted({ref for entry in requirements for ref in entry["evidence_ids"]})
        instruction.update(parent_task_id=task["task_id"],
            dependencies=sorted(set(instruction.get("dependencies", [])) | {task["task_id"]}
                | {report["task_id"] for report in run["initial_analysis_report"]["reports"]}))
        self._register(db, run, instruction, phase="initial_labels")
        if run["status"] in TERMINAL:
            return
        self._event(db, run["run_id"], "initial_routing_dispatched", "Coreの担当指示を受け、ハンドラーが尺度設計専門家へ発注しました。",
                    source="core", target="handler", result_id=meta["result_id"], raw_hash=meta["raw_hash"])
        run["phase"] = "initial_labels"
        self._write_run(db, run)

    def _initial_label_catalog(self, db, run):
        result_id = run.get("initial_label_result_id")
        if not result_id:
            return None
        catalogs = [self._initial_label_result(db, run, key) for key in run.get("initial_label_result_ids", [result_id])]
        if len(catalogs) == 1 and not run["config"].get("model_context_version"):
            return catalogs[0]
        definitions, sources, by_id = [], [], {}
        for catalog in catalogs:
            for definition in catalog["definitions"]:
                definitions.append(definition)
                sources.append(catalog["result_id"])
                by_id.setdefault(definition["definition_id"], set()).add(fingerprint(definition))
        return {**catalogs[0], "definitions": definitions, "definition_sources": sources,
                "result_ids": [catalog["result_id"] for catalog in catalogs],
                "source_hashes": {catalog["result_id"]: catalog["raw_hash"] for catalog in catalogs},
                "definition_conflicts": sorted(key for key, values in by_id.items() if len(values) > 1)}

    def _initial_label_result(self, db, run, result_id):
        row = db.execute("SELECT * FROM orchestration_results WHERE run_id=? AND result_id=?", (run["run_id"], result_id)).fetchone()
        if row is None:
            raise _error("初回の尺度作成結果が見つかりません。", "initial_labels_missing")
        metadata, raw = json.loads(row["state_json"]), json.loads(row["raw_json"])
        task_row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?", (row["task_id"], run["run_id"])).fetchone()
        task = json.loads(task_row[0]) if task_row else {}
        if (fingerprint(raw) != metadata.get("raw_hash") or metadata.get("validation_status") != "valid"
                or metadata.get("role") != "interpretation" or task.get("role") != "interpretation"
                or metadata.get("run_id") != run["run_id"] or metadata.get("result_id") != result_id
                or metadata.get("task_id") != row["task_id"] or task.get("task_id") != row["task_id"]
                or task.get("status") != "succeeded" or task.get("phase") != "initial_labels"
                or task.get("method_id") != "label-design-v1" or task.get("iteration") != 0
                or metadata.get("dataset_version") != run["input_hash"]
                or metadata.get("attempt_id") != task.get("attempt_id")):
            raise _error("初回の尺度作成結果の保存hashまたは作成主体が不正です。", "result_integrity_mismatch")
        validate_label_definitions(raw.get("label_definitions"), evidence_ids=self._label_design_evidence_ids(db, run, task))
        self._check_input_manifest(run, task, metadata)
        return {"status": "ai_draft", "created_by": "interpretation", "specialization": "label_design",
                "result_id": result_id, "raw_hash": metadata["raw_hash"], "dataset_version": run["input_hash"],
                "base_codebook_version": task["codebook_version"], "definitions": copy.deepcopy(raw["label_definitions"])}

    def _check_input_manifest(self, run, task, metadata=None):
        if not (run["config"].get("model_context_version") or run["config"].get("analysis_interval_version")) or task["kind"] != "ai":
            return
        manifest = task.get("context_manifest") or {}
        if (manifest.get("version") != (artifact_review.MANIFEST_VERSION if run["config"].get("artifact_review_version") else 1) or manifest.get("dataset_version") != run["input_hash"]
                or fingerprint(manifest) != task.get("context_manifest_hash")
                or metadata is not None and metadata.get("context_manifest_hash") != task.get("context_manifest_hash")):
            raise _error("保存結果と入力パケットの来歴が一致しません。", "context_manifest_invalid")
        scope = _scope(task["intent"])
        if scope.get("interval_id") and (manifest.get("analysis_interval") != scope or
                not set(scope["owned_evidence_ids"] + scope["boundary_evidence_ids"]).issubset(manifest.get("provided_evidence_ids", []))):
            raise _error("区間の実配送記録が所属と一致しません。", "context_manifest_invalid")

    def _validate_result(self, db, run, task, raw):
        self._check_input_manifest(run, task)
        if not isinstance(raw, dict):
            raise _error("結果はJSONオブジェクトで返してください。", "invalid_result")
        if task.get("input_artifacts"):
            binding, _ = self._recheck_review_binding(db, run, task)
            manifest = task.get("context_manifest", {})
            if manifest.get("input_artifacts") != [binding] or manifest.get("review_procedure") != binding["procedure"]:
                artifact_review.reject("点検の入力manifestが束縛と一致しません。", "context_manifest_invalid")
            artifact_review.validate_review_output(raw, binding, manifest)
        elif raw.get("claim_verdicts"):
            artifact_review.reject("主張別の反例判定は専用レビューだけが返せます。", "artifact_output_invalid")
        if raw.get("research_mode", "exploratory") != "exploratory":
            raise _error("確認的主張には未対応です。", "confirmatory_unavailable")
        if raw.get("dataset_version", run["input_hash"]) != run["input_hash"]:
            raise _error("結果の入力版が一致しません。", "revision_conflict")
        evidence = {e["evidence_id"]: e for e in self._initial(db, run["initial_id"])["evidence"] if not e["excluded"]}
        if task["phase"] == "initial_analysis":
            if task["kind"] == "ai" and (not isinstance(raw.get("summary"), str) or not raw["summary"].strip()
                    or (task["role"] in {"interpretation", "verification"} and not raw.get("claims"))):
                raise _error("初回の解釈・独立検証には空でない要約と根拠付きの主張が必要です。", "initial_analysis_empty")
            requirements = raw.get("label_requirements")
            if not isinstance(requirements, list) or len(requirements) > 12:
                raise _error("初回分析ではラベル・尺度の必要性を明示して報告してください。", "initial_requirements_missing")
            known = set()
            provided = self._label_design_evidence_ids(db, run, task)
            for entry in requirements:
                if (not isinstance(entry, dict) or any(not isinstance(entry.get(key), str) or not entry[key].strip()
                        for key in ("requirement_id", "name", "analysis", "reason"))
                        or entry.get("kind") not in {"label", "scale"}
                        or not isinstance(entry.get("evidence_ids"), list) or not entry["evidence_ids"]
                        or any(ref not in provided for ref in entry["evidence_ids"])
                        or entry["requirement_id"] in known):
                    raise _error("尺度要件には種類・分析用途・理由・読んだ根拠IDと一意IDが必要です。", "invalid_initial_requirement")
                known.add(entry["requirement_id"])
            if raw.get("label_patches") or raw.get("label_definitions"):
                raise _error("初回の予備分析は尺度の必要性を報告し、採用ラベルを変更しません。", "invalid_initial_requirement")
        label_design = task["role"] == "interpretation" and task["phase"] == "initial_labels" and task["method_id"] == "label-design-v1"
        if label_design:
            validate_label_definitions(raw.get("label_definitions"), evidence_ids=self._label_design_evidence_ids(db, run, task))
            if raw.get("label_patches"):
                raise _error("尺度設計では確定ラベルを変更しません。", "invalid_label_patch")
        elif raw.get("label_definitions"):
            raise _error("尺度定義は初回の専門家タスクだけが作成します。", "label_definition_author_invalid")
        for key in ("claims", "issues", "label_patches", "intents", "critique_responses", "label_decisions", "result_assessments"):
            if key in raw and (not isinstance(raw[key], list) or any(not isinstance(v, dict) for v in raw[key])):
                raise _error("結果配列の形式が正しくありません。", "invalid_result")
        for claim in raw.get("claims", []):
            if not claim.get("text") or not claim.get("claim_id") or claim.get("kind") not in {"observation", "interpretation", "hypothesis"}:
                raise _error("主張のID・本文・区分が必要です。", "invalid_claim")
            if not claim.get("evidence_ids"):
                raise _error("主張には根拠参照が必要です。", "evidence_missing")
        for value in [*raw.get("claims", []), *raw.get("issues", []), *raw.get("label_patches", [])]:
            refs = value.get("evidence_ids", [])
            if not isinstance(refs, list) or any(ref not in evidence for ref in refs):
                raise _error("根拠発話が存在しません。", "evidence_missing")
            if (run["config"].get("model_context_version") or task.get("input_artifacts")) and task["kind"] == "ai":
                manifest = task.get("context_manifest", {})
                if fingerprint(manifest) != task.get("context_manifest_hash") or any(ref not in manifest.get("citation_ids", []) for ref in refs):
                    raise _error("読んでいない発話は根拠として採用できません。", "evidence_not_provided")
        if task["role"] in {"core", "orchestrator"}:
            if run["config"].get("artifact_review_version") and task["role"] == "orchestrator":
                artifact_review.validate_decisions(raw, task["context_manifest"].get("artifact_candidates", []),
                    prior=self._artifact_history(db, run, task["intent"]["scope"]["domain"]))
            elif raw.get("artifact_decisions") or any(i.get("kind") == "finding_review" for i in raw.get("intents", [])):
                artifact_review.reject("先行所見の利用は専門側の専用判断で指示してください。")
            if task["role"] == "orchestrator" and (raw.get("stop") is not None or raw.get("label_patches") or raw.get("label_decisions") and task["intent"]["scope"]["domain"] != "labels"):
                raise _error("専門側は終了判断や担当外ラベルの採否を決めません。", "orchestrator_authority_invalid")
            if task["role"] == "core" and run["config"].get("specialist_orchestration_version") and any(raw.get(k) for k in ("result_assessments", "critique_responses", "label_decisions")):
                raise _error("個別結果・批判・ラベルの判断は専門側の責務です。", "core_authority_invalid")
            routing = task["phase"] == "initial_routing"
            if run["config"].get("initial_label_definitions_version") and not routing and not self._initial_label_catalog(db, run):
                raise _error("初回の専門家によるラベル・尺度出力が必要です。", "initial_labels_missing")
            if routing:
                intents = raw.get("intents", [])
                if (not isinstance(intents, list) or len(intents) != 1
                        or intents[0].get("role") != "interpretation" or intents[0].get("method_id") != "label-design-v1"
                        or intents[0].get("kind", "analysis") != "analysis" or intents[0].get("evidence_ids")
                        or intents[0].get("label_dependent") or raw.get("stop") is not None
                        or any(raw.get(key) for key in ("claims", "critique_responses", "label_decisions", "result_assessments"))):
                    raise _error("初回の担当指示は尺度設計専門家への1件の依頼です。統合・終了・ラベル更新は後続判断で行います。", "initial_routing_invalid")
            if not isinstance(raw.get("summary"), str) or not raw["summary"].strip():
                raise _error("空でない統合要約が必要です。", "invalid_result")
            for key in ("alternatives", "unresolved"):
                if key in raw and (not isinstance(raw[key], list) or any(not isinstance(value, str) for value in raw[key])):
                    raise _error("代替説明・未解決点は文字列の配列です。", "invalid_result")
            if run["config"].get("core_progress_version"):
                expected = set() if routing else set(self._review_pending(db, run, task)[:20])
                if run["config"].get("model_context_version") and not routing:
                    manifest = task.get("context_manifest", {})
                    requested = manifest.get("requested_result_ids", [])
                    pending = self._review_pending(db, run, task)
                    if fingerprint(manifest) != task.get("context_manifest_hash") or requested != pending[:len(requested)] or pending and not requested:
                        raise _error("評価範囲の保存記録が不正です。", "context_manifest_invalid")
                    expected = set(requested)
                received = []
                for assessment in raw.get("result_assessments", []):
                    if (assessment.get("result_id") not in expected
                            or assessment.get("disposition") not in {"adopt", "reject", "defer"}
                            or any(not isinstance(assessment.get(key), str) or not assessment[key].strip()
                                   for key in ("reason", "impact"))):
                        raise _error("新しい専門家結果には実在ID・採否・理由・影響が必要です。", "invalid_result_assessment")
                    received.append(assessment["result_id"])
                if len(received) != len(set(received)):
                    raise _error("同じ専門家結果を重複して評価できません。", "invalid_result_assessment")
                if set(received) != expected:
                    raise _error("新しい専門家結果の採否が未記録です。", "result_assessment_missing")
            if raw.get("stop") is not None and (not isinstance(raw["stop"], dict) or not raw["stop"].get("reason")):
                raise _error("停止案には理由が必要です。", "invalid_stop")
            for intent in raw.get("intents", []):
                role = intent.get("role")
                if (role not in {"interpretation", "statistics", "verification", "critic"}
                        or not isinstance(intent.get("question"), str) or not intent["question"].strip()
                        or not intent.get("why_now") or not intent.get("success_criteria")):
                    raise _error("追加タスクの役割・問い・理由・採用基準が不足しています。", "invalid_intent")
                if role == "statistics":
                    method = intent.get("method_id")
                    if method not in METHODS or (method != "label_frequency" and (intent.get("evidence_ids") or intent.get("scope") or intent.get("label_dependent"))):
                        raise _error("既存コード計算は初期版の全範囲専用です。", "method_scope_unavailable")
                    if method == "label_frequency" and intent.get("label_field", "codes") not in LABEL_FIELDS:
                        raise _error("対応するラベル集計列を指定してください。", "label_field_unavailable")
                elif intent.get("method_id") == "label_frequency":
                    raise _error("ラベル集計はstatisticsへ指定してください。", "label_field_unavailable")
                if not isinstance(intent.get("evidence_ids", []), list) or any(ref not in evidence for ref in intent.get("evidence_ids", [])):
                    raise _error("タスクの根拠が存在しません。", "evidence_missing")
            for response in raw.get("critique_responses", []):
                if run["config"].get("model_context_version") and response.get("issue_id") not in task["context_manifest"].get("provided_issue_ids", []):
                    raise _error("未提示の批判は評価できません。", "issue_not_provided")
                if response.get("disposition") not in {"adopt", "reject", "defer"} or not response.get("reason") or not response.get("impact"):
                    raise _error("批判への応答には採否・理由・結論への影響が必要です。", "invalid_critique_response")
                if not db.execute("SELECT 1 FROM orchestration_issues WHERE issue_id=? AND run_id=?", (response.get("issue_id"), run["run_id"])).fetchone():
                    raise _error("応答先の批判が存在しません。", "issue_missing")
        if task["role"] == "critic":
            if raw.get("review_status") not in {"issues", "no_issues", "undetermined"} or not raw.get("reviewed_scope"):
                raise _error("批判レビューの範囲と状態が必要です。", "invalid_critique")
            if raw["review_status"] == "issues" and not raw.get("issues"):
                raise _error("指摘ありのレビューには指摘が必要です。", "invalid_critique")
            if raw["review_status"] == "no_issues" and raw.get("issues"):
                raise _error("指摘なしと指摘一覧が矛盾しています。", "invalid_critique")
            for issue in raw.get("issues", []):
                if (not issue.get("issue_key") or issue.get("severity") not in IMPORTANCE or not issue.get("reason")
                        or issue.get("target_id") != task["intent"].get("target_id")
                        or str(issue.get("target_version")) != str(task["intent"].get("target_version"))):
                    raise _error("指摘の対象版・問題ID・重大度・理由が正しくありません。", "invalid_critique")
                if not issue.get("evidence_ids") and not issue.get("missing_evidence"):
                    raise _error("批判には根拠または不足している証拠の特定が必要です。", "evidence_missing")
        for patch in raw.get("label_patches", []):
            scope = _scope(task["intent"])
            if scope.get("interval_id"):
                owned = {evidence[e]["utterance_id"] for e in scope["owned_evidence_ids"]}
                if str(patch.get("utterance_id")) not in owned:
                    raise _error("文脈用発話へラベルを付与できません。", "invalid_label_patch")
            if (str(patch.get("utterance_id")) not in {e["utterance_id"] for e in evidence.values()}
                    or patch.get("field") not in LABEL_FIELDS or not patch.get("reason") or not patch.get("evidence_ids")
                    or "old_value" not in patch or "new_value" not in patch
                    or type(patch.get("base_annotation_version")) is not int
                    or patch.get("codebook_version") != task["codebook_version"]
                    or patch.get("operation", "update") not in {"add", "update", "delete"}
                    or (patch.get("operation") == "delete" and patch["new_value"] is not None)
                    or not isinstance(patch.get("reason"), str)):
                raise _error("ラベル変更案の根拠・旧値・版が不足しています。", "invalid_label_patch")
            for key in ("old_value", "new_value"):
                value = patch[key]
                if not (value is None or type(value) in {str, bool, int, float}
                        or (isinstance(value, list) and all(isinstance(v, str) for v in value))):
                    raise _error("ラベル値は文字列・数値・真偽値・文字列配列で指定してください。", "invalid_label_patch")

    def _save_issues(self, db, run, task, raw, meta):
        for issue in raw.get("issues", []):
            value = {**copy.deepcopy(issue), "issue_id": _id("issue"), "critique_id": meta["result_id"],
                     "result_id": meta["result_id"], "dataset_version": run["input_hash"],
                     "evidence_version": fingerprint([run["input_hash"], task["annotation_version"]]), "status": "open", "stale": False}
            db.execute("INSERT OR IGNORE INTO orchestration_issues VALUES (?,?,?,?,?,?,?)",
                (value["issue_id"], run["run_id"], issue["issue_key"], issue["target_id"], str(issue["target_version"]), value["evidence_version"], _json(value)))

    def _label_audit(self, db, run, patch, *, disposition, task=None,
                     result_id=None, decision_id=None, before=None, after=None,
                     before_present=None, after_present=None, before_version=None,
                     reason=None):
        """Append the recorded justification, never arbitrary model output."""
        task = task or {}
        def value(v):
            if v is None or type(v) in {bool, int, float}:
                return v
            if isinstance(v, str):
                return v
            if isinstance(v, list):
                return copy.deepcopy(v)
            return None
        operation = patch.get("operation") or ("add" if before_present is False else "update")
        event = {"event_id": _id("label_event"), "item_id": run["item_id"],
                 "run_id": run["run_id"], "proposal_id": patch["proposal_id"],
                 "task_id": task.get("task_id"), "result_id": result_id,
                 "proposal_task_id": patch.get("task_id"), "proposal_result_id": patch.get("result_id"),
                 "decision_id": decision_id, "created_at": _now(),
                 "role": task.get("role"), "model": task.get("model"), "provider": task.get("provider"),
                 "utterance_id": str(patch["utterance_id"]), "field": patch["field"],
                 "operation": operation, "disposition": disposition, "status": patch["status"],
                 "before_value": value(before), "after_value": value(after),
                 "before_present": before_present, "after_present": after_present,
                 "proposed_value": value(patch.get("new_value")),
                 "stated_old_value": value(patch.get("old_value")),
                 "tombstone": disposition == "adopt" and operation == "delete",
                 "base_annotation_version": patch.get("base_annotation_version"),
                 "before_annotation_version": before_version,
                 "after_annotation_version": before_version if disposition == "proposal" else run["annotation_version"],
                 "annotation_version": run["annotation_version"],
                 "codebook_version": run.get("codebook_version"),
                 "reason": str(reason if reason is not None else patch.get("reason", ""))[:2000],
                 "evidence_ids": [e for e in patch.get("evidence_ids", []) if isinstance(e, str)],
                 "audit_status": "recorded"}
        recorded_reason = reason if reason is not None else patch.get("reason", "")
        event["truncated_fields"] = ["reason"] if len(str(recorded_reason)) > 2000 else []
        event["reason_hash"] = fingerprint(recorded_reason)
        event["before_value_hash"] = fingerprint(before)
        event["after_value_hash"] = fingerprint(after)
        db.execute("INSERT INTO orchestration_label_audit VALUES (?,?,?,?)",
                   (event["event_id"], run["run_id"], patch["proposal_id"], _json(event)))

    def _save_patch(self, db, run, task, patch, meta):
        value = {**copy.deepcopy(patch), "proposal_id": _id("label"), "result_id": meta["result_id"],
                 "task_id": task["task_id"], "status": "proposed", "created_at": _now()}
        db.execute("INSERT INTO orchestration_label_proposals VALUES (?,?,?,?)", (value["proposal_id"], run["run_id"], meta["result_id"], _json(value)))
        row = db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                         (run["run_id"], patch["base_annotation_version"])).fetchone()
        labels = json.loads(row[0]).get(str(patch["utterance_id"]), {}) if row else None
        present = patch["field"] in labels if isinstance(labels, dict) else None
        # A proposal has not changed the saved labels. Keep the actual base
        # value on both sides; the agent's claims live in stated/proposed fields.
        before = copy.deepcopy(labels.get(patch["field"])) if isinstance(labels, dict) else None
        self._label_audit(db, run, value, disposition="proposal", task=task, result_id=meta["result_id"],
                         before=before, after=before, before_present=present, after_present=present,
                         before_version=patch["base_annotation_version"] if row else None)

    def _commit_labels(self, db, run, decisions, *, task=None, result_id=None, decision_id=None):
        # Validate the complete batch before applying any disposition.
        patches = []
        for decision in decisions:
            row = db.execute("SELECT payload_json FROM orchestration_label_proposals WHERE proposal_id=? AND run_id=?",
                             (decision.get("proposal_id"), run["run_id"])).fetchone()
            if row is None or decision.get("disposition") not in {"adopt", "reject", "defer"} or not decision.get("reason"):
                raise _error("ラベル採否の対象・理由が不足しています。", "invalid_label_decision")
            patches.append((decision, json.loads(row[0])))
        processed = set()
        for decision, patch in patches:
            if patch["status"] != "proposed" or patch["proposal_id"] in processed:
                continue
            processed.add(patch["proposal_id"])
            labels = json.loads(db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                                           (run["run_id"], run["annotation_version"])).fetchone()[0])
            utterance_labels = labels.get(str(patch["utterance_id"]), {})
            before = copy.deepcopy(utterance_labels.get(patch["field"]))
            present = patch["field"] in utterance_labels
            version = run["annotation_version"]
            patch["decision"] = copy.deepcopy(decision)
            disposition = decision["disposition"]
            if disposition != "adopt":
                patch["status"] = "rejected" if disposition == "reject" else "deferred"
            elif (patch["base_annotation_version"] != version or before != patch["old_value"]
                    or patch["codebook_version"] != run["codebook_version"]
                    or (patch.get("operation") == "add" and present)
                    or (patch.get("operation") in {"update", "delete"} and not present)):
                patch["status"], disposition = "conflict", "conflict"
            else:
                target = labels.setdefault(str(patch["utterance_id"]), {})
                if patch.get("operation") == "delete":
                    target.pop(patch["field"], None)
                else:
                    target[patch["field"]] = patch["new_value"]
                run["annotation_version"] += 1
                run["view_version"] += 1
                run["reviewed_stop_versions"] = []
                db.execute("INSERT INTO orchestration_label_versions VALUES (?,?,?)", (run["run_id"], run["annotation_version"], _json(labels)))
                patch.update(status="committed", committed_annotation_version=run["annotation_version"])
                for dependent in self._tasks(db, run["run_id"]):
                    if dependent["label_dependent"] and dependent["annotation_version"] < run["annotation_version"]:
                        dependent["stale"] = True
                        self._write_task(db, dependent)
                        result = db.execute("SELECT result_id,state_json FROM orchestration_results WHERE task_id=?", (dependent["task_id"],)).fetchone()
                        if result:
                            meta = json.loads(result[1]); meta["stale"] = True
                            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), result[0]))
                self._event(db, run["run_id"], "labels_committed", "新しいラベル版を保存し、依存結果を旧版として表示します。", annotation_version=run["annotation_version"])
            after_labels = labels.get(str(patch["utterance_id"]), {})
            self._label_audit(db, run, patch, disposition=disposition, task=task,
                             result_id=result_id, decision_id=decision_id, before=before,
                             after=after_labels.get(patch["field"]), before_present=present,
                             after_present=patch["field"] in after_labels, before_version=version,
                             reason=decision["reason"])
            db.execute("UPDATE orchestration_label_proposals SET payload_json=? WHERE proposal_id=?", (_json(patch), patch["proposal_id"]))

    def _record_critique_responses(self, db, run, raw, decision_id):
        for response in raw.get("critique_responses", []):
            value = {**response, "response_id": _id("response"), "decision_id": decision_id, "created_at": _now()}
            db.execute("INSERT OR IGNORE INTO orchestration_responses VALUES (?,?,?,?,?)", (value["response_id"], run["run_id"], response["issue_id"], decision_id, _json(value)))
            issue = json.loads(db.execute("SELECT payload_json FROM orchestration_issues WHERE issue_id=?", (response["issue_id"],)).fetchone()[0])
            issue.update(status="adopted_unresolved" if response["disposition"] == "adopt" else response["disposition"], latest_response=value)
            db.execute("UPDATE orchestration_issues SET payload_json=? WHERE issue_id=?", (_json(issue), issue["issue_id"]))

    def _apply_specialist_review(self, db, run, task, raw, meta):
        self._validate_result(db, run, task, raw)
        decision = {**copy.deepcopy(raw), "decision_id": _id("decision"), "role": "orchestrator",
            "phase": "specialist_review", "domain": task["intent"]["scope"]["domain"],
            "result_id": meta["result_id"], "task_id": task["task_id"], "iteration": run["iteration"],
            "annotation_version": task["annotation_version"], "created_at": _now()}
        if run["config"].get("artifact_review_version"):
            candidates = task["context_manifest"].get("artifact_candidates", [])
            index = {c["result_id"]: c for c in candidates}
            decision["presented_artifact_candidates"] = copy.deepcopy(candidates)
            decision["unpresented_artifact_count"] = task["context_manifest"].get("artifact_candidate_scope", {}).get("omitted_count", 0)
            history = {r["result_id"]: r for r in self._artifact_history(db, run, decision["domain"])}
            decision["artifact_decisions"] = [{**copy.deepcopy(r), "raw_hash": index[r["result_id"]]["raw_hash"],
                "information_hash": index[r["result_id"]]["information_hash"], "receiving_domain": decision["domain"],
                "previous_decision_id": history.get(r["result_id"], {}).get("decision_id", ""),
                "issuance": "not_requested" if r["disposition"] != "use" else "pending", "issued_task_id": ""}
                for r in raw.get("artifact_decisions", [])]
        if run["config"].get("analysis_interval_version"):
            groups = {}
            for assessment in raw["result_assessments"]:
                source = db.execute("SELECT state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                    (assessment["result_id"], run["run_id"])).fetchone()
                lineage = json.loads(source[0]).get("interval_lineage") if source else None
                if lineage:
                    groups.setdefault(lineage["parent_topic_id"], []).append({**lineage,
                        "source_result_id": assessment["result_id"], "disposition": assessment["disposition"]})
            decision["topic_sources"] = groups
        if run["config"].get("artifact_review_version"):
            decision["review_results"] = []
            for assessment in raw["result_assessments"]:
                source = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                    (assessment["result_id"], run["run_id"])).fetchone()
                source_raw, source_meta = json.loads(source[0]), json.loads(source[1])
                if source_meta.get("derived_from"):
                    decision["review_results"].append({"result_id": source_meta["result_id"], "raw_hash": source_meta["raw_hash"],
                        "derived_from": source_meta["derived_from"], "input_manifest_hash": source_meta.get("context_manifest_hash"),
                        "interval_lineage": source_meta.get("interval_lineage"), "claim_verdicts": source_raw["claim_verdicts"],
                        "claim_evidence_scope": source_meta.get("claim_evidence_scope", []), "review_status": source_meta.get("review_status"),
                        "missing_inputs": source_raw["missing_inputs"], "limitations": source_raw["limitations"],
                        "disposition": assessment["disposition"], "independent_verification": False})
        self._commit_labels(db, run, raw.get("label_decisions", []), task=task, result_id=meta["result_id"], decision_id=decision["decision_id"])
        self._record_critique_responses(db, run, raw, decision["decision_id"])
        db.execute("INSERT INTO orchestration_decisions VALUES (?,?,?,?)", (decision["decision_id"], run["run_id"], meta["result_id"], _json(decision)))
        self._event(db, run["run_id"], "specialist_review_committed", raw["summary"], source="orchestrator", target="handler",
                    task_id=task["task_id"], domain=decision["domain"], assessed_result_ids=[a["result_id"] for a in raw["result_assessments"]])
        for intent in raw.get("intents", []):
            artifact_choice = next((r for r in decision.get("artifact_decisions", []) if r["disposition"] == "use"), None)
            def record_issuance(reason, issued_task=None):
                if artifact_choice is not None:
                    artifact_choice.update(issuance="issued" if issued_task else "not_issued",
                        not_issued_reason="" if issued_task else reason,
                        issued_task_id=issued_task["task_id"] if issued_task else "")
                    db.execute("UPDATE orchestration_decisions SET payload_json=? WHERE decision_id=?",
                               (_json(decision), decision["decision_id"]))
            if run["status"] in TERMINAL:
                record_issuance(run["stop_reason"])
                return
            domain = task["intent"]["scope"]["domain"]
            pending = self._review_pending(db, run, task)
            parents = {t["task_id"] for t in self._tasks(db, run["run_id"])
                       if t["role"] == "orchestrator" and t["intent"]["scope"]["domain"] == domain and t["iteration"] == task["iteration"]}
            issued = any(t["phase"] == "specialist_followup" and t.get("parent_task_id") in parents for t in self._tasks(db, run["run_id"]))
            if pending or issued:
                record_issuance("pending_results" if pending else "followup_already_issued")
                self._event(db, run["run_id"], "intent_deferred", "分野内の保存結果を先に読むため、またはこの段階の追加依頼を既に発注したため保留しました。",
                            intent=intent, review_result_id=meta["result_id"], remaining_result_count=len(pending))
                continue
            if run["config"]["stop_mode"] == "importance" and IMPORTANCE.get(intent.get("importance"), 0) < IMPORTANCE[run["config"]["importance_threshold"]]:
                record_issuance("importance_threshold")
                self._event(db, run["run_id"], "intent_deferred", "重要度の閾値未満の専門側の依頼を保存しました。", intent=intent, review_result_id=meta["result_id"])
                continue
            question = " ".join(unicodedata.normalize("NFKC", intent["question"]).casefold().split())
            original = " ".join(unicodedata.normalize("NFKC", run["config"]["question"]).casefold().split())
            similar = question == original or len(original) >= 30 and SequenceMatcher(None, question, original, autojunk=False).ratio() >= .85
            if intent.get("kind", "analysis") == "analysis" and not intent.get("label_dependent") and similar:
                record_issuance("same_question")
                self._event(db, run["run_id"], "intent_deferred", "元の問いと同一または文字列が近い再発注案を保留しました。具体的な不足を調べる問いが必要です。", intent=intent, review_result_id=meta["result_id"])
                continue
            if intent["role"] == "critic":
                intent = {**intent, "target_id": "view:" + run["run_id"], "target_version": run["view_version"]}
            if intent.get("kind") == "finding_review":
                intent = {**intent, "artifact_decision_id": decision["decision_id"]}
            issued_task = self._register(db, run, {**intent, "parent_task_id": task["task_id"]}, phase="specialist_followup")
            record_issuance(run.get("stop_reason") or "duplicate_suppressed", issued_task)
        run["phase"] = "specialists"
        self._write_run(db, run)

    def _apply_core(self, db, run, task, result):
        meta, raw = json.loads(result["state_json"]), json.loads(result["raw_json"])
        # The validation commit and the decision commit are separate durable
        # boundaries. Recheck the stored bytes at adoption, including restart.
        if (fingerprint(raw) != meta["raw_hash"] or meta.get("task_id") != task["task_id"]
                or meta.get("run_id") != run["run_id"] or meta.get("result_id") != result["result_id"]
                or meta.get("attempt_id") != task["attempt_id"]):
            meta.update(validation_status="quarantined", error="result_integrity_mismatch")
            task.update(status="quarantined", validation_status="quarantined", error="result_integrity_mismatch")
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), result["result_id"]))
            self._write_task(db, task)
            self._event(db, run["run_id"], "result_quarantined", "result_integrity_mismatch", task_id=task["task_id"])
            run["error"] = "result_integrity_mismatch"
            self._stop(db, run, "execution_failure")
            return
        if db.execute("SELECT 1 FROM orchestration_decisions WHERE result_id=?", (meta["result_id"],)).fetchone():
            return
        self._check_input_manifest(run, task, meta)
        if task["role"] == "orchestrator":
            self._apply_specialist_review(db, run, task, raw, meta)
            return
        progress = None
        if run["config"].get("initial_label_definitions_version"):
            self._validate_result(db, run, task, raw)
        if run["config"].get("core_progress_version"):
            # Recheck the review references at the durable adoption boundary too.
            self._validate_result(db, run, task, raw)
            history = [json.loads(row[0]) for row in db.execute(
                "SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run["run_id"],))
                if json.loads(row[0]).get("phase") != "initial_routing" and json.loads(row[0]).get("role", "core") == "core"]
            signature = self._core_progress_signature(raw)
            repeated = next((old for old in reversed(history)
                             if self._core_progress_signature(old) == signature
                             and old.get("after_annotation_version") == run["annotation_version"]), None)
            new_responses = [response["issue_id"] for response in raw.get("critique_responses", [])
                             if not db.execute("SELECT 1 FROM orchestration_responses WHERE run_id=? AND issue_id=?",
                                               (run["run_id"], response["issue_id"])).fetchone()]
            previous_proposals = {entry["proposal_id"] for old in history for entry in old.get("label_decisions", [])}
            new_labels = [entry["proposal_id"] for entry in raw.get("label_decisions", [])
                          if entry["proposal_id"] not in previous_proposals]
            assessments = [entry["result_id"] for entry in raw.get("result_assessments", [])]
            fresh_basis = self._new_result_basis(db, run, history, assessments)
            domain_reports = self._domain_reports(db, run) if run["config"].get("specialist_orchestration_version") else []
            domain_ids = [r["result_id"] for r in domain_reports]
            previous_domain_ids = {rid for old in history for rid in old.get("domain_report_ids", [])}
            # A new review ID is not new evidence. Reuse the same source/version/
            # scope/hash comparison as legacy review, including explicit repeats.
            previous_sources = [{"result_assessments": [{"result_id": rid} for rid in report["source_result_ids"]]}
                                for report in domain_reports if report["result_id"] in previous_domain_ids]
            fresh_basis.extend(self._new_result_basis(db, run, previous_sources,
                [rid for report in domain_reports if report["result_id"] not in previous_domain_ids for rid in report["source_result_ids"]]))
            prior_results = [entry["result_id"] for d in history for entry in d.get("result_assessments", [])]
            prior_results += [entry["result_id"] for d in previous_sources for entry in d["result_assessments"]]
            current_results = assessments + [rid for report in domain_reports if report["result_id"] not in previous_domain_ids for rid in report["source_result_ids"]]
            new_review_checks = self._new_review_checks(db, run, prior_results, current_results) if run["config"].get("artifact_review_version") else []
            if repeated and not (fresh_basis or new_responses or new_labels or new_review_checks):
                meta.update(content_status="no_progress", repeated_decision_id=repeated["decision_id"])
                db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), meta["result_id"]))
                self._event(db, run["run_id"], "core_no_progress",
                            "同じ根拠・判断・作業案の繰り返しを検出しました。進展として数えず停止します。",
                            task_id=task["task_id"], result_id=meta["result_id"],
                            repeated_decision_id=repeated["decision_id"], completed_core_iterations=len(history))
                self._stop(db, run, "no_progress")
                return
            progress = {"signature": signature, "assessed_result_ids": assessments,
                        "new_result_basis_ids": fresh_basis,
                        "new_review_check_ids": new_review_checks,
                        "responded_issue_ids": new_responses, "decided_proposal_ids": new_labels}
        decision = {**copy.deepcopy(raw), "decision_id": _id("decision"), "result_id": meta["result_id"],
                    "iteration": run["iteration"], "created_at": _now(),
                    "task_id": task["task_id"], "annotation_version": task["annotation_version"],
                    "before_annotation_version": run["annotation_version"],
                    "role": task["role"], "model": task.get("model"), "provider": task.get("provider")}
        if progress is not None:
            decision["progress"] = progress
            if run["config"].get("specialist_orchestration_version"):
                decision["domain_report_ids"] = domain_ids
        if run.get("initial_label_result_id"):
            decision["initial_label_result_id"] = run["initial_label_result_id"]
        self._commit_labels(db, run, raw.get("label_decisions", []), task=task,
                            result_id=meta["result_id"], decision_id=decision["decision_id"])
        decision["after_annotation_version"] = run["annotation_version"]
        self._record_critique_responses(db, run, raw, decision["decision_id"])
        claims_changed = bool(raw.get("claims")) and fingerprint(raw.get("claims", [])) != fingerprint(run["current_view"].get("claims", []))
        next_view = {"summary": raw.get("summary", ""), "claims": raw.get("claims", []),
                     "alternatives": raw.get("alternatives", []), "unresolved": raw.get("unresolved", [])}
        view_changed = next_view != run["current_view"]
        if run["config"].get("core_progress_version"):
            claims_changed = bool(raw.get("claims")) and self._core_progress_signature({"claims": raw["claims"]}) != self._core_progress_signature({"claims": run["current_view"].get("claims", [])})
            view_changed = not run["last_decision_id"] or self._core_progress_signature(next_view) != self._core_progress_signature(run["current_view"])
        if view_changed:
            run["view_version"] += 1
            run["current_view"] = next_view
            for row in db.execute("SELECT issue_id,payload_json FROM orchestration_issues WHERE run_id=?", (run["run_id"],)).fetchall():
                issue = json.loads(row[1])
                view_issue = not run["config"].get("specialist_orchestration_version") or issue["target_id"] == "view:" + run["run_id"]
                if view_issue and str(issue["target_version"]) != str(run["view_version"]):
                    issue["stale"] = True
                    db.execute("UPDATE orchestration_issues SET payload_json=? WHERE issue_id=?", (_json(issue), row[0]))
        decision["view_version"] = run["view_version"]
        db.execute("INSERT INTO orchestration_decisions VALUES (?,?,?,?)", (decision["decision_id"], run["run_id"], meta["result_id"], _json(decision)))
        run["last_decision_id"] = decision["decision_id"]
        self._event(db, run["run_id"], "core_decision", raw.get("summary", "Core判断を保存しました。"), source="core", target="handler", task_id=task["task_id"])
        if run["config"].get("core_progress_version") and self._pending_result_assessments(db, run):
            run["phase"] = "core"
            self._event(db, run["run_id"], "result_assessments_continued", "未提示の専門家結果の採否を次の判断で確認します。")
            self._write_run(db, run)
            return
        intents = raw.get("intents", [])
        if raw.get("stop"):
            proposal = {**raw["stop"], "target_id": "view:" + run["run_id"], "target_version": run["view_version"],
                        "decision_id": decision["decision_id"], "unexecuted_intents": intents}
            # A reviewer cannot veto indefinitely. A reviewed unchanged view needs
            # only Core's explicit reasoned responses; no repeated critic call.
            reviewed = run["view_version"] in run["reviewed_stop_versions"]
            unanswered = db.execute("SELECT issue_id FROM orchestration_issues WHERE run_id=? AND issue_id NOT IN (SELECT issue_id FROM orchestration_responses WHERE run_id=?)",
                                    (run["run_id"], run["run_id"])).fetchall()
            if reviewed:
                run["pending_stop"] = proposal
                if self._continue_minimum_iterations(db, run, raw["stop"]["reason"]):
                    return
                if unanswered:
                    self._stop(db, run, "human_review_required")
                else:
                    self._stop(db, run, raw["stop"]["reason"], completed=raw["stop"]["reason"] in {"question_satisfied", "no_more_evidence"})
                return
            run["pending_stop"] = proposal
            limit = self._limit(db, run, new_round=True)
            if limit:
                self._stop(db, run, limit)
                return
            run["phase"], run["review_status"] = "stop_review", "pending"
            self._register(db, run, {"role": "critic", "question": "終了案の結論・代替説明・未解決点をレビューする",
                "target_id": proposal["target_id"], "target_version": proposal["target_version"],
                "scope": "pre_stop", "evidence_version": run["input_hash"]}, phase="stop_review", automatic=True)
            if raw.get("claims") and run["status"] not in TERMINAL and not any(t["role"] == "verification" and t["status"] == "succeeded" and t["annotation_version"] == run["annotation_version"] for t in self._tasks(db, run["run_id"])):
                self._register(db, run, {"role": "verification", "question": "原文から独立に観察事実・矛盾を確認する",
                    "target_version": run["view_version"] if claims_changed else None}, phase="stop_review", automatic=True)
        else:
            run["pending_stop"] = None
            run["phase"] = "specialists"
            registered = 0
            for intent in intents:
                if run["status"] in TERMINAL:
                    break
                if intent.get("role") == "core":
                    raise _error("Coreは専門家として再帰発注できません。", "invalid_intent")
                if run["config"]["stop_mode"] == "importance":
                    importance = intent.get("importance")
                    if importance not in IMPORTANCE or not intent.get("importance_reason"):
                        raise _error("重要度モードには重要度と理由が必要です。", "invalid_intent")
                    if IMPORTANCE[importance] < IMPORTANCE[run["config"]["importance_threshold"]]:
                        self._event(db, run["run_id"], "intent_deferred", "重要度の閾値未満の案を保存し、実行しません。", intent=intent)
                        continue
                if intent.get("role") == "critic":
                    intent = {**intent, "target_id": "view:" + run["run_id"], "target_version": run["view_version"]}
                if self._register(db, run, intent, phase="specialists"):
                    registered += 1
            if claims_changed and run["status"] not in TERMINAL:
                requested_roles = {intent["role"] for intent in intents}
                if "verification" not in requested_roles:
                    registered += bool(self._register(db, run, {"role": "verification", "question": "原文から独立に観察事実・矛盾を確認する",
                        "target_version": run["view_version"]}, phase="specialists", automatic=True))
                if "critic" not in requested_roles and run["status"] not in TERMINAL:
                    registered += bool(self._register(db, run, {"role": "critic", "question": "主要な主張と代替説明をレビューする",
                        "target_id": "view:" + run["run_id"], "target_version": run["view_version"], "scope": "major_claim"},
                        phase="specialists", automatic=True))
            if not registered and run["status"] not in TERMINAL:
                # No useful new work is a bounded pause, not a fabricated success.
                reason = "importance_threshold" if run["config"]["stop_mode"] == "importance" else "no_new_tasks"
                if not self._continue_minimum_iterations(db, run, reason):
                    self._stop(db, run, reason)
        self._write_run(db, run)

    def _drain_tasks(self, run_id):
        with self._db() as db:
            run = self._read_run(db, run_id)
            concurrency = run["config"]["concurrency"]
        pool = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="analysis-task")
        futures = {}
        try:
            while True:
                with self._db() as db:
                    received = [t["task_id"] for t in self._tasks(db, run_id) if t["status"] == "received"]
                for task_id in received:
                    self._validate_received(run_id, task_id)
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    limit = self._limit(db, run)
                    if limit:
                        self._stop(db, run, limit)
                    if run["status"] in TERMINAL or run["status"] == "recovery_required":
                        return
                    tasks = self._tasks(db, run_id)
                    if any(t["status"] == "running" and t.get("started_epoch") is not None and time.time() - t["started_epoch"] > run["config"]["call_timeout_seconds"] for t in tasks):
                        self._stop(db, run, "call_timeout")
                        return
                    by_id = {t["task_id"]: t for t in tasks}
                    for task in tasks:
                        if task["status"] != "queued" or task["task_id"] in futures.values():
                            continue
                        dependencies = [by_id[i] for i in task["dependencies"]]
                        if any(t["status"] in {"failed", "quarantined", "cancelled", "blocked"} for t in dependencies):
                            task.update(status="blocked", error="dependency_failed")
                            self._write_task(db, task)
                        elif all(t["status"] == "succeeded" for t in dependencies) and len(futures) < concurrency:
                            futures[pool.submit(self._execute, run_id, task["task_id"])] = task["task_id"]
                    active = [t for t in tasks if t["status"] in {"running", "queued", "received"}]
                    if not futures and not active:
                        return
                if futures:
                    done, _ = wait(futures, timeout=.05, return_when=FIRST_COMPLETED)
                    for future in done:
                        future.result()
                        futures.pop(future, None)
                else:
                    # Unresolvable dependency is explicit, never a busy loop.
                    with self._db() as db:
                        for task in self._tasks(db, run_id):
                            if task["status"] == "queued":
                                task.update(status="blocked", error="dependency_unavailable")
                                self._write_task(db, task)
                    return
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def run(self, run_id: str) -> None:
        """Drive the initial stages and Core phases without duplicate local drivers."""
        with self._worker_lock:
            if run_id in self._driving:
                return
            self._driving.add(run_id)
        try:
            if self._build_initial(run_id):
                self._run_analysis(run_id)
            self._notify_completed(run_id)
        finally:
            with self._worker_lock:
                self._driving.discard(run_id)

    def _prepare_intervals(self, run_id):
        """Freeze run-owned AI drafts and ownership without altering the input."""
        from .services import analysis_intervals as intervals
        from .services.model_context import digest
        with self._db() as db:
            run = self._read_run(db, run_id)
            if not run["config"].get("analysis_interval_version"):
                return
            if run.get("analysis_partition"):
                intervals.check_partition(run["analysis_partition"], run["config"], run["input_hash"])
                return
            if run.get("interval_preparation", {}).get("status") == "running":
                raise _error("議題生成の実行結果を照合してください。自動再生成しません。", "interval_recovery_required")
            initial = self._initial(db, run["initial_id"])
            rows = [e for e in initial["evidence"] if not e["excluded"]]
            source_outline = initial.get("source_outline")
            original = initial.get("archive_snapshot", {}).get("original_source", {}).get("segments")
            matched = isinstance(source_outline, dict) and (source_outline.get("dataset_version") == run["input_hash"]
                or original is not None and source_outline.get("provenance", {}).get("input_sha256") == hashlib.sha256(
                    json.dumps(original, ensure_ascii=False, sort_keys=True).encode()).hexdigest())
            outline = copy.deepcopy(source_outline) if matched else {"sections": []}
            spans = intervals.candidate_spans(rows, outline)
            config, generation = copy.deepcopy(run["config"]), run["generation"]
            run["interval_preparation"] = {"status": "running", "source_outline_sha256": digest(source_outline),
                                            "source_outline_matched": matched, "drafts": []}
            self._write_run(db, run)

        check = lambda: self._check(run_id, generation)

        def before_call():
            check()
            with self._db() as db:
                current = self._read_run(db, run_id)
                if current["calls_started"] >= config["max_calls"]:
                    raise _error("議題生成の呼出し予算が不足しています。", "context_budget_unavailable")
                current["calls_started"] += 1
                self._write_run(db, current)

        # Reuse valid explicit boundaries. Refine coarse topics; gaps and legacy
        # citation-only outlines are separate generation jobs on the same source.
        jobs, cursor = [], 0
        for first, last, topic, title in spans:
            if cursor < first:
                jobs.append((cursor, first, None, "generated"))
            if last - first > config["context_evidence_limit"] - 2 or sum(len(r["text"]) for r in rows[first:last]) > config["context_text_limit"]:
                jobs.append((first, last, topic, "refined"))
            cursor = last
        if cursor < len(rows):
            jobs.append((cursor, len(rows), None, "generated"))
        drafts = []
        for first, last, parent, method in jobs:
            check()
            if parent:
                replaced = {r["utterance_id"] for r in rows[first:last]}
                outline["sections"] = [s for s in outline["sections"] if s.get("start_segment_id") not in replaced]
            draft = {"generation_run_id": _id("outline"), "owner_run_id": run_id, "method": method,
                     "dataset_version": run["input_hash"], "owned_utterance_ids": [r["utterance_id"] for r in rows[first:last]],
                     "status": "unavailable", "reason": "outline_builder_unavailable"}
            if self.outline_builder is not None:
                segments = [{"id": r["utterance_id"], "text": r["text"], "speaker": r["speaker"],
                             "start": r["start"], "end": r["end"]} for r in rows[first:last]]
                try:
                    generated = self.outline_builder(segments, outline if matched else None, config, check, before_call,
                                                     lambda usage: None)
                    check()
                    if (not isinstance(generated, dict) or not generated.get("sections")
                            or len(intervals.candidate_spans(rows[first:last], generated)) != len(generated["sections"])):
                        raise _error("議題境界が対象発話と一致しません。", "outline_invalid")
                    generated = copy.deepcopy(generated)
                    for section in generated["sections"]:
                        section["partition_method"] = method
                    if parent:
                        for section in generated["sections"]:
                            section["parent_topic_id"] = parent
                        replaced = {r["utterance_id"] for r in rows[first:last]}
                        outline["sections"] = [s for s in outline["sections"] if s.get("start_segment_id") not in replaced]
                    outline["sections"].extend(generated["sections"])
                    draft.update(status="ai_draft", reason="", outline=generated, sha256=digest(generated))
                except ExecutionStopped:
                    raise
                except Exception as exc:
                    # Failed/unavailable candidates fall back to time; do not
                    # expose provider exception text or retry cancelled work.
                    check()
                    draft.update(status="failed", reason=getattr(exc, "code", type(exc).__name__))
            if parent and draft["status"] != "ai_draft":
                outline["sections"].append({"title": "", "parent_topic_id": parent, "partition_method": "time",
                    "start_segment_id": rows[first]["utterance_id"], "end_segment_id": rows[last - 1]["utterance_id"]})
            drafts.append(draft)
            with self._db() as db:
                current = self._read_run(db, run_id)
                current["interval_preparation"]["drafts"] = copy.deepcopy(drafts)
                self._write_run(db, current)
        check()
        partition = intervals.build_partition(rows, outline, dataset_version=run["input_hash"],
            time_width=config["analysis_interval_seconds"], row_limit=config["context_evidence_limit"],
            text_limit=config["context_text_limit"], outline_method="existing" if matched else "generated",
            provenance={"source_outline_sha256": digest(source_outline), "source_outline_matched": matched,
                        "drafts": [{k: v for k, v in d.items() if k != "outline"} for d in drafts]})
        partition["excluded_utterance_ids"] = [e["utterance_id"] for e in initial["evidence"] if e["excluded"]]
        partition["sha256"] = digest({k: v for k, v in partition.items() if k != "sha256"})
        with self._db() as db:
            current = self._read_run(db, run_id)
            if current["status"] in TERMINAL or current["generation"] != generation:
                raise ExecutionStopped()
            current.update(analysis_partition=partition)
            current["interval_preparation"]["status"] = "ready"
            self._write_run(db, current)
            self._event(db, run_id, "analysis_intervals_frozen", "分析区間と全発話の所属を固定しました。", partition_sha256=partition["sha256"])
            if any(i["status"] != "ready" for i in partition["intervals"]):
                current.update(status="recovery_required", error="時刻不正または1発話の入力上限超過があります。固定入力を確認して新規実行してください。")
                self._write_run(db, current)

    def _initial_specialist_intents(self, db, run):
        rows = [e for e in self._initial(db, run["initial_id"])["evidence"] if not e["excluded"]]
        pages = []
        if run["config"].get("analysis_interval_version"):
            from .services.analysis_intervals import interval_scope
            pages = [{"evidence_ids": i["owned_evidence_ids"] + i["boundary_evidence_ids"], "scope": interval_scope(i)}
                     for i in run["analysis_partition"]["intervals"]]
        elif run["config"].get("model_context_version"):
            start = 0
            while start < len(rows):
                end, size = start, 0
                while end < len(rows) and end - start < run["config"]["context_evidence_limit"]:
                    length = len(rows[end]["text"])
                    if end > start and size + length > run["config"]["context_text_limit"]:
                        break
                    size += length
                    end += 1
                owned = [e["evidence_id"] for e in rows[start:end]]
                visible = [e["evidence_id"] for e in rows[max(0, start - 1):min(len(rows), end + 1)]]
                pages.append({"evidence_ids": visible, "scope": {"page_number": len(pages) + 1,
                              "owned_evidence_ids": owned, "boundary_evidence_ids": [ref for ref in visible if ref not in owned]}})
                start = end
        else:
            pages = [{}]
        intents = []
        for role in ("interpretation", "verification", "critic"):
            for page in pages:
                page = copy.deepcopy(page)
                if role == "verification" and "scope" in page:
                    page["scope"].pop("title", None)
                intents.append({"role": role, "question": "初回の専門分析: " + run["config"]["question"],
                    **copy.deepcopy(page),
                    **({"target_id": run["initial_id"], "target_version": 0} if role == "critic" else {})})
        intents.extend({"role": "statistics", "method_id": method,
                       "question": "初回の数量・統計: " + method, "label_field": "codes"}
                       for method in sorted(METHODS))
        return intents

    def _run_analysis(self, run_id: str) -> None:
        """Drive persisted phases; safe to call synchronously with mock adapters."""
        try:
            with self._db() as db:
                run = self._read_run(db, run_id)
                if run["status"] in TERMINAL or run["status"] == "recovery_required":
                    return
                self._check_version(run)
                if any(t["status"] in {"running", "uncertain"} for t in self._tasks(db, run_id)):
                    run.update(status="recovery_required", error="進行中だった呼出しを照合してから再開してください。")
                    self._write_run(db, run)
                    return
                if run["started_at"] is None:
                    run["started_at"] = _now()
                    seconds = run["config"]["time_limit_seconds"]
                    run["deadline"] = time.time() + seconds if seconds is not None else None
                run["status"] = "running"
                self._write_run(db, run)
            self._prepare_intervals(run_id)
            while True:
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    if run["status"] in TERMINAL or run["status"] == "recovery_required":
                        return
                    limit = self._limit(db, run)
                    if limit:
                        self._stop(db, run, limit); return
                    phase = run["phase"]
                    tasks = self._tasks(db, run_id)
                    if phase == "core" and run["iteration"] == 0 and run["config"].get("initial_label_definitions_version"):
                        if not run.get("initial_label_result_id"):
                            if run["config"].get("initial_specialist_analysis_version"):
                                initial_intents = self._initial_specialist_intents(db, run)
                                for initial_intent in initial_intents:
                                    self._register(db, run, initial_intent, phase="initial_analysis", automatic=True)
                                    if run["status"] in TERMINAL:
                                        return
                                run["phase"] = phase = "initial_analysis"
                            else:
                                self._register(db, run, {"role": "interpretation", "method_id": "label-design-v1",
                                    "question": "初回のラベル・尺度を設計する: " + run["config"]["question"],
                                    "importance": "high"}, phase="initial_labels", automatic=True)
                                run["phase"] = phase = "initial_labels"
                            self._write_run(db, run)
                    if run["config"].get("specialist_orchestration_version") and phase in {"core", "specialists"}:
                        pending = self._pending_result_assessments(db, run)
                        if pending:
                            queued = [t for t in tasks if t["role"] == "orchestrator" and t["status"] == "queued"]
                            if not queued:
                                domain = self._result_domain(db, pending[0])
                                batch = [rid for rid in pending if self._result_domain(db, rid) == domain][:20]
                                self._register(db, run, {"role": "orchestrator", "method_id": "result-review-v1",
                                    "question": "担当分野の保存結果を評価して具体的な所見と限界を報告する",
                                    "scope": {"domain": domain, "result_ids": batch}}, phase="specialist_review", automatic=True)
                            if run["status"] in TERMINAL:
                                return
                            run["phase"] = phase = "specialist_review"
                            self._write_run(db, run)
                    if phase == "core":
                        pending_core = [t for t in tasks if t["role"] == "core" and t["iteration"] == run["iteration"]]
                        if not pending_core or pending_core[-1]["status"] == "succeeded" and db.execute(
                            "SELECT 1 FROM orchestration_decisions WHERE result_id=(SELECT result_id FROM orchestration_results WHERE task_id=?)", (pending_core[-1]["task_id"],)).fetchone():
                            limit = self._limit(db, run, new_round=True)
                            if limit:
                                self._stop(db, run, limit); return
                            run["iteration"] += 1
                            self._register(db, run, {"role": "core", "question": run["config"]["question"]}, phase="core", automatic=True)
                            self._write_run(db, run)
                self._drain_tasks(run_id)
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    if run["status"] in TERMINAL or run["status"] == "recovery_required":
                        return
                    tasks = self._tasks(db, run_id)
                    if run["config"].get("specialist_orchestration_version") and any(
                            t["phase"] == "specialist_followup" and t["status"] in {"failed", "quarantined", "blocked"}
                            and not t["stale"] for t in tasks):
                        self._stop(db, run, "execution_failure"); return
                    if run["phase"] == "initial_analysis":
                        try:
                            run["initial_analysis_report"] = self._collect_initial_analysis(db, run)
                        except AnalysisContractError as exc:
                            run["error"] = exc.code
                            self._stop(db, run, "initial_analysis_incomplete"); return
                        self._event(db, run_id, "initial_analysis_aggregated", "全専門家の初回分析と尺度要件を集約してCoreへ報告しました。",
                                    source="handler", target="core", report_count=len(run["initial_analysis_report"]["reports"]),
                                    requirement_count=len(run["initial_analysis_report"]["label_requirements"]))
                        self._register(db, run, {"role": "core", "question": "初回の尺度要件を担当へ振り分ける: " + run["config"]["question"],
                            "dependencies": [report["task_id"] for report in run["initial_analysis_report"]["reports"]]},
                            phase="initial_routing", automatic=True)
                        if run["status"] in TERMINAL:
                            return
                        run["phase"] = "initial_routing"
                        self._write_run(db, run)
                    elif run["phase"] == "initial_routing":
                        routing_tasks = [t for t in tasks if t["phase"] == "initial_routing"]
                        if not routing_tasks or any(t["status"] != "succeeded" for t in routing_tasks):
                            self._stop(db, run, "initial_routing_invalid"); return
                        for task in routing_tasks:
                            self._apply_initial_routing(db, run, task)
                            if run["status"] in TERMINAL:
                                return
                    elif run["phase"] == "initial_labels":
                        label_tasks = [t for t in tasks if t["phase"] == "initial_labels"]
                        if not label_tasks or any(t["status"] != "succeeded" for t in label_tasks):
                            self._stop(db, run, "initial_labels_missing"); return
                        task = label_tasks[0]
                        run["initial_label_result_id"] = task["result_id"]
                        if run["config"].get("model_context_version"):
                            run["initial_label_result_ids"] = [t["result_id"] for t in label_tasks]
                        catalog = self._initial_label_catalog(db, run)
                        self._event(db, run_id, "initial_labels_created", "専門家による初回のラベル・尺度定義をAI下書きとして保存しました。",
                                    source="interpretation", target="core", result_id=catalog["result_id"], raw_hash=catalog["raw_hash"])
                        if run["config"].get("specialist_orchestration_version"):
                            references = sorted({ref for definition in catalog["definitions"] for ref in definition["evidence_ids"]})
                            self._register(db, run, {"role": "critic", "question": "初回のラベル・尺度下書きを独立に検証する。欠測を低水準に含めていないか、否定の発話を高評価にしていないか、基準と尺度水準の妥当性を確認する。",
                                "scope": "label_review", "evidence_ids": references, "dependencies": [t["task_id"] for t in label_tasks],
                                "target_id": "labels:" + catalog["result_id"], "target_version": run["annotation_version"]}, phase="label_review", automatic=True)
                            if run["status"] in TERMINAL:
                                return
                            run["phase"] = "label_review"
                        else:
                            run["phase"] = "core"
                        self._write_run(db, run)
                    elif run["phase"] == "label_review":
                        reviews = [t for t in tasks if t["phase"] == "label_review"]
                        if not reviews or any(t["status"] != "succeeded" for t in reviews):
                            self._stop(db, run, "label_review_incomplete"); return
                        run["phase"] = "specialists"
                        self._write_run(db, run)
                    elif run["phase"] == "specialist_review":
                        reviews = [t for t in tasks if t["role"] == "orchestrator" and t["phase"] == "specialist_review" and t.get("result_id")
                            and not db.execute("SELECT 1 FROM orchestration_decisions WHERE result_id=?", (t["result_id"],)).fetchone()]
                        if not reviews or any(t["status"] != "succeeded" for t in reviews):
                            self._stop(db, run, "specialist_review_incomplete"); return
                        for task in reviews:
                            result = db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
                            self._apply_core(db, run, task, result)
                            if run["status"] in TERMINAL:
                                return
                    elif run["phase"] == "core":
                        task = next((t for t in reversed(tasks) if t["role"] == "core" and t["iteration"] == run["iteration"]), None)
                        if task is None or task["status"] != "succeeded":
                            reason = "unreviewed_results" if task and task.get("error") == "result_assessment_missing" else "execution_failure"
                            self._stop(db, run, reason); return
                        result = db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
                        self._apply_core(db, run, task, result)
                    elif run["phase"] == "stop_review":
                        reviews = [t for t in tasks if t["role"] == "critic" and t["phase"] == "stop_review" and t["intent"].get("target_version") == run["pending_stop"]["target_version"]]
                        blind_reviews = [t for t in tasks if t["role"] == "verification" and t["phase"] == "stop_review" and t["iteration"] == run["iteration"]]
                        if not reviews or reviews[-1]["status"] != "succeeded" or any(t["status"] != "succeeded" for t in blind_reviews):
                            run["review_status"] = "unavailable"
                            self._stop(db, run, "review_incomplete"); return
                        run["reviewed_stop_versions"].append(run["pending_stop"]["target_version"])
                        run["review_status"] = "reviewed"
                        run["phase"] = "specialists" if run["config"].get("specialist_orchestration_version") else "core"
                        self._write_run(db, run)
                    else:
                        run["phase"] = "core"
                        self._write_run(db, run)
        except Exception as exc:
            with self._db() as db:
                run = self._read_run(db, run_id)
                if run["status"] not in TERMINAL:
                    run["error"] = getattr(exc, "code", type(exc).__name__)
                    self._stop(db, run, "execution_failure")
