"""Notation's explicit SQLite read/save boundaries, reusing transcript history."""
from __future__ import annotations

from copy import deepcopy
import json
import uuid
import sqlite3

from .. import transcript_preparation as history
from . import notation, vocabulary_store


def protected_ids(changes):
    ids = set()
    for change in changes:
        if change["origin"] != "researcher":
            continue
        for op in json.loads(change["ops_json"]):
            if op["op"] == "segment_set" and op["key"] == "text":
                ids.add(op["target"])
            elif op["op"] == "segment_add":
                ids.add(op["id"])
            elif op["op"] == "replace" and op["key"] == "segments":
                ids.update(s["id"] for s in op["value"])
    return ids


def researcher_current_ids(changes):
    """Cross-conversation evidence must still have a researcher as last writer."""
    owners = {}
    for change in changes:
        for op in json.loads(change["ops_json"]):
            if op["op"] == "segment_set" and op["key"] == "text":
                owners[op["target"]] = change["origin"]
            elif op["op"] == "segment_add":
                owners[op["id"]] = change["origin"]
            elif op["op"] == "replace" and op["key"] == "segments":
                owners = {s["id"]: change["origin"] for s in op["value"]}
            elif op["op"] == "segment_delete":
                owners.pop(op["id"], None)
    return {key for key, owner in owners.items() if owner == "researcher"}


def prepare(connection, segments, *, item_id=None, analyze=notation.morphology):
    changes = history._changes(connection, item_id) if item_id else []
    protected = protected_ids(changes)
    if item_id:
        row = connection.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
        if row is None or history.current_version(connection, row) is None:
            raise ValueError("差分履歴へ固定されていない会話です。先に通常保存してください。")
        current = {s["id"]: s["text"] for s in history.source(row)["segments"]}
        # Workbench input edits are researcher data before they are committed.
        protected.update(s["id"] for s in segments if current.get(s["id"]) != s["text"])
    source_refs = {"speaker_registry": {}, "researcher_history": {}}
    registry = []
    for record in connection.execute("SELECT id, display_name, organization, department FROM speaker_registry WHERE active=1"):
        for field in ("display_name", "organization", "department"):
            value = record[field]
            if value:
                registry.append(value)
                source_refs["speaker_registry"].setdefault(value, []).append(
                    {"speaker_id": record["id"], "field": field, "value": value})
    confirmed = []
    other_ids = [r[0] for r in connection.execute(
        "SELECT DISTINCT item_id FROM transcript_changes WHERE origin='researcher' AND item_id<>?", (item_id or "",))]
    for other_id in other_ids:
        versions = history.read_versions(connection, other_id, include_source=True)
        selected = researcher_current_ids(history._changes(connection, other_id))
        if versions:
            # Only currently researcher-fixed segments, with a verified hash chain.
            latest = versions[-1]["source"]["segments"]
            other_tokens, _ = analyze([s for s in latest if s["id"] in selected])
            confirmed.extend(t["surface"] for t in other_tokens)
            for token in other_tokens:
                source_refs["researcher_history"].setdefault(token["surface"], []).append(
                    {"item_id": other_id, "input_version": versions[-1]["version"],
                     "source_hash": versions[-1]["source_hash"], "segment_id": token.get("segment_id")})
    dictionary, terms = vocabulary_store.variants(connection), vocabulary_store.terms(connection)
    plan = notation.detect(segments, dictionary=dictionary, terms=terms, registry=registry,
                           confirmed=confirmed, protected=protected, analyze=analyze)
    for group in plan["groups"]:
        label, canonical = group["source"], group["canonical"]
        if label in {"dictionary", "vocabulary"}:
            entity = "notation_variants" if label == "dictionary" else "vocabulary_terms"
            seq = connection.execute("SELECT MAX(seq) FROM change_log WHERE entity=? AND entity_id='global'", (entity,)).fetchone()[0]
            group["source_refs"] = [{"entity": entity, "seq": seq,
                                     "source_hash": history.digest(dictionary if label == "dictionary" else list(terms)),
                                     "canonical": canonical}]
        else:
            group["source_refs"] = source_refs.get(label, {}).get(canonical, [])
    return plan


