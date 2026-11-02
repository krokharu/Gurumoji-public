"""HTTP adapters for analysis queries and fixed-result commands."""

from __future__ import annotations

import io
import csv
import re
import sqlite3
import subprocess
import zipfile
from typing import Callable

from flask import Blueprint, Flask, jsonify, request, send_file

from .. import transcript_preparation as preparation
from ..analysis_store import StoreConflict
from ..services.analysis_package import MissingReference
from ..analysis_core import AnalysisContractError
from ..handlers.analysis_commands import (
    AnalysisCommandRequestError,
    AnalysisCommands,
    AnalysisCommandNotFound,
    ComparisonRequestError,
    TranscriptConflictError,
)
from ..handlers.analysis_queries import AnalysisQueries, AnalysisQueryNotFound


def register_analysis_routes(
    app: Flask,
    queries: Callable[[], AnalysisQueries],
    commands: Callable[[], AnalysisCommands],
    ai_providers: frozenset[str] | set[str],
) -> None:
    blueprint = Blueprint("analysis_queries", __name__)

    @blueprint.get("/api/analysis/methods")
    def get_analysis_methods():
        return jsonify(queries().methods())

    @blueprint.get("/api/library/<item_id>/analysis/runs")
    def get_analysis_runs(item_id: str):
        try:
            limit = int(request.args.get("limit", 100))
            offset = int(request.args.get("offset", 0))
            if not 1 <= limit <= 100 or not 0 <= offset <= 2**63 - 1:
                raise ValueError()
            return jsonify(queries().runs(item_id, limit=limit, offset=offset))
        except AnalysisQueryNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except (ValueError, OverflowError):
            return jsonify(error="履歴のページ指定が正しくありません。"), 400

    @blueprint.get("/api/library/<item_id>/analysis/runs/<run_id>")
    def get_analysis_run(item_id: str, run_id: str):
        try:
            return jsonify(queries().run(item_id, run_id))
        except AnalysisQueryNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except (OSError, ValueError, TypeError, KeyError, LookupError, csv.Error):
            return jsonify({"error": "固定成果物が欠落・破損しているか、未対応の形式です。再計算せず停止しました。"}), 409

    @blueprint.get("/api/library/<item_id>/analysis/runs/<run_id>/previews/<artifact_id>")
    def get_analysis_run_preview(item_id: str, run_id: str, artifact_id: str):
        try:
            return jsonify(queries().run_preview(item_id, run_id, artifact_id))
        except AnalysisQueryNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except MissingReference as exc:
            return jsonify({'error': str(exc), 'reason_code': exc.code,
                            'recovery_status': getattr(exc, 'recovery_status', 'missing_reference')}), 409
        except (OSError, ValueError, TypeError, KeyError, LookupError, csv.Error):
            return jsonify({"error": "固定成果物を読み取れません。再計算せず停止しました。"}), 409

    @blueprint.get("/api/analysis/artifacts/<artifact_id>")
    def get_analysis_artifact(artifact_id: str):
        try:
            artifact = queries().artifact(artifact_id)
            return send_file(
                io.BytesIO(artifact.data),
                mimetype=artifact.media_type,
                as_attachment=True,
                download_name=artifact.download_name,
            )
        except AnalysisQueryNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except MissingReference as exc:
            return jsonify({'error': str(exc), 'reason_code': exc.code,
                            'recovery_status': getattr(exc, 'recovery_status', 'missing_reference')}), 409
        except (OSError, ValueError):
            return jsonify({"error": "保存ファイルが移動または変更されています。"}), 409

    @blueprint.get('/api/analysis/runs/<run_id>/tables/<name>.csv')
    def get_analysis_table_csv(run_id: str, name: str):
        try:
            artifact = queries().table_csv(run_id, name)
            return send_file(io.BytesIO(artifact.data), mimetype=artifact.media_type,
                             as_attachment=True, download_name=artifact.download_name)
        except AnalysisQueryNotFound as exc:
            return jsonify({'error': str(exc)}), 404
        except MissingReference as exc:
            return jsonify({'error': str(exc), 'reason_code': exc.code,
                            'recovery_status': getattr(exc, 'recovery_status', 'missing_reference')}), 409
        except (OSError, ValueError, KeyError, LookupError) as exc:
            return jsonify({'error': str(exc)}), 409

    @blueprint.get("/api/analysis/runs/<run_id>/export.zip")
    def get_analysis_run_bundle(run_id: str):
        try:
            artifact = queries().run_bundle(run_id)
            return send_file(
                io.BytesIO(artifact.data), mimetype=artifact.media_type,
                as_attachment=True, download_name=artifact.download_name,
            )
        except AnalysisQueryNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except MissingReference as exc:
            return jsonify({'error': str(exc), 'reason_code': exc.code,
                            'recovery_status': getattr(exc, 'recovery_status', 'missing_reference')}), 409
        except (OSError, ValueError, TypeError, KeyError, LookupError, csv.Error, zipfile.BadZipFile):
            return jsonify({"error": "固定成果物のZIPを作成できませんでした。"}), 409

    @blueprint.get('/api/library/<item_id>/analysis/runs/<run_id>/tables/<name>/schema')
    def get_fixed_table_schema(item_id: str, run_id: str, name: str):
        try:
            return jsonify(queries().table_schema(item_id, run_id, name))
        except AnalysisQueryNotFound as exc:
            return jsonify(error=str(exc)), 404
        except (ValueError, KeyError, LookupError, OSError) as exc:
            return jsonify(error=str(exc)), 409

    @blueprint.post('/api/library/<item_id>/analysis/runs/<run_id>/statistics')
    def run_fixed_statistics(item_id: str, run_id: str):
        try:
            return jsonify(commands().run_statistics(item_id, run_id, request.get_json(silent=True), request.url_root))
        except AnalysisCommandNotFound as exc:
            return jsonify(error=str(exc)), 404
        except (ValueError, TypeError, KeyError, LookupError) as exc:
            return jsonify(error=str(exc)), 400
        except ImportError:
            return jsonify(error='統計用の依存が未導入です。セットアップを実行してください。'), 503

    @blueprint.get('/api/analysis/runs/<run_id>/export.<format>')
    def get_analysis_run_export(run_id: str, format: str):
        if format not in {'xlsx', 'sav', 'svg', 'png'}:
            return jsonify(error='未対応の出力形式です。'), 404
        try:
            artifact = queries().run_export(run_id, format, request.args.get('dataset'))
            return send_file(io.BytesIO(artifact.data), mimetype=artifact.media_type,
                             as_attachment=True, download_name=artifact.download_name)
        except AnalysisQueryNotFound as exc:
            return jsonify(error=str(exc)), 404
        except ImportError:
            return jsonify(error='この出力に必要な依存が未導入です。セットアップを実行してください。'), 503
        except (ValueError, OSError, KeyError, LookupError) as exc:
            return jsonify(error=str(exc)), 409

    def pipeline_error(exc: AnalysisContractError):
        status = 409 if exc.code in {
            "revision_conflict", "request_conflict", "definition_not_adopted",
            "unresolved_binding", "binding_out_of_scope", "ineligible",
            "nothing_to_retry", "provider_unavailable", "method_unavailable",
            "retry_limit_reached", "trial_conflict", "binding_conflict",
            "definition_snapshot_missing", "definition_version_invalid",
            "retry_in_progress", "publication_scope_conflict",
            "pipeline_terminal", "resume_required", "nothing_to_resume",
        } else 400
        return jsonify({"error": str(exc), "reason_code": exc.code, "field": exc.field}), status

    @blueprint.get("/api/analysis/pipeline-capabilities")
    def get_pipeline_capabilities():
        return jsonify(commands().pipeline_capabilities())

    @blueprint.get("/api/library/<item_id>/analysis/definitions/<definition_id>")
    def get_analysis_definition(item_id: str, definition_id: str):
        try:
            return jsonify({"definition": commands().get_definition(item_id, definition_id)})
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except AnalysisContractError as exc:
            return pipeline_error(exc)
        except sqlite3.Error:
            return jsonify({"error": "定義を取得できませんでした。"}), 500

    @blueprint.put("/api/library/<item_id>/analysis/definitions/<definition_id>")
    def put_analysis_definition(item_id: str, definition_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "定義はJSONオブジェクトで送信してください。"}), 400
        try:
            return jsonify({"definition": commands().save_definition(item_id, definition_id, payload)})
        except AnalysisCommandNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except AnalysisContractError as exc:
            return pipeline_error(exc)
        except sqlite3.Error:
            return jsonify({"error": "定義を保存できませんでした。"}), 500

    @blueprint.post("/api/library/<item_id>/analysis/definitions/<definition_id>/trials")
    def trial_analysis_definition(item_id: str, definition_id: str):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "試行条件はJSONオブジェクトで送信してください。"}), 400
        try:
            return jsonify({"trial": commands().trial_definition(
                item_id, definition_id, limit=payload.get("limit", 20)
            )})
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (AnalysisContractError, ValueError) as exc:
            return pipeline_error(exc) if isinstance(exc, AnalysisContractError) else (jsonify({"error": str(exc)}), 400)
        except sqlite3.Error:
            return jsonify({"error": "定義の試行を保存できませんでした。"}), 500

    @blueprint.post("/api/library/<item_id>/analysis/plans/preview")
    def preview_analysis_pipeline(item_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "計画はJSONオブジェクトで送信してください。"}), 400
        try:
            return jsonify(commands().preview_pipeline(item_id, payload))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except AnalysisContractError as exc:
            return pipeline_error(exc)
        except sqlite3.Error:
            return jsonify({"error": "計画を確認できませんでした。"}), 500

    @blueprint.post("/api/library/<item_id>/analysis/plans/proposals")
    def propose_analysis_pipeline(item_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "計画候補はJSONオブジェクトで指定してください。"}), 400
        try:
            return jsonify(commands().propose_pipeline(item_id, payload))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except AnalysisContractError as exc:
            return pipeline_error(exc)
        except (ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 503
        except (OSError, sqlite3.Error):
            return jsonify({"error": "計画候補を生成できませんでした。"}), 500

    @blueprint.post("/api/library/<item_id>/analysis/pipelines")
    def start_analysis_pipeline(item_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "実行計画はJSONオブジェクトで送信してください。"}), 400
        try:
            body, status = commands().start_pipeline(item_id, payload, app_url=request.url_root)
            return jsonify(body), status
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except AnalysisContractError as exc:
            return pipeline_error(exc)
        except (OSError, sqlite3.Error):
            return jsonify({"error": "分析pipelineを開始できませんでした。"}), 500

    @blueprint.get("/api/library/<item_id>/analysis/pipelines/<pipeline_id>")
    def get_analysis_pipeline(item_id: str, pipeline_id: str):
        try:
            return jsonify(commands().pipeline_status(item_id, pipeline_id))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (OSError, sqlite3.Error):
            return jsonify({"error": "分析pipelineの状態を取得できませんでした。"}), 500

    @blueprint.post("/api/library/<item_id>/analysis/pipelines/<pipeline_id>/cancel")
    def cancel_analysis_pipeline(item_id: str, pipeline_id: str):
        try:
            return jsonify(commands().cancel_pipeline(item_id, pipeline_id))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (OSError, sqlite3.Error):
            return jsonify({"error": "分析pipelineを中止できませんでした。"}), 500

    @blueprint.post("/api/library/<item_id>/analysis/pipelines/<pipeline_id>/retry")
    def retry_analysis_pipeline(item_id: str, pipeline_id: str):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "再試行条件はJSONオブジェクトで送信してください。"}), 400
        try:
            return jsonify(commands().retry_pipeline(
                item_id, pipeline_id, payload, app_url=request.url_root
            ))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except AnalysisContractError as exc:
            return pipeline_error(exc)
        except (OSError, sqlite3.Error):
            return jsonify({"error": "分析pipelineを再試行できませんでした。"}), 500

    @blueprint.post("/api/library/<item_id>/analysis/pipelines/<pipeline_id>/resume")
    def resume_analysis_pipeline(item_id: str, pipeline_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "再開条件はJSONオブジェクトで送信してください。"}), 400
        try:
            return jsonify(commands().resume_pipeline(item_id, pipeline_id, payload, app_url=request.url_root))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except AnalysisContractError as exc:
            return pipeline_error(exc)
        except (OSError, sqlite3.Error):
            return jsonify({"error": "分析pipelineを再開できませんでした。"}), 500

    @blueprint.get("/api/library/<item_id>/analysis/insights")
    def get_analysis_insights(item_id: str):
        try:
            return jsonify(queries().insights(item_id))
        except AnalysisQueryNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except (ValueError, TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "見解の生成状態を取得できませんでした。"}), 500

    @blueprint.post("/api/library/<item_id>/analysis/insights")
    def start_analysis_insights(item_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({
                "error": "見解生成の指定はJSONオブジェクトで送信してください。"
            }), 400
        provider, request_id = payload.get("provider"), payload.get("request_id")
        if not isinstance(provider, str) or provider not in ai_providers:
            return jsonify({
                "error": "OpenAI、Google Gemini、またはローカルLLMを選択してください。"
            }), 400
        if not isinstance(request_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{16,100}", request_id
        ):
            return jsonify({"error": "リクエストIDが正しくありません。"}), 400
        if any(type(payload.get(key)) is not int for key in (
            "source_revision", "analysis_revision"
        )):
            return jsonify({"error": "元データと分析のrevisionを指定してください。"}), 400
        try:
            body, status = commands().start_insight(
                item_id, payload, app_url=request.url_root
            )
            return jsonify(body), status
        except AnalysisCommandRequestError as exc:
            return jsonify({"error": str(exc), **exc.details}), exc.status

    @blueprint.post("/api/library/<item_id>/analysis/insights/cancel")
    def cancel_analysis_insights(item_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(
            payload.get("request_id"), str
        ):
            return jsonify({"error": "中止するリクエストIDを指定してください。"}), 400
        try:
            return jsonify(commands().cancel_insight(item_id, payload["request_id"]))
        except AnalysisCommandRequestError as exc:
            return jsonify({"error": str(exc), **exc.details}), exc.status

    @blueprint.get("/api/library/<item_id>/analysis/transformer")
    def get_transformer_analysis(item_id: str):
        try:
            return jsonify(queries().transformer(item_id))
        except AnalysisQueryNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except (ValueError, TypeError, OverflowError, sqlite3.Error):
            return jsonify({
                "error": "Transformer分析の状態を取得できませんでした。"
            }), 500

    @blueprint.post("/api/library/<item_id>/analysis/transformer")
    def start_transformer_analysis(item_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({
                "error": "Transformer分析の指定はJSONオブジェクトで送信してください。"
            }), 400
        try:
            body, status = commands().start_transformer(
                item_id, payload, app_url=request.url_root
            )
            return jsonify(body), status
        except AnalysisCommandRequestError as exc:
            return jsonify({"error": str(exc), **exc.details}), exc.status

    @blueprint.post("/api/library/<item_id>/analysis/transformer/cancel")
    def cancel_transformer_analysis(item_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(
            payload.get("request_id"), str
        ):
            return jsonify({"error": "中止するリクエストIDを指定してください。"}), 400
        try:
            return jsonify(commands().cancel_transformer(
                item_id, payload["request_id"]
            ))
        except AnalysisCommandRequestError as exc:
            return jsonify({"error": str(exc), **exc.details}), exc.status

    @blueprint.get("/api/library/<item_id>/analysis/classifications")
    def get_segment_classifications(item_id: str):
        try:
            return jsonify(queries().classifications(item_id))
        except AnalysisQueryNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except (ValueError, TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "発話分類の状態を取得できませんでした。"}), 500

    @blueprint.post("/api/library/<item_id>/analysis/classifications")
    def run_segment_classifications(item_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({
                "error": "実行条件をJSONオブジェクトで送信してください。"
            }), 400
        try:
            return jsonify(commands().run_classification(
                item_id, payload, app_url=request.url_root
            ))
        except AnalysisCommandRequestError as exc:
            return jsonify({"error": str(exc), **exc.details}), exc.status

    @blueprint.post("/api/library/<item_id>/analysis/runs")
    def save_analysis_run(item_id: str):
        payload = request.get_json(silent=True)
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("request_id"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", payload["request_id"])
            or any(
                type(payload.get(key)) is not int
                for key in ("source_revision", "analysis_revision")
            )
        ):
            return jsonify({
                "error": "リクエストIDと保存済みデータのrevisionを指定してください。"
            }), 400
        kwic_request = payload.get("kwic")
        if kwic_request is not None and not isinstance(kwic_request, dict):
            return jsonify({"error": "検索条件が正しくありません。"}), 400
        try:
            run = commands().save(
                item_id,
                request_id=payload["request_id"],
                source_revision=payload["source_revision"],
                analysis_revision=payload["analysis_revision"],
                kwic_request=kwic_request,
                app_url=request.url_root,
            )
            return jsonify({"run": run})
        except AnalysisCommandNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except StoreConflict as exc:
            return jsonify({"error": str(exc), "conflict": True}), 409
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, sqlite3.Error):
            return jsonify({
                "error": "分析結果を保存できませんでした。元データは保持されています。"
            }), 500

    @blueprint.post("/api/analysis/runs/<run_id>/vault")
    def retry_analysis_vault(run_id: str):
        try:
            return jsonify({"run": commands().retry_vault(run_id)})
        except AnalysisCommandNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except (OSError, ValueError, LookupError, sqlite3.Error):
            return jsonify({"error": "Vaultへの再保存に失敗しました。"}), 409

    @blueprint.post("/api/library/interview-comparison/runs")
    def save_interview_comparison_run():
        if request.content_length and request.content_length > 64 * 1024:
            return jsonify({"error": "比較対象の指定が大きすぎます。"}), 413
        payload = request.get_json(silent=True)
        request_id = payload.get("request_id") if isinstance(payload, dict) else None
        if not isinstance(request_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{16,100}", request_id
        ):
            return jsonify({"error": "リクエストIDを指定してください。"}), 400
        input_fingerprints = payload.get("input_fingerprints")
        if not isinstance(input_fingerprints, dict):
            return jsonify({
                "error": "表示時の入力版が必要です。比較を再集計してください。"
            }), 400
        try:
            run = commands().save_comparison(
                payload,
                request_id=request_id,
                input_fingerprints=input_fingerprints,
                app_url=request.url_root,
            )
            return jsonify({"run": run})
        except ComparisonRequestError as exc:
            return jsonify({"error": str(exc)}), exc.status
        except StoreConflict as exc:
            return jsonify({"error": str(exc), "conflict": True}), 409
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 409
        except (OSError, OverflowError, sqlite3.Error):
            return jsonify({
                "error": "インタビュー比較を保存できませんでした。元データは保持されています。"
            }), 500

    @blueprint.put("/api/library/<item_id>/preparation")
    def update_transcript_preparation(item_id: str):
        if request.content_length and request.content_length > 16 * 1024 * 1024:
            return jsonify({"error": "準備データが大きすぎます。"}), 413
        try:
            return jsonify(commands().save_preparation(
                item_id, request.get_json(silent=True)
            ))
        except AnalysisCommandNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except preparation.Conflict as exc:
            return jsonify({"error": str(exc), "conflict": True}), 409
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @blueprint.put("/api/library/<item_id>")
    def update_library_item(item_id: str):
        try:
            return jsonify(commands().update_item(
                item_id, request.get_json(silent=True)
            ))
        except TranscriptConflictError as exc:
            return jsonify({
                "error": str(exc),
                "conflict": True,
                "current_revision": exc.current_revision,
            }), 409
        except AnalysisCommandNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
            return jsonify({"error": f"保存できません: {exc}"}), 500

    app.register_blueprint(blueprint)
