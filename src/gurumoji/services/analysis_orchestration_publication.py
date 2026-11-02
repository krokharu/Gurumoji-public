"""Seal completed autonomous ledgers, then save/publish without recomputation.

SQLite seals are immutable. Store calls deliberately happen outside the sealing
transaction; their commit guards use the connection supplied by AnalysisStore.
The initial opt-in is the only authority for the four existing Vault writers.
"""
from __future__ import annotations

import copy
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable

from ..analysis_core import (AnalysisContractError, EFFECTIVE_PUBLICATION_WRITERS,
                             canonical, fingerprint, validate_publication_targets)
from ..analysis_store import StoreConflict

KIND = "autonomous_analysis"
OUTPUT_VERSION = "autonomous-output-1"
PUBLICATION_LOCK = threading.RLock()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    return canonical(value).decode("utf-8")


def initialize_orchestration_publication_store(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS orchestration_publications (
        run_id TEXT PRIMARY KEY, item_id TEXT NOT NULL, generation INTEGER NOT NULL,
        sealed_json TEXT NOT NULL, sealed_hash TEXT NOT NULL, targets_json TEXT NOT NULL,
        initial_hash TEXT NOT NULL, save_status TEXT NOT NULL DEFAULT 'not_started',
        publication_status TEXT NOT NULL, result_run_id TEXT NOT NULL DEFAULT '',
        package_hash TEXT NOT NULL DEFAULT '', active_attempt_id TEXT NOT NULL DEFAULT '',
        stale INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS orchestration_publication_attempts (
        attempt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, sequence INTEGER NOT NULL,
        generation INTEGER NOT NULL, sealed_hash TEXT NOT NULL, status TEXT NOT NULL,
        save_status TEXT NOT NULL, publication_status TEXT NOT NULL,
        result_run_id TEXT NOT NULL DEFAULT '', package_hash TEXT NOT NULL DEFAULT '',
        error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, ended_at TEXT,
        UNIQUE(run_id,sequence))""")


def recover_orchestration_publications(connection):
    """Startup only: uncertain work needs explicit retry, never automatic writes."""
    now = _now()
    connection.execute("""UPDATE orchestration_publication_attempts SET status='interrupted',
        error='保存・公開の確認が再起動で中断されました。',ended_at=? WHERE status='running'""", (now,))
    connection.execute("""UPDATE orchestration_publications SET
        save_status=CASE WHEN save_status='saving' THEN 'interrupted' ELSE save_status END,
        publication_status=CASE WHEN publication_status='publishing' THEN 'interrupted' ELSE publication_status END,
        active_attempt_id='',error='保存・公開の確認が再起動で中断されました。',updated_at=?
        WHERE active_attempt_id!=''""", (now,))


def _scope(run):
    # Legacy runs never acquire publication permission merely by being exported.
    return validate_publication_targets(run.get("config", {}).get("publication_targets", []))


def _validate_export(db, item_id, run_id, run, exported):
    """Verify immutable bytes and relational ownership before the one-time seal."""
    initial = db.execute("SELECT * FROM orchestration_initials WHERE initial_id=?", (run["initial_id"],)).fetchone()
    if not initial or initial["item_id"] != item_id or initial["status"] != "ready":
        raise StoreConflict("初期分析の所有権または固定版を確認できません。")
    snapshot = json.loads(initial["snapshot_json"])
    if (fingerprint(snapshot) != initial["snapshot_hash"] or snapshot.get("input_hash") != run["input_hash"]
            or any(snapshot.get(key, 0) != run[key] for key in ("source_revision", "analysis_revision"))
            or exported.get("initial") != {"initial_id": initial["initial_id"], "hash": initial["snapshot_hash"], "snapshot": snapshot}):
        raise StoreConflict("初期分析のhashまたは出力版が一致しません。")
    expected_run = copy.deepcopy(run)
    expected_run["config"].setdefault("publication_targets", [])
    expected_run["config"]["effective_publication_writers"] = list(EFFECTIVE_PUBLICATION_WRITERS) if _scope(run) else []
    if any(exported.get("run", {}).get(key) != value for key, value in expected_run.items()):
        raise StoreConflict("出力のrun版が一致しません。")
    tasks = {}
    for row in db.execute("SELECT * FROM orchestration_tasks WHERE run_id=? ORDER BY rowid", (run_id,)):
        task = json.loads(row["state_json"])
        if (task.get("task_id") != row["task_id"] or task.get("run_id") != run_id
                or task.get("idempotency_key") != row["idempotency_key"] or not task.get("attempt_id")
                or task.get("dataset_version") != run["input_hash"]):
            raise StoreConflict("タスクのrun・attempt所有権が一致しません。")
        tasks[row["task_id"]] = task
    if exported["run"].get("tasks") != list(tasks.values()):
        raise StoreConflict("タスクの固定出力が一致しません。")
    results = []
    for row in db.execute("SELECT * FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run_id,)):
        meta, raw = json.loads(row["state_json"]), json.loads(row["raw_json"])
        task = tasks.get(row["task_id"])
        if (not task or meta.get("result_id") != row["result_id"] or meta.get("run_id") != run_id
                or meta.get("task_id") != task["task_id"] or meta.get("attempt_id") != task["attempt_id"]
                or task.get("result_id") != row["result_id"] or meta.get("raw_hash") != fingerprint(raw)
                or meta.get("role") != task["role"] or meta.get("annotation_version") != task["annotation_version"]
                or meta.get("dataset_version") != run["input_hash"]):
            raise StoreConflict("原結果のhashまたはrun・task・attempt所有権が一致しません。")
        results.append({**meta, "raw": raw})
    if exported.get("raw_results") != results:
        raise StoreConflict("原結果の固定出力が一致しません。")
    # A well-formed export must include every source label version and decision.
    for key, query in (("decisions", "SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid"),):
        if exported.get(key) != [json.loads(row[0]) for row in db.execute(query, (run_id,))]:
            raise StoreConflict("判断履歴の固定出力が一致しません。")
    labels = [{"annotation_version": row[0], "labels": json.loads(row[1])} for row in db.execute(
        "SELECT annotation_version,payload_json FROM orchestration_label_versions WHERE run_id=? ORDER BY annotation_version", (run_id,))]
    if exported.get("label_versions") != labels:
        raise StoreConflict("ラベル版の固定出力が一致しません。")
    usage = [{"usage_id": row[0], "task_id": row[1], "payload": json.loads(row[2])} for row in db.execute(
        "SELECT usage_id,task_id,payload_json FROM orchestration_usage WHERE run_id=? ORDER BY rowid", (run_id,))]
    if exported.get("usage_records", []) != usage or any(
            value["task_id"] not in tasks or value["payload"].get("task_id") != value["task_id"] for value in usage):
        raise StoreConflict("利用量の全件記録またはタスク所有権が一致しません。")
    return initial["snapshot_hash"]


def build_orchestration_package(exported, sealed_hash):
    """Pure projection: readable notes plus the complete unmodified ledger JSON."""
    run, initial = exported["run"], exported["initial"]
    snapshot = initial["snapshot"]
    evidence = {}
    by_id = {}
    for row in snapshot.get("evidence", []):
        sid, eid = str(row["utterance_id"]), row["evidence_id"]
        if sid in evidence or eid in by_id or row.get("source_hash") != fingerprint(row["text"]):
            raise StoreConflict("固定根拠のIDまたは本文hashが一致しません。")
        expected_id = "ev_" + fingerprint({"dataset": run["input_hash"], "utterance": sid, "text": row["text"]})[7:31]
        if eid != expected_id or row.get("dataset_version") != run["input_hash"]:
            raise StoreConflict("固定根拠の入力版が一致しません。")
        by_id[eid] = row
        if not row.get("excluded"):
            evidence[sid] = {"id": sid, **{key: row.get(key) for key in ("text", "speaker", "start", "end")}}
    findings = []
    for claim in run.get("current_view", {}).get("claims", []):
        ids = claim.get("evidence_ids")
        if not isinstance(ids, list) or not ids or any(eid not in by_id or by_id[eid].get("excluded") for eid in ids):
            raise StoreConflict("主張の根拠を固定した分析本文へ対応付けられません。")
        findings.append({"title": str(claim.get("claim_id", "主張")),
                         "text": f"{claim.get('kind', 'AI下書き')}：{claim.get('text', '')}",
                         "segment_ids": list(dict.fromkeys(by_id[eid]["utterance_id"] for eid in ids))})
    limitations = ["探索的なAI下書きです。研究者が確定した解釈や因果関係・人物属性の証明ではありません。",
                   "全原結果・初期分析・判断履歴・批判・ラベル版は保存パッケージのorchestration文書に保存されています。"]
    if run.get("review_status") != "reviewed":
        limitations.append("終了時の独立批判レビューは完了していません。")
    unresolved = run.get("unresolved_issues", [])
    limitations += [f"未解決の批判 {issue.get('issue_id', '')}：{issue.get('description', issue.get('message', issue.get('text', issue.get('summary', '原記録を参照'))))}" for issue in unresolved]
    summaries = [{"title": "問い", "text": run["config"]["question"]},
                 {"title": "Coreの暫定要約", "text": run.get("current_view", {}).get("summary", "")},
                 {"title": "終了と確認状態", "text": f"{run['status']} / {run.get('stop_reason', '')} / review: {run.get('review_status', '')}"}]
    # One provenance table also gives VisualizationVault an actual artifact to
    # describe. Detailed numerical results remain intact in the complete ledger.
    rows = [{"run_id": run["run_id"], "question": run["config"]["question"],
             "status": run["status"], "stop_reason": run.get("stop_reason", ""),
             "iteration": run.get("iteration", 0), "claim_count": len(findings),
             "unresolved_count": len(unresolved), "review_status": run.get("review_status", ""),
             "sealed_hash": sealed_hash}]
    fields = list(rows[0])
    method = {"method_id": KIND, "title": "自律探索分析・Core／Handler", "method_version": OUTPUT_VERSION,
              "status": "completed", "summaries": summaries, "findings": findings,
              "details": {"evidence": evidence}, "datasets": ["autonomous_summary"],
              "previews": [{"dataset": "autonomous_summary", "fields": fields, "rows": rows, "total": 1}],
              "analysis_unit": "固定入力の発話と探索的な分析履歴",
              "engine": {"adapter_version": run["config"].get("adapter_version"), "roles": run["config"].get("roles", {})},
              "limitations": limitations}
    parameters = {"autonomous_run_id": run["run_id"], "sealed_hash": sealed_hash,
                  "initial_id": initial["initial_id"], "initial_hash": initial["hash"],
                  "generation": run["generation"], "publication_targets": _scope(run),
                  "output_version": OUTPUT_VERSION, "research_mode": "exploratory",
                  **{key: run.get(key) for key in ("view_version", "annotation_version", "codebook_version")}}
    archived = copy.deepcopy(snapshot.get("archive_snapshot") or {
        "title": run["item_id"], "segments": snapshot["analysis"].get("segments", [])})
    result = {"schema_version": 1, "parameters": parameters,
              "algorithms": {"orchestration_output": OUTPUT_VERSION}, "methods": [method],
              "orchestration": copy.deepcopy(exported)}
    return archived, result, {"autonomous_summary": (fields, rows)}


class AnalysisOrchestrationPublicationService:
    def __init__(self, *, connect: Callable, store_factory: Callable,
                 source_guard: Callable, export_locked: Callable, write_lock=None):
        self.connect, self.store_factory = connect, store_factory
        self.source_guard, self.export_locked = source_guard, export_locked
        self.lock = write_lock or threading.RLock()
        with self._db() as db:
            initialize_orchestration_publication_store(db)

    @contextmanager
    def _db(self):
        with self.lock, self.connect() as db:
            db.row_factory = sqlite3.Row
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            yield db

    def recover(self):
        with self._db() as db:
            recover_orchestration_publications(db)

    @staticmethod
    def _run(db, item_id, run_id):
        row = db.execute("SELECT * FROM orchestration_runs WHERE run_id=? AND item_id=?", (run_id, item_id)).fetchone()
        if row is None:
            raise LookupError("自律分析runが見つかりません。")
        run = json.loads(row["state_json"])
        if (run.get("run_id") != run_id or run.get("item_id") != item_id
                or run.get("initial_id") != row["initial_id"] or run.get("request_id") != row["request_id"]):
            raise StoreConflict("自律分析runの所有権が一致しません。")
        return run

    def _source(self, db, item_id, run, *, allow_stale):
        try:
            self.source_guard(db, item_id, run["input_hash"])
            return False
        except AnalysisContractError as exc:
            if allow_stale and exc.code == "revision_conflict":
                return True
            raise

    def _seal(self, db, item_id, run_id):
        run = self._run(db, item_id, run_id)
        if run["status"] != "completed" or run.get("cancel_requested"):
            raise StoreConflict("正常終了した自律分析だけを固定保存・公開できます。")
        row = db.execute("SELECT * FROM orchestration_publications WHERE run_id=?", (run_id,)).fetchone()
        if row:
            self._verify_seal(row, run)
            return dict(row)
        stale = self._source(db, item_id, run, allow_stale=True)
        exported = self.export_locked(db, item_id, run_id)
        initial_hash = _validate_export(db, item_id, run_id, run, exported)
        sealed_hash = fingerprint(exported)
        # Validate readable evidence projection before any durable output exists.
        build_orchestration_package(exported, sealed_hash)
        now, targets = _now(), _scope(run)
        db.execute("""INSERT INTO orchestration_publications
            (run_id,item_id,generation,sealed_json,sealed_hash,targets_json,initial_hash,
             publication_status,stale,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                   (run_id, item_id, run["generation"], _json(exported), sealed_hash, _json(targets), initial_hash,
                    "pending" if targets else "not_selected", int(stale), now, now))
        return dict(db.execute("SELECT * FROM orchestration_publications WHERE run_id=?", (run_id,)).fetchone())

    @staticmethod
    def _verify_seal(row, run):
        exported = json.loads(row["sealed_json"])
        sealed = exported["run"]
        if (fingerprint(exported) != row["sealed_hash"] or row["item_id"] != run["item_id"]
                or row["generation"] != run["generation"] or sealed["generation"] != row["generation"]
                or sealed["run_id"] != run["run_id"] or sealed["input_hash"] != run["input_hash"]
                or sealed["initial_id"] != run["initial_id"] or exported["initial"]["hash"] != row["initial_hash"]
                or fingerprint(exported["initial"]["snapshot"]) != row["initial_hash"]
                or json.loads(row["targets_json"]) != _scope(run) or _scope(sealed) != _scope(run)):
            raise StoreConflict("固定出力のhash・実行世代・承認範囲が一致しません。")
        return exported

    def _guard(self, db, item_id, run_id, attempt_id, *, allow_stale=False, source=True):
        run = self._run(db, item_id, run_id)
        row = db.execute("SELECT * FROM orchestration_publications WHERE run_id=?", (run_id,)).fetchone()
        attempt = db.execute("SELECT * FROM orchestration_publication_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        if (not row or not attempt or run["status"] != "completed" or run.get("cancel_requested")
                or row["active_attempt_id"] != attempt_id or attempt["status"] != "running"
                or attempt["run_id"] != run_id or attempt["generation"] != run["generation"]
                or attempt["sealed_hash"] != row["sealed_hash"]):
            raise StoreConflict("保存・公開試行の所有権または実行世代が変わりました。")
        self._verify_seal(row, run)
        if row["result_run_id"]:
            saved = db.execute("SELECT * FROM analysis_runs WHERE id=?", (row["result_run_id"],)).fetchone()
            if (not saved or saved["item_id"] != item_id or saved["kind"] != KIND
                    or saved["fingerprint"] != row["package_hash"]
                    or saved["input_fingerprint"] != run["input_hash"]):
                raise StoreConflict("固定packageの保存先またはhash所有権が一致しません。")
        if source and self._source(db, item_id, run, allow_stale=allow_stale):
            db.execute("UPDATE orchestration_publications SET stale=1 WHERE run_id=?", (run_id,))
            if row["result_run_id"]:
                db.execute("UPDATE analysis_runs SET stale=1 WHERE id=?", (row["result_run_id"],))
        return row

    def finalize(self, item_id, run_id):
        return self._execute(item_id, run_id)

    def retry(self, item_id, run_id):
        # Exactly the same immutable package/scope; no runtime resume or exporter
        # call for a sealed run, and no analysis/snapshot/model recomputation.
        return self._execute(item_id, run_id)

    def _execute(self, item_id, run_id):
        # Match the application's library -> Store -> Vault lock order. This
        # holds no database transaction during filesystem publication.
        with self.lock, PUBLICATION_LOCK:
            with self._db() as db:
                row = self._seal(db, item_id, run_id)
                if row["active_attempt_id"]:
                    raise StoreConflict("保存・公開の試行は実行中です。")
                attempt_id, now = uuid.uuid4().hex, _now()
                sequence = db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM orchestration_publication_attempts WHERE run_id=?", (run_id,)).fetchone()[0]
                save_status = "saved" if row["result_run_id"] else "saving"
                publication_status = "pending" if json.loads(row["targets_json"]) else "not_selected"
                db.execute("""INSERT INTO orchestration_publication_attempts
                    (attempt_id,run_id,sequence,generation,sealed_hash,status,save_status,publication_status,created_at)
                    VALUES (?,?,?,?,?,'running',?,?,?)""", (attempt_id, run_id, sequence, row["generation"], row["sealed_hash"], save_status, publication_status, now))
                db.execute("UPDATE orchestration_publications SET active_attempt_id=?,save_status=?,publication_status=?,error='',updated_at=? WHERE run_id=?",
                           (attempt_id, save_status, publication_status, now, run_id))
            error = ""
            try:
                store = self.store_factory()
                exported = json.loads(row["sealed_json"])
                run = exported["run"]
                snapshot, result, datasets = build_orchestration_package(exported, row["sealed_hash"])
                # save() supports recovery after an acknowledgement was lost.
                saved = store.save(item_id=item_id, kind=KIND, snapshot=snapshot, result=result, datasets=datasets,
                    request_id="autonomous-output-" + run_id, input_fingerprint=run["input_hash"],
                    source_revision=run["source_revision"], analysis_revision=run["analysis_revision"],
                    app_url=run.get("app_url") or "http://127.0.0.1:7860", provider=run["config"].get("provider", ""),
                    model=run["config"].get("model", ""), publish=False,
                    commit_guard=lambda db: self._guard(db, item_id, run_id, attempt_id, allow_stale=True))
                verified = store.verified_package(saved["id"])
                if (verified[1].get("parameters") != result["parameters"]
                        or verified[1].get("orchestration") != exported or saved["item_id"] != item_id):
                    raise StoreConflict("保存済みpackageと封印した出力が一致しません。")
                with self._db() as db:
                    current = self._guard(db, item_id, run_id, attempt_id, allow_stale=True)
                    if current["stale"]:
                        db.execute("UPDATE analysis_runs SET stale=1 WHERE id=?", (saved["id"],))
                    db.execute("UPDATE orchestration_publications SET result_run_id=?,package_hash=?,save_status='saved',updated_at=? WHERE run_id=?",
                               (saved["id"], saved["fingerprint"], _now(), run_id))
                save_status = "saved"
                targets = json.loads(row["targets_json"])
                if targets:
                    with self._db() as db:
                        self._guard(db, item_id, run_id, attempt_id)
                        db.execute("UPDATE orchestration_publications SET publication_status='publishing',updated_at=? WHERE run_id=?", (_now(), run_id))
                    store.publish(saved["id"], targets=targets, reuse_completed=True,
                        commit_guard=lambda db: self._guard(db, item_id, run_id, attempt_id))
                    latest = store.public(store.get(saved["id"]))
                    publication_status = "published" if latest["vault_outputs_complete"] else "incomplete"
                    if publication_status == "incomplete":
                        error = "一部のVault出力を完了できませんでした。固定成果物は保存済みです。"
                else:
                    publication_status = "not_selected"
            except Exception as exc:
                error = str(exc)[:1000]
                publication_status = "conflict" if isinstance(exc, (StoreConflict, AnalysisContractError, LookupError)) else "incomplete"
                if save_status != "saved":
                    save_status = "failed"
            with self._db() as db:
                # A superseded/recovered attempt cannot overwrite its new owner.
                self._guard(db, item_id, run_id, attempt_id, source=False)
                current = db.execute("SELECT * FROM orchestration_publications WHERE run_id=?", (run_id,)).fetchone()
                db.execute("""UPDATE orchestration_publication_attempts SET status=?,save_status=?,publication_status=?,
                    result_run_id=?,package_hash=?,error=?,ended_at=? WHERE attempt_id=?""",
                    ("failed" if error else "completed", save_status, publication_status,
                     current["result_run_id"], current["package_hash"], error, _now(), attempt_id))
                db.execute("""UPDATE orchestration_publications SET active_attempt_id='',save_status=?,
                    publication_status=?,error=?,updated_at=? WHERE run_id=?""",
                    (save_status, publication_status, error, _now(), run_id))
        return self.status(item_id, run_id)

    def status(self, item_id, run_id):
        with self._db() as db:
            run = self._run(db, item_id, run_id)
            row = db.execute("SELECT * FROM orchestration_publications WHERE run_id=?", (run_id,)).fetchone()
            targets = json.loads(row["targets_json"]) if row else _scope(run)
            attempts = [dict(value) for value in db.execute(
                "SELECT * FROM orchestration_publication_attempts WHERE run_id=? ORDER BY sequence", (run_id,))]
            stale = bool(row["stale"]) if row else bool(run.get("stale"))
            try:
                stale = self._source(db, item_id, run, allow_stale=True) or stale
            except LookupError:
                stale = True
            result = {"save_status": row["save_status"] if row else "not_started",
                      "publication_status": row["publication_status"] if row else ("pending" if targets else "not_selected"),
                      "publication_targets": targets, "effective_writers": list(EFFECTIVE_PUBLICATION_WRITERS) if targets else [],
                      "result_run_id": row["result_run_id"] if row else "", "result_run": None,
                      "sealed_hash": row["sealed_hash"] if row else "", "package_hash": row["package_hash"] if row else "",
                      "stale": stale, "error": row["error"] if row else "", "attempts": attempts,
                      "can_retry": run["status"] == "completed" and not stale and not (row and row["active_attempt_id"])}
        selected_status = "pending" if targets else "not_selected"
        if run["status"] in {"cancelled", "failed", "stopped"} and not row:
            result["publication_status"] = selected_status = "skipped"
        result["outcomes"] = {kind: {"status": selected_status, "error": ""} for kind in EFFECTIVE_PUBLICATION_WRITERS}
        if result["result_run_id"]:
            store = self.store_factory()
            saved = store.get(result["result_run_id"])
            if saved:
                result["result_run"] = store.public(saved)
                if targets:
                    result["outcomes"] = result["result_run"]["publication_outcomes"]
        if result["save_status"] == "saved" and result["publication_status"] in {"published", "not_selected"}:
            result["can_retry"] = False
        return result
