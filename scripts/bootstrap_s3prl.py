"""Install the pinned S3PRL source without requiring Git."""

from __future__ import annotations

import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


VERSION = "0.4.17"
ARCHIVE_URL = f"https://github.com/s3prl/s3prl/archive/refs/tags/v{VERSION}.zip"


def valid_repository(target: Path) -> bool:
    version_file = target / "s3prl" / "version.txt"
    runner_file = target / "s3prl" / "run_downstream.py"
    try:
        return version_file.read_text(encoding="utf-8").strip() == VERSION and runner_file.is_file()
    except OSError:
        return False


def safe_extract(archive: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            member_path = (destination / member.filename).resolve()
            if member_path != destination_resolved and destination_resolved not in member_path.parents:
                raise RuntimeError(f"Unsafe archive member: {member.filename}")
        bundle.extractall(destination)


def install(target: Path) -> None:
    target = target.resolve()
    if valid_repository(target):
        print(f"S3PRL {VERSION} source already exists: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mojiokosi-s3prl-") as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / "s3prl.zip"
        extracted = temporary_path / "extracted"
        print(f"Downloading S3PRL {VERSION} source archive ...")
        urllib.request.urlretrieve(ARCHIVE_URL, archive)
        safe_extract(archive, extracted)
        source = extracted / f"s3prl-{VERSION}"
        if not valid_repository(source):
            raise RuntimeError("The downloaded S3PRL archive is incomplete or has an unexpected version.")
        # Overlaying supports recovery from an interrupted previous download
        # without deleting anything from the user's models directory.
        shutil.copytree(source, target, dirs_exist_ok=True)
    if not valid_repository(target):
        raise RuntimeError(f"S3PRL {VERSION} source validation failed after extraction.")
    print(f"S3PRL {VERSION} source is ready: {target}")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: bootstrap_s3prl.py TARGET_DIRECTORY", file=sys.stderr)
        return 2
    try:
        install(Path(sys.argv[1]))
        return 0
    except Exception as exc:
        print(f"Could not download S3PRL {VERSION}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
