"""HTTP adapters for the library: listing, items, media, thumbnails and files."""

from __future__ import annotations

import mimetypes
import datetime
import math
import sqlite3
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request, send_file

from ..handlers.analysis_commands import ComparisonRequestError
from ..services.durable_files import path_is_within
from ..services.library_trash import TrashError
from ..services.library_rows import emotion_values
from ..services.media_files import media_kind
from ..services.transcription.segments import default_speaker_name
from ..text_utils import json_load
from ..services import data_catalog


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
        try:
            page_limit = int(request.args.get('limit', 0))
            page_offset = int(request.args.get('offset', 0))
            if not 0 <= page_limit <= 200 or not 0 <= page_offset <= 2**63 - 1:
                raise ValueError()
        except (ValueError, OverflowError):
            return jsonify(error='一覧のページ指定が正しくありません。'), 400
        keyword = request.args.get("keyword", "").strip().casefold()
        speaker_filter = request.args.get("speaker", "").strip().casefold()
        emotion_filter = request.args.get("emotion", "").strip().casefold()
        group_filter = request.args.get("group", "").strip()
        sort_key = request.args.get("sort", "updated_desc").strip()
        date_from = request.args.get("recorded_from", "").strip()
        date_to = request.args.get("recorded_to", "").strip()
        try:
            duration_min = float(request.args["media_duration_min"]) if request.args.get("media_duration_min") else None
            duration_max = float(request.args["media_duration_max"]) if request.args.get("media_duration_max") else None
            for value in (duration_min, duration_max):
                if value is not None and (not math.isfinite(value) or value < 0):
                    raise ValueError
            for value in (date_from, date_to):
                if value:
                    datetime.date.fromisoformat(value)
            if date_from and date_to and date_from > date_to:
                raise ValueError
            if duration_min is not None and duration_max is not None and duration_min > duration_max:
                raise ValueError
        except ValueError:
            return jsonify({"error": "収録日・メディアの長さの条件を確認してください。"}), 400
        with database_connection() as connection:
            catalog = data_catalog.catalog(connection)
            selected_group = request.args.get('data_group', '')
            selected_tag = request.args.get('tag', '')
            try:
                selected_members = set(data_catalog.members(connection, selected_group)) if selected_group else None
            except LookupError as exc:
                return jsonify(error=str(exc)), 404
            catalog_items = {item['id']: item for item in catalog['items']}
            rows = connection.execute("""SELECT i.*, m.duration_seconds AS media_duration_seconds,
                m.media_created_at AS media_created_at FROM library_items i
                LEFT JOIN media_assets m ON m.item_id=i.id AND m.role='stored'
                ORDER BY i.updated_at DESC""").fetchall()
            group_rows = connection.execute(
                """
                SELECT g.id, g.name, g.created_at, g.updated_at,
                       COUNT(items.id) AS item_count
                FROM library_groups AS g
                LEFT JOIN library_items AS items ON items.group_id = g.id
                GROUP BY g.id, g.name, g.created_at, g.updated_at
                ORDER BY g.name COLLATE NOCASE, g.created_at
                """
            ).fetchall()

        groups = [
            {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "item_count": int(row["item_count"] or 0),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in group_rows
        ]
        group_names = {group["id"]: group["name"] for group in groups}

        all_speakers: set[str] = set()
        all_emotions: set[str] = set()
        candidates: list[tuple[sqlite3.Row, int, list[dict[str, Any]], list[str], str, list[str]]] = []
        for row in rows:
            recording_date = str(row["media_created_at"] or "")[:10]
            duration = row["media_duration_seconds"]
            if (date_from or date_to) and (not recording_date or date_from and recording_date < date_from or date_to and recording_date > date_to):
                continue
            if (duration_min is not None or duration_max is not None) and (
                duration is None or duration_min is not None and duration < duration_min or duration_max is not None and duration > duration_max
            ):
                continue
            # Parsed once per row and without stable IDs, which the list does not show (PERF-01).
            raw_segments = json_load(row["segments_json"], [])
            segments = [item for item in raw_segments if isinstance(item, dict)] if isinstance(raw_segments, list) else []
            names = json_load(row["speaker_names_json"], {})
            if not isinstance(names, dict):
                names = {}
            speakers = sorted({
                str(names.get(str(item.get("speaker") or "")) or default_speaker_name(item.get("speaker")))
                for item in segments if item.get("speaker")
            })
            emotions = sorted({value for item in segments for value in emotion_values(item)})
            all_speakers.update(speakers)
            all_emotions.update(emotions)
            searchable_segments = [str(item.get("text") or "") for item in segments]
            match_count = sum(1 for text_value in searchable_segments if keyword and keyword in text_value.casefold())
            source_match = bool(keyword and keyword in str(row["source_name"]).casefold())
            if keyword and not match_count and not source_match:
                continue
            if speaker_filter and not any(speaker_filter == value.casefold() for value in speakers):
                continue
            if emotion_filter and not any(emotion_filter == value.casefold() for value in emotions):
                continue
            row_group_id = str(row["group_id"] or "")
            if selected_members is not None and row['id'] not in selected_members:
                continue
            if selected_tag and selected_tag not in catalog_items[row['id']]['tag_ids']:
                continue
            if group_filter == "__ungrouped__" and row_group_id:
                continue
            if group_filter and group_filter != "__ungrouped__" and row_group_id != group_filter:
                continue
            candidates.append((row, match_count, segments, emotions, group_names.get(row_group_id, ""), speakers))

        if sort_key in ("recorded_desc", "media_duration_desc"):
            field = "media_created_at" if sort_key == "recorded_desc" else "media_duration_seconds"
            candidates.sort(key=lambda item: (item[0][field] is not None, item[0][field] if item[0][field] is not None else "" if field == "media_created_at" else -1), reverse=True)
        elif sort_key == "created_desc":
            candidates.sort(key=lambda item: item[0]["created_at"], reverse=True)
        elif sort_key == "speaker":
            candidates.sort(key=lambda item: ((item[5][0] if item[5] else "￿"), item[0]["updated_at"]))
        elif sort_key == "emotion":
            candidates.sort(key=lambda item: ((item[3][0] if item[3] else "￿"), item[0]["updated_at"]))
        elif sort_key == "keyword":
            candidates.sort(key=lambda item: (item[1], item[0]["updated_at"]), reverse=True)
        elif sort_key == "name":
            candidates.sort(key=lambda item: str(item[0]["source_name"]).casefold())
        elif sort_key == "group":
            candidates.sort(key=lambda item: (
                not bool(item[4]), item[4].casefold(), str(item[0]["source_name"]).casefold()
            ))
        else:
            candidates.sort(key=lambda item: item[0]["updated_at"], reverse=True)
        total = len(candidates)
        page_candidates = candidates[page_offset:page_offset + page_limit] if page_limit else candidates
        return jsonify({
            "items": [
                library_public(row, full=False, match_count=count, group_name=group_name, segments=segments)
                for row, count, segments, _, group_name, _ in page_candidates
            ],
            "total": total,
            "pagination": {"offset": page_offset, "limit": page_limit or total,
                           "has_more": bool(page_limit and page_offset + len(page_candidates) < total)},
            "groups": groups,
            "data_groups": catalog['groups'],
            "tags": catalog['tags'],
            "facets": {
                "speakers": sorted(all_speakers),
                "emotions": sorted(all_emotions),
                "groups": groups,
            },
        })

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
