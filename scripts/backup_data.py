"""Back up, verify, or restore the Gurumoji data directory (DATA-03).

  python scripts/backup_data.py create [--include-media]
  python scripts/backup_data.py verify <backup folder>
  python scripts/backup_data.py restore <backup folder> [--data-dir <empty folder>]

``create`` and ``restore`` refuse to run while the app uses the data directory;
use the app's 「バックアップを作成」 button then. The data directory is
``MOJIOKOSI_DATA_DIR`` or ``runtime/data``; backups go to ``MOJIOKOSI_BACKUP_DIR``
or ``runtime/backups``. tokens.json and runtime/output are not included.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gurumoji.services.data_backup import BackupError, create_backup, restore_backup, verify_backup  # noqa: E402
from gurumoji.services.instance_lock import InstanceLock  # noqa: E402


def default_data_dir() -> Path:
    return Path(os.environ.get("MOJIOKOSI_DATA_DIR", str(ROOT / "runtime" / "data"))).expanduser()


def default_backup_dir() -> Path:
    return Path(os.environ.get("MOJIOKOSI_BACKUP_DIR", str(ROOT / "runtime" / "backups"))).expanduser()


def app_stopped(data_dir: Path) -> InstanceLock | None:
    """Hold the app's own data-directory lock so it cannot start meanwhile."""
    lock = InstanceLock(lambda: [data_dir / ".gurumoji.instance.lock"])
    return lock if lock.acquire() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gurumoji のデータをバックアップ・検証・復元します。")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="バックアップを作成する（アプリ停止中）")
    create.add_argument("--data-dir", type=Path, default=default_data_dir())
    create.add_argument("--backup-dir", type=Path, default=default_backup_dir())
    create.add_argument("--include-media", action="store_true", help="元の音声・動画と学習用音声も含める")
    verify = commands.add_parser("verify", help="バックアップの内容をhashで確認する")
    verify.add_argument("backup", type=Path)
    restore = commands.add_parser("restore", help="空のデータフォルダーへ復元する（アプリ停止中）")
    restore.add_argument("backup", type=Path)
    restore.add_argument("--data-dir", type=Path, default=default_data_dir())
    args = parser.parse_args(argv)

    try:
        if args.command == "verify":
            problems = verify_backup(args.backup)
            for problem in problems:
                print(problem)
            print("問題はありません。" if not problems else f"{len(problems)}件の問題があります。")
            return 0 if not problems else 1
        if args.command == "create":
            lock = app_stopped(args.data_dir)
            if lock is None:
                print("アプリがこのデータフォルダーを使用中です。画面の「バックアップを作成」を使うか、アプリを終了してから実行してください。")
                return 2
            try:
                result = create_backup(args.data_dir, args.backup_dir, include_media=args.include_media)
            finally:
                lock.release()
            print(f"作成しました: {result['path']}（{result['file_count']}ファイル、{result['total_bytes']:,}バイト）")
            print("含めていないもの: " + "、".join(result["excluded"]))
            return 0
        if args.data_dir.exists() and any(args.data_dir.iterdir()):
            print("復元先のデータフォルダーが空ではありません。既存のフォルダーを別名に移してから実行してください。")
            return 2
        result = restore_backup(args.backup, args.data_dir)
        print(f"復元しました: {args.data_dir}（{result['file_count']}ファイル）")
        print("config/tokens.json を設定し直してください。出力ファイルは次の編集保存で書き直されます。"
              + ("" if result["include_media"] else "元の音声・動画は含まれていません。"))
        return 0
    except BackupError as exc:
        print(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
