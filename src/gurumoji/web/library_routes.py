"""HTTP adapters for the library: listing, items, media, thumbnails and files."""

from __future__ import annotations

import mimetypes
import sqlite3
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request, send_file

from ..handlers.analysis_commands import ComparisonRequestError
from ..services.durable_files import path_is_within
from ..services.library_trash import TrashError
from ..services.media_files import media_kind
from ..text_utils import json_load
from ..services import data_catalog
from ..services.library_listing import list_library_items


def register_library_routes(
    app: Flask,
    *,
    media_directory: Callable[[], Any],
    _delete_library_item_locked: Any,
    analysis_archive_store: Any,
    archive_source_stamp: Any,
    build_interview_comparison: Any,
    database_connection: Any,
    file_dialog_lock: Any,
    generate_video_thumbnail: Any,
    generate_word_cloud_thumbnail: Any,
    interview_comparison_request: Any,
    library_public: Any,
    library_row: Any,
    library_write_lock: Any,
    local_path_access_allowed: Any,
    manual_output_directory: Any,
    resolve_local_media_path: Any,
    row_segments: Any,
    runtime_info: Any,
    upsert_library_item: Any,
    list_library_trash: Callable[[], dict[str, Any]],
    restore_library_trash: Callable[[str], str],
    purge_library_trash: Callable[[str], None],
) -> None:
    def select_input_file():
        if not local_path_access_allowed():
            return jsonify({"error": "Local filesystem selection is disabled for remote access."}), 403
        if not runtime_info()["native_file_dialog"]:
            return jsonify({
                "error": "この実行環境ではOSのファイル選択画面を利用できません。",
                "hint": "ブラウザーのファイルアップロードを使用してください。",
                "browser_upload_only": True,
            }), 409
        if not file_dialog_lock.acquire(blocking=False):
            return jsonify({"error": "ファイル選択画面をすでに開いています。"}), 409
        try:
            try:
                import tkinter as tk
                from tkinter import filedialog
            except Exception as exc:
                return jsonify({
                    "error": "Windows のファイル選択画面を開けませんでした。",
                    "hint": "ファイルのフルパスを入力欄へ直接貼り付けてください。",
                    "details": str(exc),
                }), 500

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            root.update()
            try:
                selected = filedialog.askopenfilename(
                    parent=root,
                    title="処理する音声・動画ファイルを選択",
                    filetypes=[
                        ("音声・動画", "*.mp4 *.m4v *.mov *.mkv *.wav *.mp3 *.m4a *.flac"),
                        ("動画", "*.mp4 *.m4v *.mov *.mkv"),
                        ("音声", "*.wav *.mp3 *.m4a *.flac"),
                        ("すべてのファイル", "*.*"),
                    ],
                )
            finally:
                root.destroy()

            if not selected:
                return jsonify({"ok": True, "cancelled": True})
            path = resolve_local_media_path(selected)
            return jsonify({
                "ok": True,
                "cancelled": False,
                "path": str(path),
                "name": path.name,
                "size": path.stat().st_size,
                "media_kind": media_kind(path),
            })
        except (ValueError, OSError) as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            file_dialog_lock.release()

    def source_thumbnail():
        if not local_path_access_allowed():
            return jsonify({"error": "Local filesystem thumbnails are disabled for remote access."}), 403
        try:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict) or not isinstance(payload.get("path"), str):
                raise ValueError("A media path is required.")
            source_path = resolve_local_media_path(payload["path"])
            thumbnail_path = generate_video_thumbnail(source_path)
            return send_file(thumbnail_path, mimetype="image/jpeg", conditional=True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
            return jsonify({"error": f"サムネイルを作成できません: {exc}"}), 500

    def list_library():
        payload, status = list_library_items(
            request.args, database_connection=database_connection, library_public=library_public,
        )
        return jsonify(payload), status

    def compare_group_interviews():
        if request.content_length and request.content_length > 64 * 1024:
            return jsonify({"error": "比較対象の指定が大きすぎます。"}), 413
        try:
            with library_write_lock:
                payload = request.get_json(silent=True)
                rows, allow_different = interview_comparison_request(payload)
                with database_connection() as connection:
                    selection = data_catalog.freeze(connection, [str(row['id']) for row in rows],
                        group_ids=[payload['data_group_id']] if payload.get('data_group_id') else [], group_by=payload.get('group_by'))
                result = build_interview_comparison(rows, allow_different_content=allow_different)
                result['target_snapshot'] = selection
                result["input_fingerprints"] = {str(row["id"]): archive_source_stamp(row) for row in rows}
        except ComparisonRequestError as exc:
            return jsonify({"error": str(exc)}), exc.status
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 409
        except (OverflowError, sqlite3.Error):
            return jsonify({"error": "インタビュー比較を生成できません。"}), 500
        return jsonify(result)

    def list_interview_comparison_runs():
        store = analysis_archive_store()
        local = local_path_access_allowed()
        return jsonify({"runs": [{**store.public(run, local=local), "member_ids": store.members(run["id"])}
                                 for run in store.list_comparisons()]})

    def create_library_item():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "追加内容が JSON ではありません。"}), 400
        source_name = str(payload.get("source_name") or "新規文字起こし").strip()
        if any(ord(character) < 32 or ord(character) == 127 for character in source_name):
            return jsonify({"error": "Source names cannot contain control characters."}), 400
        if not source_name or len(source_name) > 255:
            return jsonify({"error": "データ名は 1～255 文字で指定してください。"}), 400
        item_id = uuid.uuid4().hex
        try:
            row = upsert_library_item(
                item_id=item_id,
                source_name=source_name,
                output_dir=manual_output_directory(source_name, item_id),
                media_path=None, language=None, segments=[], speaker_names={}, outline=None,
                emotion_analysis=None, files=[], write_srt=True, write_json=True,
            )
            return jsonify(library_public(row)), 201
        except (OSError, sqlite3.Error) as exc:
            return jsonify({"error": f"データを追加できません: {exc}"}), 500

    def get_library_item(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "データが見つかりません。"}), 404
        return jsonify(library_public(row))

    def library_thumbnail(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "データが見つかりません。"}), 404
        try:
            thumbnail_path = generate_word_cloud_thumbnail(
                item_id,
                str(row["source_name"]),
                row_segments(row),
            )
            return send_file(
                thumbnail_path,
                mimetype="image/svg+xml",
                conditional=True,
                max_age=86400,
            )
        except OSError as exc:
            return jsonify({"error": f"ワードクラウドを作成できません: {exc}"}), 500

    def delete_library_item(item_id: str):
        with library_write_lock:
            return _delete_library_item_locked(item_id)

    # DATA-01: deleted conversations wait in the trash until restored, purged or expired.
    def list_trash():
        try:
            return jsonify(list_library_trash())
        except OSError:
            return jsonify({"error": "ゴミ箱を読み込めませんでした。"}), 500

    def restore_trash_entry(entry_id: str):
        with library_write_lock:
            try:
                item_id = restore_library_trash(entry_id)
            except TrashError as exc:
                return jsonify({"error": str(exc)}), 409
            except (OSError, sqlite3.Error, ValueError, KeyError):
                return jsonify({"error": "ゴミ箱から復元できませんでした。ゴミ箱の項目は残っています。"}), 500
        return jsonify({"ok": True, "item_id": item_id, "message": "ゴミ箱から復元しました。"})

    def purge_trash_entry(entry_id: str):
        with library_write_lock:
            try:
                purge_library_trash(entry_id)
            except TrashError as exc:
                return jsonify({"error": str(exc)}), 404
            except OSError:
                return jsonify({"error": "ゴミ箱の項目を完全に削除できませんでした。"}), 500
        return jsonify({"ok": True, "message": "ゴミ箱の項目を完全に削除しました。"})

    def stream_library_media(item_id: str):
        row = library_row(item_id)
        if row is None or not row["media_path"]:
            return jsonify({"error": "元の音声・動画が保存されていません。"}), 404
        media_path = Path(row["media_path"])
        expected_media_dir = media_directory() / item_id
        if not path_is_within(media_path, expected_media_dir) or not media_path.is_file():
            return jsonify({"error": "元の音声・動画が見つかりません。"}), 404
        return send_file(media_path, conditional=True, mimetype=mimetypes.guess_type(media_path.name)[0])

    def download_library_file(item_id: str, filename: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "データが見つかりません。"}), 404
        paths = [Path(value) for value in json_load(row["files_json"], []) if isinstance(value, str)]
        output_root = Path(row["output_dir"])
        matching = next(
            (
                path for path in paths
                if path.name == filename and path_is_within(path, output_root)
            ),
            None,
        )
        if matching is None or not matching.is_file():
            return jsonify({"error": "出力ファイルが見つかりません。"}), 404
        return send_file(matching, as_attachment=True, download_name=matching.name)

    # Keep established endpoint names: the security hook and the
    # route-map snapshot depend on them.
    endpoints = (
        ('/api/select-input', 'select_input_file', select_input_file, 'POST'),
        ('/api/source-thumbnail', 'source_thumbnail', source_thumbnail, 'POST'),
        ('/api/library', 'list_library', list_library, 'GET'),
        ('/api/library/interview-comparison', 'compare_group_interviews', compare_group_interviews, 'POST'),
        ('/api/library/interview-comparison/runs', 'list_interview_comparison_runs', list_interview_comparison_runs, 'GET'),
        ('/api/library', 'create_library_item', create_library_item, 'POST'),
        ('/api/library/<item_id>', 'get_library_item', get_library_item, 'GET'),
        ('/api/library/<item_id>/thumbnail', 'library_thumbnail', library_thumbnail, 'GET'),
        ('/api/library/<item_id>', 'delete_library_item', delete_library_item, 'DELETE'),
        ('/api/library/trash', 'list_library_trash', list_trash, 'GET'),
        ('/api/library/trash/<entry_id>/restore', 'restore_library_trash', restore_trash_entry, 'POST'),
        ('/api/library/trash/<entry_id>', 'purge_library_trash', purge_trash_entry, 'DELETE'),
        ('/api/library/<item_id>/media', 'stream_library_media', stream_library_media, 'GET'),
        ('/api/library/<item_id>/files/<path:filename>', 'download_library_file', download_library_file, 'GET'),
    )
    for rule, endpoint, view, method in endpoints:
        app.add_url_rule(rule, endpoint, view, methods=[method])
