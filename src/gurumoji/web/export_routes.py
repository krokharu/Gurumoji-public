"""HTTP adapters for downloadable exports (analysis, meeting minutes, speakers)."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from typing import Any

from flask import Flask, jsonify, request, send_file

from .. import transcript_preparation as preparation
from ..research_analysis import build_analysis_workbook
from ..services.group_analysis import (
    ANALYSIS_CSV_FIELDS,
    analysis_csv_content,
    analysis_csv_rows,
    analysis_csv_safe,
    focus_group_analysis_report_markdown,
)
from ..services.meeting_minutes import (
    format_meeting_minutes_markdown,
    meeting_external_payload,
    meeting_tasks_csv_text,
)
from ..services.outputs import safe_output_stem
from ..services.speaker_registry import speaker_registry_csv_bytes, speaker_attribute_csv_headers
from ..services.transcription.segments import segment_bounds
from ..text_utils import json_load


def register_export_routes(
    app: Flask,
    *,
    database_connection: Any,
    group_analysis_for_row: Any,
    library_row: Any,
    list_speaker_registry: Any,
    meeting_minutes_export_row: Any,
    row_segments: Any,
    row_session_profile: Any,
    row_speaker_profiles: Any,
) -> None:
    def export_speaker_registry():
        content = speaker_registry_csv_bytes(list_speaker_registry())
        return send_file(
            io.BytesIO(content),
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name="gurumoji_speaker_registry.csv",
        )

    def export_transcript_preparation(item_id: str):
        with database_connection() as connection:
            connection.execute("BEGIN")
            row = connection.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
            if row is None:
                return jsonify({"error": "データが見つかりません。"}), 404
            value = preparation.view(connection, row, row_segments(row))
            value["original_segments"] = json_load(row["original_segments_json"], [])
            value["original_status"] = row["original_segments_status"]
            value["versions"] = preparation.read_versions(connection, item_id, include_source=True)
            value["review_history"] = [
                {"revision": v["revision"], "created_at": v["created_at"], "state": json.loads(v["state_json"])}
                for v in connection.execute("SELECT * FROM transcript_preparation_events WHERE item_id=? ORDER BY revision", (item_id,))
            ]
            value["manifest"] = {"schema_version": 1, "encoding": "UTF-8", "row_count": len(value["rows"]),
                "rows_sha256": preparation.digest(value["rows"]), "columns": preparation.FIELDS,
                "missing_value": "JSON null / CSV empty", "order_basis": "saved transcript array; verification is separate",
                "ids": "application-managed IDs; split/merge lineage is researcher-confirmed",
                "csv_note": "CSV applies spreadsheet formula escaping; JSON preserves exact text.",
                "privacy": "Local export may contain personal data. Review before sharing. Media not included."}
        return send_file(io.BytesIO(preparation.encode(value).encode("utf-8")),
                         mimetype="application/json", as_attachment=True, download_name=f"{item_id}_preparation.json")

    def export_library_analysis_json(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        try:
            analysis = group_analysis_for_row(row, include_research_rows=True)
            content = json.dumps(
                analysis,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ).encode("utf-8")
        except (ValueError, TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "分析データを出力できません。元データを確認してください。"}), 500
        return send_file(
            io.BytesIO(content),
            mimetype="application/json; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_analysis.json",
        )

    def export_library_analysis_report(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        try:
            analysis = group_analysis_for_row(row, include_research_rows=True)
            content = focus_group_analysis_report_markdown(analysis).encode("utf-8")
        except (ValueError, TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "分析レポートを出力できません。元データを確認してください。"}), 500
        return send_file(
            io.BytesIO(content),
            mimetype="text/markdown; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:64]}_分析レポート.md",
        )

    def export_library_analysis_xlsx(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        try:
            analysis = group_analysis_for_row(row, include_research_rows=True)
            datasets = {
                dataset: analysis_csv_rows(analysis, dataset)
                for dataset in ANALYSIS_CSV_FIELDS
            }
            content = build_analysis_workbook(analysis, datasets)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "Excel分析データを出力できません。元データを確認してください。"}), 500
        return send_file(
            io.BytesIO(content),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=(
                f"{safe_output_stem(str(row['source_name']))[:64]}_研究分析.xlsx"
            ),
        )

    def export_library_analysis_csv(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        dataset = request.args.get("dataset", "speakers").strip().lower()
        try:
            analysis = group_analysis_for_row(row, include_research_rows=True)
            content = analysis_csv_content(analysis, dataset)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "分析データを出力できません。元データを確認してください。"}), 500
        return send_file(
            io.BytesIO(content),
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name=(
                f"{safe_output_stem(str(row['source_name']))[:64]}_analysis_{dataset}.csv"
            ),
        )

    def export_meeting_json(item_id: str):
        try:
            row, minutes = meeting_minutes_export_row(item_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        content = json.dumps(
            meeting_external_payload(str(row["source_name"]), minutes, item_id),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        return send_file(
            io.BytesIO(content), mimetype="application/json; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_meeting.json",
        )

    def export_meeting_tasks_csv(item_id: str):
        try:
            row, minutes = meeting_minutes_export_row(item_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        content = ("\ufeff" + meeting_tasks_csv_text(minutes)).encode("utf-8")
        return send_file(
            io.BytesIO(content), mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_tasks.csv",
        )

    def export_meeting_minutes_markdown(item_id: str):
        try:
            row, minutes = meeting_minutes_export_row(item_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        content = format_meeting_minutes_markdown(str(row["source_name"]), minutes).encode("utf-8")
        return send_file(
            io.BytesIO(content), mimetype="text/markdown; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_meeting_minutes.md",
        )

    def export_conversation_speakers(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "データが見つかりません。"}), 404
        segments = row_segments(row)
        raw_names = json_load(row["speaker_names_json"], {})
        speaker_names = raw_names if isinstance(raw_names, dict) else {}
        profiles = row_speaker_profiles(row, segments, speaker_names)
        session = row_session_profile(row)
        registry = {item["id"]: item for item in list_speaker_registry()}
        metrics: dict[str, dict[str, float | int]] = {}
        for segment in segments:
            label = str(segment.get("speaker") or "UNKNOWN")
            start, end = segment_bounds(segment)
            data = metrics.setdefault(label, {"count": 0, "seconds": 0.0, "characters": 0})
            data["count"] = int(data["count"]) + 1
            data["seconds"] = float(data["seconds"]) + max(0.0, end - start)
            data["characters"] = int(data["characters"]) + len(str(segment.get("text") or ""))
        custom_headers = sorted({
            key
            for profile in profiles.values()
            for key in (
                registry.get(profile.get("global_speaker_id"), {}).get("attributes", {}) or {}
            )
        })
        fixed_headers = [
            "会話ID", "データ名", "会話種別", "実施日", "場所", "目的",
            "話者ラベル", "表示名", "グローバル話者ID", "参加者コード",
            "話者登録状態", "テーマカラー", "会話役割", "組織", "部署", "役職", "参加状態",
            "会話固有条件", "メモ", "発話数", "発話秒数", "文字数",
        ]
        attribute_headers = speaker_attribute_csv_headers(custom_headers, fixed_headers)
        custom_headers = list(attribute_headers.values())
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fixed_headers + custom_headers)
        writer.writerow({header: analysis_csv_safe(header) for header in fixed_headers + custom_headers})
        for label, profile in profiles.items():
            global_record = registry.get(profile.get("global_speaker_id"), {})
            metric = metrics.get(label, {"count": 0, "seconds": 0.0, "characters": 0})
            export_row = {
                "会話ID": row["id"],
                "データ名": row["source_name"],
                "会話種別": session["session_type"],
                "実施日": session["session_date"],
                "場所": session["location"],
                "目的": session["objective"],
                "話者ラベル": label,
                "表示名": profile["display_name"] or speaker_names.get(label, ""),
                "グローバル話者ID": profile["global_speaker_id"],
                "参加者コード": global_record.get("participant_code", ""),
                "話者登録状態": {
                    "registered": "登録済み",
                    "temporary_single_group": "一時話者（この会話のみ）",
                    "unidentified": "未特定",
                }.get(profile.get("registration_status"), "未特定"),
                "テーマカラー": profile["theme_color"],
                "会話役割": profile["session_role"],
                "組織": profile["organization"],
                "部署": profile["department"],
                "役職": profile["job_title"],
                "参加状態": profile["attendance_status"],
                "会話固有条件": profile["conditions"],
                "メモ": profile["notes"],
                "発話数": metric["count"],
                "発話秒数": round(float(metric["seconds"]), 3),
                "文字数": metric["characters"],
                **{attribute_headers[key]: value
                   for key, value in (global_record.get("attributes", {}) or {}).items()},
            }
            writer.writerow({key: analysis_csv_safe(value) for key, value in export_row.items()})
        content = ("\ufeff" + stream.getvalue()).encode("utf-8")
        return send_file(
            io.BytesIO(content),
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_speakers.csv",
        )

    # Keep established endpoint names: the security hook and the
    # route-map snapshot depend on them.
    endpoints = (
        ('/api/speakers/export.csv', 'export_speaker_registry', export_speaker_registry, 'GET'),
        ('/api/library/<item_id>/preparation/export.json', 'export_transcript_preparation', export_transcript_preparation, 'GET'),
        ('/api/library/<item_id>/analysis/export.json', 'export_library_analysis_json', export_library_analysis_json, 'GET'),
        ('/api/library/<item_id>/analysis/export.md', 'export_library_analysis_report', export_library_analysis_report, 'GET'),
        ('/api/library/<item_id>/analysis/export.xlsx', 'export_library_analysis_xlsx', export_library_analysis_xlsx, 'GET'),
        ('/api/library/<item_id>/analysis/export.csv', 'export_library_analysis_csv', export_library_analysis_csv, 'GET'),
        ('/api/library/<item_id>/meeting.json', 'export_meeting_json', export_meeting_json, 'GET'),
        ('/api/library/<item_id>/meeting-tasks.csv', 'export_meeting_tasks_csv', export_meeting_tasks_csv, 'GET'),
        ('/api/library/<item_id>/meeting-minutes.md', 'export_meeting_minutes_markdown', export_meeting_minutes_markdown, 'GET'),
        ('/api/library/<item_id>/speakers.csv', 'export_conversation_speakers', export_conversation_speakers, 'GET'),
    )
    for rule, endpoint, view, method in endpoints:
        app.add_url_rule(rule, endpoint, view, methods=[method])
