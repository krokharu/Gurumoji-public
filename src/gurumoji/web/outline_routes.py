"""HTTP adapter for re-running the AI outline of a saved conversation."""

from __future__ import annotations

import sqlite3
from typing import Callable

from flask import Blueprint, Flask, jsonify, request

from ..handlers.outline_rerun import OutlineRerunError, OutlineRerunHandler


def register_outline_routes(
    app: Flask,
    handler: Callable[[], OutlineRerunHandler],
    ai_providers: frozenset[str] | set[str],
) -> None:
    blueprint = Blueprint("library_outline", __name__)

    @blueprint.post("/api/library/<item_id>/outline")
    def rerun_library_outline(item_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "アウトライン再実行の指定が JSON ではありません。"}), 400
        provider = str(payload.get("provider") or "").strip().casefold()
        if provider not in ai_providers:
            return jsonify({"error": "OpenAI、Google Gemini、またはローカルLLMを選択してください。"}), 400
        expected_revision = payload.get("revision_count")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
            return jsonify({"error": "最新の編集内容を保存してから実行してください。"}), 400
        try:
            return jsonify(handler().run(item_id, provider=provider, expected_revision=expected_revision))
        except OutlineRerunError as exc:
            body = {"error": str(exc)}
            if exc.current_revision is not None:
                body.update({"conflict": True, "current_revision": exc.current_revision})
            return jsonify(body), exc.status
        except (OSError, sqlite3.Error) as exc:
            return jsonify({"error": f"アウトラインを保存できません: {exc}"}), 500

    app.register_blueprint(blueprint)
