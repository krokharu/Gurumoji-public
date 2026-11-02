"""Background AI-insight and Transformer analysis jobs.

Each job is split into a runner (the worker-thread body) and its start/cancel
commands. app.py builds both through the make_* factories and passes the
shared locks, cancel events and storage functions."""

from __future__ import annotations

import json
import os
import re
import threading
from typing import Any, Callable

from .. import method_experts
from ..ai_effort import normalize_efforts
from ..analysis_insights import (
    INSIGHT_VERSION,
    create_ai_insights,
    included_segments,
    input_fingerprint,
)
from ..handlers.analysis_commands import AnalysisCommandRequestError
from ..text_utils import json_load, utc_now_iso
from ..transformer_analysis import (
    DEFAULT_MANUAL_MIN_SIMILARITY,
    DEFAULT_MODEL as DEFAULT_TRANSFORMER_MODEL,
    MAX_MANUAL_TOPICS,
    TOPIC_MODES,
    saved_embeddings as saved_transformer_embeddings,
    transformer_input_fingerprint,
    transformer_source_provenance,
)
from .ai.settings import local_llm_model_required_message
from . import segment_embeddings


class InsightCancelled(RuntimeError):
    pass


class TransformerAnalysisCancelled(RuntimeError):
    pass


def make_insight_jobs(
    *,
    AnalysisConflictError: Any,
    archive_group_analysis: Any,
    call_ai_json: Any,
    database_connection: Any,
    group_analysis_for_row: Any,
    insight_cancel_events: Any,
    insight_jobs_lock: Any,
    library_row: Any,
    library_write_lock: Any,
    merge_ai_usage: Any,
    public_diagnostic_text: Any,
) -> tuple[Callable[..., Any], ...]:
    def public_insight_request(row) -> dict[str, Any] | None:
        if row is None:
            return None
        return {**{key: row[key] for key in (
            "request_id", "item_id", "provider", "model", "status", "progress", "message",
            "created_at", "updated_at", "source_revision", "analysis_revision",
        )}, "usage": json_load(row["usage_json"], {})}

    def update_insight_request(request_id: str, status: str, progress: int, message: str,
                               usage: dict[str, Any]) -> None:
        with database_connection() as connection:
            connection.execute("""
                UPDATE analysis_insight_requests SET status=?, progress=?, message=?, usage_json=?, updated_at=?
                WHERE request_id=?
            """, (status, progress, message, json.dumps(usage, ensure_ascii=False), utc_now_iso(), request_id))

    def run_analysis_insight_job(request_id: str, analysis: dict, provider: str, api_key: str,
                                 model: str, cancel_event: threading.Event, base_url: str = "",
                                 app_url: str = "http://127.0.0.1:7860",
                                 ai_efforts: dict | None = None) -> None:
        usage: dict[str, Any] = {}
        progress_value = 0
        message = "発話の確認を準備しています。"

        def cancelled():
            if cancel_event.is_set():
                raise InsightCancelled("AI見解の生成を中止しました。")

        def progress(value, text):
            nonlocal progress_value, message
            with insight_jobs_lock:
                cancelled()
                progress_value, message = value, text
                update_insight_request(request_id, "running", value, text, usage)

        def record_usage(sample):
            nonlocal usage
            usage = merge_ai_usage(usage, sample)
            progress(progress_value, message)

        def call(system, prompt, schema):
            return call_ai_json(provider, api_key, model, system, prompt, "conversation_insights",
                                schema, cancelled, record_usage, base_url, ai_efforts=ai_efforts)

        try:
            expert = method_experts.ai_context(analysis.get("experts"))
            findings = create_ai_insights(analysis, call, progress, cancelled, expert=expert)
            with insight_jobs_lock, library_write_lock:
                cancelled()
                latest = library_row(analysis["item"]["id"])
                if latest is None:
                    raise AnalysisConflictError("対象の会話が削除されたため見解を保存しませんでした。")
                current = group_analysis_for_row(latest)
                fingerprint = input_fingerprint(analysis)
                if current["insights"]["fingerprint"] != fingerprint:
                    raise AnalysisConflictError("生成中に元データまたは分析条件が更新されました。再生成してください。")
                saved = {"findings": findings, "provider": provider, "model": model,
                         "generated_at": utc_now_iso(), "fingerprint": fingerprint,
                         "algorithm_version": INSIGHT_VERSION, "request_id": request_id,
                         "source_revision": analysis["item"]["revision_count"],
                         "analysis_revision": analysis["item"]["analysis_revision"], "usage": usage,
                         **({"expert": {key: expert[key] for key in
                                        ("expert_id", "definition_version", "knowledge_hash", "fingerprint")}}
                            if expert else {}),
                         "evidence": {s["id"]: {k: s.get(k) for k in
                                      ("id", "speaker", "speaker_name", "start", "end", "text")}
                                      for s in included_segments(analysis)
                                      if any(s["id"] in f["segment_ids"] for f in findings)}}
                full_analysis = group_analysis_for_row(latest, include_research_rows=True)
                full_analysis["insights"].update({"ai": saved, "stale": False})
                archived = archive_group_analysis(latest, full_analysis, "insights-" + request_id,
                                                   kind="ai_insights", app_url=app_url, check_cancelled=cancelled)
                saved["archive_id"] = archived["id"]
                saved["vault_status"] = archived["vault_status"]
                with database_connection() as connection:
                    cursor = connection.execute("""
                        UPDATE library_items SET analysis_insights_json=?
                        WHERE id=? AND revision_count=? AND analysis_revision=?
                    """, (json.dumps(saved, ensure_ascii=False), latest["id"],
                          analysis["item"]["revision_count"], analysis["item"]["analysis_revision"]))
                    if cursor.rowcount != 1:
                        raise AnalysisConflictError("保存直前にデータが更新されました。再生成してください。")
                    connection.execute("""
                        UPDATE analysis_insight_requests SET status='completed', progress=100,
                            message='AI見解を保存しました。', usage_json=?, updated_at=? WHERE request_id=?
                    """, (json.dumps(usage, ensure_ascii=False), utc_now_iso(), request_id))
        except InsightCancelled as exc:
            update_insight_request(request_id, "cancelled", progress_value, str(exc), usage)
        except AnalysisConflictError as exc:
            update_insight_request(request_id, "stale", progress_value, str(exc), usage)
        except Exception as exc:
            update_insight_request(request_id, "failed", progress_value,
                                   "AI見解を生成できませんでした: "
                                   + public_diagnostic_text(str(exc), reveal_local_paths=False)[:700], usage)
        finally:
            with insight_jobs_lock:
                insight_cancel_events.pop(request_id, None)

    return (public_insight_request, update_insight_request, run_analysis_insight_job)


