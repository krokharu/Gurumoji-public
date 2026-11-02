"""HTTP boundary for durable autonomous analysis; GET never calls a model."""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable

from flask import Blueprint, Flask, Response, jsonify, request

from ..analysis_core import AnalysisContractError
from ..analysis_store import StoreConflict


def register_orchestration_routes(app: Flask, service: Callable[[], Any],
                                  prepare: Callable[[dict], dict],
                                  publication: Callable[[], Any] | None = None,
                                  history_viewer: Callable[[], Any] | None = None) -> None:
    blueprint = Blueprint("analysis_orchestration", __name__)

    def payload() -> dict:
        if request.content_length and request.content_length > 64 * 1024:
            raise AnalysisContractError("実行条件が大きすぎます。")
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise AnalysisContractError("実行条件をJSONオブジェクトで指定してください。")
        return value

    def public_run(item_id: str, value: dict) -> dict:
        if publication is None:
            return value
        return {**value, "publication": publication().status(item_id, value["run_id"])}

    @blueprint.errorhandler(AnalysisContractError)
    def contract_error(exc):
        conflict = exc.code in {"revision_conflict", "request_conflict", "active_run",
                                "provider_unavailable", "resume_blocked", "uncertain_execution",
                                "nothing_to_resume", "recovery_required", "version_conflict", "history_integrity_mismatch", "initial_hash_mismatch"}
        return jsonify(error=str(exc), reason_code=exc.code, field=exc.field), 409 if conflict else 400

    @blueprint.errorhandler(StoreConflict)
    def publication_conflict(exc):
        return jsonify(error=str(exc), reason_code="publication_conflict"), 409

    @blueprint.errorhandler(LookupError)
    def not_found(_exc):
        return jsonify(error="対象の会話または分析履歴が見つかりません。"), 404

    @blueprint.errorhandler(sqlite3.Error)
    @blueprint.errorhandler(OSError)
    def storage_error(_exc):
        return jsonify(error="分析台帳を読み書きできません。元データは保持されています。"), 503

    def viewer():
        if history_viewer is not None:
            return history_viewer()
        # Never fall back to the execution factory: its lazy constructor can
        # initialize schema even when the caller only requests a GET.
        raise OSError("read-only history service is not configured")

    def viewer_response(value):
        response = jsonify(value)
        response.headers["Cache-Control"] = "no-store"
        return response

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/viewer")
    def viewer_runs(item_id):
        return viewer_response(viewer().runs(item_id, limit=request.args.get("limit", "20"), offset=request.args.get("offset", "0")))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/viewer")
    def viewer_timeline(item_id, run_id):
        allowed = ("limit", "offset", "kind", "role", "operation", "status", "after", "before", "annotation_version")
        return viewer_response(viewer().timeline(item_id, run_id, **{key: request.args[key] for key in allowed if key in request.args}))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/viewer/entries/<entry_id>")
    def viewer_entry(item_id, run_id, entry_id):
        return viewer_response(viewer().entry(item_id, run_id, entry_id, annotation_version=request.args.get("annotation_version"),
                                              evidence_offset=request.args.get("evidence_offset", "0"), evidence_limit=request.args.get("evidence_limit", "30")))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/viewer/sources/<utterance_id>")
    def viewer_source(item_id, run_id, utterance_id):
        return viewer_response(viewer().source(item_id, run_id, utterance_id, annotation_version=request.args.get("annotation_version")))

    @blueprint.post("/api/library/<item_id>/analysis/orchestration")
    def start(item_id):
        value = service().start(item_id, prepare(payload()), app_url=request.url_root)
        return jsonify(run=public_run(item_id, value)), 202

    @blueprint.get("/api/library/<item_id>/analysis/orchestration")
    def history(item_id):
        return jsonify(runs=[public_run(item_id, value) for value in service().history(item_id)])

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>")
    def status(item_id, run_id):
        return jsonify(run=public_run(item_id, service().status(item_id, run_id)))

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/cancel")
    def cancel(item_id, run_id):
        return jsonify(run=public_run(item_id, service().cancel(item_id, run_id)))

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/resume")
    def resume(item_id, run_id):
        return jsonify(run=public_run(item_id, service().resume(item_id, run_id, payload()))), 202

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/publication/retry")
    def retry_publication(item_id, run_id):
        if publication is None:
            return jsonify(error="固定成果物の保存・公開を利用できません。"), 503
        value = payload()
        if value:
            raise AnalysisContractError("保存・公開の再試行で条件や公開先を変更できません。")
        publication().retry(item_id, run_id)
        return jsonify(run=public_run(item_id, service().status(item_id, run_id)))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/results")
    def results(item_id, run_id):
        return jsonify(service().result(item_id, run_id))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/results/<result_id>")
    def result(item_id, run_id, result_id):
        return jsonify(service().result(item_id, run_id, result_id))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/export.json")
    def export_json(item_id, run_id):
        value = service().result(item_id, run_id)
        return Response(json.dumps(value, ensure_ascii=False, indent=2),
                        mimetype="application/json", headers={
                            "Content-Disposition": 'attachment; filename="analysis-history.json"',
                            "Cache-Control": "no-store",
                        })

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/export.md")
    def export_markdown(item_id, run_id):
        # A download only: never writes into a researcher-owned Vault. The full
        # ledger is included, rather than substituting a lossy LLM summary.
        backend = service()
        state = backend.status(item_id, run_id)
        value = backend.result(item_id, run_id)
        encoded = json.dumps(value, ensure_ascii=False, indent=2)
        catalog = state.get("initial_label_catalog")
        label_output = ("## 初回のラベル・尺度（専門エージェント作成・AI下書き）\n\n````json\n"
                        + json.dumps(catalog, ensure_ascii=False, indent=2) + "\n````\n\n") if catalog else ""
        report = state.get("initial_analysis_report")
        report_output = ("## 全担当の初回分析・ラベルと尺度の要件\n\n````json\n"
                         + json.dumps(report, ensure_ascii=False, indent=2) + "\n````\n\n") if report else ""
        text = (
            "---\nnote_type: gurumoji-analysis-history\nresearch_mode: exploratory\n---\n\n"
            "# 自律分析の保存履歴\n\n"
            f"- Run ID: {run_id}\n- 状態: {state.get('status', 'unknown')}\n"
            f"- 終了理由: {state.get('stop_reason') or '未確定'}\n\n"
            "このノートは保存済み台帳の書き出しです。探索的な分析・AIの解釈を含み、"
            "独立検証や批判レビューだけで科学的な確認結果にはなりません。\n\n"
            "初期全量、タスク結果、根拠ID、ラベル版、批判とCoreの応答は以下の履歴を参照してください。"
            "原文を含む場合があるため、保存先と共有範囲を確認してください。\n\n"
            + report_output + label_output + "## 完全な保存履歴\n\n````json\n" + encoded + "\n````\n"
        )
        return Response(text, mimetype="text/markdown", headers={
            "Content-Disposition": 'attachment; filename="gurumoji-analysis-history.md"',
            "Cache-Control": "no-store",
        })

    app.register_blueprint(blueprint)
