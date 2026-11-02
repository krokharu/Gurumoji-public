"""Consistent backup and restore of the data directory (DATA-03).

One conversation's data is spread over SQLite, ``analysis_store``, the
Vaults and their ledgers. A backup copies, at one moment, only what cannot be
recreated: the database (through SQLite's backup API), the fixed analysis
results, the Vaults, their ledgers and history, the finishing workbench and
the custom vocabulary. The original media, and the training clips cut from it,
are optional because of their size.

Left out on purpose: thumbnails and training exports (regenerated), the trash
and upload staging, migration backups, ``runtime/output`` (rewritten from the
database on the next save), and ``config/tokens.json`` (a secret: set it again).

A backup is a folder ``gurumoji-backup-<UTC time>`` holding ``data/`` and
``manifest.json`` with the SHA-256 of every file. Restore verifies all hashes
and writes only into an empty data directory.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

BACKUP_FORMAT = 1
MANIFEST = "manifest.json"
DATABASE = "library.sqlite3"
ALWAYS = ("analysis_store", "obsidian", "obsidian_layout", "obsidian_workbench", "custom_vocabulary.json")
MEDIA = ("media", "kushinada_training/audio")
EXCLUDED_NOTE = [
    "thumbnails（再生成される）",
    "analysis-derived.sqlite3（派生解析行。失われたら再計算）",
    "kushinada_training の書き出し（DBから再生成される）",
    "trash・アップロードの一時領域・移行時の backup-*",
    "runtime/output（次の編集保存でDBから書き直される）",
    "config/tokens.json（秘密情報。復元後に設定し直す）",
]


class BackupError(ValueError):
    pass


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _skip(relative: Path) -> bool:
    name = relative.name
    parts = relative.parts
    return (
        name.endswith(".tmp")
        or name == ".gurumoji.instance.lock"
        or any(part.startswith((".delete-staging-", ".edit-staging-", ".edit-preparing-")) for part in parts)
        or (parts[:1] == ("obsidian_layout",) and len(parts) > 1 and parts[1].startswith("backup-"))
    )


def _files(data_dir: Path, names: Iterable[str]) -> Iterable[Path]:
    for name in names:
        source = data_dir / name
        if source.is_symlink():
            raise BackupError(f"リンクを含むためバックアップできません: {name}")
        if source.is_file():
            yield source
        elif source.is_dir():
            for path in sorted(source.rglob("*")):
                if path.is_symlink():
                    raise BackupError(f"リンクを含むためバックアップできません: {path.relative_to(data_dir)}")
                if path.is_file() and not _skip(path.relative_to(data_dir)):
                    yield path


def create_backup(data_dir: Path, backup_root: Path, *, include_media: bool = False,
                  app_version: str = "", now: datetime | None = None) -> dict[str, Any]:
    """Copy the data directory into a new backup folder and return its manifest.

    The caller keeps the application's writers paused (or the app stopped)
    for the duration, so the database and files belong to the same moment.
    """
    data_dir = Path(data_dir)
    database = data_dir / DATABASE
    if not database.is_file():
        raise BackupError("データフォルダーに library.sqlite3 がありません。")
    stamp = f"{(now or datetime.now(timezone.utc)).astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"
    target = Path(backup_root) / f"gurumoji-backup-{stamp}"
    if target.exists():
        raise BackupError("同じ時刻のバックアップがあります。少し待ってから実行してください。")
    partial = target.with_name(target.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    (partial / "data").mkdir(parents=True)
    try:
        with closing(sqlite3.connect(database)) as source, \
                closing(sqlite3.connect(partial / "data" / DATABASE)) as copy:
            source.backup(copy)
        entries = [{"path": DATABASE, "sha256": _sha(partial / "data" / DATABASE),
                    "bytes": (partial / "data" / DATABASE).stat().st_size}]
        for path in _files(data_dir, ALWAYS + (MEDIA if include_media else ())):
            relative = path.relative_to(data_dir)
            destination = partial / "data" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            entries.append({"path": relative.as_posix(), "sha256": _sha(destination),
                            "bytes": destination.stat().st_size})
        manifest = {
            "format": BACKUP_FORMAT, "app_version": app_version,
            "created_at": stamp, "include_media": include_media,
            "excluded": EXCLUDED_NOTE + ([] if include_media else ["media・学習用音声（既定で除外）"]),
            "files": entries,
        }
        (partial / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        partial.rename(target)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return {**manifest, "path": target, "file_count": len(entries),
            "total_bytes": sum(entry["bytes"] for entry in entries)}


def verify_backup(backup_dir: Path) -> list[str]:
    """Return problems; an empty list means every listed file matches its hash."""
    backup_dir = Path(backup_dir)
    try:
        manifest = json.loads((backup_dir / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"manifest.json を読めません: {exc}"]
    if manifest.get("format") != BACKUP_FORMAT:
        return [f"対応していない形式です: {manifest.get('format')}"]
    root = backup_dir / "data"
    problems = []
    listed = set()
    for entry in manifest.get("files", []):
        relative = str(entry.get("path", ""))
        listed.add(relative)
        path = root / relative
        if ".." in Path(relative).parts or Path(relative).is_absolute():
            problems.append(f"不正なパス: {relative}")
        elif not path.is_file():
            problems.append(f"ファイルがありません: {relative}")
        elif _sha(path) != entry.get("sha256"):
            problems.append(f"内容が一致しません: {relative}")
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_file() and path.relative_to(root).as_posix() not in listed:
                problems.append(f"manifest にないファイル: {path.relative_to(root).as_posix()}")
    if DATABASE not in listed:
        problems.append("library.sqlite3 が含まれていません。")
    return problems


def restore_backup(backup_dir: Path, data_dir: Path) -> dict[str, Any]:
    """Verify, then copy the backup into an empty (or missing) data directory."""
    problems = verify_backup(backup_dir)
    if problems:
        raise BackupError("バックアップを検証できませんでした: " + " / ".join(problems[:5]))
    data_dir = Path(data_dir)
    if data_dir.exists() and any(data_dir.iterdir()):
        raise BackupError("復元先のデータフォルダーが空ではありません。既存のフォルダーを別名に移してから実行してください。")
    partial = data_dir.with_name(data_dir.name + ".restoring")
    if partial.exists():
        raise BackupError(f"前回の復元途中のフォルダーが残っています: {partial.name}")
    shutil.copytree(Path(backup_dir) / "data", partial)
    if data_dir.exists():
        data_dir.rmdir()
    partial.rename(data_dir)
    manifest = json.loads((Path(backup_dir) / MANIFEST).read_text(encoding="utf-8"))
    return {"file_count": len(manifest["files"]), "include_media": manifest.get("include_media", False)}
