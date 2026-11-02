"""Explicit notation preview, apply and researcher review endpoints."""
import sqlite3
from flask import jsonify, request


def register_notation_routes(app, *, service):
    def invoke(operation):
        try:
            return jsonify(operation())
        except LookupError as exc:
            return jsonify(error=str(exc)), 404
        except (ValueError, TypeError) as exc:
            return jsonify(error=str(exc)), 409
        except (OSError, sqlite3.Error):
            return jsonify(error="表記の保存を完了できませんでした。再表示して保存状態を確認してください。"), 500

    def payload():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise ValueError("JSONオブジェクトで指定してください。")
        return value

    def preview(item_id):
        return invoke(lambda: service().preview(item_id, request.args.get("provider", "none")))

    def execute(item_id):
        return invoke(lambda: service().execute(item_id, payload()))

    def review(item_id):
        return invoke(lambda: service().review(item_id))

    def change(item_id):
        return invoke(lambda: service().change(item_id, payload()))

    app.add_url_rule("/api/library/<item_id>/notation/preview", "notation_preview", preview, methods=["GET"])
    app.add_url_rule("/api/library/<item_id>/notation", "notation_execute", execute, methods=["POST"])
    app.add_url_rule("/api/library/<item_id>/notation", "notation_review", review, methods=["GET"])
    app.add_url_rule("/api/library/<item_id>/notation/review", "notation_change", change, methods=["POST"])