def latest_review(connection, item_id):
    base = history._base(connection, item_id)
    if base is None:
        return None
    value = json.loads(base["base_json"])
    if history.digest(value) != base["base_hash"]:
        raise ValueError("表記履歴の起点が不正です。")
    review = None
    for seq, change in enumerate(history._changes(connection, item_id), 1):
        if change["seq"] != seq:
            raise ValueError("表記履歴の順番が不正です。")
        after = history.reconstruct(value, [change])
        metadata = json.loads(change["metadata_json"])
        if change["process"] == "notation":
            review = {"seq": seq, "run_id": metadata.get("run_id"),
                      "groups": metadata["notation"]["groups"], "before": value["segments"],
                      "expected": after["segments"], "overrides": {}}
        elif change["process"] == "notation_review" and review and metadata.get("notation_seq") == review["seq"]:
            review["expected"] = after["segments"]
            review["overrides"] = metadata["overrides"]
        value = after
    return review


class NotationWorkflows:
    def __init__(self, dependencies):
        self.d = dependencies

    def finish(self, segments, provider, api_key, model, check, usage_callback=None,
               *, base_url="", ai_efforts=None, item_id=None):
        with self.d.database_connection() as db:
            plan = prepare(db, segments, item_id=item_id)
        call = None
        if provider in {"openai", "google", "lmstudio"}:
            call = lambda system, prompt, name, schema: self.d.call_ai_json(
                provider, api_key, model, system, prompt, name, schema, check,
                usage_callback, base_url, ai_efforts=ai_efforts)
        return notation.resolve(segments, plan, call=call, check=check)

    def preview(self, item_id, provider):
        if provider not in {"none", "openai", "google", "lmstudio"}:
            raise ValueError("表記統一の送信先が不正です。")
        row = self.d.library_row(item_id)
        if row is None:
            raise LookupError("会話が見つかりません。")
        with self.d.database_connection() as db:
            plan = prepare(db, self.d.row_segments(row), item_id=item_id)
        model, destination = "", "送信なし（確定済みの表記だけ）"
        if provider != "none":
            config = self.d.load_token_config()
            _, model = self.d.configured_ai_credentials(config, provider)
            destination = {"openai": "OpenAI", "google": "Google Gemini", "lmstudio": "LM Studio"}[provider]
            if provider == "lmstudio":
                # Match the actual configured endpoint, including remote LM Studio.
                destination += " / " + config.lmstudio_base_url
        result = {"plan": plan, "revision_count": row["revision_count"], "source_hash": history.digest(history.source(row)),
                  "provider": provider, "model": model, "destination": destination,
                  "estimated_input_tokens": notation.token_estimate(plan) if provider != "none" else 0}
        result["preview_hash"] = history.digest(result)
        return result

    def execute(self, item_id, payload):
        preview = self.preview(item_id, payload.get("provider", "none"))
        if payload.get("preview_hash") != preview["preview_hash"]:
            raise ValueError("会話・辞書・送信先が変わりました。候補を再表示してください。")
        row = self.d.library_row(item_id)
        segments = self.d.row_segments(row)
        usage = {}
        call = None
        provider = preview["provider"]
        if provider != "none":
            config = self.d.load_token_config()
            key, model = self.d.configured_ai_credentials(config, provider)
            if not model or provider != "lmstudio" and not key:
                raise ValueError("送信先のモデルとAPIキーをアプリで設定してください。")
            def record(sample):
                nonlocal usage
                usage = self.d.merge_ai_usage(usage, sample)
            call = lambda system, prompt, name, schema: self.d.call_ai_json(
                provider, key, model, system, prompt, name, schema, lambda: None,
                record, config.lmstudio_base_url if provider == "lmstudio" else "")
        resolved = notation.resolve(segments, preview["plan"], call=call)
        run_id = "notation-" + uuid.uuid4().hex
        with self.d.library_write_lock:
            latest = self.d.library_row(item_id)
            if latest is None or history.digest(history.source(latest)) != preview["source_hash"] or latest["revision_count"] != preview["revision_count"]:
                raise ValueError("処理中に会話が変わりました。反映を停止しました。")
            result = self.d.update_library_item_locked(item_id,
                {"revision_count": preview["revision_count"], "segments": resolved["segments"],
                 "speaker_names": json.loads(latest["speaker_names_json"] or "{}")},
                record_training=False, ai_usage_override=self.d.merge_ai_usage(json.loads(latest["ai_usage_json"] or "{}"), usage),
                finishing_history=[{"segments": resolved["segments"], "origin": "ai", "process": "notation",
                    "speaker_names": json.loads(latest["speaker_names_json"] or "{}"),
                    "speaker_profiles": json.loads(latest["speaker_profiles_json"] or "{}"),
                    "process_version": notation.NOTATION_VERSION,
                    "metadata": {"run_id": run_id, "provider": provider, "model": preview["model"],
                                 "notation": resolved["notation"]}}])
            try:
                self.d.archive_ai_finishing(self.d.library_row(item_id), segments, {"notation": "completed"},
                                           provider, preview["model"], usage, request_id=run_id)
            except (OSError, ValueError, TypeError, sqlite3.Error):
                result["notation_archive_warning"] = "本文と差分は保存済みです。分析履歴の書き出しは未完了です。"
        return result

    def review(self, item_id):
        row = self.d.library_row(item_id)
        if row is None:
            raise LookupError("会話が見つかりません。")
        with self.d.database_connection() as db:
            review = latest_review(db, item_id)
        return {"revision_count": row["revision_count"], "seq": review["seq"] if review else None,
                "groups": review["groups"] if review else [], "overrides": review["overrides"] if review else {}}

    def change(self, item_id, payload):
        action = payload.get("action")
        if action not in {"cancel", "change", "register", "delete_dictionary"}:
            raise ValueError("表記確認の操作が不正です。")
        with self.d.library_write_lock:
            row = self.d.library_row(item_id)
            if row is None:
                raise LookupError("会話が見つかりません。")
            if payload.get("revision_count") != row["revision_count"]:
                raise ValueError("会話が更新されています。再表示してください。")
            with self.d.database_connection() as db:
                review = latest_review(db, item_id)
            if review is None or payload.get("seq") != review["seq"]:
                raise ValueError("表記確認の対象版が変わりました。")
            group = next((g for g in review["groups"] if g["id"] == payload.get("group_id")), None)
            if group is None:
                raise ValueError("表記群が見つかりません。")
            choice = payload.get("canonical")
            if action != "cancel" and action != "delete_dictionary" and (not isinstance(choice, str) or not choice.strip() or len(choice) > 80):
                raise ValueError("正しい表記は1〜80文字で指定してください。")
            if action in {"register", "delete_dictionary"}:
                changes = {v["term"]: choice if action == "register" else None for v in group["variants"]}
                self.d.save_custom_vocabulary(self.d.load_custom_vocabulary(), notation_changes=changes)
                return {"ok": True, "message": "表記辞書と変更履歴を保存しました。"}
            current = self.d.row_segments(row)
            expected = {s["id"]: s["text"] for s in review["expected"]}
            impacted = {o["segment_id"] for g in review["groups"] for o in g["occurrences"]}
            if any(s["text"] != expected.get(s["id"]) for s in current if s["id"] in impacted) or not impacted <= {s["id"] for s in current}:
                raise ValueError("表記統一後に対象の発話が編集されています。本文を保護して停止しました。")
            overrides = {**review["overrides"], group["id"]: None if action == "cancel" else choice}
            revised = {s["id"]: s["text"] for s in notation.apply_choices(review["before"], review["groups"], overrides)}
            segments = deepcopy(current)
            for s in segments:
                if s["id"] in impacted:
                    s["text"] = revised[s["id"]]
            return self.d.update_library_item_locked(item_id,
                {"revision_count": row["revision_count"], "segments": segments,
                 "speaker_names": json.loads(row["speaker_names_json"] or "{}")}, record_training=False,
                finishing_history=[{"segments": segments, "origin": "researcher", "process": "notation_review",
                    "speaker_names": json.loads(row["speaker_names_json"] or "{}"),
                    "speaker_profiles": json.loads(row["speaker_profiles_json"] or "{}"),
                    "process_version": notation.NOTATION_VERSION,
                    "metadata": {"notation_seq": review["seq"], "group_id": group["id"], "action": action, "overrides": overrides}}])
