"""Bounded, read-only projections of the saved orchestration ledger.

No execution service, provider, source rebuild, migration or recovery is invoked.
Only explicitly allowlisted public summaries/justifications are returned; model
scratch work and arbitrary raw result dictionaries remain outside this API.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from ..analysis_core import AnalysisContractError, fingerprint
from ..analysis_orchestration import AI_ROLES, LABEL_FIELDS, ROLES, TERMINAL

MAX_PAGE = 100
MAX_REFS = 100
LIMITS = {"text_chars": 2000, "summary_chars": 4000, "claims": 50, "evidence_refs": 100, "label_values": 50}


def _strings(value, maximum=MAX_REFS):
    return [r for r in value[:maximum] if isinstance(r, str)] if isinstance(value, list) else []


def _over(value, maximum):
    return isinstance(value, (str, list)) and len(value) > maximum



def _text(value, limit=2000):
    return value[:limit] if isinstance(value, str) else None


def _value(value):
    if value is None or type(value) in {bool, int, float}:
        return value
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, list):
        return [v[:2000] for v in value[:50] if isinstance(v, str)]
    return None


def _labels(value):
    return {k: _value(v) for k, v in value.items() if k in LABEL_FIELDS} if isinstance(value, dict) else None


def _integer(value, default, minimum=0, maximum=None, field="limit"):
    if value is None or value == "":
        return default
    try:
        if isinstance(value, bool) or str(int(value)) != str(value):
            raise ValueError
        result = int(value)
        if result < minimum or result > 2**63 - 1 or (maximum is not None and result > maximum):
            raise ValueError
        return result
    except (ValueError, TypeError, OverflowError):
        raise AnalysisContractError("履歴のページ・版指定が正しくありません。", field=field)


def _date(value, field):
    if value in (None, ""):
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.tzinfo is None:
            raise ValueError
        return date.isoformat()
    except (ValueError, TypeError, AttributeError):
        raise AnalysisContractError("日時はタイムゾーン付きISO形式で指定してください。", field=field)


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds") if parsed.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def _page(offset, limit, total):
    return {"offset": offset, "limit": limit, "total": total, "has_more": offset + limit < total}


class AnalysisHistoryService:
    def __init__(self, *, connect, find_item):
        self.connect, self.find_item = connect, find_item

    @contextmanager
    def _read(self, item_id):
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            db.create_function("history_time", 1, _timestamp, deterministic=True)
            # Enforce the boundary, including when a caller supplies a writable
            # connection. A deferred read transaction pins all projections.
            previous = db.execute("PRAGMA query_only").fetchone()[0]
            db.execute("PRAGMA query_only=ON")
            started = not db.in_transaction
            if started:
                db.execute("BEGIN")
            try:
                yield db
            finally:
                if started:
                    db.rollback()
                db.execute(f"PRAGMA query_only={int(previous)}")

    @staticmethod
    def _table(db, name):
        return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())

    def _run(self, db, item_id, run_id):
        if not self._table(db, "orchestration_runs"):
            raise LookupError("分析履歴が見つかりません。")
        row = db.execute("SELECT * FROM orchestration_runs WHERE item_id=? AND run_id=?", (item_id, run_id)).fetchone()
        if row is None:
            raise LookupError("分析履歴が見つかりません。")
        run = json.loads(row["state_json"])
        if any(run.get(key) != row[key] for key in ("item_id", "run_id", "initial_id")):
            raise AnalysisContractError("保存された分析履歴の所属情報が一致しません。", code="history_integrity_mismatch")
        return run

    def _audit(self, db, run):
        complete = run.get("label_audit_version") == 1 and self._table(db, "orchestration_label_audit")
        return {"status": "complete" if complete else "partial", "message":
                "ラベル提案・採否は追記監査記録です。表示は保存済みの要約と理由に限定しています。" if complete else
                "旧履歴を含みます。保存済み状態からの表示であり、未記録の操作時刻・担当・変更過程は復元できません。"}

    def _public_run(self, db, run):
        value = {key: _value(run.get(key)) for key in (
            "run_id", "item_id", "status", "created_at", "updated_at", "stop_reason", "initial_id", "input_hash",
            "annotation_version", "view_version", "source_revision", "analysis_revision", "last_decision_id")}
        value.update(question=_text(run.get("config", {}).get("question")),
                     current_summary=_text(run.get("current_view", {}).get("summary"), 4000),
                     summary_entry_id="decision:" + run["last_decision_id"] if run.get("last_decision_id") else None,
                     audit_status=self._audit(db, run)["status"])
        value["truncated_fields"] = [key for key, raw, limit in (
            ("question", run.get("config", {}).get("question"), 2000),
            ("current_summary", run.get("current_view", {}).get("summary"), 4000)) if _over(raw, limit)]
        value["summary_annotation_version"] = None
        value["summary_after_annotation_version"] = None
        if run.get("last_decision_id"):
            row = db.execute("SELECT payload_json,result_id FROM orchestration_decisions WHERE run_id=? AND decision_id=?",
                             (run["run_id"], run["last_decision_id"])).fetchone()
            if row:
                decision = json.loads(row[0])
                value["summary_annotation_version"] = decision.get("annotation_version")
                value["summary_after_annotation_version"] = decision.get("after_annotation_version")
                if value["summary_annotation_version"] is None:
                    result = db.execute("SELECT state_json FROM orchestration_results WHERE run_id=? AND result_id=?", (run["run_id"], row["result_id"])).fetchone()
                    if result:
                        value["summary_annotation_version"] = json.loads(result[0]).get("annotation_version")
        return value

    def runs(self, item_id, *, limit=20, offset=0):
        limit, offset = _integer(limit, 20, 1, MAX_PAGE), _integer(offset, 0, field="offset")
        with self._read(item_id) as db:
            if not self._table(db, "orchestration_runs"):
                return {"runs": [], "pagination": _page(offset, limit, 0)}
            total = db.execute("SELECT count(*) FROM orchestration_runs WHERE item_id=?", (item_id,)).fetchone()[0]
            rows = db.execute("SELECT run_id FROM orchestration_runs WHERE item_id=? ORDER BY rowid DESC LIMIT ? OFFSET ?",
                              (item_id, limit, offset)).fetchall()
            return {"runs": [self._public_run(db, self._run(db, item_id, row[0])) for row in rows], "pagination": _page(offset, limit, total)}

    def agents(self, item_id, run_id):
        """Project saved role/task state without constructing an executor."""
        with self._read(item_id) as db:
            run = self._run(db, item_id, run_id)
            tasks = []
            for row in db.execute("SELECT task_id,state_json FROM orchestration_tasks WHERE run_id=? ORDER BY rowid", (run_id,)):
                task = json.loads(row["state_json"])
                if task.get("run_id") != run_id or task.get("task_id") != row["task_id"] or task.get("role") not in ROLES:
                    raise AnalysisContractError("保存された担当タスクの所属情報が一致しません。", code="history_integrity_mismatch")
                tasks.append(task)
            roles = []
            for role, label in ROLES.items():
                assigned = [task for task in tasks if task["role"] == role]
                counts = {}
                for task in assigned:
                    status = task.get("status") or "unknown"
                    counts[status] = counts.get(status, 0) + 1
                state = "idle"
                for status in ("uncertain", "cancel_requested", "running", "queued", "received"):
                    if counts.get(status):
                        state = status
                        break
                else:
                    state = run.get("status") if run.get("status") in TERMINAL | {"recovery_required"} else "idle"
                options = run.get("config", {}).get("roles", {}).get(role, {})
                roles.append({"id": role, "label": label, "kind": "ai" if role in AI_ROLES else "code",
                    "provider": _text(options.get("provider"), 100) if role in AI_ROLES else "python",
                    "model": _text(options.get("model"), 200) if role in AI_ROLES else "deterministic",
                    "status": state, "assigned": len(assigned), "status_counts": counts,
                    "active_tasks": [{"task_id": task["task_id"], "status": task.get("status"),
                                      "method_id": _text(task.get("method_id"), 100)}
                                     for task in assigned if task.get("status") in {"running", "cancel_requested", "uncertain", "received"}]})
            return {"run_id": run_id, "item_id": item_id, "input_hash": _text(run.get("input_hash"), 100),
                    "status": _text(run.get("status"), 100), "phase": _text(run.get("phase"), 100),
                    "updated_at": _text(run.get("updated_at"), 100), "stop_reason": _text(run.get("stop_reason"), 100),
                    "roles": roles, "observation": "saved_ledger_only"}

    def _versions(self, db, run, selected):
        selected = _integer(selected, run.get("annotation_version", 0), field="annotation_version")
        rows = db.execute("SELECT annotation_version FROM orchestration_label_versions WHERE run_id=? ORDER BY annotation_version LIMIT 201",
                          (run["run_id"],)).fetchall() if self._table(db, "orchestration_label_versions") else []
        total = db.execute("SELECT count(*) FROM orchestration_label_versions WHERE run_id=?", (run["run_id"],)).fetchone()[0] if rows else 0
        if selected is not None and total and not db.execute(
                "SELECT 1 FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?", (run["run_id"], selected)).fetchone():
            raise LookupError("指定されたラベル版が見つかりません。")
        if not total and selected != 0:
            raise LookupError("指定されたラベル版が見つかりません。")
        return {"initial": 0 if total else None, "selected": selected if total else None,
                "latest": run.get("annotation_version") if total else None,
                "available": [row[0] for row in rows[:200]], "total": total, "has_more": len(rows) > 200}

    def _timeline_sql(self, db, run):
        # SELECT/filter/order/limit precede deserialization of individual entries.
        tables = [
            ("task", "orchestration_tasks", "task_id", "state_json", "created_at", "role", "NULL", "status"),
            ("result", "orchestration_results", "result_id", "state_json", "received_at", "role", "NULL", "validation_status"),
            ("decision", "orchestration_decisions", "decision_id", "payload_json", "created_at", "'core'", "'decision'", "'saved'"),
            ("event", "orchestration_events", "seq", "payload_json", "created_at", "from", "type", "type"),
        ]
        if self._table(db, "orchestration_label_audit"):
            tables.append(("label", "orchestration_label_audit", "event_id", "payload_json", "created_at", "role", "operation", "status"))
        terms = []
        params = []
        for rank, (kind, table, key, payload, date, role, operation, status) in enumerate(tables):
            if not self._table(db, table):
                continue
            def j(field):
                return field if field == "NULL" or field.startswith("'") else f"json_extract({payload}, '$.{field}')"
            terms.append(f"SELECT '{kind}:' || {key} AS entry_id,'{kind}' AS kind,{j(date)} AS created_at,{j(role)} AS role,"
                         f"{j(operation)} AS operation,{j(status)} AS status,{j('disposition') if kind == 'label' else 'NULL'} AS disposition,"
                         f"{rank} AS rank,rowid AS sequence FROM {table} WHERE run_id=?")
            params.append(run["run_id"])
        if self._table(db, "orchestration_initials"):
            terms.append("SELECT 'initial:'||initial_id,'initial',created_at,'handler','initial',status,NULL,-1,rowid "
                         "FROM orchestration_initials WHERE item_id=? AND initial_id=?")
            params.extend([run["item_id"], run["initial_id"]])
        if self._table(db, "orchestration_label_proposals"):
            # Compatibility is a projection, never a migration or fabricated
            # action timestamp. The current proposal status is explicitly legacy.
            exclusion = (" AND NOT EXISTS (SELECT 1 FROM orchestration_label_audit a WHERE a.run_id=p.run_id AND a.proposal_id=p.proposal_id)"
                         if self._table(db, "orchestration_label_audit") else "")
            terms.append("SELECT 'legacy_label:'||proposal_id,'label',json_extract(payload_json,'$.created_at'),NULL,"
                         "json_extract(payload_json,'$.operation'),json_extract(payload_json,'$.status'),NULL,5,rowid "
                         "FROM orchestration_label_proposals p WHERE run_id=?" + exclusion)
            params.append(run["run_id"])
        return " UNION ALL ".join(terms), params

    def timeline(self, item_id, run_id, *, limit=30, offset=0, kind=None, role=None, operation=None,
                 status=None, after=None, before=None, annotation_version=None):
        limit, offset = _integer(limit, 30, 1, MAX_PAGE), _integer(offset, 0, field="offset")
        after, before = _date(after, "after"), _date(before, "before")
        if after and before and datetime.fromisoformat(after) > datetime.fromisoformat(before):
            raise AnalysisContractError("日時範囲の開始は終了以前にしてください。", field="after")
        filters, values = [], []
        for key, value in (("kind", kind), ("role", role), ("operation", operation), ("status", status)):
            if value:
                if not isinstance(value, str) or len(value) > 100:
                    raise AnalysisContractError("履歴フィルターが正しくありません。", field=key)
                filters.append("(operation=? OR disposition=?)" if key == "operation" else f"{key}=?")
                values.extend([value, value] if key == "operation" else [value])
        for operator, date in ((">=", after), ("<=", before)):
            if date:
                filters.append(f"history_time(created_at) {operator} history_time(?)")
                values.append(date)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self._read(item_id) as db:
            run = self._run(db, item_id, run_id)
            versions = self._versions(db, run, annotation_version)
            union, params = self._timeline_sql(db, run)
            sql = "WITH timeline AS (" + union + ") "
            total = db.execute(sql + "SELECT count(*) FROM timeline" + where, params + values).fetchone()[0]
            rows = db.execute(sql + "SELECT entry_id FROM timeline" + where +
                              " ORDER BY history_time(created_at) IS NULL,history_time(created_at),rank,sequence,entry_id LIMIT ? OFFSET ?",
                              params + values + [limit, offset]).fetchall()
            entries = [self._entry(db, run, row[0], detail=False) for row in rows]
            return {"run": self._public_run(db, run), "versions": versions, "audit": self._audit(db, run),
                    "entries": entries, "pagination": _page(offset, limit, total), "limits": LIMITS}

    def _record(self, db, run, kind, identifier):
        spec = {"task": ("orchestration_tasks", "task_id"), "result": ("orchestration_results", "result_id"),
                "decision": ("orchestration_decisions", "decision_id"), "event": ("orchestration_events", "seq"),
                "label": ("orchestration_label_audit", "event_id"), "legacy_label": ("orchestration_label_proposals", "proposal_id")}
        if kind == "initial":
            row = db.execute("SELECT * FROM orchestration_initials WHERE item_id=? AND initial_id=? AND initial_id=?",
                             (run["item_id"], run["initial_id"], identifier)).fetchone()
        elif kind in spec and self._table(db, spec[kind][0]):
            table, key = spec[kind]
            row = db.execute(f"SELECT * FROM {table} WHERE run_id=? AND {key}=?", (run["run_id"], identifier)).fetchone()
        else:
            row = None
        if row is None:
            raise LookupError("履歴の項目が見つかりません。")
        return row

    @staticmethod
    def _claims(raw):
        claims = raw.get("claims", [])
        if not isinstance(claims, list):
            return []
        return [{"claim_id": _text(c.get("claim_id"), 200), "text": _text(c.get("text")), "kind": _text(c.get("kind"), 50),
                 "evidence_ids": _strings(c.get("evidence_ids"))}
                for c in claims[:50] if isinstance(c, dict)]

    def _entry(self, db, run, entry_id, *, detail):
        kind, separator, identifier = entry_id.partition(":")
        if not separator:
            raise LookupError("履歴の項目が見つかりません。")
        row = self._record(db, run, kind, identifier)
        if kind == "initial":
            data = dict(row)
        else:
            data = json.loads(row["state_json"] if kind in {"task", "result"} else row["payload_json"])
        if kind != "initial":
            self._guard_export_record(db, run, row, data, None)
        identity_key = {"task": "task_id", "result": "result_id", "decision": "decision_id", "label": "event_id", "legacy_label": "proposal_id"}.get(kind)
        if (any(data.get(key, run[key]) != run[key] for key in ("item_id", "run_id"))
                or (identity_key and data.get(identity_key, identifier) != identifier)):
            raise AnalysisContractError("保存された履歴項目の所属情報が一致しません。", code="history_integrity_mismatch")
        value = {key: _value(data.get(key)) for key in (
            "task_id", "result_id", "decision_id", "proposal_id", "annotation_version", "before_annotation_version", "after_annotation_version",
            "utterance_id", "field", "role", "model", "provider", "operation", "disposition", "status", "view_version")}
        value.update(entry_id=entry_id, kind="label" if kind == "legacy_label" else kind,
                     created_at=_text(data.get("received_at") if kind == "result" else data.get("created_at"), 80),
                     summary=_text(data.get("summary")), reason=_text(data.get("reason")),
                     title=_text(data.get("title"), 300), audit_status="recorded", missing_fields=[])
        task = data if kind == "task" else {}
        raw = {}
        if kind == "result":
            candidate = json.loads(row["raw_json"])
            if data.get("raw_hash") and fingerprint(candidate) != data["raw_hash"]:
                raise AnalysisContractError("保存された結果のhashが一致しません。", code="history_integrity_mismatch")
            if not data.get("raw_hash"):
                value["missing_fields"].append("raw_hash")
                value["audit_status"] = "legacy_projection"
            raw = candidate if isinstance(candidate, dict) else {}
            value.update(status=_text(data.get("validation_status"), 100), summary=_text(raw.get("summary")), title="保存された分析結果")
        elif kind == "decision":
            raw = data
            value.update(role="core", operation="decision", title="Coreの統合判断", status="saved")
            if not data.get("task_id"):
                linked = db.execute("SELECT task_id,state_json FROM orchestration_results WHERE run_id=? AND result_id=?",
                                    (run["run_id"], row["result_id"])).fetchone()
                if linked:
                    value["task_id"] = linked["task_id"]
                    value["annotation_version"] = json.loads(linked["state_json"]).get("annotation_version")
        elif kind in {"label", "legacy_label"}:
            value["title"] = "ラベル変更: " + str(data.get("field", "未記録"))
            if kind == "legacy_label":
                value.update(audit_status="legacy_projection", operation=data.get("operation"),
                             annotation_version=data.get("committed_annotation_version", data.get("base_annotation_version")))
                value["missing_fields"] = ["disposition_time", "decision_id", "actor_at_disposition", "intermediate_events"]
            else:
                value["audit_status"] = data.get("audit_status", "recorded")
        elif kind == "event":
            value.update(title=_text(data.get("type"), 200), summary=_text(data.get("message")), role=_text(data.get("from"), 100),
                         operation=_text(data.get("type"), 100), status=_text(data.get("type"), 100))
        elif kind == "initial":
            value.update(title="固定された初期分析・ラベル", role="handler", operation="initial", annotation_version=0,
                         summary="実行開始時の入力・分析結果を固定保存したものです。", initial_id=row["initial_id"], snapshot_hash=row["snapshot_hash"])
        if kind == "task":
            value["reason"] = _text(data.get("intent", {}).get("why_now"))
        if not task and value.get("task_id"):
            linked = db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=? AND task_id=?", (run["run_id"], value["task_id"])).fetchone()
            if linked:
                task = json.loads(linked[0])
        for field in ("role", "model", "provider", "annotation_version"):
            if value.get(field) is None:
                value[field] = _value(task.get(field))
        if value["created_at"] is None:
            value["missing_fields"].append("created_at")
        value["truncated_fields"] = _strings(data.get("truncated_fields")) + [key for key in ("summary", "reason", "title")
            if _over(raw.get(key, data.get(key)), 300 if key == "title" else 2000)]
        if not detail:
            return value
        value["claims"] = self._claims(raw)
        refs = list(data.get("evidence_ids", [])) if isinstance(data.get("evidence_ids"), list) else []
        refs += [r for c in value["claims"] for r in c["evidence_ids"]]
        if kind == "task":
            refs += _strings(task.get("intent", {}).get("evidence_ids"))
        # The allowlist is deliberately shallow: do not recursively mine raw
        # results for strings, hidden reasoning, provider traces or instructions.
        all_refs = list(dict.fromkeys(r for r in refs if isinstance(r, str)))
        value["evidence_ids"] = all_refs[:MAX_REFS]
        if len(all_refs) > MAX_REFS:
            value["truncated_fields"].append("evidence_ids")
        if _over(raw.get("claims"), 50):
            value["truncated_fields"].append("claims")
        if isinstance(raw.get("claims"), list) and any(
                _over(c.get("text"), 2000) or _over(c.get("evidence_ids"), MAX_REFS)
                for c in raw["claims"] if isinstance(c, dict)):
            value["truncated_fields"].append("claim_content")
        value["related_entry_ids"] = [prefix + ":" + value[field] for prefix, field in
            (("task", "task_id"), ("result", "result_id"), ("decision", "decision_id")) if value.get(field) and prefix != kind]
        value["related_entry_ids"] = [ref for ref in value["related_entry_ids"] if self._exists(db, run, ref)]
        if kind in {"label", "legacy_label"}:
            for key in ("before_value", "after_value", "before_present", "after_present", "proposed_value", "stated_old_value", "tombstone", "base_annotation_version"):
                value[key] = _value(data.get(key))
                if (_over(data.get(key), 50 if isinstance(data.get(key), list) else 2000)
                        or (isinstance(data.get(key), list) and any(_over(v, 2000) for v in data[key]))):
                    value["truncated_fields"].append(key)
            if kind == "legacy_label":
                # These are the proposal's stated values, not reconstructed
                # applied changes. Never substitute current mutable status time.
                value.update(before_value=None, stated_old_value=_value(data.get("old_value")), proposed_value=_value(data.get("new_value")),
                             after_value=None, before_present=None, after_present=None, tombstone=None)
                value["missing_fields"] += ["applied_before_value", "applied_after_value"]
            for key in ("proposal_task_id", "proposal_result_id"):
                value[key] = _text(data.get(key), 200)
                prefix = "task" if key == "proposal_task_id" else "result"
                if value[key] and self._exists(db, run, prefix + ":" + value[key]):
                    value["related_entry_ids"].append(prefix + ":" + value[key])
        if kind == "initial":
            snapshot = self._snapshot(db, run)
            value["source_count"] = len(snapshot.get("evidence", [])) if snapshot else None
            value["snapshot_status"] = row["status"]
        value["related_entry_ids"] = list(dict.fromkeys(value["related_entry_ids"]))[:MAX_REFS]
        return value

    def _exists(self, db, run, ref):
        try:
            kind, identifier = ref.split(":", 1)
            self._record(db, run, kind, identifier)
            return True
        except (LookupError, ValueError):
            return False

    def _snapshot(self, db, run):
        row = db.execute("SELECT snapshot_json,snapshot_hash,status FROM orchestration_initials WHERE item_id=? AND initial_id=?",
                         (run["item_id"], run["initial_id"])).fetchone()
        if row is None or not row["snapshot_json"] or row["status"] != "ready":
            return None
        snapshot = json.loads(row["snapshot_json"])
        if not row["snapshot_hash"] or fingerprint(snapshot) != row["snapshot_hash"] or snapshot.get("input_hash") != run.get("input_hash"):
            raise AnalysisContractError("固定分析のhashが一致しません。", code="initial_hash_mismatch")
        return snapshot

    @staticmethod
    def _source(evidence, *, text=False):
        keys = ["evidence_id", "utterance_id", "speaker", "start", "end", "excluded", "source_hash", "dataset_version"]
        source = {key: _value(evidence.get(key)) for key in keys}
        if text:
            # Literal original text is allowed only on this explicit source route.
            source["text"] = _text(evidence.get("text"), 100000)
            source["text_truncated"] = isinstance(evidence.get("text"), str) and len(evidence["text"]) > 100000
        return source

    def entry(self, item_id, run_id, entry_id, *, annotation_version=None, evidence_offset=0, evidence_limit=30):
        offset = _integer(evidence_offset, 0, field="evidence_offset")
        limit = _integer(evidence_limit, 30, 1, MAX_PAGE, field="evidence_limit")
        with self._read(item_id) as db:
            run = self._run(db, item_id, run_id)
            self._versions(db, run, annotation_version)
            entry = self._entry(db, run, entry_id, detail=True)
            snapshot = self._snapshot(db, run)
            evidence = snapshot.get("evidence", []) if snapshot else []
            requested = set(entry["evidence_ids"])
            matches = [e for e in evidence if e.get("evidence_id") in requested]
            if entry["kind"] == "initial":
                matches = evidence
            entry["missing_evidence_ids"] = sorted(requested - {e.get("evidence_id") for e in matches})
            return {"entry": entry, "evidence": [self._source(e) for e in matches[offset:offset+limit]],
                    "evidence_total": len(matches), "evidence_has_more": offset + limit < len(matches),
                    "evidence_pagination": _page(offset, limit, len(matches)), "limits": LIMITS}

    def source(self, item_id, run_id, utterance_id, *, annotation_version=None):
        with self._read(item_id) as db:
            run = self._run(db, item_id, run_id)
            versions = self._versions(db, run, annotation_version)
            snapshot = self._snapshot(db, run)
            evidence = next((e for e in (snapshot or {}).get("evidence", []) if e.get("utterance_id") == utterance_id), None)
            if evidence is None:
                raise LookupError("固定された発話が見つかりません。")
            labels, truncated, loaded = {}, [], {}
            for name in ("initial", "selected", "latest"):
                version = versions[name]
                if version not in loaded:
                    row = db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                                     (run_id, version)).fetchone() if version is not None else None
                    loaded[version] = json.loads(row[0]).get(utterance_id) if row else None
                original = loaded[version]
                labels[name] = _labels(original)
                if isinstance(original, dict) and any(
                        _over(v, 50 if isinstance(v, list) else 2000)
                        or (isinstance(v, list) and any(_over(element, 2000) for element in v))
                        for key, v in original.items() if key in LABEL_FIELDS):
                    truncated.append(name)
            return {"source": self._source(evidence, text=True), "labels": labels, "truncated_fields": truncated, "limits": LIMITS,
                    "versions": {key: versions[key] for key in ("initial", "selected", "latest")},
                    "provenance": {"item_id": item_id, "run_id": run_id, "initial_id": run["initial_id"],
                                   "input_hash": run.get("input_hash"), "snapshot_hash": fingerprint(snapshot)},
                    "audit": self._audit(db, run)}

    def _guard_export_record(self, db, run, row, value, evidence_ids):
        """Validate recorded IDs against relational ownership; missing is not guessed."""
        if not isinstance(value, dict):
            raise AnalysisContractError("保存された履歴項目の形式が一致しません。", code="history_integrity_mismatch")
        expected = {"item_id": run["item_id"], "run_id": run["run_id"], "dataset_version": run.get("input_hash")}
        for key in ("task_id", "result_id", "decision_id", "proposal_id", "event_id", "issue_id", "response_id", "usage_id"):
            if key in row.keys():
                expected[key] = row[key]
        if any(key in value and value[key] is not None and value[key] != target for key, target in expected.items()):
            raise AnalysisContractError("保存された履歴項目の所属情報が一致しません。", code="history_integrity_mismatch")
        tables = {"task_id": "orchestration_tasks", "result_id": "orchestration_results",
                  "decision_id": "orchestration_decisions", "proposal_id": "orchestration_label_proposals",
                  "issue_id": "orchestration_issues"}
        missing = []
        references = list(tables.items()) + [("proposal_task_id", "orchestration_tasks"), ("proposal_result_id", "orchestration_results")]
        for key, table in references:
            identifier = value.get(key)
            if identifier in (None, "") or not self._table(db, table):
                continue
            if not isinstance(identifier, str):
                raise AnalysisContractError("保存された参照IDの形式が一致しません。", code="history_integrity_mismatch")
            target_key = key.removeprefix("proposal_") if key in {"proposal_task_id", "proposal_result_id"} else key
            linked = db.execute(f"SELECT run_id FROM {table} WHERE {target_key}=?", (identifier,)).fetchone()
            if linked is not None and linked[0] != run["run_id"]:
                raise AnalysisContractError("別の実行の記録を参照しています。", code="history_integrity_mismatch")
            if linked is None:
                missing.append(key)
        if missing:
            value["missing_reference_fields"] = missing
        refs = value.get("evidence_ids")
        if evidence_ids is not None and isinstance(refs, list):
            missing_evidence = [ref for ref in refs if isinstance(ref, str) and ref not in evidence_ids]
            if missing_evidence:
                # Preserve legacy evidence gaps, never join a different snapshot.
                value["missing_evidence_ids"] = missing_evidence

    def saved_export(self, item_id, run_id):
        """Internal saved-run input for deterministic exports, never a model call.

        Explicit size bounds fail rather than silently producing an incomplete
        presentation. The browser viewer itself never serializes this raw DTO.
        """
        with self._read(item_id) as db:
            run = self._run(db, item_id, run_id)
            initial_row = db.execute("SELECT initial_id,snapshot_hash,length(CAST(snapshot_json AS BLOB)) FROM orchestration_initials WHERE item_id=? AND initial_id=?",
                                     (item_id, run["initial_id"])).fetchone()
            specs = {
                "tasks": ("orchestration_tasks", "state_json"),
                "events": ("orchestration_events", "payload_json"),
                "results": ("orchestration_results", "state_json"),
                "decisions": ("orchestration_decisions", "payload_json"),
                "issues": ("orchestration_issues", "payload_json"),
                "critique_responses": ("orchestration_responses", "payload_json"),
                "label_proposals": ("orchestration_label_proposals", "payload_json"),
                "label_audit": ("orchestration_label_audit", "payload_json"),
                "label_versions": ("orchestration_label_versions", "payload_json"),
                "usage_records": ("orchestration_usage", "payload_json"),
            }
            count, size = 0, (initial_row[2] or 0) if initial_row else 0
            available = {}
            for key, (table, column) in specs.items():
                if not self._table(db, table):
                    continue
                available[key] = (table, column)
                extra = "+length(CAST(raw_json AS BLOB))" if table == "orchestration_results" else ""
                row = db.execute(f"SELECT count(*),coalesce(sum(length(CAST({column} AS BLOB)){extra}),0) FROM {table} WHERE run_id=?", (run_id,)).fetchone()
                count, size = count + row[0], size + row[1]
            if count > 2000 or size > 32 * 1024 * 1024:
                raise AnalysisContractError("保存履歴が書き出し上限（2000記録・32MiB）を超えています。", code="history_export_limit")
            # Check SQL byte counts before parsing any large snapshot/result.
            snapshot = self._snapshot(db, run)
            evidence_ids = {e.get("evidence_id") for e in snapshot.get("evidence", [])} if snapshot else None
            if snapshot:
                for evidence in snapshot.get("evidence", []):
                    if (evidence.get("dataset_version", run["input_hash"]) != run["input_hash"]
                            or (evidence.get("source_hash") and fingerprint(evidence.get("text", "")) != evidence["source_hash"])):
                        raise AnalysisContractError("固定発話の版・hashが一致しません。", code="history_integrity_mismatch")
            data = {key: [] for key in specs}
            raw_results = []
            for key, (table, column) in available.items():
                for row in db.execute(f"SELECT * FROM {table} WHERE run_id=? ORDER BY rowid", (run_id,)):
                    value = json.loads(row[column])
                    if key != "label_versions":
                        self._guard_export_record(db, run, row, value, evidence_ids)
                    if key == "label_versions":
                        value = {"annotation_version": row["annotation_version"], "labels": value}
                    elif key == "usage_records":
                        value = {"usage_id": row["usage_id"], "task_id": row["task_id"], "payload": value}
                    elif key == "results":
                        raw = json.loads(row["raw_json"])
                        if value.get("raw_hash") and fingerprint(raw) != value["raw_hash"]:
                            raise AnalysisContractError("保存された結果のhashが一致しません。", code="history_integrity_mismatch")
                        raw_results.append({**value, "raw": raw})
                    elif key == "events":
                        value = {"seq": row["seq"], **value}
                    data[key].append(value)
            public_run = {**run, **{key: data[key] for key in ("tasks", "events", "results", "issues", "critique_responses", "label_proposals")}}
            return {"run": public_run,
                    "initial": {"initial_id": run["initial_id"], "hash": initial_row["snapshot_hash"] if initial_row else None, "snapshot": snapshot},
                    "raw_results": raw_results, **{key: data[key] for key in ("decisions", "label_versions", "usage_records", "label_audit")}}
