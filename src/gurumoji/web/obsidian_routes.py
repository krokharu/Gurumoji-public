"""HTTP adapters for local-only Obsidian workbench actions."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable

from flask import Flask, jsonify, request


def register_obsidian_routes(
    app: Flask,
    *,
    local_access_allowed: Callable[[], bool],
    library_row: Callable[[str], Any],
    row_segments: Callable[[Any], list[dict[str, Any]]],
    workbench: Callable[[], Any],
    normalize_efforts: Callable[[Any], dict[str, Any]],
    write_lock: Any,
    meeting_export_row: Callable[[str], tuple[Any, dict[str, Any]]],
    meeting_fingerprint: Callable[[dict[str, Any]], str],
    archive_meeting_minutes: Callable[[Any], Any],
    publish_meeting_minutes: Callable[[Any], dict[str, Any]],
    log_warning: Callable[..., None],
    watcher_status: Callable[[], dict[str, Any]] = lambda: {},
) -> None:
    def prepare_finishing(item_id: str):
        if not local_access_allowed():
            return jsonify({"error": "Obsidianの作業ノートは保存PCから開いてください。"}), 403
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "操作の指定が不正です。"}), 400
        try:
            with write_lock:
                row = library_row(item_id)
                if row is None:
                    return jsonify({"error": "会話が見つかりません。"}), 404
                provider = str(payload.get("provider") or "none")
                if provider not in {"none", "openai", "google", "lmstudio"}:
                    raise ValueError("AIプロバイダーが不正です。")
                current = workbench()
                state = current.prepare(
                    item_id, row["source_name"], row_segments(row),
                    revision=int(row["revision_count"] or 0), provider=provider,
                    source_kind="saved_transcript", jev_compare=payload.get("jev_compare") is True,
                    ai_efforts=normalize_efforts(payload.get("ai_efforts")),
                )
                if not state.get("ready"):
                    current.activate(item_id, int(row["revision_count"] or 0), row_segments(row))
                    state = current.load(item_id)
                return jsonify(current.public(state))
        except (OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    def finishing_status(item_id: str):
        if not local_access_allowed():
            return jsonify({"error": "保存PCから確認してください。"}), 403
        try:
            state = workbench().load(item_id)
            # Without the watcher, checks in the operation note are never read (OBS-09).
            watcher = watcher_status()
            if not state:
                return jsonify({"status": "unprepared", "watcher": watcher})
            return jsonify({
                "status": state.get("status", "ready"),
                "message": state.get("message", ""),
                "watcher": watcher,
            })
        except (OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    def meeting_status(item_id: str):
        if not local_access_allowed():
            return jsonify({"error": "Obsidian連携は保存PCから操作してください。"}), 403
        try:
            _row, minutes = meeting_export_row(item_id)
            current = workbench()
            return jsonify(current.meeting_public(current.load(item_id), meeting_fingerprint(minutes)))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, json.JSONDecodeError):
            return jsonify({"error": "Obsidian の会議議事録状態を確認できませんでした。"}), 500

    def save_meeting(item_id: str):
        if not local_access_allowed():
            return jsonify({"error": "Obsidian連携は保存PCから操作してください。"}), 403
        try:
            row, _minutes = meeting_export_row(item_id)
            try:
                with write_lock:
                    archive_meeting_minutes(row)
            except (OSError, ValueError, TypeError, LookupError, sqlite3.Error):
                log_warning("会議議事録を分析履歴として保存できませんでした。", exc_info=True)
            return jsonify(publish_meeting_minutes(row))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, TypeError, json.JSONDecodeError):
            return jsonify({"error": "会議議事録をObsidianへ保存できませんでした。"}), 500

    app.add_url_rule(
        "/api/library/<item_id>/obsidian-finishing", "prepare_obsidian_finishing_route",
        prepare_finishing, methods=["POST"],
    )
    app.add_url_rule(
        "/api/library/<item_id>/obsidian-finishing", "obsidian_finishing_status_route",
        finishing_status, methods=["GET"],
    )
    app.add_url_rule(
        "/api/library/<item_id>/meeting-obsidian", "meeting_obsidian_status",
        meeting_status, methods=["GET"],
    )
    app.add_url_rule(
        "/api/library/<item_id>/meeting-obsidian", "save_meeting_to_obsidian",
        save_meeting, methods=["POST"],
    )
