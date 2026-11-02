"""HTTP adapters for the correction-training dataset downloads."""

from __future__ import annotations

import io
import sqlite3
from typing import Any, Callable

from flask import Flask, jsonify, send_file

from ..services.training_corpus import training_export_contents


def register_training_routes(
    app: Flask,
    *,
    remote_access_enabled: Callable[[], bool],
    database_connection: Any,
    refresh_training_exports: Any,
    training_events_from_connection: Any,
) -> None:
    def training_status():
        try:
            with database_connection() as connection:
                events = training_events_from_connection(connection)
        except (OSError, sqlite3.Error):
            app.logger.exception("Could not read canonical training events")
            return jsonify({"error": "学習履歴を読み取れません。"}), 500
        event_count = len(events)
        ready_count = sum(int(bool(event.get("ready_for_kushinada"))) for event in events)
        downloads_allowed = not remote_access_enabled()
        return jsonify({
            "event_count": event_count,
            "ready_count": ready_count,
            "jsonl_url": (
                "/api/training/corrections.jsonl"
                if downloads_allowed and event_count > 0
                else None
            ),
            "manifest_url": (
                "/api/training/manifest.csv"
                if downloads_allowed and event_count > 0
                else None
            ),
        })

    def download_training_jsonl():
        if remote_access_enabled():
            return jsonify({"error": "Raw training data downloads are disabled for remote access."}), 403
        try:
            events = refresh_training_exports()
        except (OSError, sqlite3.Error) as exc:
            return jsonify({"error": f"学習データを生成できません: {exc}"}), 500
        if not events:
            return jsonify({"error": "学習データはまだありません。"}), 404
        jsonl_content, _manifest_content = training_export_contents(events)
        return send_file(
            io.BytesIO(jsonl_content.encode("utf-8")),
            mimetype="application/x-ndjson; charset=utf-8",
            as_attachment=True,
            download_name="kushinada_corrections.jsonl",
        )

    def download_training_manifest():
        if remote_access_enabled():
            return jsonify({"error": "Raw training data downloads are disabled for remote access."}), 403
        try:
            events = refresh_training_exports()
        except (OSError, sqlite3.Error) as exc:
            return jsonify({"error": f"学習データを生成できません: {exc}"}), 500
        if not events:
            return jsonify({"error": "学習データはまだありません。"}), 404
        _jsonl_content, manifest_content = training_export_contents(events)
        return send_file(
            io.BytesIO(("\ufeff" + manifest_content).encode("utf-8")),
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name="kushinada_manifest.csv",
        )

    # Keep established endpoint names: the security hook and the
    # route-map snapshot depend on them.
    endpoints = (
        ('/api/training', 'training_status', training_status, 'GET'),
        ('/api/training/corrections.jsonl', 'download_training_jsonl', download_training_jsonl, 'GET'),
        ('/api/training/manifest.csv', 'download_training_manifest', download_training_manifest, 'GET'),
    )
    for rule, endpoint, view, method in endpoints:
        app.add_url_rule(rule, endpoint, view, methods=[method])
