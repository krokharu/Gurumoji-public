"""Trash for conversations deleted from the library (DATA-01).

Deleting a conversation moves its managed media and thumbnails into
``<data>/trash/<entry>/`` together with a manifest of the database rows the
delete removed, so the whole conversation can be restored. The manifest is
written as ``manifest.pending.json`` before the database commit and becomes
``manifest.json`` once the files are in the trash; startup recovery finishes
an entry a crash left pending. Entries older than the retention period are
purged at startup, and 0 days keeps them until they are purged by hand.
Output files, analysis runs and Vault notes are never touched here.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .durable_files import write_durably
from . import change_log

MANIFEST = "manifest.json"
PENDING = "manifest.pending.json"
ENTRY_PATTERN = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{12}")
DEFAULT_RETENTION_DAYS = 30
# Rows removed by a library delete, restored in this order.
ITEM_TABLES = ("library_items", "transcript_versions", "transcript_preparations",
               "transcript_preparation_events", "output_import_provenance",
               "transcript_change_bases", "transcript_changes",
               "conversation_attributes", "conversation_tags", "data_group_members", "analysis_definitions")
# Disposable query copies and derived facts are deleted, but not put in the manifest.
DISPOSABLE_ITEM_TABLES = (
    "conversation_speakers", "conversation_segments", "media_assets", "segment_embeddings", "segment_labels",
)
ASSET_FOLDERS = {"media": "media", "thumbnail": "thumbnails"}


class TrashError(RuntimeError):
    """A trash operation that cannot proceed; the message is safe to show."""


def retention_days(value: str | None) -> int:
    """MOJIOKOSI_TRASH_RETENTION_DAYS: whole days, 0 keeps entries until purged by hand."""
    try:
        days = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS
    return days if 0 <= days <= 36500 else DEFAULT_RETENTION_DAYS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes__": base64.b64encode(value).decode("ascii")}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"__bytes__"}:
        return base64.b64decode(value["__bytes__"])
    return value


def _table_exists(connection: Any, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def snapshot_rows(connection: Any, item_id: str) -> dict[str, list[dict[str, Any]]]:
    """Copy every row a library delete removes for one conversation."""
    rows: dict[str, list[dict[str, Any]]] = {}
    for table in ITEM_TABLES:
        if not _table_exists(connection, table):
            continue
        key = "id" if table == "library_items" else "item_id"
        cursor = connection.execute(f"SELECT * FROM {table} WHERE {key}=?", (item_id,))
        names = [column[0] for column in cursor.description]
        rows[table] = [{name: _encode(value) for name, value in zip(names, row)} for row in cursor.fetchall()]
    if _table_exists(connection, "change_log"):
        cursor = connection.execute("SELECT * FROM change_log WHERE " + change_log.conversation_condition(),
                                    change_log.conversation_parameters(item_id))
        names = [column[0] for column in cursor.description]
        rows["change_log"] = [dict(zip(names, row)) for row in cursor.fetchall()]
    return rows


def delete_disposable_rows(connection: Any, item_id: str) -> None:
    """Run within the library-delete transaction; tolerate later-stage tables being absent."""
    if _table_exists(connection, "data_group_members"):
        targets = [("data_groups", r[0]) for r in connection.execute(
            "SELECT group_id FROM data_group_members WHERE item_id=?", (item_id,))]
        with change_log.tracking(connection, targets, origin="rule", process="conversation_trash"):
            connection.execute("DELETE FROM data_group_members WHERE item_id=?", (item_id,))
    if _table_exists(connection, "analysis_definitions"):
        connection.execute("DELETE FROM analysis_definitions WHERE item_id=?", (item_id,))
    for table in DISPOSABLE_ITEM_TABLES:
        if _table_exists(connection, table):
            connection.execute(f"DELETE FROM {table} WHERE item_id=?", (item_id,))
    if _table_exists(connection, "change_log"):
        connection.execute("DELETE FROM change_log WHERE " + change_log.conversation_condition(),
                           change_log.conversation_parameters(item_id))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    write_durably(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifest is not an object")
    return value


def _manifest_assets(manifest: dict[str, Any], *, pending: bool = False) -> list[dict[str, Any]]:
    """Validate recovery identities before making any move or delete decision."""
    item_id, assets = manifest.get("item_id"), manifest.get("assets")
    invalid = "ゴミ箱の移動記録の形式または識別情報が不正です。復旧が必要です。"
    if (type(manifest.get("version")) is not int or manifest["version"] != 1
            or not isinstance(item_id, str) or not item_id or item_id in {".", ".."}
            or "/" in item_id or "\\" in item_id or not isinstance(assets, list)):
        raise ValueError(invalid)
    identities = {"media": {item_id}, "thumbnail": {
        f"text_mining_{item_id}.svg", f"word_cloud_{item_id}.svg",
    }}
    for asset in assets:
        if (not isinstance(asset, dict) or not isinstance(asset.get("kind"), str)
                or asset["kind"] not in ASSET_FOLDERS or not isinstance(asset.get("name"), str)
                or asset["name"] not in identities[asset["kind"]]):
            raise ValueError(invalid)
        if pending:
            quarantine = asset.get("quarantine")
            if not isinstance(quarantine, str) or Path(quarantine).name != asset["name"]:
                raise ValueError(invalid)
        if (not pending or "in_trash" in asset) and type(asset.get("in_trash")) is not bool:
            raise ValueError(invalid)
    return assets


def _entry_path(root: Path, entry_id: str) -> Path:
    if not ENTRY_PATTERN.fullmatch(str(entry_id or "")):
        raise TrashError("ゴミ箱の項目が見つかりません。")
    return root / entry_id


def _size(path: Path) -> int:
    total = 0
    for current, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(current) / name).stat().st_size
            except OSError:
                pass
    return total


def begin(root: Path, *, item_id: str, source_name: str, rows: dict[str, Any],
          tombstones_added: list[str], tombstones_replaced: list[dict[str, Any]],
          assets: list[tuple[str, Path, Path]]) -> Path:
    """Write the pending manifest; call inside the delete transaction, before commit.

    ``assets`` holds (kind, quarantined path, original path) for each moved file.
    """
    root.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    entry = root / f"{stamp}-{uuid.uuid4().hex[:12]}"
    entry.mkdir()
    _write_json(entry / PENDING, {
        "version": 1,
        "item_id": item_id,
        "source_name": source_name,
        "deleted_at": _now().isoformat(timespec="seconds"),
        "rows": rows,
        "tombstones_added": tombstones_added,
        "tombstones_replaced": tombstones_replaced,
        "assets": [{"kind": kind, "name": original.name, "quarantine": str(quarantined)}
                   for kind, quarantined, original in assets],
    })
    return entry


def discard(entry: Path) -> None:
    """The delete did not commit: drop the pending entry."""
    shutil.rmtree(entry, ignore_errors=True)


def finish(entry: Path, move: Callable[[Path, Path], None]) -> list[str]:
    """Move quarantined files into the entry and mark it trashed; returns errors."""
    manifest = _read_json(entry / PENDING)
    assets = _manifest_assets(manifest, pending=True)
    errors: list[str] = []
    for asset in assets:
        source = Path(asset["quarantine"])
        target = entry / ASSET_FOLDERS[asset["kind"]] / asset["name"]
        if source.exists() or source.is_symlink():
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                move(source, target)
                try:
                    source.parent.rmdir()
                except OSError:
                    pass
            except OSError as exc:
                errors.append(str(exc))
        asset["in_trash"] = target.exists() or target.is_symlink()
        if not asset["in_trash"] and not (source.exists() or source.is_symlink()):
            errors.append(f"ゴミ箱へ移動するファイルが見つかりません: {asset['name']}")
    if errors:
        # Keep the recovery journal, including every original quarantine path.
        # A subsequent startup or restore can retry without losing partial moves.
        _write_json(entry / PENDING, manifest)
        _write_json(entry / MANIFEST, manifest)
        return errors
    for asset in manifest["assets"]:
        asset.pop("quarantine", None)
    _write_json(entry / MANIFEST, manifest)
    (entry / PENDING).unlink()
    return errors


def recover_pending(root: Path, *, row_exists: Callable[[str], bool],
                    move: Callable[[Path, Path], None]) -> list[str]:
    """At startup, finish or drop entries a crash left pending.

    Runs before the delete-quarantine recovery so quarantined media of a
    committed delete reaches the trash instead of being removed.
    """
    warnings: list[str] = []
    if not root.is_dir():
        return warnings
    for entry in sorted(root.iterdir()):
        if not ENTRY_PATTERN.fullmatch(entry.name) or not (entry / PENDING).is_file():
            continue
        try:
            manifest = _read_json(entry / PENDING)
            _manifest_assets(manifest, pending=True)
            if row_exists(str(manifest["item_id"])):
                discard(entry)  # the delete rolled back; quarantine recovery restores the files
            else:
                warnings.extend(finish(entry, move))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            warnings.append(f"ゴミ箱の保留項目 {entry.name} を処理できませんでした: {exc}")
    return warnings


def protected_quarantine_assets(root: Path) -> set[tuple[str, str]] | None:
    """Protect unfinished trash assets from legacy delete-quarantine cleanup.

    None means an unfinished or unreadable journal makes deletion unsafe. Also recognize
    older final manifests with failed moves, which lacked a pending journal.
    Only kind/name identities are read; paths from manifests are not followed.
    """
    protected: set[tuple[str, str]] = set()
    if not root.is_dir():
        return protected
    try:
        for entry in root.iterdir():
            if not ENTRY_PATTERN.fullmatch(entry.name):
                continue
            # Recovery has already attempted pending moves. If any remain,
            # their identities may be damaged: do not delete any orphan yet.
            if (entry / PENDING).is_file():
                return None
            path = entry / MANIFEST
            if not path.is_file():
                continue
            manifest = _read_json(path)
            _manifest_assets(manifest)
            item_id = manifest["item_id"]
            identities = {"media": {item_id}, "thumbnail": {
                f"text_mining_{item_id}.svg", f"word_cloud_{item_id}.svg",
            }}
            # A recorded trash entry owns these identities, even after a
            # partial or damaged journal has been marked finalized. Its empty
            # asset list cannot prove matching quarantined files are disposable.
            protected.update((kind, name) for kind, names in identities.items() for name in names)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return protected


def list_entries(root: Path, days: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not root.is_dir():
        return entries
    for entry in sorted(root.iterdir(), reverse=True):
        if not ENTRY_PATTERN.fullmatch(entry.name) or not (entry / MANIFEST).is_file():
            continue
        try:
            manifest = _read_json(entry / MANIFEST)
            _manifest_assets(manifest, pending=(entry / PENDING).exists())
        except (OSError, ValueError):
            continue
        deleted_at = str(manifest.get("deleted_at") or "")
        expires_at = ""
        if days and deleted_at:
            try:
                expires_at = (datetime.fromisoformat(deleted_at) + timedelta(days=days)).isoformat(timespec="seconds")
            except ValueError:
                pass
        entries.append({
            "id": entry.name,
            "item_id": manifest.get("item_id", ""),
            "source_name": manifest.get("source_name", ""),
            "deleted_at": deleted_at,
            "expires_at": expires_at,
            "bytes": _size(entry),
            "media_files": sum(1 for asset in manifest.get("assets", []) if asset.get("in_trash")),
            "restorable": bool(manifest.get("rows", {}).get("library_items")),
        })
    return entries


def purge(root: Path, entry_id: str) -> None:
    entry = _entry_path(root, entry_id)
    if (entry / PENDING).exists():
        raise TrashError("ゴミ箱への移動が未完了です。アプリを再起動して復旧してから完全削除してください。")
    if not (entry / MANIFEST).is_file():
        raise TrashError("ゴミ箱の項目が見つかりません。")
    try:
        assets = _manifest_assets(_read_json(entry / MANIFEST))
    except ValueError as exc:
        raise TrashError(str(exc)) from exc
    if any(not asset["in_trash"] for asset in assets):
        raise TrashError("ゴミ箱への移動が未完了のファイルがあるため、完全削除を保留しました。復旧が必要です。")
    shutil.rmtree(entry)


def purge_expired(root: Path, days: int, now: datetime | None = None) -> list[str]:
    """Remove trashed entries older than ``days``; pending entries are left to recovery."""
    if not days or not root.is_dir():
        return []
    limit = (now or _now()) - timedelta(days=days)
    purged: list[str] = []
    for entry in root.iterdir():
        if (not ENTRY_PATTERN.fullmatch(entry.name) or not (entry / MANIFEST).is_file()
                or (entry / PENDING).exists()):
            continue
        try:
            manifest = _read_json(entry / MANIFEST)
            if any(not asset["in_trash"] for asset in _manifest_assets(manifest)):
                continue
            deleted_at = datetime.fromisoformat(str(manifest.get("deleted_at")))
        except (OSError, ValueError, TypeError):
            continue
        if deleted_at < limit:
            shutil.rmtree(entry, ignore_errors=True)
            purged.append(entry.name)
    return purged


def _insert(connection: Any, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows or not _table_exists(connection, table):
        return
    current = {str(column[1]) for column in connection.execute(f"PRAGMA table_info({table})")}
    for row in rows:
        names = [name for name in row if name in current]
        placeholders = ",".join("?" for _ in names)
        connection.execute(
            f"INSERT INTO {table} ({','.join(names)}) VALUES ({placeholders})",
            [_decode(row[name]) for name in names],
        )


def restore(root: Path, entry_id: str, *, connect: Callable[[], Any],
            targets: dict[str, Path], move: Callable[[Path, Path], None]) -> str:
    """Put a trashed conversation back: files first, then its rows; returns the item ID.

    ``targets`` maps an asset kind to the directory it was deleted from.
    """
    entry = _entry_path(root, entry_id)
    try:
        if (entry / PENDING).is_file() and finish(entry, move):
            raise TrashError("ゴミ箱への移動が未完了のため復元を保留しました。ファイルの使用を終了してから再試行してください。")
    except ValueError as exc:
        raise TrashError(str(exc)) from exc
    if not (entry / MANIFEST).is_file():
        raise TrashError("ゴミ箱の項目が見つかりません。")
    try:
        manifest = _read_json(entry / MANIFEST)
        assets = _manifest_assets(manifest)
    except ValueError as exc:
        raise TrashError(str(exc)) from exc
    if any(not asset["in_trash"] for asset in assets):
        raise TrashError("ゴミ箱への移動が未完了のファイルがあるため、復元を保留しました。復旧が必要です。")
    item_id = str(manifest["item_id"])
    rows = manifest.get("rows") or {}
    if not rows.get("library_items"):
        raise TrashError("この項目には会話の記録がないため復元できません。")
    with connect() as connection:
        if connection.execute("SELECT 1 FROM library_items WHERE id=?", (item_id,)).fetchone():
            raise TrashError("同じIDの会話が既にあるため復元できません。")
    moves: list[tuple[Path, Path]] = []
    for asset in manifest.get("assets", []):
        source = entry / ASSET_FOLDERS[asset["kind"]] / asset["name"]
        if not (source.exists() or source.is_symlink()):
            continue
        target = targets[asset["kind"]] / asset["name"]
        if target.exists() or target.is_symlink():
            raise TrashError(f"復元先に同じ名前のファイルがあるため復元できません: {asset['name']}")
        moves.append((source, target))
    done: list[tuple[Path, Path]] = []
    try:
        for source, target in moves:
            target.parent.mkdir(parents=True, exist_ok=True)
            move(source, target)
            done.append((source, target))
        with connect() as connection:
            for table, key, parent in (("conversation_tags", "tag_id", "tags"),
                                       ("data_group_members", "group_id", "data_groups")):
                for row in rows.get(table, []):
                    if not connection.execute(f"SELECT 1 FROM {parent} WHERE {key}=?", (row[key],)).fetchone():
                        raise TrashError("所属先のタグまたはグループが削除されています。復元前に確認してください。")
            targets = [("data_groups", r["group_id"]) for r in rows.get("data_group_members", [])]
            with change_log.tracking(connection, targets, origin="rule", process="conversation_restore"):
                for table in ITEM_TABLES:
                    _insert(connection, table, rows.get(table, []))
                history = rows.get("change_log", [])
                if any(row.get("entity_id") != item_id or row.get("entity") not in change_log.CONVERSATION_ENTITIES for row in history):
                    raise TrashError("会話の変更履歴の識別情報が不正です。")
                _insert(connection, "change_log", history)
            for canonical_path in manifest.get("tombstones_added", []):
                connection.execute("DELETE FROM output_import_tombstones WHERE canonical_path=?", (canonical_path,))
            _insert(connection, "output_import_tombstones", manifest.get("tombstones_replaced", []))
    except Exception:
        for source, target in reversed(done):
            try:
                move(target, source)
            except OSError:
                pass
        raise
    shutil.rmtree(entry, ignore_errors=True)
    return item_id