def make_insight_commands(
    *,
    configured_ai_credentials: Any,
    database_connection: Any,
    group_analysis_for_row: Any,
    insight_cancel_events: Any,
    insight_jobs_lock: Any,
    library_row: Any,
    load_token_config: Any,
    public_insight_request: Any,
    run_analysis_insight_job: Any,
    update_insight_request: Any,
) -> tuple[Callable[..., Any], ...]:
    def start_analysis_insights_command(
        item_id: str, payload: dict[str, Any], *, app_url: str
    ) -> tuple[dict[str, Any], int]:
        provider, request_id = payload.get("provider"), payload.get("request_id")
        with insight_jobs_lock:
            row = library_row(item_id)
            if row is None:
                raise AnalysisCommandRequestError(
                    "処理済みデータが見つかりません。", 404
                )
            with database_connection() as connection:
                previous = connection.execute("SELECT * FROM analysis_insight_requests WHERE request_id=?",
                                              (request_id,)).fetchone()
                if previous:
                    if any(previous[k] != v for k, v in {
                        "item_id": item_id, "provider": provider,
                        "source_revision": payload["source_revision"],
                        "analysis_revision": payload["analysis_revision"],
                    }.items()):
                        raise AnalysisCommandRequestError(
                            "リクエストIDが別の指定に使われています。", 409
                        )
                    return {"run": public_insight_request(previous)}, 200
                active = connection.execute("""
                    SELECT * FROM analysis_insight_requests WHERE item_id=?
                        AND status IN ('queued','running','cancelling') LIMIT 1
                """, (item_id,)).fetchone()
                if active:
                    raise AnalysisCommandRequestError(
                        "この会話のAI見解は生成中です。",
                        409,
                        details={"run": public_insight_request(active)},
                    )
            if payload["source_revision"] != int(row["revision_count"]) or payload["analysis_revision"] != int(row["analysis_revision"]):
                raise AnalysisCommandRequestError(
                    "データが更新されています。分析を再読み込みしてください。",
                    409,
                    details={"conflict": True},
                )
            analysis = group_analysis_for_row(row)
            blocked = method_experts.ai_block_reason(analysis.get("experts"))
            if blocked:
                raise AnalysisCommandRequestError(
                    blocked, 409, details={"expert_blocked": True}
                )
            if not included_segments(analysis):
                raise AnalysisCommandRequestError(
                    "見解の生成に利用できる発話がありません。", 400
                )
            try:
                ai_efforts = normalize_efforts(payload.get("ai_efforts"))
                config = load_token_config()
                api_key, model = configured_ai_credentials(config, provider)
                base_url = config.lmstudio_base_url if provider == "lmstudio" else ""
                if provider != "lmstudio" and not api_key:
                    raise ValueError("tokens.jsonに選択したプロバイダーのAPIキーを設定してください。")
                if not model:
                    raise ValueError(local_llm_model_required_message())
            except (ValueError, RuntimeError) as exc:
                raise AnalysisCommandRequestError(str(exc), 400) from exc
            now = utc_now_iso()
            with database_connection() as connection:
                connection.execute("""
                    INSERT INTO analysis_insight_requests
                    (request_id,item_id,source_revision,analysis_revision,fingerprint,provider,model,status,message,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,'queued','生成を準備しています。',?,?)
                """, (request_id, item_id, payload["source_revision"], payload["analysis_revision"],
                      analysis["insights"]["fingerprint"], provider, model, now, now))
                run = connection.execute("SELECT * FROM analysis_insight_requests WHERE request_id=?", (request_id,)).fetchone()
            event = threading.Event()
            insight_cancel_events[request_id] = event
            try:
                threading.Thread(target=run_analysis_insight_job,
                                 args=(request_id, analysis, provider, api_key, model, event, base_url,
                                       app_url, ai_efforts),
                                 name=f"insights-{item_id}", daemon=True).start()
            except RuntimeError:
                insight_cancel_events.pop(request_id, None)
                update_insight_request(request_id, "failed", 0, "生成処理を開始できませんでした。", {})
                raise AnalysisCommandRequestError(
                    "生成処理を開始できませんでした。", 503
                )
            return {"run": public_insight_request(run)}, 202

    def cancel_analysis_insights_command(
        item_id: str, request_id: str
    ) -> dict[str, Any]:
        with insight_jobs_lock, database_connection() as connection:
            row = connection.execute("SELECT * FROM analysis_insight_requests WHERE item_id=? AND request_id=?",
                                     (item_id, request_id)).fetchone()
            if row is None:
                raise AnalysisCommandRequestError("生成処理が見つかりません。", 404)
            if row["status"] in {"queued", "running", "cancelling"}:
                event = insight_cancel_events.get(row["request_id"])
                if event:
                    event.set()
                connection.execute("UPDATE analysis_insight_requests SET status='cancelling', message='中止しています。' WHERE request_id=?",
                                   (row["request_id"],))
            return {"ok": True}

    return (start_analysis_insights_command, cancel_analysis_insights_command)


