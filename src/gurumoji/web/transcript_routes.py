"""保存済み文字起こしの編集と確認状態を扱うHTTP境界。"""
from __future__ import annotations

import sqlite3
import subprocess

from flask import jsonify, request

from .. import transcript_preparation as preparation
from ..handlers.transcript_errors import TranscriptConflictError


def register_transcript_routes(app, *, update_item, connect, write_lock, row_segments):
    def update_transcript(item_id):
        try:
            return jsonify(update_item(item_id, request.get_json(silent=True)))
        except TranscriptConflictError as exc:
            return jsonify(error=str(exc), conflict=True, current_revision=exc.current_revision), 409
        except LookupError as exc:
            return jsonify(error=str(exc)), 404
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except (OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
            return jsonify(error=f"保存できません: {exc}"), 500

    def update_preparation(item_id):
        if request.content_length and request.content_length > 16 * 1024 * 1024:
            return jsonify(error="確認データが大きすぎます。"), 413
        try:
            with write_lock, connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
                if row is None:
                    return jsonify(error="データが見つかりません。"), 404
                result = preparation.save(db, row, row_segments(row), request.get_json(silent=True))
            return jsonify(result)
        except preparation.Conflict as exc:
            return jsonify(error=str(exc), conflict=True), 409
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    app.add_url_rule('/api/library/<item_id>', 'update_library_item', update_transcript, methods=['PUT'])
    app.add_url_rule('/api/library/<item_id>/preparation', 'update_transcript_preparation', update_preparation, methods=['PUT'])
