"""DELETE /api/library/<item_id>: move one library item and its managed media to the trash.

Managed media and thumbnails are first moved into a .delete-staging-* folder.
The rows the delete removes are written to a pending trash manifest inside the
same transaction; after the commit the files move into the trash entry
(DATA-01). If the database step fails they are moved back. A crash in between
is resolved at startup by library_trash.recover_pending and
recover_delete_quarantines. Output files and training history are kept, and
tombstones stop the deleted output from being imported again."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any, Callable

from flask import jsonify

from ..text_utils import json_load, utc_now_iso
from ..services import library_trash
from ..services.durable_files import file_sha256, path_is_within
from ..services.outputs import safe_output_stem
from ..services.transcription.options import ACTIVE_JOB_STATUSES


def make_library_deletion(
    *,
    default_output_directory: Callable[[], Any],
    media_directory: Callable[[], Any],
    thumbnail_directory: Callable[[], Any],
    canonical_output_import_path: Any,
    database_connection: Any,
    durable_move: Any,
    jobs: Any,
    jobs_lock: Any,
    library_row: Any,
    local_path_access_allowed: Any,
    reconcile_edit_transactions_before_delete: Any,
    retire_input_vault: Any,
    trash_directory: Callable[[], Path],
    trash_retention_days: Callable[[], int],
) -> Callable[..., Any]:
    def _delete_library_item_locked(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "Data not found."}), 404
        with jobs_lock:
            job = jobs.get(item_id)
            if job and job.status in ACTIVE_JOB_STATUSES:
                return jsonify({"error": "An active job cannot be deleted."}), 409

        edit_recovery_errors, edit_recovery_paths = (
            reconcile_edit_transactions_before_delete(item_id, row)
        )
        if edit_recovery_errors:
            visible_paths = (
                [str(path) for path in edit_recovery_paths]
                if local_path_access_allowed()
                else [path.name for path in edit_recovery_paths]
            )
            return jsonify({
                'error': (
                    '保留中の編集トランザクションを安全に完了できないため、'
                    '削除を中止しました。アプリを再起動して復旧してください。'
                ),
                'recovery_paths': visible_paths,
            }), 409
        row = library_row(item_id)
        if row is None:
            return jsonify({'error': 'Data not found.'}), 404

        nonce = uuid.uuid4().hex
        candidates: list[Path] = []
        media_dir = (media_directory() / item_id).resolve()
        media_root = media_directory().resolve()
        if media_dir.parent == media_root and media_dir.is_dir():
            candidates.append(media_dir)
        for thumbnail_name in (f"text_mining_{item_id}.svg", f"word_cloud_{item_id}.svg"):
            thumbnail = thumbnail_directory() / thumbnail_name
            if thumbnail.is_file() or thumbnail.is_symlink():
                candidates.append(thumbnail)

        moved: list[tuple[Path, Path]] = []
        quarantine_roots: set[Path] = set()

        def restore_assets() -> list[str]:
            errors: list[str] = []
            for quarantined, original in reversed(moved):
                try:
                    if quarantined.exists() or quarantined.is_symlink():
                        original.parent.mkdir(parents=True, exist_ok=True)
                        durable_move(quarantined, original, replace_existing=False)
                except OSError as exc:
                    errors.append(str(exc))
            return errors

        def cleanup_empty_quarantine_roots() -> None:
            for quarantine_root in quarantine_roots:
                try:
                    quarantine_root.rmdir()
                except OSError:
                    # A non-empty directory contains an asset that could not be
                    # restored.  Retain it for manual recovery.
                    pass

        def retained_quarantine_paths() -> list[str]:
            retained = sorted(path for path in quarantine_roots if path.exists())
            if local_path_access_allowed():
                return [str(path) for path in retained]
            return [path.name for path in retained]

        try:
            for original in candidates:
                quarantine_root = original.parent / f".delete-staging-{nonce}"
                quarantine_root.mkdir(parents=True, exist_ok=True)
                quarantine_roots.add(quarantine_root)
                quarantined = quarantine_root / original.name
                durable_move(original, quarantined, replace_existing=False)
                moved.append((quarantined, original))
        except OSError as exc:
            restore_errors = restore_assets()
            cleanup_empty_quarantine_roots()
            retained = retained_quarantine_paths()
            return jsonify({
                "error": f"削除準備に失敗しました: {exc}",
                "restore_errors": restore_errors,
                "recovery_paths": retained,
            }), 409

        trash_entry: Path | None = None
        try:
            with database_connection() as connection:
                files = json_load(row["files_json"], [])
                output_json_paths: set[Path] = set()
                expected_current_json = Path(str(row["output_dir"])) / (
                    f"{safe_output_stem(str(row['source_name']))}_話者分離.json"
                )
                expected_current_canonical = canonical_output_import_path(
                    expected_current_json
                )
                if isinstance(files, list):
                    output_json_paths.update(
                        Path(str(value))
                        for value in files
                        if (
                            Path(str(value)).name.endswith("_話者分離.json")
                            and canonical_output_import_path(Path(str(value)))
                            == expected_current_canonical
                        )
                    )
                provenance_rows = connection.execute(
                    "SELECT canonical_path, content_sha256 "
                    "FROM output_import_provenance WHERE item_id = ?",
                    (item_id,),
                ).fetchall()
                provenance_fingerprints = {
                    str(provenance["canonical_path"]): str(
                        provenance["content_sha256"] or ""
                    )
                    for provenance in provenance_rows
                }
                output_json_paths.update(
                    Path(canonical_path)
                    for canonical_path in provenance_fingerprints
                )
                tombstone_records: list[tuple[str, str]] = []
                for output_path in output_json_paths:
                    canonical_path = canonical_output_import_path(output_path)
                    is_provenance = canonical_path in provenance_fingerprints
                    if (
                        not is_provenance
                        and not path_is_within(output_path, default_output_directory())
                    ):
                        continue
                    provenance_fingerprint = provenance_fingerprints.get(
                        canonical_path, ""
                    )
                    if output_path.is_file():
                        try:
                            fingerprint = file_sha256(output_path)
                        except OSError:
                            fingerprint = provenance_fingerprint if is_provenance else ""
                    else:
                        fingerprint = provenance_fingerprint if is_provenance else ""
                    tombstone_records.append((canonical_path, fingerprint))
                rows = library_trash.snapshot_rows(connection, item_id)
                replaced = [
                    dict(zip(("canonical_path", "content_sha256", "deleted_at"), existing))
                    for canonical_path, _ in tombstone_records
                    for existing in connection.execute(
                        "SELECT canonical_path, content_sha256, deleted_at "
                        "FROM output_import_tombstones WHERE canonical_path=?",
                        (canonical_path,),
                    ).fetchall()
                ]
                for canonical_path, fingerprint in tombstone_records:
                    connection.execute(
                        "INSERT OR REPLACE INTO output_import_tombstones "
                        "(canonical_path, content_sha256, deleted_at) VALUES (?, ?, ?)",
                        (canonical_path, fingerprint, utc_now_iso()),
                    )
                connection.execute(
                    "DELETE FROM output_import_provenance WHERE item_id = ?",
                    (item_id,),
                )
                for table in ("transcript_versions", "transcript_preparations", "transcript_preparation_events",
                              "transcript_changes", "transcript_change_bases"):
                    connection.execute(f"DELETE FROM {table} WHERE item_id=?", (item_id,))
                library_trash.delete_disposable_rows(connection, item_id)
                connection.execute("DELETE FROM library_items WHERE id = ?", (item_id,))
                # Written before the commit so a crash after it still reaches the trash.
                trash_entry = library_trash.begin(
                    trash_directory(), item_id=item_id, source_name=str(row["source_name"]),
                    rows=rows, tombstones_added=[path for path, _ in tombstone_records],
                    tombstones_replaced=replaced,
                    assets=[("media" if quarantined.parent.parent.resolve() == media_root else "thumbnail",
                             quarantined, original) for quarantined, original in moved],
                )
        except (sqlite3.Error, OSError, ValueError) as exc:
            if trash_entry is not None:
                library_trash.discard(trash_entry)
            restore_errors = restore_assets()
            cleanup_empty_quarantine_roots()
            retained = retained_quarantine_paths()
            suffix = f"; restore errors: {'; '.join(restore_errors)}" if restore_errors else ""
            return jsonify({
                "error": f"ライブラリレコードを削除できませんでした: {exc}{suffix}",
                "restore_errors": restore_errors,
                "recovery_paths": retained,
            }), 500

        with jobs_lock:
            jobs.pop(item_id, None)
        retire_input_vault(item_id)
        try:
            cleanup_errors = library_trash.finish(
                trash_entry, lambda source, target: durable_move(source, target, replace_existing=False))
        except (OSError, ValueError, KeyError) as exc:
            cleanup_errors = [str(exc)]
        cleanup_empty_quarantine_roots()
        retained = retained_quarantine_paths()
        days = trash_retention_days()
        result: dict[str, Any] = {
            "ok": True,
            "message": (
                "ライブラリ項目と管理対象メディアをゴミ箱に移しました。"
                + (f"{days}日後に自動で完全に削除されます。" if days else "完全に削除するまでゴミ箱に残ります。")
                + "出力と学習履歴は保持しています。"
            ),
            "trash_entry": trash_entry.name,
            "recovery_paths": retained,
        }
        if cleanup_errors or retained:
            result["cleanup_warning"] = (
                "ライブラリ項目は削除しましたが、一部の隔離ファイルを消去できませんでした。"
                "表示された場所を管理者が確認してください。"
            )
            result["cleanup_errors"] = cleanup_errors
        return jsonify(result)

    return _delete_library_item_locked