def make_transformer_jobs(
    *,
    AnalysisConflictError: Any,
    analyze_transformer_topics: Any,
    archive_group_analysis: Any,
    build_research_analysis: Any,
    database_connection: Any,
    group_analysis_for_row: Any,
    library_row: Any,
    library_write_lock: Any,
    public_diagnostic_text: Any,
    transformer_cancel_events: Any,
    transformer_jobs_lock: Any,
) -> tuple[Callable[..., Any], ...]:
    def public_transformer_request(row) -> dict[str, Any] | None:
        if row is None:
            return None
        keys = row.keys()
        return {
            **{key: row[key] for key in (
                "request_id", "item_id", "model", "max_topics", "min_topic_size", "topic_count",
                "status", "progress", "message", "created_at", "updated_at",
                "source_revision", "analysis_revision",
            )},
            "mode": str(row["mode"]) if "mode" in keys else "auto",
            "min_similarity": float(row["min_similarity"]) if "min_similarity" in keys else 0.0,
        }

    def update_transformer_request(request_id: str, status: str, progress: int, message: str) -> None:
        with database_connection() as connection:
            connection.execute("""
                UPDATE transformer_analysis_requests
                SET status=?, progress=?, message=?, updated_at=? WHERE request_id=?
            """, (status, progress, message, utc_now_iso(), request_id))

    def run_transformer_analysis_job(
        request_id: str, analysis: dict, model: str, max_topics: int,
        min_topic_size: int, topic_count: int, cancel_event: threading.Event,
        app_url: str = "http://127.0.0.1:7860", mode: str = "auto",
        manual_topics: list[dict] | None = None,
        min_similarity: float = DEFAULT_MANUAL_MIN_SIMILARITY,
        saved_result: dict | None = None,
    ) -> None:
        progress_value = 0

        def cancelled() -> None:
            if cancel_event.is_set():
                raise TransformerAnalysisCancelled("Transformer分析を中止しました。")

        def progress(value: int, message: str) -> None:
            nonlocal progress_value
            with transformer_jobs_lock:
                cancelled()
                progress_value = max(0, min(99, int(value)))
                update_transformer_request(request_id, "running", progress_value, message)

        try:
            progress(2, "日本語の解析結果を準備しています。")
            research = build_research_analysis(analysis)
            reuse = (saved_transformer_embeddings(saved_result, analysis, model=model)
                     if mode in {"candidate", "manual"} else None)
            embeddings, embedding_segment_ids, engine = reuse if reuse else (None, None, None)
            saved_quality = (saved_result or {}).get("quality")
            previous_candidates = (saved_quality.get("cluster_candidates")
                                   if isinstance(saved_quality, dict) else None)
            if reuse:
                progress(60, "保存済みの意味ベクトルを再利用します。")
            elif mode != "auto":
                progress(5, "保存済みの意味ベクトルがないため、発話を意味ベクトル化します。")
            result = analyze_transformer_topics(
                analysis, research["linguistics"]["morphemes"], model_name=model,
                max_topics=max_topics, min_topic_size=min_topic_size,
                topic_count=topic_count or None, mode=mode,
                manual_topics=manual_topics or [], manual_min_similarity=min_similarity,
                embeddings=embeddings, embedding_segment_ids=embedding_segment_ids, engine=engine,
                revision=str((engine or {}).get("revision") or ""),
                previous_candidates=previous_candidates,
                progress=progress, check_cancelled=cancelled,
            )
            result.update({
                "generated_at": utc_now_iso(), "request_id": request_id,
                "source_revision": analysis["item"]["revision_count"],
                "analysis_revision": analysis["item"]["analysis_revision"],
                "source_provenance": transformer_source_provenance(analysis),
            })
            with transformer_jobs_lock, library_write_lock:
                cancelled()
                latest = library_row(analysis["item"]["id"])
                if latest is None:
                    raise AnalysisConflictError("対象の会話が削除されたため結果を保存しませんでした。")
                current = group_analysis_for_row(latest)
                expected = transformer_input_fingerprint(analysis, model=model, parameters=result.get("parameters"))
                actual = transformer_input_fingerprint(current, model=model, parameters=result.get("parameters"))
                if expected != actual:
                    raise AnalysisConflictError("分析中に元データが更新されました。再実行してください。")
                embedding_rows = segment_embeddings.prepare_rows(analysis, result)
                full_analysis = group_analysis_for_row(latest, include_research_rows=True)
                full_analysis["transformer"] = {"result": result, "stale": False}
                progress(95, "分析結果を保存しています。")
                archived = archive_group_analysis(
                    latest, full_analysis, "transformer-" + request_id,
                    kind="transformer_topics", app_url=app_url, check_cancelled=cancelled,
                )
                result["archive_id"] = archived["id"]
                result["vault_status"] = archived["vault_status"]
                with database_connection() as connection:
                    cursor = connection.execute("""
                        UPDATE library_items SET transformer_analysis_json=?
                        WHERE id=? AND revision_count=? AND analysis_revision=?
                    """, (json.dumps(result, ensure_ascii=False), latest["id"],
                          analysis["item"]["revision_count"], analysis["item"]["analysis_revision"]))
                    if cursor.rowcount != 1:
                        raise AnalysisConflictError("保存直前にデータが更新されました。再実行してください。")
                    segment_embeddings.write_rows(connection, embedding_rows)
                    connection.execute("""
                        UPDATE transformer_analysis_requests SET status='completed', progress=100,
                            message='Transformerテーマ分析を保存しました。', updated_at=? WHERE request_id=?
                    """, (utc_now_iso(), request_id))
        except TransformerAnalysisCancelled as exc:
            update_transformer_request(request_id, "cancelled", progress_value, str(exc))
        except AnalysisConflictError as exc:
            update_transformer_request(request_id, "stale", progress_value, str(exc))
        except Exception as exc:
            update_transformer_request(
                request_id, "failed", progress_value,
                "Transformer分析を実行できませんでした: "
                + public_diagnostic_text(str(exc), reveal_local_paths=False)[:700],
            )
        finally:
            with transformer_jobs_lock:
                transformer_cancel_events.pop(request_id, None)

    return (public_transformer_request, update_transformer_request, run_transformer_analysis_job)


