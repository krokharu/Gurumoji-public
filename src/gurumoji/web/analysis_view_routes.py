"""HTTP adapters for reading and annotating a conversation's analysis view.

Saved runs, AI jobs and exports have their own route modules."""

from __future__ import annotations

import csv
import io
import sqlite3
from typing import Any

from flask import Flask, jsonify, request, send_file

from .. import method_experts
from ..analysis_insights import KWIC_FIELDS, search_kwic
from ..analysis_method_registry import (
    METHOD_GROUPS,
    SEPARATE_RUN_METHODS,
    method_results,
)
from ..services.group_analysis import (
    ANALYSIS_CSV_FIELDS,
    analysis_csv_rows,
    analysis_csv_safe,
)
from ..services.outputs import safe_output_stem
from ..text_utils import json_load


def register_analysis_view_routes(
    app: Flask,
    *,
    AnalysisConflictError: Any,
    analysis_archive_store: Any,
    build_research_analysis: Any,
    group_analysis_for_row: Any,
    library_row: Any,
    public_diagnostic_text: Any,
    save_group_analysis: Any,
    transformer_semantic_search: Any,
) -> None:
    def get_analysis_experts():
        return jsonify(method_experts.catalog_summary())

    def get_analysis_expert(expert_id: str):
        try:
            return jsonify(method_experts.expert_detail(expert_id))
        except (method_experts.ExpertDefinitionError, KeyError) as exc:
            return jsonify({"error": str(exc)}), 404

    def get_analysis_method_overview(item_id: str):
        """Per-method state for the method view: what each analysis produced and what its expert says."""
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        try:
            analysis = group_analysis_for_row(row, include_research_rows=True)
            datasets = {name: analysis_csv_rows(analysis, name) for name in ANALYSIS_CSV_FIELDS}
            outline = json_load(row["outline_json"], None)
            finished = any(run["kind"] == "ai_finishing" and run["status"] == "completed"
                           for run in analysis_archive_store().list(item_id))
            methods = [method for method in method_results(analysis, datasets, outline=outline)
                       if method["method_id"] not in SEPARATE_RUN_METHODS]
            # Context search runs on demand and AI finishing belongs to the transcript screen,
            # so both are listed with their own state instead of a result table.
            methods += [
                {"method_id": "kwic", "title": "文脈検索", "status": "not_run", "datasets": ["kwic"],
                 "previews": [], "analysis_unit": "出現箇所",
                 "limitations": ["語を検索したときだけ結果が出ます。検索結果はCSVで保存できます。"]},
                {"method_id": "ai_finishing", "title": "AI仕上げ・変更記録",
                 "datasets": ["ai_changes", "ai_jev_comparison"],
                 "status": "completed" if finished else "not_run", "previews": [], "analysis_unit": "発話",
                 "limitations": ["実行と変更記録の確認は文字起こし画面です。保存記録に仕上げ前後の発話が残ります。"]},
            ]
            overview = method_experts.method_overview(methods, analysis)
            overview["groups"] = [
                {"id": key, "title": title, "description": description,
                 "method_ids": [value for value in ids if value not in SEPARATE_RUN_METHODS]}
                for key, title, description, ids in METHOD_GROUPS
                if any(value not in SEPARATE_RUN_METHODS for value in ids)
            ]
            return jsonify(overview)
        except (ValueError, TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "手法別の分析状態を取得できませんでした。"}), 500

    def get_analysis_kwic(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        try:
            offset = int(request.args.get("offset", "0"))
            limit = int(request.args.get("limit", "50"))
            if offset < 0 or not 1 <= limit <= 200:
                raise ValueError("検索結果の表示範囲が正しくありません。")
            analysis = group_analysis_for_row(row)
            research = build_research_analysis(analysis)
            export = request.args.get("format") == "csv"
            result = search_kwic(analysis, research["linguistics"]["morphemes"],
                                 request.args.get("q", ""), mode=request.args.get("mode", "normalized"),
                                 speaker=request.args.get("speaker", ""),
                                 offset=0 if export else offset, limit=None if export else limit)
            if export:
                stream = io.StringIO(newline="")
                writer = csv.DictWriter(stream, fieldnames=KWIC_FIELDS, extrasaction="ignore")
                writer.writeheader()
                for hit in result["hits"]:
                    writer.writerow({key: analysis_csv_safe(value) for key, value in hit.items()})
                return send_file(io.BytesIO(stream.getvalue().encode("utf-8-sig")),
                                 mimetype="text/csv; charset=utf-8", as_attachment=True,
                                 download_name=f"{safe_output_stem(str(row['source_name']))[:64]}_文脈検索.csv")
            result["fingerprint"] = analysis["insights"]["fingerprint"]
            return jsonify(result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "文脈検索に失敗しました。"}), 500

    def get_transformer_semantic_search(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        try:
            limit = int(request.args.get("limit", "20"))
            if not 1 <= limit <= 100:
                raise ValueError("表示件数は1〜100で指定してください。")
            analysis = group_analysis_for_row(row)
            state = analysis.get("transformer", {})
            public_saved = state.get("result")
            if not public_saved:
                return jsonify({"error": "先にTransformerテーマ分析を実行してください。"}), 409
            if state.get("stale"):
                return jsonify({"error": "元データが更新されています。Transformer分析を再実行してください。"}), 409
            saved = json_load(row["transformer_analysis_json"], {})
            if not isinstance(saved, dict) or not saved.get("vectors"):
                return jsonify({"error": "保存済み意味ベクトルがありません。Transformer分析を再実行してください。"}), 409
            query = request.args.get("q", "")
            hits = transformer_semantic_search(saved, query, limit=limit)
            return jsonify({"query": query, "hits": hits, "model": saved.get("engine", {})})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": "意味検索を実行できませんでした: "
                            + public_diagnostic_text(str(exc), reveal_local_paths=False)[:500]}), 500

    def get_library_analysis(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        try:
            execute = request.args.get("execute", "0").strip() in {"1", "true"}
            return jsonify(group_analysis_for_row(row, execute=execute))
        except (ValueError, TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "分析データを生成できません。元データを確認してください。"}), 500

    def update_library_analysis(item_id: str):
        if request.content_length and request.content_length > 16 * 1024 * 1024:
            return jsonify({"error": "分析設定が大きすぎます。"}), 413
        try:
            return jsonify(save_group_analysis(item_id, request.get_json(silent=True)))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except AnalysisConflictError as exc:
            return jsonify({"error": str(exc), "conflict": True}), 409
        except sqlite3.Error:
            return jsonify({"error": "分析設定を保存できません。"}), 500

    # Keep established endpoint names: the security hook and the
    # route-map snapshot depend on them.
    endpoints = (
        ('/api/analysis/experts', 'get_analysis_experts', get_analysis_experts, 'GET'),
        ('/api/analysis/experts/<expert_id>', 'get_analysis_expert', get_analysis_expert, 'GET'),
        ('/api/library/<item_id>/analysis/methods', 'get_analysis_method_overview', get_analysis_method_overview, 'GET'),
        ('/api/library/<item_id>/analysis/kwic', 'get_analysis_kwic', get_analysis_kwic, 'GET'),
        ('/api/library/<item_id>/analysis/semantic-search', 'get_transformer_semantic_search', get_transformer_semantic_search, 'GET'),
        ('/api/library/<item_id>/analysis', 'get_library_analysis', get_library_analysis, 'GET'),
        ('/api/library/<item_id>/analysis', 'update_library_analysis', update_library_analysis, 'PUT'),
    )
    for rule, endpoint, view, method in endpoints:
        app.add_url_rule(rule, endpoint, view, methods=[method])
