"""Choose WAL only for a positively identified local fixed filesystem."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import re
import sys


def _windows_volume(path: Path) -> tuple[int, str]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    root = ctypes.create_unicode_buffer(32768)
    if not kernel.GetVolumePathNameW(str(path), root, len(root)):
        raise OSError(ctypes.get_last_error(), "GetVolumePathNameW")
    filesystem = ctypes.create_unicode_buffer(256)
    if not kernel.GetVolumeInformationW(root.value, None, 0, None, None, None,
                                      filesystem, len(filesystem)):
        raise OSError(ctypes.get_last_error(), "GetVolumeInformationW")
    return kernel.GetDriveTypeW(root.value), filesystem.value


def _linux_filesystem(path: Path) -> str:
    # Longest enclosing mount, including bind mounts; unknown types fail closed.
    matches = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        before, after = line.split(" - ", 1)
        mount = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), before.split()[4])
        if path.is_relative_to(Path(mount)):
            matches.append((len(mount), after.split()[0]))
    return max(matches)[1] if matches else ""


def local_fixed_directory(directory: Path, *, colab: bool = False) -> bool:
    raw = str(directory).replace("\\", "/").casefold()
    if colab or raw == "/content/drive" or raw.startswith("/content/drive/"):
        return False
    if any(name in raw for name in ("onedrive", "google drive", "googledrive", "マイドライブ", "dropbox")):
        return False
    if raw.startswith("//"):
        return False
    try:
        path = Path(directory).resolve(strict=True)
        resolved = str(path).replace("\\", "/").casefold()
        if resolved != raw and any(name in resolved for name in
                                   ("onedrive", "google drive", "googledrive", "マイドライブ", "dropbox")):
            return False
        if resolved == "/content/drive" or resolved.startswith("/content/drive/"):
            return False
        if os.name == "nt":
            drive_type, filesystem = _windows_volume(path)
            return drive_type == 3 and filesystem.upper() in {"NTFS", "REFS"}
        if sys.platform.startswith("linux"):
            return _linux_filesystem(path) in {"ext2", "ext3", "ext4", "xfs", "btrfs"}
    except (OSError, ValueError, AttributeError):
        pass
    return False


def configure_journal(connection, directory: Path, *, colab: bool = False) -> str:
    mode = "WAL" if local_fixed_directory(directory, colab=colab) else "DELETE"
    actual = str(connection.execute(f"PRAGMA journal_mode={mode}").fetchone()[0]).upper()
    if actual != mode:
        raise RuntimeError(f"SQLite journal mode: expected {mode}, got {actual}")
    return actual