def make_transformer_commands(
    *,
    database_connection: Any,
    group_analysis_for_row: Any,
    library_row: Any,
    public_transformer_request: Any,
    run_transformer_analysis_job: Any,
    transformer_cancel_events: Any,
    transformer_jobs_lock: Any,
    update_transformer_request: Any,
) -> tuple[Callable[..., Any], ...]:
    def start_transformer_analysis_command(
        item_id: str, payload: dict[str, Any], *, app_url: str
    ) -> tuple[dict[str, Any], int]:
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", request_id):
            raise AnalysisCommandRequestError("リクエストIDが正しくありません。", 400)
        if any(type(payload.get(key)) is not int for key in ("source_revision", "analysis_revision")):
            raise AnalysisCommandRequestError(
                "元データと分析のrevisionを指定してください。", 400
            )
        try:
            max_topics = int(payload.get("max_topics", 8))
            min_topic_size = int(payload.get("min_topic_size", 2))
            topic_count = int(payload.get("topic_count", 0))
            if (not 2 <= max_topics <= 12 or not 2 <= min_topic_size <= 20
                    or topic_count not in {0, *range(2, 13)}):
                raise ValueError
        except (TypeError, ValueError):
            raise AnalysisCommandRequestError(
                "テーマ上限・固定数は2〜12、最小発話数は2〜20で指定してください。",
                400,
            )
        mode = str(payload.get("mode") or "auto")
        if mode not in TOPIC_MODES:
            raise AnalysisCommandRequestError(
                "テーマの決め方は自動・候補・手動のいずれかで指定してください。",
                400,
            )
        try:
            min_similarity = float(payload.get("min_similarity", DEFAULT_MANUAL_MIN_SIMILARITY))
            if not 0.0 <= min_similarity <= 0.95:
                raise ValueError
        except (TypeError, ValueError):
            raise AnalysisCommandRequestError(
                "割り当てのしきい値は0〜0.95で指定してください。", 400
            )
        if mode == "candidate" and topic_count < 2:
            raise AnalysisCommandRequestError(
                "候補から選ぶときは、テーマ数を指定してください。", 400
            )
        if mode == "auto":
            topic_count = 0
        model = str(os.environ.get("MOJIOKOSI_TRANSFORMER_MODEL", DEFAULT_TRANSFORMER_MODEL)).strip()
        if not model or len(model) > 200:
            raise AnalysisCommandRequestError(
                "Transformerモデルの設定が正しくありません。", 400
            )
        with transformer_jobs_lock:
            row = library_row(item_id)
            if row is None:
                raise AnalysisCommandRequestError(
                    "処理済みデータが見つかりません。", 404
                )
            with database_connection() as connection:
                previous = connection.execute(
                    "SELECT * FROM transformer_analysis_requests WHERE request_id=?", (request_id,)
                ).fetchone()
                if previous:
                    expected = {
                        "item_id": item_id, "model": model,
                        "source_revision": payload["source_revision"],
                        "analysis_revision": payload["analysis_revision"],
                        "max_topics": max_topics, "min_topic_size": min_topic_size,
                        "topic_count": topic_count, "mode": mode,
                    }
                    if any(previous[key] != value for key, value in expected.items()):
                        raise AnalysisCommandRequestError(
                            "リクエストIDが別の指定に使われています。", 409
                        )
                    return {"run": public_transformer_request(previous)}, 200
                active = connection.execute("""
                    SELECT * FROM transformer_analysis_requests WHERE item_id=?
                        AND status IN ('queued','running','cancelling') LIMIT 1
                """, (item_id,)).fetchone()
                if active:
                    raise AnalysisCommandRequestError(
                        "この会話のTransformer分析は実行中です。",
                        409,
                        details={"run": public_transformer_request(active)},
                    )
            if (payload["source_revision"] != int(row["revision_count"])
                    or payload["analysis_revision"] != int(row["analysis_revision"])):
                raise AnalysisCommandRequestError(
                    "データが更新されています。分析を再読み込みしてください。",
                    409,
                    details={"conflict": True},
                )
            analysis = group_analysis_for_row(row)
            if not included_segments(analysis):
                raise AnalysisCommandRequestError(
                    "Transformer分析に利用できる発話がありません。", 400
                )
            manual_topics = list(analysis.get("config", {}).get("transformer_topics") or [])
            if mode == "manual" and not 2 <= len(manual_topics) <= MAX_MANUAL_TOPICS:
                raise AnalysisCommandRequestError(
                    f"手動で割り当てるには、テーマを2〜{MAX_MANUAL_TOPICS}件定義して保存してください。",
                    400,
                )
            saved_result = json_load(row["transformer_analysis_json"], {}) \
                if "transformer_analysis_json" in row.keys() else {}
            fingerprint = transformer_input_fingerprint(analysis, model=model)
            now = utc_now_iso()
            with database_connection() as connection:
                connection.execute("""
                    INSERT INTO transformer_analysis_requests
                    (request_id,item_id,source_revision,analysis_revision,fingerprint,model,
                     max_topics,min_topic_size,topic_count,mode,min_similarity,
                     status,message,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,'queued','モデルの準備を開始します。',?,?)
                """, (request_id, item_id, payload["source_revision"], payload["analysis_revision"],
                      fingerprint, model, max_topics, min_topic_size, topic_count, mode,
                      min_similarity, now, now))
                run = connection.execute(
                    "SELECT * FROM transformer_analysis_requests WHERE request_id=?", (request_id,)
                ).fetchone()
            event = threading.Event()
            transformer_cancel_events[request_id] = event
            try:
                threading.Thread(
                    target=run_transformer_analysis_job,
                    args=(request_id, analysis, model, max_topics, min_topic_size,
                          topic_count, event, app_url),
                    kwargs={"mode": mode, "manual_topics": manual_topics,
                            "min_similarity": min_similarity,
                            "saved_result": saved_result if isinstance(saved_result, dict) else {}},
                    name=f"transformer-{item_id}", daemon=True,
                ).start()
            except RuntimeError:
                transformer_cancel_events.pop(request_id, None)
                update_transformer_request(request_id, "failed", 0, "分析処理を開始できませんでした。")
                raise AnalysisCommandRequestError(
                    "分析処理を開始できませんでした。", 503
                )
            return {"run": public_transformer_request(run)}, 202

    def cancel_transformer_analysis_command(
        item_id: str, request_id: str
    ) -> dict[str, Any]:
        with transformer_jobs_lock, database_connection() as connection:
            row = connection.execute("""
                SELECT * FROM transformer_analysis_requests WHERE item_id=? AND request_id=?
            """, (item_id, request_id)).fetchone()
            if row is None:
                raise AnalysisCommandRequestError(
                    "Transformer分析処理が見つかりません。", 404
                )
            if row["status"] in {"queued", "running", "cancelling"}:
                event = transformer_cancel_events.get(row["request_id"])
                if event:
                    event.set()
                connection.execute("""
                    UPDATE transformer_analysis_requests SET status='cancelling',
                        message='中止しています。' WHERE request_id=?
                """, (row["request_id"],))
            return {"ok": True}

    return (start_transformer_analysis_command, cancel_transformer_analysis_command)
