"""Media file handling: archived copies, thumbnails, output folders and local paths."""

from __future__ import annotations

import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable

from werkzeug.utils import secure_filename

from ..media_formats import ALLOWED_EXTENSIONS, VIDEO_EXTENSIONS
from .durable_files import atomic_copy_file, sync_file_data, temporary_output_path
from .word_cloud import write_word_cloud


def media_kind(path: Path | None) -> str | None:
    if path is None:
        return None
    mime = mimetypes.guess_type(path.name)[0] or ""
    return "video" if mime.startswith("video/") or path.suffix.lower() in {".mp4", ".m4v", ".mov", ".mkv"} else "audio"


def is_unc_path(value: str | Path) -> bool:
    raw = str(value).strip()
    return raw.startswith("\\") or raw.startswith("//")


def safe_media_filename(original_name: str, fallback_stem: str = 'media') -> str:
    '''Keep an allowed media suffix when Werkzeug strips a non-ASCII stem.'''
    suffix = Path(original_name).suffix.lower()
    safe_stem = secure_filename(Path(original_name).stem).strip(' .')
    if not safe_stem:
        safe_stem = fallback_stem
    return f'{safe_stem}{suffix}'


def is_video_path(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def make_media_files(
    *,
    default_output_directory: Callable[[], Any],
    max_media_upload_bytes: int,
    media_directory: Callable[[], Any],
    thumbnail_directory: Callable[[], Any],
    durable_move: Any,
    library_row: Any,
) -> tuple[Callable[..., Any], ...]:
    def stage_media_archive(
        item_id: str,
        source_path: Path,
        check_cancelled: Callable[[], None] | None = None,
    ) -> tuple[Path, Path]:
        target_dir = media_directory() / item_id
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = safe_media_filename(source_path.name)
        target = target_dir / safe_name
        staged = temporary_output_path(target)
        try:
            atomic_copy_file(source_path, staged, check_cancelled)
        except Exception:
            staged.unlink(missing_ok=True)
            raise
        return target, staged

    def commit_staged_media(target: Path, staged: Path) -> Path:
        if staged.parent.resolve() != target.parent.resolve() or not staged.is_file():
            raise OSError("The staged media file is missing or outside its destination directory.")
        sync_file_data(staged)
        durable_move(staged, target)
        return target

    def archive_media(
        item_id: str,
        source_path: Path,
        check_cancelled: Callable[[], None] | None = None,
    ) -> Path:
        target, staged = stage_media_archive(item_id, source_path, check_cancelled)
        try:
            return commit_staged_media(target, staged)
        finally:
            staged.unlink(missing_ok=True)

    def remove_owned_directory(path: Path, *, ignore_errors: bool = False) -> None:
        try:
            if path.is_symlink():
                path.unlink(missing_ok=True)
            elif path.exists():
                shutil.rmtree(path)
        except OSError:
            if not ignore_errors:
                raise

    def cleanup_uncommitted_job_artifacts(job: Any, options: Any) -> list[str]:
        """Remove only resources reserved for this job when no library row was committed."""
        warnings: list[str] = []
        try:
            if library_row(job.id) is not None:
                return warnings
        except (OSError, sqlite3.Error) as exc:
            return [f"Could not verify library persistence; temporary artifacts were retained: {exc}"]

        if options.owns_output_dir:
            expected_suffix = f"_{job.id[:8]}"
            if options.output_dir.name.endswith(expected_suffix):
                try:
                    remove_owned_directory(options.output_dir)
                except OSError as exc:
                    warnings.append(f"Could not remove the incomplete output directory: {exc}")
            else:
                warnings.append("The incomplete output directory failed its ownership check and was retained.")

        media_dir = media_directory() / job.id
        if re.fullmatch(r"[0-9a-f]{32}", job.id):
            try:
                media_root = media_directory().resolve()
                if media_dir.parent.resolve() == media_root:
                    remove_owned_directory(media_dir)
            except OSError as exc:
                warnings.append(f"Could not remove the incomplete media archive: {exc}")
        return warnings

    def resolve_local_media_path(raw_path: str) -> Path:
        raw_path = raw_path.strip().strip('"')
        if not raw_path:
            raise ValueError("処理する音声・動画ファイルを選択してください。")
        expanded = os.path.expandvars(raw_path)
        if is_unc_path(raw_path) or is_unc_path(expanded):
            raise ValueError("UNC/network media paths are disabled by default. Upload the file instead.")
        try:
            path = Path(expanded).expanduser().resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"指定したパスを開けません: {exc}") from exc
        if not path.is_file():
            raise ValueError("指定したパスはファイルではありません。")
        if path.stat().st_size == 0:
            raise ValueError("指定したファイルが空です。")
        if path.stat().st_size > max_media_upload_bytes:
            raise ValueError("The media file exceeds the configured size limit.")
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValueError("対応形式は MP4/MOV/MKV/WAV/MP3/M4A/FLAC です。")
        return path

    def prepare_output_root(raw_path: str) -> Path:
        expanded = os.path.expandvars(raw_path.strip().strip('"'))
        if expanded and (is_unc_path(raw_path) or is_unc_path(expanded)):
            raise ValueError("UNC/network output paths are disabled by default.")
        output_root = Path(expanded).expanduser() if expanded else default_output_directory()
        if is_unc_path(output_root):
            raise ValueError("UNC/network output paths are disabled by default.")
        output_root.mkdir(parents=True, exist_ok=True)
        if not output_root.is_dir():
            raise ValueError("The output destination must be a directory.")
        probe = output_root / f".gurumoji-write-test-{uuid.uuid4().hex}"
        try:
            with probe.open("xb") as stream:
                stream.write(b"ok")
        except OSError as exc:
            raise ValueError(f"The output directory is not writable: {exc}") from exc
        finally:
            probe.unlink(missing_ok=True)
        return output_root.resolve()

    def thumbnail_cache_path(source_path: Path) -> Path:
        stat = source_path.stat()
        seed = f"{source_path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
        return thumbnail_directory() / f"{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex}.jpg"

    def generate_word_cloud_thumbnail(
        item_id: str,
        source_name: str,
        segments: list[dict[str, Any]],
    ) -> Path:
        return write_word_cloud(
            thumbnail_directory() / f"word_cloud_{item_id}.svg",
            source_name,
            segments,
        )

    def generate_video_thumbnail(source_path: Path) -> Path:
        if not is_video_path(source_path):
            raise ValueError("サムネイルは動画ファイルだけ作成できます。")
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg が見つかりません。README の手順でインストールしてください。")
        thumbnail_directory().mkdir(parents=True, exist_ok=True)
        target = thumbnail_cache_path(source_path)
        if target.is_file() and target.stat().st_size > 0:
            return target
        last_error = ""
        for seek_at in ("00:00:01.000", "00:00:00.000"):
            temporary = temporary_output_path(target)
            try:
                completed = subprocess.run(
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                        "-ss", seek_at, "-i", str(source_path), "-frames:v", "1",
                        "-vf", "scale=640:-2:force_original_aspect_ratio=decrease",
                        "-q:v", "3", str(temporary),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    check=False,
                )
                if completed.returncode == 0 and temporary.is_file() and temporary.stat().st_size > 0:
                    sync_file_data(temporary)
                    durable_move(temporary, target)
                    return target
                last_error = completed.stderr.strip()
            except subprocess.TimeoutExpired:
                last_error = "サムネイル作成がタイムアウトしました。"
            finally:
                temporary.unlink(missing_ok=True)
        raise RuntimeError(last_error or "動画からサムネイルを作成できませんでした。")

    return (
        stage_media_archive,
        commit_staged_media,
        archive_media,
        remove_owned_directory,
        cleanup_uncommitted_job_artifacts,
        resolve_local_media_path,
        prepare_output_root,
        thumbnail_cache_path,
        generate_word_cloud_thumbnail,
        generate_video_thumbnail,
    )
