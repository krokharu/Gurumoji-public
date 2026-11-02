"""HTTP routes for saved-design, deterministic slide preview and download."""
from __future__ import annotations

import sqlite3
from typing import Any, Callable

from flask import Blueprint, Flask, jsonify, request, send_file

from ..analysis_core import AnalysisContractError
from ..analysis_store import StoreConflict


def register_analysis_slides_routes(app: Flask, service: Callable[[], Any]) -> None:
    bp = Blueprint("analysis_slides", __name__)
    prefix = "/api/library/<item_id>/analysis/orchestration/<run_id>/slides"

    @bp.after_request
    def private_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @bp.errorhandler(AnalysisContractError)
    def contract_error(exc):
        if exc.code == "slide_renderer_unavailable":
            status = 503
        elif exc.code in {"slide_design_required", "slide_design_conflict", "slide_design_unverified",
                          "slide_snapshot_conflict", "slide_snapshot_invalid", "slide_review_required"}:
            status = 409
        else:
            status = 400
        return jsonify(error=str(exc), reason_code=exc.code, field=exc.field), status

    @bp.errorhandler(StoreConflict)
    def conflict(_exc):
        return jsonify(error="Obsidianの設計ノートの履歴・削除状態を確認してください。", reason_code="slide_design_conflict"), 409

    @bp.errorhandler(LookupError)
    def missing(_exc):
        return jsonify(error="対象の会話または分析履歴が見つかりません。"), 404

    @bp.errorhandler(sqlite3.Error)
    @bp.errorhandler(OSError)
    def unavailable(_exc):
        return jsonify(error="保存履歴またはObsidianの設計を読み書きできません。生成は完了していません。", reason_code="slide_storage_unavailable"), 503

    def template_query():
        return request.args.get("template", "research")

    @bp.get(prefix + "/templates")
    def templates(item_id, run_id):
        return jsonify(service().catalog(item_id, run_id))

    @bp.post(prefix + "/design")
    def design(item_id, run_id):
        if request.content_length and request.content_length > 4096:
            raise AnalysisContractError("設計保存の指定が大きすぎます。")
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) - {"template", "expected_snapshot"}:
            raise AnalysisContractError("設計IDと確認した保存版だけを指定してください。")
        return jsonify(service().save_design(item_id, run_id, payload.get("template", "research"), payload.get("expected_snapshot")))

    @bp.get(prefix + "/preview")
    def preview(item_id, run_id):
        return jsonify(service().preview(item_id, run_id, template_query(), request.args.get("expected_snapshot")))

    @bp.get(prefix + "/presentation.pptx")
    def presentation(item_id, run_id):
        stream = service().presentation(item_id, run_id, template_query(), request.args.get("expected_snapshot"))
        return send_file(stream, as_attachment=True, download_name="gurumoji-saved-analysis.pptx",
                         mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                         conditional=False, etag=False, max_age=0)

    app.register_blueprint(bp)
