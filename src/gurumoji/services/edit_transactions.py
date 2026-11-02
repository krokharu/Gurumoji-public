"""Crash-safe promotion of edited transcript outputs.

An edit writes its new files into a staging directory beside the output
directory, records a signed manifest, and only then swaps the files into place.
If the process dies at any point, the marker and the manifest are enough to
either finish or undo the swap on the next start.

Windows needs most of the care here: handles stay open, renames are not atomic
across directories by default, and a directory can be renamed out from under an
in-flight transaction.  The composition root supplies the database connection
factory; nothing else in the module reaches into application state.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import stat
import sys
import time
import uuid
from pathlib import Path, PurePosixPath
from collections import Counter
from contextlib import contextmanager
from typing import Any, Callable

from .durable_files import (
    atomic_copy_file,
    durable_move,
    durable_write_json,
    ensure_staging_tree_has_no_reparse_points,
    file_matches_fingerprint,
    file_sha256,
    path_entry_exists,
    path_has_reparse_ancestor,
    path_is_link_or_reparse,
    path_is_within,
    sync_directory_metadata,
    sync_file_data,
    sync_rename_metadata,
    windows_case_insensitive_text,
    windows_extended_path,
)
from ..text_utils import utc_now_iso

EDIT_TRANSACTION_MANIFEST_NAME = '.edit-transaction.json'
EDIT_PREPARATION_MARKER_NAME = '.edit-preparation.json'
EDIT_TRANSACTION_SCHEMA_VERSION = 1
MAX_EDIT_TRANSACTION_MANIFEST_BYTES = 1024 * 1024
MAX_EDIT_TRANSACTION_FILES = 256


def edit_storage_id(
    connection: sqlite3.Connection | None = None,
    *,
    connect: Callable[[], Any],
) -> str:
    def read(active_connection: sqlite3.Connection) -> str:
        active_connection.execute(
            'INSERT OR IGNORE INTO application_metadata (key, value) VALUES (?, ?)',
            ('edit_storage_id', uuid.uuid4().hex),
        )
        row = active_connection.execute(
            'SELECT value FROM application_metadata WHERE key = ?',
            ('edit_storage_id',),
        ).fetchone()
        value = str(row['value'] if row is not None else '')
        if not re.fullmatch(r'[0-9a-f]{32}', value):
            raise RuntimeError('The edit transaction storage identity is missing or invalid.')
        return value

    if connection is not None:
        return read(connection)
    with connect() as owned_connection:
        return read(owned_connection)


def edit_journal_secret(
    connection: sqlite3.Connection | None = None,
    *,
    connect: Callable[[], Any],
) -> bytes:
    def read(active_connection: sqlite3.Connection) -> bytes:
        active_connection.execute(
            'INSERT OR IGNORE INTO application_metadata (key, value) VALUES (?, ?)',
            ('edit_journal_secret', secrets.token_hex(32)),
        )
        row = active_connection.execute(
            'SELECT value FROM application_metadata WHERE key = ?',
            ('edit_journal_secret',),
        ).fetchone()
        value = str(row['value'] if row is not None else '')
        if not re.fullmatch(r'[0-9a-f]{64}', value):
            raise RuntimeError('The edit journal authentication secret is missing or invalid.')
        return bytes.fromhex(value)

    if connection is not None:
        return read(connection)
    with connect() as owned_connection:
        return read(owned_connection)


def edit_journal_mac(payload: dict[str, Any], secret: bytes) -> str:
    authenticated = {
        key: value
        for key, value in payload.items()
        if key != 'mac' and not key.startswith('_')
    }
    encoded = json.dumps(
        authenticated,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hmac.new(secret, encoded, hashlib.sha256).hexdigest()


def safe_edit_relative_path(raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path or len(raw_path) > 1024:
        raise ValueError('An edit transaction contains an invalid relative path.')
    if '\\' in raw_path or '\x00' in raw_path:
        raise ValueError('An edit transaction contains an unsafe relative path.')
    pure = PurePosixPath(raw_path)
    if (
        pure.is_absolute()
        or pure.as_posix() != raw_path
        or any(part in {'', '.', '..'} for part in pure.parts)
    ):
        raise ValueError('An edit transaction contains an unsafe relative path.')
    reserved_devices = {
        'con', 'prn', 'aux', 'nul', 'conin$', 'conout$',
        *(f'com{index}' for index in range(1, 10)),
        *(f'lpt{index}' for index in range(1, 10)),
        'com¹', 'com²', 'com³', 'lpt¹', 'lpt²', 'lpt³',
    }
    reserved_internal = {
        '.previous',
        '.discarded',
        EDIT_TRANSACTION_MANIFEST_NAME.casefold(),
        EDIT_PREPARATION_MARKER_NAME.casefold(),
    }
    for part in pure.parts:
        folded = part.casefold()
        device_base = part.split('.', 1)[0].rstrip(' .').casefold()
        if (
            folded in reserved_internal
            or device_base in reserved_devices
            or part.endswith((' ', '.'))
            or any(
                character in '<>:|?*' or character == chr(34)
                for character in part
            )
            or any(ord(character) < 32 or ord(character) == 127 for character in part)
        ):
            raise ValueError('An edit transaction contains an unsafe Windows path.')
    relative = Path(*pure.parts)
    if relative.is_absolute() or relative.drive:
        raise ValueError('An edit transaction contains an unsafe relative path.')
    return relative


def edit_relative_path_key(relative: Path) -> str:
    # NTFS comparisons are case-insensitive, but they do not use Unicode
    # case-fold expansions (for example, German sharp-s is not equal to SS).
    return PurePosixPath(*(
        windows_case_insensitive_text(part)
        for part in relative.parts
    )).as_posix()


def edit_staging_identity(path: Path) -> tuple[int, int]:
    candidate = Path(os.path.abspath(os.fspath(path)))
    if path_is_link_or_reparse(candidate) or not candidate.is_dir():
        raise OSError('The edit staging path is not a local directory.')
    metadata = candidate.lstat()
    inode = int(metadata.st_ino)
    if not inode:
        raise OSError('The filesystem does not provide a stable staging identity.')
    return int(metadata.st_dev), inode


def edit_cleanup_entry_identity(path: Path) -> tuple[str, int, int]:
    if path_is_link_or_reparse(path):
        raise OSError('An edit cleanup entry is a symbolic link or reparse point.')
    metadata = path.lstat()
    if stat.S_ISDIR(metadata.st_mode):
        kind = 'directory'
    elif stat.S_ISREG(metadata.st_mode):
        kind = 'file'
    else:
        raise OSError('An edit cleanup entry has an unsupported filesystem type.')
    inode = int(metadata.st_ino)
    if not inode:
        raise OSError('An edit cleanup entry has no stable filesystem identity.')
    return kind, int(metadata.st_dev), inode


def edit_cleanup_allowed_directories(file_names: set[str]) -> set[str]:
    directories: set[str] = set()
    for file_name in file_names:
        relative = PurePosixPath(file_name)
        for parent in relative.parents:
            if parent != PurePosixPath('.'):
                directories.add(parent.as_posix())
    return directories


def capture_edit_cleanup_inventory(
    staging_root: Path,
    file_options: dict[str, set[tuple[int, str]]],
) -> dict[str, Any]:
    root = Path(os.path.abspath(os.fspath(staging_root)))
    root_identity = edit_staging_identity(root)
    allowed_files = set(file_options)
    allowed_directories = edit_cleanup_allowed_directories(allowed_files)
    entries: dict[str, tuple[str, int, int]] = {}
    seen_keys: set[str] = set()
    ensure_staging_tree_has_no_reparse_points(root)
    for candidate in root.rglob('*'):
        relative = candidate.relative_to(root)
        relative_name = PurePosixPath(*relative.parts).as_posix()
        relative_key = edit_relative_path_key(relative)
        if relative_key in seen_keys:
            raise OSError('An edit cleanup tree contains a Windows path collision.')
        seen_keys.add(relative_key)
        entry_identity = edit_cleanup_entry_identity(candidate)
        kind = entry_identity[0]
        if kind == 'directory':
            if relative_name not in allowed_directories:
                raise OSError('An edit cleanup tree contains an unowned directory.')
        else:
            options = file_options.get(relative_name)
            if options is None:
                raise OSError('An edit cleanup tree contains an unowned file.')
            if not any(
                file_matches_fingerprint(candidate, sha256, size)
                for size, sha256 in options
            ):
                raise OSError('An edit cleanup file changed ownership or content.')
        entries[relative_name] = entry_identity
    if edit_staging_identity(root) != root_identity:
        raise OSError('An edit cleanup tree changed while it was inventoried.')
    return {
        'root_identity': root_identity,
        'entries': entries,
        'file_options': {
            name: set(options)
            for name, options in file_options.items()
        },
    }


def validate_edit_cleanup_inventory(
    staging_root: Path,
    inventory: dict[str, Any],
) -> None:
    expected_root = inventory.get('root_identity')
    expected_entries = inventory.get('entries')
    file_options = inventory.get('file_options')
    if (
        not isinstance(expected_root, tuple)
        or len(expected_root) != 2
        or not isinstance(expected_entries, dict)
        or not isinstance(file_options, dict)
    ):
        raise OSError('The edit cleanup inventory is invalid.')
    current = capture_edit_cleanup_inventory(staging_root, file_options)
    if current['root_identity'] != expected_root or current['entries'] != expected_entries:
        raise OSError('The edit cleanup inventory changed before removal.')


@contextmanager
def hold_edit_directory_against_rename(
    path: Path,
    expected_identity: tuple[int, int],
):
    candidate = Path(os.path.abspath(os.fspath(path)))
    if os.name == 'nt':
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        create_file.restype = ctypes.c_void_p
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        handle = create_file(
            windows_extended_path(candidate),
            0x80,
            0x1 | 0x2,
            None,
            3,
            0x02000000 | 0x00200000,
            None,
        )
        invalid_handle = ctypes.c_void_p(-1).value
        if handle in {None, invalid_handle}:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if edit_staging_identity(candidate) != expected_identity:
                raise OSError('The edit staging identity changed before it was locked.')
            yield None
        finally:
            close_handle(handle)
        return

    flags = os.O_RDONLY
    flags |= int(getattr(os, 'O_DIRECTORY', 0))
    flags |= int(getattr(os, 'O_NOFOLLOW', 0))
    directory_fd = os.open(str(candidate), flags)
    try:
        metadata = os.fstat(directory_fd)
        actual_identity = (int(metadata.st_dev), int(metadata.st_ino))
        if actual_identity != expected_identity:
            raise OSError('The edit staging identity changed before it was locked.')
        yield directory_fd
    finally:
        os.close(directory_fd)


def write_edit_preparation_marker(
    staging_dir: Path,
    output_dir: Path,
    *,
    item_id: str,
    expected_revision: int,
    previous_output_dir: Path,
    staged_files: list[Path] | None = None,
    connect: Callable[[], Any],
) -> Path:
    if path_is_link_or_reparse(staging_dir) or not staging_dir.is_dir():
        raise OSError('The edit staging directory must be a local directory.')
    staging_root = staging_dir.resolve()
    output_root = output_dir.resolve()
    if staging_root.parent != output_root:
        raise OSError('The edit staging directory is outside its output directory.')
    final_match = re.fullmatch(r'\.edit-staging-([0-9a-f]{32})', staging_root.name)
    preparing_match = re.fullmatch(
        r'\.edit-preparing-([0-9a-f]{32})-[0-9a-f]{32}',
        staging_root.name,
    )
    match = final_match or preparing_match
    if match is None:
        raise OSError('The edit staging directory name is invalid.')
    transaction_id = match.group(1)
    final_staging_name = f'.edit-staging-{transaction_id}'
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        raise ValueError('The edit transaction revision is invalid.')
    if (
        not isinstance(item_id, str)
        or not 1 <= len(item_id) <= 255
        or re.search(r'[\x00-\x1f]', item_id)
    ):
        raise ValueError('The edit transaction item ID is invalid.')
    for candidate in output_root.glob('.edit-staging-*'):
        if (
            candidate != staging_root
            and re.fullmatch(r'\.edit-staging-[0-9a-f]{32}', candidate.name)
        ):
            raise OSError('A previous edit transaction must be recovered before saving.')
    prepared_entries: list[dict[str, Any]] | None = None
    if staged_files is not None:
        if not 1 <= len(staged_files) <= MAX_EDIT_TRANSACTION_FILES:
            raise OSError('An edit preparation contains an invalid number of files.')
        prepared_entries = []
        seen_prepared: set[str] = set()
        for staged_path in staged_files:
            if path_is_link_or_reparse(staged_path):
                raise OSError('A prepared output file is a symbolic link or reparse point.')
            staged = staged_path.resolve()
            if not path_is_within(staged, staging_root) or not staged.is_file():
                raise OSError('A prepared output file is missing or outside staging.')
            relative = staged.relative_to(staging_root)
            relative_text = PurePosixPath(*relative.parts).as_posix()
            safe_relative = safe_edit_relative_path(relative_text)
            relative_key = edit_relative_path_key(safe_relative)
            if relative_key in seen_prepared:
                raise OSError('An edit preparation contains duplicate targets.')
            seen_prepared.add(relative_key)
            entry_identity = edit_cleanup_entry_identity(staged)
            prepared_entries.append({
                'relative_path': relative_text,
                'size': staged.stat().st_size,
                'sha256': file_sha256(staged),
                'device': entry_identity[1],
                'inode': entry_identity[2],
            })
    with connect() as connection:
        storage_id = edit_storage_id(connection, connect=connect)
        journal_secret = edit_journal_secret(connection, connect=connect)
    payload: dict[str, Any] = {
        'schema_version': EDIT_TRANSACTION_SCHEMA_VERSION,
        'kind': 'library-edit-preparation',
        'transaction_id': transaction_id,
        'final_staging_name': final_staging_name,
        'storage_id': storage_id,
        'item_id': item_id,
        'expected_revision': expected_revision,
        'output_dir': str(output_root),
        'previous_output_dir': str(previous_output_dir.resolve()),
        'created_at': utc_now_iso(),
    }
    if prepared_entries is not None:
        payload['files'] = prepared_entries
    payload['mac'] = edit_journal_mac(payload, journal_secret)
    marker = staging_root / EDIT_PREPARATION_MARKER_NAME
    durable_write_json(marker, payload)
    return marker


def write_edit_transaction_manifest(
    staging_dir: Path,
    output_dir: Path,
    staged_files: list[Path],
    *,
    item_id: str,
    expected_revision: int,
    previous_output_dir: Path,
    connect: Callable[[], Any],
) -> Path:
    if path_is_link_or_reparse(staging_dir) or not staging_dir.is_dir():
        raise OSError('The edit staging directory must be a local directory.')
    ensure_staging_tree_has_no_reparse_points(staging_dir)
    staging_root = staging_dir.resolve()
    output_root = output_dir.resolve()
    if staging_root.parent != output_root:
        raise OSError('The edit staging directory is outside its output directory.')
    match = re.fullmatch(r'\.edit-staging-([0-9a-f]{32})', staging_root.name)
    if match is None:
        raise OSError('The edit staging directory name is invalid.')
    for candidate in output_root.glob('.edit-staging-*'):
        if (
            candidate != staging_root
            and re.fullmatch(r'\.edit-staging-[0-9a-f]{32}', candidate.name)
        ):
            raise OSError('A previous edit transaction must be recovered before saving.')
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        raise ValueError('The edit transaction revision is invalid.')
    if not 1 <= len(staged_files) <= MAX_EDIT_TRANSACTION_FILES:
        raise OSError('The edit transaction contains an invalid number of files.')

    entries: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    for staged_path in staged_files:
        if staged_path.is_symlink():
            raise OSError('A staged output file must not be a symbolic link.')
        staged = staged_path.resolve()
        if not path_is_within(staged, staging_root) or not staged.is_file():
            raise OSError('A staged output file is missing or outside the staging directory.')
        relative = staged.relative_to(staging_root)
        relative_text = PurePosixPath(*relative.parts).as_posix()
        safe_relative = safe_edit_relative_path(relative_text)
        if (
            safe_relative.parts[0] in {'.previous', '.discarded'}
            or safe_relative.name == EDIT_TRANSACTION_MANIFEST_NAME
        ):
            raise OSError('A staged output file uses a reserved transaction path.')
        target = output_root / safe_relative
        target_key = edit_relative_path_key(safe_relative)
        if target_key in seen_targets:
            raise OSError('Duplicate staged output target.')
        seen_targets.add(target_key)
        if not path_is_within(target, output_root):
            raise OSError('A staged output target escapes the output directory.')
        if target.is_symlink():
            raise OSError('A staged output target must not be a symbolic link.')
        if target.exists() and not target.is_file():
            raise OSError('A staged output target is not a file.')
        with staged.open('r+b') as stream:
            os.fsync(stream.fileno())
        had_previous = target.exists() or target.is_symlink()
        previous_sha256 = ''
        previous_size: int | None = None
        if had_previous and target.is_file():
            previous_size = target.stat().st_size
            previous_sha256 = file_sha256(target)
        entries.append({
            'relative_path': relative_text,
            'had_previous': had_previous,
            'new_size': staged.stat().st_size,
            'new_sha256': file_sha256(staged),
            'previous_size': previous_size,
            'previous_sha256': previous_sha256,
        })

    with connect() as connection:
        storage_id = edit_storage_id(connection, connect=connect)
        journal_secret = edit_journal_secret(connection, connect=connect)
    manifest = staging_root / EDIT_TRANSACTION_MANIFEST_NAME
    payload: dict[str, Any] = {
        'schema_version': EDIT_TRANSACTION_SCHEMA_VERSION,
        'kind': 'library-edit',
        'transaction_id': match.group(1),
        'storage_id': storage_id,
        'item_id': item_id,
        'expected_revision': expected_revision,
        'target_revision': expected_revision + 1,
        'output_dir': str(output_root),
        'previous_output_dir': str(previous_output_dir.resolve()),
        'created_at': utc_now_iso(),
        'files': entries,
    }
    payload['mac'] = edit_journal_mac(payload, journal_secret)
    durable_write_json(manifest, payload)
    (staging_root / EDIT_PREPARATION_MARKER_NAME).unlink(missing_ok=True)
    sync_directory_metadata(staging_root)
    return manifest


@contextmanager
def open_windows_edit_entry_for_deletion(
    path: Path,
    expected_entry: tuple[str, int, int],
):
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_int
    handle = create_file(
        windows_extended_path(path),
        0x00010000 | 0x80,
        0x1 | 0x2,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle in {None, invalid_handle}:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if edit_cleanup_entry_identity(path) != expected_entry:
            raise OSError('An edit cleanup entry changed before its delete handle opened.')
        yield handle
    finally:
        close_handle(handle)


def mark_windows_handle_for_deletion(handle: int) -> None:
    class FileDispositionInfo(ctypes.Structure):
        _fields_ = [('delete_file', ctypes.c_int)]

    set_information = ctypes.WinDLL(
        'kernel32',
        use_last_error=True,
    ).SetFileInformationByHandle
    set_information.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    set_information.restype = ctypes.c_int
    disposition = FileDispositionInfo(1)
    if not set_information(
        handle,
        4,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def remove_windows_edit_directory_contents(
    directory: Path,
    expected_identity: tuple[int, int],
    *,
    transaction_root: Path,
    expected_entries: dict[str, tuple[str, int, int]],
    top_level: bool,
) -> None:
    expected_directory = ('directory', expected_identity[0], expected_identity[1])

    def journal_order(child: Path) -> tuple[int, str]:
        if top_level and child.name == EDIT_PREPARATION_MARKER_NAME:
            return 1, child.name
        if top_level and child.name == EDIT_TRANSACTION_MANIFEST_NAME:
            return 2, child.name
        return 0, child.name

    with open_windows_edit_entry_for_deletion(
        directory,
        expected_directory,
    ) as directory_handle:
        children = sorted(list(directory.iterdir()), key=journal_order)
        for child in children:
            relative_name = PurePosixPath(
                *child.relative_to(transaction_root).parts
            ).as_posix()
            expected_entry = expected_entries.get(relative_name)
            if expected_entry is None:
                raise OSError('An unowned entry appeared during edit cleanup.')
            if expected_entry[0] == 'directory':
                remove_windows_edit_directory_contents(
                    child,
                    (expected_entry[1], expected_entry[2]),
                    transaction_root=transaction_root,
                    expected_entries=expected_entries,
                    top_level=False,
                )
            else:
                with open_windows_edit_entry_for_deletion(
                    child,
                    expected_entry,
                ) as child_handle:
                    mark_windows_handle_for_deletion(child_handle)
            expected_entries.pop(relative_name, None)
        if list(directory.iterdir()):
            raise OSError('A new entry appeared while edit cleanup was finishing.')
        mark_windows_handle_for_deletion(directory_handle)


def remove_edit_directory_contents(
    directory: Path,
    expected_identity: tuple[int, int],
    *,
    transaction_root: Path,
    expected_entries: dict[str, tuple[str, int, int]],
    top_level: bool = True,
) -> None:
    if os.name == 'nt':
        remove_windows_edit_directory_contents(
            directory,
            expected_identity,
            transaction_root=transaction_root,
            expected_entries=expected_entries,
            top_level=top_level,
        )
        return

    def journal_order(name: str) -> tuple[int, str]:
        if top_level and name == EDIT_PREPARATION_MARKER_NAME:
            return 1, name
        if top_level and name == EDIT_TRANSACTION_MANIFEST_NAME:
            return 2, name
        return 0, name

    with hold_edit_directory_against_rename(
        directory,
        expected_identity,
    ) as directory_fd:
        if directory_fd is not None:
            entries = sorted(list(os.scandir(directory_fd)), key=lambda item: journal_order(item.name))
            for entry in entries:
                child = directory / entry.name
                relative_name = PurePosixPath(
                    *child.relative_to(transaction_root).parts
                ).as_posix()
                expected_entry = expected_entries.get(relative_name)
                if expected_entry is None:
                    raise OSError('An unowned entry appeared during edit cleanup.')
                if edit_cleanup_entry_identity(child) != expected_entry:
                    raise OSError('An edit cleanup entry changed identity before removal.')
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if stat.S_ISDIR(metadata.st_mode):
                    flags = os.O_RDONLY
                    flags |= int(getattr(os, 'O_DIRECTORY', 0))
                    flags |= int(getattr(os, 'O_NOFOLLOW', 0))
                    child_fd = os.open(entry.name, flags, dir_fd=directory_fd)
                    try:
                        child_metadata = os.fstat(child_fd)
                        child_identity = (
                            int(child_metadata.st_dev),
                            int(child_metadata.st_ino),
                        )
                    finally:
                        os.close(child_fd)
                    remove_edit_directory_contents(
                        child,
                        child_identity,
                        transaction_root=transaction_root,
                        expected_entries=expected_entries,
                        top_level=False,
                    )
                    os.rmdir(entry.name, dir_fd=directory_fd)
                    expected_entries.pop(relative_name, None)
                else:
                    os.unlink(entry.name, dir_fd=directory_fd)
                    expected_entries.pop(relative_name, None)
            if list(os.scandir(directory_fd)):
                raise OSError('A new entry appeared while edit cleanup was finishing.')
            os.fsync(directory_fd)
            return

        children = sorted(list(directory.iterdir()), key=lambda child: journal_order(child.name))
        for child in children:
            relative_name = PurePosixPath(
                *child.relative_to(transaction_root).parts
            ).as_posix()
            expected_entry = expected_entries.get(relative_name)
            if expected_entry is None:
                raise OSError('An unowned entry appeared during edit cleanup.')
            if edit_cleanup_entry_identity(child) != expected_entry:
                raise OSError('An edit cleanup entry changed identity before removal.')
            try:
                metadata = child.lstat()
            except FileNotFoundError:
                continue
            if path_is_link_or_reparse(child):
                if stat.S_ISDIR(metadata.st_mode):
                    child.rmdir()
                else:
                    child.unlink()
                expected_entries.pop(relative_name, None)
                continue
            if stat.S_ISDIR(metadata.st_mode):
                child_identity = (int(metadata.st_dev), int(metadata.st_ino))
                if not child_identity[1]:
                    raise OSError('A cleanup child has no stable filesystem identity.')
                remove_edit_directory_contents(
                    child,
                    child_identity,
                    transaction_root=transaction_root,
                    expected_entries=expected_entries,
                    top_level=False,
                )
                if edit_staging_identity(child) != child_identity:
                    raise OSError('A cleanup child identity changed before removal.')
                child.rmdir()
                expected_entries.pop(relative_name, None)
            else:
                child.unlink()
                expected_entries.pop(relative_name, None)
        if list(directory.iterdir()):
            raise OSError('A new entry appeared while edit cleanup was finishing.')
        sync_directory_metadata(directory, required=True)


def cleanup_edit_staging(
    staging_root: Path,
    *,
    expected_identity: tuple[int, int],
    inventory: dict[str, Any],
) -> list[str]:
    original_root = Path(os.path.abspath(os.fspath(staging_root)))
    errors: list[str] = []
    journal_snapshots: dict[str, tuple[tuple[str, int, int], bytes]] = {}
    try:
        with hold_edit_directory_against_rename(original_root, expected_identity):
            validate_edit_cleanup_inventory(original_root, inventory)
            ensure_staging_tree_has_no_reparse_points(original_root)
            for name in (EDIT_TRANSACTION_MANIFEST_NAME, EDIT_PREPARATION_MARKER_NAME):
                journal = original_root / name
                if journal.is_file() and not path_is_link_or_reparse(journal):
                    journal_snapshots[name] = (
                        edit_cleanup_entry_identity(journal),
                        journal.read_bytes(),
                    )
            if edit_staging_identity(original_root) != expected_identity:
                raise OSError('The edit staging identity changed during cleanup preflight.')
    except OSError as exc:
        return [str(exc)]

    quarantine = original_root.with_name(
        f'.edit-cleanup-{original_root.name.removeprefix(chr(46))}-{uuid.uuid4().hex}'
    )

    def preserve_journal_snapshot(root: Path, name: str, content: bytes) -> Path:
        recovery = root / (
            f'.{name}.authenticated-{uuid.uuid4().hex}.recovery'
        )
        temporary = root / f'.{recovery.name}.{uuid.uuid4().hex}.tmp'
        with temporary.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        durable_move(temporary, recovery, replace_existing=False)
        return recovery

    def restore_journals(root: Path) -> None:
        if edit_staging_identity(root) != expected_identity:
            raise OSError('The cleanup quarantine no longer belongs to this transaction.')
        with hold_edit_directory_against_rename(root, expected_identity):
            for name, (original_entry_identity, content) in journal_snapshots.items():
                target = root / name
                if target.exists() or target.is_symlink():
                    try:
                        target_matches = (
                            edit_cleanup_entry_identity(target) == original_entry_identity
                            and target.read_bytes() == content
                        )
                    except OSError:
                        target_matches = False
                    if target_matches:
                        continue
                    recovery = preserve_journal_snapshot(root, name, content)
                    raise OSError(
                        'A conflicting journal appeared during cleanup; the authenticated '
                        f'snapshot was retained at {recovery}.'
                    )
                temporary = root / f'.{name}.{uuid.uuid4().hex}.tmp'
                with temporary.open('xb') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    durable_move(temporary, target, replace_existing=False)
                except OSError:
                    recovery = preserve_journal_snapshot(root, name, content)
                    raise OSError(
                        'A journal could not be restored without replacement; the '
                        f'authenticated snapshot was retained at {recovery}.'
                    )
                if target.read_bytes() != content:
                    recovery = preserve_journal_snapshot(root, name, content)
                    raise OSError(
                        'A restored journal changed unexpectedly; the authenticated '
                        f'snapshot was retained at {recovery}.'
                    )

    def restore_quarantine() -> None:
        if not path_entry_exists(quarantine):
            return
        try:
            if edit_staging_identity(quarantine) != expected_identity:
                raise OSError('The cleanup quarantine was replaced; it was left untouched.')
            restore_journals(quarantine)
        except OSError as exc:
            errors.append(f'{quarantine}: could not preserve cleanup quarantine: {exc}')

    try:
        durable_move(original_root, quarantine, replace_existing=False)
    except OSError as exc:
        errors.append(f'{original_root}: could not quarantine edit staging: {exc}')
        if path_entry_exists(quarantine):
            restore_quarantine()
        return errors
    try:
        if edit_staging_identity(quarantine) != expected_identity:
            raise OSError('The edit staging identity changed before cleanup.')
        validate_edit_cleanup_inventory(quarantine, inventory)
        expected_entries = dict(inventory['entries'])
        remove_edit_directory_contents(
            quarantine,
            expected_identity,
            transaction_root=quarantine,
            expected_entries=expected_entries,
        )
        if expected_entries:
            raise OSError('The edit cleanup inventory was not removed completely.')
        if os.name == 'nt':
            if path_entry_exists(quarantine):
                raise OSError('The handle-bound edit cleanup did not remove its root.')
        else:
            if edit_staging_identity(quarantine) != expected_identity:
                raise OSError('The edit staging identity changed before final removal.')
            quarantine.rmdir()
        sync_directory_metadata(quarantine.parent, required=True)
    except OSError as exc:
        errors.append(f'{quarantine}: {exc}')
        restore_quarantine()
    return errors


def load_edit_transaction_manifest(
    staging_dir: Path,
    *,
    expected_storage_id: str,
    expected_secret: bytes,
) -> dict[str, Any]:
    try:
        staging_identity = edit_staging_identity(staging_dir)
        ensure_staging_tree_has_no_reparse_points(staging_dir)
    except OSError as exc:
        raise ValueError(str(exc)) from exc
    if staging_dir.is_symlink() or not staging_dir.is_dir():
        raise ValueError('An edit staging path is not a local directory.')
    staging_root = staging_dir.resolve()
    match = re.fullmatch(r'\.edit-staging-([0-9a-f]{32})', staging_root.name)
    if match is None:
        raise ValueError('An edit staging directory name is invalid.')
    manifest_path = staging_root / EDIT_TRANSACTION_MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError('An edit transaction manifest is missing or unsafe.')
    if manifest_path.stat().st_size > MAX_EDIT_TRANSACTION_MANIFEST_BYTES:
        raise ValueError('An edit transaction manifest is too large.')
    try:
        manifest_content = manifest_path.read_bytes()
        payload = json.loads(manifest_content.decode('utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('An edit transaction manifest cannot be read.') from exc
    if not isinstance(payload, dict):
        raise ValueError('An edit transaction manifest is not an object.')
    if payload.get('schema_version') != EDIT_TRANSACTION_SCHEMA_VERSION:
        raise ValueError('An edit transaction manifest has an unsupported schema.')
    if payload.get('kind') != 'library-edit':
        raise ValueError('An edit transaction manifest has an invalid kind.')
    if payload.get('transaction_id') != match.group(1):
        raise ValueError('An edit transaction ID does not match its directory.')
    if payload.get('storage_id') != expected_storage_id:
        raise ValueError('An edit transaction belongs to a different database.')
    supplied_mac = payload.get('mac')
    if (
        not isinstance(supplied_mac, str)
        or not re.fullmatch(r'[0-9a-f]{64}', supplied_mac)
        or not hmac.compare_digest(
            supplied_mac,
            edit_journal_mac(payload, expected_secret),
        )
    ):
        raise ValueError('An edit transaction manifest authentication failed.')

    item_id = payload.get('item_id')
    if (
        not isinstance(item_id, str)
        or not 1 <= len(item_id) <= 255
        or re.search(r'[\x00-\x1f]', item_id)
    ):
        raise ValueError('An edit transaction item ID is invalid.')
    expected_revision = payload.get('expected_revision')
    target_revision = payload.get('target_revision')
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
        or isinstance(target_revision, bool)
        or not isinstance(target_revision, int)
        or target_revision != expected_revision + 1
    ):
        raise ValueError('An edit transaction revision is invalid.')
    raw_output_dir = payload.get('output_dir')
    if not isinstance(raw_output_dir, str) or not raw_output_dir:
        raise ValueError('An edit transaction output directory is invalid.')
    output_root = Path(raw_output_dir).resolve()
    if output_root != staging_root.parent:
        raise ValueError('An edit transaction output directory does not match its location.')
    raw_previous_output_dir = payload.get('previous_output_dir')
    if not isinstance(raw_previous_output_dir, str) or not raw_previous_output_dir:
        raise ValueError('An edit transaction previous output directory is invalid.')
    previous_output_root = Path(raw_previous_output_dir).resolve()

    raw_files = payload.get('files')
    if not isinstance(raw_files, list) or not 1 <= len(raw_files) <= MAX_EDIT_TRANSACTION_FILES:
        raise ValueError('An edit transaction file list is invalid.')
    resolved_files: list[dict[str, Any]] = []
    seen: set[str] = set()
    allowed_files = {EDIT_TRANSACTION_MANIFEST_NAME}
    cleanup_file_options: dict[str, set[tuple[int, str]]] = {
        EDIT_TRANSACTION_MANIFEST_NAME: {
            (len(manifest_content), hashlib.sha256(manifest_content).hexdigest())
        },
    }
    preparation_marker = staging_root / EDIT_PREPARATION_MARKER_NAME
    if path_entry_exists(preparation_marker):
        if (
            path_is_link_or_reparse(preparation_marker)
            or not preparation_marker.is_file()
            or preparation_marker.stat().st_size > MAX_EDIT_TRANSACTION_MANIFEST_BYTES
        ):
            raise ValueError('A retained edit preparation marker is unsafe.')
        try:
            preparation_content = preparation_marker.read_bytes()
            preparation_payload = json.loads(preparation_content.decode('utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError('A retained edit preparation marker cannot be read.') from exc
        supplied_preparation_mac = (
            preparation_payload.get('mac')
            if isinstance(preparation_payload, dict)
            else None
        )
        if (
            not isinstance(preparation_payload, dict)
            or preparation_payload.get('schema_version') != EDIT_TRANSACTION_SCHEMA_VERSION
            or preparation_payload.get('kind') != 'library-edit-preparation'
            or preparation_payload.get('transaction_id') != match.group(1)
            or preparation_payload.get('storage_id') != expected_storage_id
            or preparation_payload.get('item_id') != item_id
            or preparation_payload.get('expected_revision') != expected_revision
            or not isinstance(supplied_preparation_mac, str)
            or not re.fullmatch(r'[0-9a-f]{64}', supplied_preparation_mac)
            or not hmac.compare_digest(
                supplied_preparation_mac,
                edit_journal_mac(preparation_payload, expected_secret),
            )
        ):
            raise ValueError('A retained edit preparation marker authentication failed.')
        allowed_files.add(EDIT_PREPARATION_MARKER_NAME)
        cleanup_file_options[EDIT_PREPARATION_MARKER_NAME] = {
            (
                len(preparation_content),
                hashlib.sha256(preparation_content).hexdigest(),
            )
        }
    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict):
            raise ValueError('An edit transaction file entry is invalid.')
        relative = safe_edit_relative_path(raw_entry.get('relative_path'))
        relative_text = PurePosixPath(*relative.parts).as_posix()
        relative_key = edit_relative_path_key(relative)
        if relative_key in seen:
            raise ValueError('An edit transaction contains duplicate targets.')
        seen.add(relative_key)
        had_previous = raw_entry.get('had_previous')
        new_size = raw_entry.get('new_size')
        new_sha256 = raw_entry.get('new_sha256')
        previous_size = raw_entry.get('previous_size')
        previous_sha256 = raw_entry.get('previous_sha256')
        if not isinstance(had_previous, bool):
            raise ValueError('An edit transaction previous-file flag is invalid.')
        if isinstance(new_size, bool) or not isinstance(new_size, int) or new_size < 0:
            raise ValueError('An edit transaction file size is invalid.')
        if not isinstance(new_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', new_sha256):
            raise ValueError('An edit transaction new-file fingerprint is invalid.')
        if not isinstance(previous_sha256, str) or (
            previous_sha256 and not re.fullmatch(r'[0-9a-f]{64}', previous_sha256)
        ):
            raise ValueError('An edit transaction previous-file fingerprint is invalid.')
        if previous_size is not None and (
            isinstance(previous_size, bool)
            or not isinstance(previous_size, int)
            or previous_size < 0
        ):
            raise ValueError('An edit transaction previous-file size is invalid.')
        if bool(previous_sha256) != (previous_size is not None):
            raise ValueError('An edit transaction previous-file identity is incomplete.')
        if had_previous != bool(previous_sha256):
            raise ValueError('An edit transaction previous-file identity is inconsistent.')
        target = output_root / relative
        staged = staging_root / relative
        backup = staging_root / '.previous' / relative
        discarded = staging_root / '.discarded' / relative
        if not path_is_within(target, output_root):
            raise ValueError('An edit transaction target escapes its output directory.')
        for internal in (staged, backup, discarded):
            if not path_is_within(internal, staging_root):
                raise ValueError('An edit transaction path escapes its staging directory.')
        allowed_files.update({
            relative_text,
            f'.previous/{relative_text}',
            f'.discarded/{relative_text}',
        })
        cleanup_file_options.setdefault(relative_text, set()).add(
            (new_size, new_sha256)
        )
        cleanup_file_options.setdefault(
            f'.discarded/{relative_text}',
            set(),
        ).add((new_size, new_sha256))
        if had_previous:
            cleanup_file_options.setdefault(
                f'.previous/{relative_text}',
                set(),
            ).add((previous_size, previous_sha256))
        resolved_files.append({
            'relative': relative,
            'had_previous': had_previous,
            'new_size': new_size,
            'new_sha256': new_sha256,
            'previous_size': previous_size,
            'previous_sha256': previous_sha256,
            'target': target,
            'staged': staged,
            'backup': backup,
            'discarded': discarded,
        })

    actual_seen: set[str] = set()
    for candidate in staging_root.rglob('*'):
        if path_is_link_or_reparse(candidate):
            raise ValueError('An edit transaction contains a symbolic link.')
        relative_path = candidate.relative_to(staging_root)
        actual_key = edit_relative_path_key(relative_path)
        if actual_key in actual_seen:
            raise ValueError('An edit transaction contains a Windows path collision.')
        actual_seen.add(actual_key)
        if candidate.is_file():
            relative_name = PurePosixPath(*relative_path.parts).as_posix()
            if relative_name not in allowed_files:
                raise ValueError('An edit transaction contains an unlisted file.')
    if edit_staging_identity(staging_root) != staging_identity:
        raise ValueError('An edit staging identity changed while its manifest was loaded.')
    payload['_output_root'] = output_root
    payload['_previous_output_root'] = previous_output_root
    payload['_resolved_files'] = resolved_files
    payload['_staging_identity'] = staging_identity
    payload['_cleanup_file_options'] = cleanup_file_options
    payload['_cleanup_inventory'] = capture_edit_cleanup_inventory(
        staging_root,
        cleanup_file_options,
    )
    return payload


def load_edit_preparation_marker(
    staging_dir: Path,
    *,
    expected_storage_id: str,
    expected_secret: bytes,
) -> dict[str, Any]:
    try:
        staging_identity = edit_staging_identity(staging_dir)
        ensure_staging_tree_has_no_reparse_points(staging_dir)
    except OSError as exc:
        raise ValueError(str(exc)) from exc
    staging_root = staging_dir.resolve()
    final_match = re.fullmatch(r'\.edit-staging-([0-9a-f]{32})', staging_root.name)
    preparing_match = re.fullmatch(
        r'\.edit-preparing-([0-9a-f]{32})-[0-9a-f]{32}',
        staging_root.name,
    )
    match = final_match or preparing_match
    if match is None:
        raise ValueError('An edit preparation directory name is invalid.')
    marker = staging_root / EDIT_PREPARATION_MARKER_NAME
    if not marker.is_file() or path_is_link_or_reparse(marker):
        raise ValueError('An authenticated edit preparation marker is missing.')
    if marker.stat().st_size > MAX_EDIT_TRANSACTION_MANIFEST_BYTES:
        raise ValueError('An edit preparation marker is too large.')
    try:
        marker_content = marker.read_bytes()
        payload = json.loads(marker_content.decode('utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('An edit preparation marker cannot be read.') from exc
    if not isinstance(payload, dict):
        raise ValueError('An edit preparation marker is not an object.')
    if payload.get('schema_version') != EDIT_TRANSACTION_SCHEMA_VERSION:
        raise ValueError('An edit preparation marker has an unsupported schema.')
    if payload.get('kind') != 'library-edit-preparation':
        raise ValueError('An edit preparation marker has an invalid kind.')
    if payload.get('transaction_id') != match.group(1):
        raise ValueError('An edit preparation ID does not match its directory.')
    final_staging_name = payload.get('final_staging_name')
    expected_final_staging_name = f'.edit-staging-{match.group(1)}'
    if (
        final_staging_name not in {None, expected_final_staging_name}
        or preparing_match is not None
        and final_staging_name != expected_final_staging_name
    ):
        raise ValueError('An edit preparation final directory is invalid.')
    if payload.get('storage_id') != expected_storage_id:
        raise ValueError('An edit preparation belongs to a different database.')
    supplied_mac = payload.get('mac')
    if (
        not isinstance(supplied_mac, str)
        or not re.fullmatch(r'[0-9a-f]{64}', supplied_mac)
        or not hmac.compare_digest(
            supplied_mac,
            edit_journal_mac(payload, expected_secret),
        )
    ):
        raise ValueError('An edit preparation marker authentication failed.')
    item_id = payload.get('item_id')
    expected_revision = payload.get('expected_revision')
    if (
        not isinstance(item_id, str)
        or not 1 <= len(item_id) <= 255
        or re.search(r'[\x00-\x1f]', item_id)
        or isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        raise ValueError('An edit preparation identity is invalid.')
    raw_output_dir = payload.get('output_dir')
    raw_previous_output_dir = payload.get('previous_output_dir')
    if not isinstance(raw_output_dir, str) or not raw_output_dir:
        raise ValueError('An edit preparation output directory is invalid.')
    if not isinstance(raw_previous_output_dir, str) or not raw_previous_output_dir:
        raise ValueError('An edit preparation previous output directory is invalid.')
    output_root = Path(raw_output_dir).resolve()
    if output_root != staging_root.parent:
        raise ValueError('An edit preparation output directory does not match its location.')
    cleanup_file_options: dict[str, set[tuple[int, str]]] = {
        EDIT_PREPARATION_MARKER_NAME: {
            (len(marker_content), hashlib.sha256(marker_content).hexdigest())
        },
    }
    raw_files = payload.get('files')
    if raw_files is not None:
        if not isinstance(raw_files, list) or not 1 <= len(raw_files) <= MAX_EDIT_TRANSACTION_FILES:
            raise ValueError('An edit preparation file list is invalid.')
        seen_files: set[str] = set()
        for raw_entry in raw_files:
            if not isinstance(raw_entry, dict):
                raise ValueError('An edit preparation file entry is invalid.')
            relative = safe_edit_relative_path(raw_entry.get('relative_path'))
            relative_name = PurePosixPath(*relative.parts).as_posix()
            relative_key = edit_relative_path_key(relative)
            if relative_key in seen_files:
                raise ValueError('An edit preparation contains duplicate targets.')
            seen_files.add(relative_key)
            size = raw_entry.get('size')
            sha256 = raw_entry.get('sha256')
            device = raw_entry.get('device')
            inode = raw_entry.get('inode')
            if (
                isinstance(size, bool)
                or not isinstance(size, int)
                or size < 0
                or not isinstance(sha256, str)
                or not re.fullmatch(r'[0-9a-f]{64}', sha256)
                or isinstance(device, bool)
                or not isinstance(device, int)
                or device < 0
                or isinstance(inode, bool)
                or not isinstance(inode, int)
                or inode <= 0
            ):
                raise ValueError('An edit preparation file identity is invalid.')
            prepared_path = staging_root / relative
            if not path_is_within(prepared_path, staging_root):
                raise ValueError('An edit preparation file escapes staging.')
            if edit_cleanup_entry_identity(prepared_path) != ('file', device, inode):
                raise ValueError('An edit preparation file changed filesystem identity.')
            if not file_matches_fingerprint(prepared_path, sha256, size):
                raise ValueError('An edit preparation file changed content.')
            cleanup_file_options.setdefault(relative_name, set()).add((size, sha256))
    try:
        cleanup_inventory = capture_edit_cleanup_inventory(
            staging_root,
            cleanup_file_options,
        )
    except OSError as exc:
        raise ValueError(str(exc)) from exc
    if edit_staging_identity(staging_root) != staging_identity:
        raise ValueError('An edit staging identity changed while its marker was loaded.')
    payload['_output_root'] = output_root
    payload['_previous_output_root'] = Path(raw_previous_output_dir).resolve()
    payload['_staging_identity'] = staging_identity
    payload['_cleanup_file_options'] = cleanup_file_options
    payload['_cleanup_inventory'] = cleanup_inventory
    return payload


def edit_transaction_cleanup_inventory(
    staging_root: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inventory = capture_edit_cleanup_inventory(
        staging_root,
        payload['_cleanup_file_options'],
    )
    if inventory['root_identity'] != payload['_staging_identity']:
        raise OSError('The edit staging identity changed before cleanup inventory refresh.')
    return inventory


def transaction_file_kind(path: Path, entry: dict[str, Any], *, previous=False) -> str:
    if not path_entry_exists(path):
        return 'missing'
    if previous and entry['previous_sha256'] and file_matches_fingerprint(path,entry['previous_sha256'],entry['previous_size']):
        return 'previous'
    if file_matches_fingerprint(path, entry['new_sha256'], entry['new_size']):
        return 'new'
    previous_sha256 = entry['previous_sha256']
    previous_size = entry['previous_size']
    if previous_sha256 and file_matches_fingerprint(
        path, previous_sha256, previous_size
    ):
        return 'previous'
    return 'unknown'


def preflight_rollback_edit_transaction(
    payload: dict[str, Any],
) -> list[tuple[dict[str, Any], str, str, str, str]]:
    states: list[tuple[dict[str, Any], str, str, str, str]] = []
    for entry in payload['_resolved_files']:
        target_kind = transaction_file_kind(entry['target'], entry, previous=True)
        staged_kind = transaction_file_kind(entry['staged'], entry)
        backup_kind = transaction_file_kind(entry['backup'], entry, previous=True)
        discarded_kind = transaction_file_kind(entry['discarded'], entry)
        if staged_kind not in {'missing', 'new'}:
            raise OSError('An edit transaction staged file was changed externally.')
        if discarded_kind not in {'missing', 'new'}:
            raise OSError('An edit transaction discarded file was changed externally.')
        if entry['had_previous']:
            if target_kind not in {'missing', 'new', 'previous'}:
                raise OSError('An edit transaction target was changed externally.')
            if backup_kind not in {'missing', 'previous'}:
                raise OSError('An edit transaction backup was changed externally.')
            if target_kind != 'previous' and backup_kind != 'previous':
                raise OSError('An edit transaction lost its previous output.')
        else:
            if target_kind not in {'missing', 'new'}:
                raise OSError('A new edit target was changed externally.')
            if backup_kind != 'missing':
                raise OSError('A new edit transaction has an unexpected backup.')
        states.append((entry, target_kind, staged_kind, backup_kind, discarded_kind))
    return states


def discard_transaction_target(entry: dict[str, Any]) -> None:
    target = entry['target']
    discarded = entry['discarded']
    if path_entry_exists(discarded):
        if not file_matches_fingerprint(
            discarded, entry['new_sha256'], entry['new_size']
        ):
            raise OSError('An edit transaction has a conflicting discarded file.')
        if not file_matches_fingerprint(
            target, entry['new_sha256'], entry['new_size']
        ):
            raise OSError('An edit transaction target was changed externally.')
        target.unlink()
        sync_directory_metadata(target.parent)
        return
    discarded.parent.mkdir(parents=True, exist_ok=True)
    durable_move(target, discarded)
    sync_rename_metadata(target, discarded)


def rollback_edit_transaction(staging_root: Path, payload: dict[str, Any]) -> None:
    states = preflight_rollback_edit_transaction(payload)
    for entry, target_kind, _, backup_kind, _ in reversed(states):
        target = entry['target']
        backup = entry['backup']
        had_previous = entry['had_previous']
        if had_previous:
            if target_kind == 'previous':
                if not file_matches_fingerprint(
                    target, entry['previous_sha256'], entry['previous_size']
                ):
                    raise OSError('An edit target changed after recovery preflight.')
                if backup_kind == 'previous' and not file_matches_fingerprint(
                    backup, entry['previous_sha256'], entry['previous_size']
                ):
                    raise OSError('An edit backup changed after recovery preflight.')
                continue
            if backup_kind != 'previous' or not file_matches_fingerprint(
                backup, entry['previous_sha256'], entry['previous_size']
            ):
                raise OSError('An edit backup changed after recovery preflight.')
            if target_kind == 'new':
                if not file_matches_fingerprint(
                    target, entry['new_sha256'], entry['new_size']
                ):
                    raise OSError('An edit target changed after recovery preflight.')
                discard_transaction_target(entry)
            elif path_entry_exists(target):
                raise OSError('An edit target appeared after recovery preflight.')
            target.parent.mkdir(parents=True, exist_ok=True)
            durable_move(backup, target)
            sync_rename_metadata(backup, target)
            if not file_matches_fingerprint(
                target, entry['previous_sha256'], entry['previous_size']
            ):
                raise OSError('An edit transaction backup could not be restored exactly.')
            continue

        if target_kind == 'new':
            if not file_matches_fingerprint(
                target, entry['new_sha256'], entry['new_size']
            ):
                raise OSError('A new edit target changed after recovery preflight.')
            discard_transaction_target(entry)
        elif path_entry_exists(target):
            raise OSError('A new edit target appeared after recovery preflight.')

    cleanup_errors = cleanup_edit_staging(
        staging_root,
        expected_identity=payload['_staging_identity'],
        inventory=edit_transaction_cleanup_inventory(staging_root, payload),
    )
    if cleanup_errors:
        raise OSError('Edit rollback cleanup failed: ' + '; '.join(cleanup_errors))


def finish_committed_edit_transaction(
    staging_root: Path,
    payload: dict[str, Any],
) -> list[str]:
    states: list[tuple[dict[str, Any], str, str, str, str]] = []
    for entry in payload['_resolved_files']:
        target_kind = transaction_file_kind(entry['target'], entry)
        staged_kind = transaction_file_kind(entry['staged'], entry)
        backup_kind = transaction_file_kind(entry['backup'], entry, previous=True)
        discarded_kind = transaction_file_kind(entry['discarded'], entry)
        if staged_kind not in {'missing', 'new'}:
            raise OSError('A committed edit staged file was changed externally.')
        if backup_kind not in {'missing', 'previous'}:
            raise OSError('A committed edit backup was changed externally.')
        if discarded_kind not in {'missing', 'new'}:
            raise OSError('A committed edit discarded file was changed externally.')
        if target_kind == 'previous' and not entry['had_previous']:
            raise OSError('A committed new target was changed externally.')
        if target_kind not in {'new', 'missing', 'previous'}:
            raise OSError('A committed edit target was changed externally.')
        if target_kind != 'new' and staged_kind != 'new':
            raise OSError('A committed edit target and its staged copy are missing.')
        states.append((entry, target_kind, staged_kind, backup_kind, discarded_kind))

    for entry, target_kind, staged_kind, backup_kind, _ in states:
        target = entry['target']
        staged = entry['staged']
        backup = entry['backup']
        if target_kind == 'new':
            if not file_matches_fingerprint(target, entry['new_sha256'], entry['new_size']):
                raise OSError('A committed edit target changed after recovery preflight.')
            continue
        if staged_kind != 'new' or not file_matches_fingerprint(
            staged, entry['new_sha256'], entry['new_size']
        ):
            raise OSError('A committed staged file changed after recovery preflight.')
        if target_kind == 'previous':
            if not file_matches_fingerprint(
                target, entry['previous_sha256'], entry['previous_size']
            ):
                raise OSError('A committed previous target changed after recovery preflight.')
            if backup_kind == 'previous':
                if not file_matches_fingerprint(
                    backup, entry['previous_sha256'], entry['previous_size']
                ):
                    raise OSError('A committed backup changed after recovery preflight.')
                target.unlink()
                sync_directory_metadata(target.parent)
            else:
                backup.parent.mkdir(parents=True, exist_ok=True)
                durable_move(target, backup)
                sync_rename_metadata(target, backup)
        elif path_entry_exists(target):
            raise OSError('A committed target appeared after recovery preflight.')
        target.parent.mkdir(parents=True, exist_ok=True)
        durable_move(staged, target)
        sync_rename_metadata(staged, target)
        if not file_matches_fingerprint(target, entry['new_sha256'], entry['new_size']):
            raise OSError('A committed edit target could not be restored exactly.')
    return cleanup_edit_staging(
        staging_root,
        expected_identity=payload['_staging_identity'],
        inventory=edit_transaction_cleanup_inventory(staging_root, payload),
    )


def reconcile_edit_transaction_with_database(
    staging_root: Path,
    payload: dict[str, Any],
    *,
    connect: Callable[[], Any],
) -> list[str]:
    with connect() as connection:
        row = connection.execute(
            'SELECT revision_count, output_dir FROM library_items WHERE id = ?',
            (payload['item_id'],),
        ).fetchone()
    if row is None:
        raise OSError('The edit transaction library row is missing.')
    current_revision = int(row['revision_count'] or 0)
    current_output_root = Path(str(row['output_dir'])).resolve()
    if current_revision == payload['expected_revision']:
        if current_output_root != payload['_previous_output_root']:
            raise OSError('The uncommitted edit does not match the library output directory.')
        rollback_edit_transaction(staging_root, payload)
        return []
    if current_revision == payload['target_revision']:
        if current_output_root != payload['_output_root']:
            raise OSError('The committed edit does not match the library output directory.')
        return finish_committed_edit_transaction(staging_root, payload)
    if current_revision > payload['target_revision']:
        if current_output_root != payload['_output_root']:
            raise OSError(
                'A stale edit transaction belongs to a different output directory.'
            )
        return cleanup_edit_staging(
            staging_root,
            expected_identity=payload['_staging_identity'],
            inventory=edit_transaction_cleanup_inventory(staging_root, payload),
        )
    raise OSError('The database revision predates the edit transaction.')


def preflight_edit_promotion(
    staging_root: Path,
    staged_files: list[Path],
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    expected = {
        edit_relative_path_key(entry['relative']): entry
        for entry in payload['_resolved_files']
    }
    supplied: dict[str, Path] = {}
    for staged_path in staged_files:
        if path_is_link_or_reparse(staged_path):
            raise OSError('A staged output file is a symbolic link or reparse point.')
        staged = staged_path.resolve()
        if not path_is_within(staged, staging_root) or not staged.is_file():
            raise OSError('A staged output file is missing or outside the staging directory.')
        relative_key = edit_relative_path_key(staged.relative_to(staging_root))
        if relative_key in supplied:
            raise OSError('Duplicate staged output target.')
        supplied[relative_key] = staged
    if set(supplied) != set(expected):
        raise OSError('The staged output set does not match its edit transaction manifest.')
    for relative_key, entry in expected.items():
        staged = supplied[relative_key]
        if not file_matches_fingerprint(staged, entry['new_sha256'], entry['new_size']):
            raise OSError('A staged output file was changed after manifest creation.')
        if path_entry_exists(entry['backup']) or path_entry_exists(entry['discarded']):
            raise OSError('A new edit transaction already contains promoted state.')
        if entry['had_previous']:
            if not file_matches_fingerprint(
                entry['target'], entry['previous_sha256'], entry['previous_size']
            ):
                raise OSError('An edit target was changed after manifest creation.')
        elif path_entry_exists(entry['target']):
            raise OSError('A new edit target appeared after manifest creation.')
    return expected


@contextmanager
def promote_staged_files(
    staging_dir: Path,
    output_dir: Path,
    staged_files: list[Path],
    *,
    connect: Callable[[], Any],
):
    staging_root = staging_dir.resolve()
    staging_identity = edit_staging_identity(staging_root)
    output_root = output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    backup_root = staging_root / ".previous"
    states: list[tuple[Path, Path | None, Path, int, str]] = []
    final_files: list[Path] = []
    seen: set[str] = set()
    retain_staging = False
    cleanup_handled = False
    transaction_payload: dict[str, Any] | None = None
    transaction_entries: dict[str, dict[str, Any]] = {}
    cleanup_file_options: dict[str, set[tuple[int, str]]] = {}
    manifest = staging_root / EDIT_TRANSACTION_MANIFEST_NAME
    if manifest.is_file() and not manifest.is_symlink():
        with connect() as connection:
            storage_id = edit_storage_id(connection, connect=connect)
            journal_secret = edit_journal_secret(connection, connect=connect)
        transaction_payload = load_edit_transaction_manifest(
            staging_root,
            expected_storage_id=storage_id,
            expected_secret=journal_secret,
        )
        staging_identity = transaction_payload['_staging_identity']
        transaction_entries = {
            edit_relative_path_key(entry['relative']): entry
            for entry in transaction_payload['_resolved_files']
        }
        transaction_entries = preflight_edit_promotion(
            staging_root,
            staged_files,
            transaction_payload,
        )
    try:
        for staged_path in staged_files:
            staged = staged_path.resolve()
            if not path_is_within(staged, staging_root) or not staged.is_file():
                raise OSError("A staged output file is missing or outside the staging directory.")
            relative = staged.relative_to(staging_root)
            target = output_root / relative
            relative_key = edit_relative_path_key(relative)
            if relative_key in seen:
                raise OSError("Duplicate staged output target.")
            seen.add(relative_key)
            transaction_entry = transaction_entries.get(relative_key)
            if transaction_payload is not None and transaction_entry is None:
                raise OSError('A staged file is absent from its edit transaction manifest.')
            if transaction_entry is not None:
                staged_size = transaction_entry['new_size']
                staged_sha256 = transaction_entry['new_sha256']
                if not file_matches_fingerprint(staged, staged_sha256, staged_size):
                    raise OSError('A staged output changed after promotion preflight.')
                if transaction_entry['had_previous']:
                    if not file_matches_fingerprint(
                        target,
                        transaction_entry['previous_sha256'],
                        transaction_entry['previous_size'],
                    ):
                        raise OSError('An edit target changed after promotion preflight.')
                elif path_entry_exists(target):
                    raise OSError('A new edit target appeared after promotion preflight.')
                if path_entry_exists(transaction_entry['backup']):
                    raise OSError('An edit backup appeared after promotion preflight.')
                if path_entry_exists(transaction_entry['discarded']):
                    raise OSError('An edit discarded file appeared after promotion preflight.')
            else:
                staged_size = staged.stat().st_size
                staged_sha256 = file_sha256(staged)
            relative_name = PurePosixPath(*relative.parts).as_posix()
            cleanup_file_options.setdefault(relative_name, set()).add(
                (staged_size, staged_sha256)
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            backup: Path | None = None
            if target.exists() or target.is_symlink():
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                durable_move(target, backup)
                sync_rename_metadata(target, backup)
                if transaction_entry is not None and not file_matches_fingerprint(
                    backup,
                    transaction_entry['previous_sha256'],
                    transaction_entry['previous_size'],
                ):
                    raise OSError('An edit backup changed during promotion.')
                if transaction_entry is None:
                    backup_name = PurePosixPath('.previous', *relative.parts).as_posix()
                    cleanup_file_options.setdefault(backup_name, set()).add(
                        (backup.stat().st_size, file_sha256(backup))
                    )
            states.append((target, backup, relative, staged_size, staged_sha256))
            if transaction_entry is not None:
                # Keep the authenticated new copy until the database commit is
                # known to have completed. If the target is replaced while the
                # transaction yields, recovery still has both old and new data.
                atomic_copy_file(staged, target, replace_existing=False)
            else:
                durable_move(staged, target)
                sync_rename_metadata(staged, target)
            if not file_matches_fingerprint(target, staged_sha256, staged_size):
                raise OSError('A promoted edit target does not match its manifest.')
            final_files.append(target)
        yield final_files
        for target, _, _, staged_size, staged_sha256 in states:
            if not file_matches_fingerprint(target, staged_sha256, staged_size):
                raise OSError('A promoted output target changed during database commit.')
    except BaseException as original_exc:
        if transaction_payload is not None:
            try:
                recovery_warnings = reconcile_edit_transaction_with_database(
                    staging_root,
                    transaction_payload,
                    connect=connect,
                )
                cleanup_handled = True
                if recovery_warnings:
                    print(
                        'Edit transaction reconciliation warning: '
                        + '; '.join(recovery_warnings),
                        file=sys.stderr,
                    )
            except (OSError, ValueError, sqlite3.Error) as recovery_exc:
                retain_staging = True
                raise OSError(
                    'Output commit state was uncertain; recovery files were retained at '
                    f'{staging_root}: {recovery_exc}'
                ) from original_exc
            raise
        rollback_errors: list[str] = []
        for target, backup, relative, staged_size, staged_sha256 in reversed(states):
            try:
                if target.exists() or target.is_symlink():
                    if not file_matches_fingerprint(
                        target, staged_sha256, staged_size
                    ):
                        raise OSError('A promoted output target was changed externally.')
                    discarded = staging_root / '.discarded' / relative
                    discarded.parent.mkdir(parents=True, exist_ok=True)
                    durable_move(target, discarded)
                    sync_rename_metadata(target, discarded)
                    discarded_name = PurePosixPath(
                        '.discarded',
                        *relative.parts,
                    ).as_posix()
                    cleanup_file_options.setdefault(discarded_name, set()).add(
                        (staged_size, staged_sha256)
                    )
                if backup is not None and backup.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    durable_move(backup, target)
                    sync_rename_metadata(backup, target)
            except OSError as exc:
                rollback_errors.append(str(exc))
        if rollback_errors:
            retain_staging = True
            raise OSError(
                "Output rollback failed; recovery files were retained at "
                f"{staging_root}: {'; '.join(rollback_errors)}"
            ) from original_exc
        raise
    finally:
        if not retain_staging and not cleanup_handled:
            cleanup_inventory = (
                edit_transaction_cleanup_inventory(staging_root, transaction_payload)
                if transaction_payload is not None
                else capture_edit_cleanup_inventory(
                    staging_root,
                    cleanup_file_options,
                )
            )
            cleanup_errors = cleanup_edit_staging(
                staging_root,
                expected_identity=staging_identity,
                inventory=cleanup_inventory,
            )
            if cleanup_errors:
                print(
                    'Edit staging cleanup warning: ' + '; '.join(cleanup_errors),
                    file=sys.stderr,
                )


# --- Startup and pre-mutation recovery ------------------------------------

def recover_delete_quarantines(
    *,
    connect: Callable[[], Any],
    media_directory: Path,
    thumbnail_directory: Path,
) -> list[str]:
    """Resolve crash-left delete staging from the canonical library row state."""
    warnings: list[str] = []
    storage_roots = ((media_directory, "media"), (thumbnail_directory, "thumbnail"))
    with connect() as connection:
        from .library_trash import protected_quarantine_assets

        # The trash, like app.trash_directory(), lives beside the active DB.
        database = next((row[2] for row in connection.execute("PRAGMA database_list")
                         if row[1] == "main"), "")
        protected = (protected_quarantine_assets(Path(database).parent / "trash")
                     if database else None)
        for storage_root, asset_kind in storage_roots:
            if not storage_root.is_dir():
                continue
            for quarantine_root in sorted(storage_root.glob(".delete-staging-*")):
                if quarantine_root.is_symlink() or not quarantine_root.is_dir():
                    warnings.append(f"Unrecognized delete quarantine retained: {quarantine_root}")
                    continue
                try:
                    quarantined_assets = list(quarantine_root.iterdir())
                except OSError as exc:
                    warnings.append(f"Could not inspect delete quarantine {quarantine_root}: {exc}")
                    continue
                for quarantined in quarantined_assets:
                    if asset_kind == "media":
                        item_id = quarantined.name
                    else:
                        match = re.fullmatch(
                            r"(?:text_mining|word_cloud)_(.+)\.svg",
                            quarantined.name,
                        )
                        item_id = match.group(1) if match else ""
                    if not item_id:
                        warnings.append(f"Unrecognized quarantined asset retained: {quarantined}")
                        continue
                    row_exists = connection.execute(
                        "SELECT 1 FROM library_items WHERE id = ?",
                        (item_id,),
                    ).fetchone() is not None
                    if not row_exists and (protected is None or (asset_kind, quarantined.name) in protected):
                        warnings.append(f"Unfinished trash asset retained for recovery: {quarantined}")
                        continue
                    target = storage_root / quarantined.name
                    try:
                        if row_exists:
                            if target.exists() or target.is_symlink():
                                warnings.append(
                                    f"Delete recovery target already exists; quarantine retained: {quarantined}"
                                )
                                continue
                            durable_move(quarantined, target, replace_existing=False)
                        elif quarantined.is_dir() and not quarantined.is_symlink():
                            shutil.rmtree(quarantined)
                        else:
                            quarantined.unlink(missing_ok=True)
                    except OSError as exc:
                        action = "restore" if row_exists else "remove"
                        warnings.append(
                            f"Could not {action} quarantined asset {quarantined}: {exc}"
                        )
                try:
                    quarantine_root.rmdir()
                except OSError:
                    # Unknown, conflicting, or locked assets remain recoverable.
                    pass
    return warnings


def discover_edit_transaction_staging_dirs(
    *,
    additional_output_roots: list[Path] | None = None,
    include_database_outputs: bool = True,
    connect: Callable[[], Any],
    output_root: Path,
) -> list[Path]:
    candidates: dict[str, Path] = {}
    scan_errors: list[str] = []

    def remember(candidate: Path) -> None:
        cleanup_match = re.fullmatch(
            r'\.edit-cleanup-((?:edit-staging-[0-9a-f]{32}|edit-preparing-[0-9a-f]{32}-[0-9a-f]{32}))-[0-9a-f]{32}',
            candidate.name,
        )
        if cleanup_match is not None:
            try:
                if path_is_link_or_reparse(candidate) or not candidate.is_dir():
                    scan_errors.append(f'Unsafe edit cleanup quarantine: {candidate}')
                    return
                cleanup_identity = edit_staging_identity(candidate)
                with hold_edit_directory_against_rename(candidate, cleanup_identity):
                    cleanup_children = list(candidate.iterdir())
                if not cleanup_children:
                    if edit_staging_identity(candidate) != cleanup_identity:
                        raise OSError('An empty cleanup quarantine changed identity.')
                    candidate.rmdir()
                    sync_directory_metadata(candidate.parent, required=True)
                    return
                journal_names = {
                    EDIT_TRANSACTION_MANIFEST_NAME,
                    EDIT_PREPARATION_MARKER_NAME,
                }
                if any(
                    re.fullmatch(
                        r'\..+\.authenticated-[0-9a-f]{32}\.recovery',
                        child.name,
                    )
                    for child in cleanup_children
                ):
                    print(
                        f'Conflicted edit cleanup quarantine retained: {candidate}',
                        file=sys.stderr,
                    )
                    return
                if not any(child.name in journal_names for child in cleanup_children):
                    print(
                        f'Unrecognized edit cleanup quarantine retained: {candidate}',
                        file=sys.stderr,
                    )
                    return
                restored = candidate.with_name(f'.{cleanup_match.group(1)}')
                if path_entry_exists(restored):
                    scan_errors.append(
                        f'Edit cleanup quarantine conflicts with staging path: {candidate}'
                    )
                    return
                durable_move(candidate, restored, replace_existing=False)
                if edit_staging_identity(restored) != cleanup_identity:
                    raise OSError('A cleanup quarantine changed identity during restore.')
                candidate = restored
            except OSError as exc:
                scan_errors.append(f'{candidate}: {exc}')
                return
        if not re.fullmatch(
            r'(?:\.edit-staging-[0-9a-f]{32}|\.edit-preparing-[0-9a-f]{32}-[0-9a-f]{32})',
            candidate.name,
        ):
            return
        try:
            if path_is_link_or_reparse(candidate) or not candidate.is_dir():
                scan_errors.append(f'Unsafe edit staging path: {candidate}')
                return
        except OSError as exc:
            scan_errors.append(f'{candidate}: {exc}')
            return
        key = windows_case_insensitive_text(os.path.abspath(str(candidate)))
        candidates.setdefault(key, candidate)

    default_root = Path(os.path.abspath(os.fspath(output_root)))
    if path_entry_exists(default_root):
        if path_has_reparse_ancestor(default_root) or not default_root.is_dir():
            scan_errors.append(f'Unsafe default output directory: {default_root}')
        else:
            pending = [default_root]
            visited: set[tuple[Any, ...]] = set()
            while pending:
                current = pending.pop()
                try:
                    if path_is_link_or_reparse(current):
                        scan_errors.append(f'Output directory became a reparse point: {current}')
                        continue
                    current_stat = current.stat()
                    if int(current_stat.st_ino):
                        identity = (
                            'inode',
                            int(current_stat.st_dev),
                            int(current_stat.st_ino),
                        )
                    else:
                        identity = (
                            'path',
                            windows_case_insensitive_text(
                                os.path.abspath(str(current))
                            ),
                        )
                    if identity in visited:
                        continue
                    visited.add(identity)
                    with os.scandir(current) as entries:
                        children = list(entries)
                except OSError as exc:
                    scan_errors.append(f'{current}: {exc}')
                    continue
                for entry in children:
                    child = Path(entry.path)
                    stage_name = bool(re.fullmatch(
                        r'(?:\.edit-staging-[0-9a-f]{32}|\.edit-preparing-[0-9a-f]{32}-[0-9a-f]{32}|\.edit-cleanup-(?:edit-staging-[0-9a-f]{32}|edit-preparing-[0-9a-f]{32}-[0-9a-f]{32})-[0-9a-f]{32})',
                        entry.name,
                    ))
                    try:
                        if path_is_link_or_reparse(child):
                            if stage_name:
                                scan_errors.append(
                                    f'Unsafe edit staging reparse point: {child}'
                                )
                            continue
                        is_directory = entry.is_dir(follow_symlinks=False)
                    except OSError as exc:
                        scan_errors.append(f'{child}: {exc}')
                        continue
                    if stage_name:
                        if is_directory:
                            remember(child)
                        else:
                            scan_errors.append(f'Edit staging path is not a directory: {child}')
                    elif is_directory:
                        pending.append(child)

    output_roots = list(additional_output_roots or [])
    if include_database_outputs:
        with connect() as connection:
            output_rows = connection.execute(
                'SELECT DISTINCT output_dir FROM library_items'
            ).fetchall()
        output_roots.extend(Path(str(row['output_dir'])) for row in output_rows)
    for raw_output_root in output_roots:
        try:
            output_root = Path(os.path.abspath(os.fspath(raw_output_root)))
            if path_has_reparse_ancestor(output_root):
                scan_errors.append(f'Unsafe output directory reparse point: {output_root}')
                continue
            if not output_root.is_dir():
                continue
            for candidate in output_root.glob('.edit-staging-*'):
                remember(candidate)
            for candidate in output_root.glob('.edit-preparing-*'):
                remember(candidate)
            for candidate in output_root.glob('.edit-cleanup-*'):
                remember(candidate)
        except OSError as exc:
            scan_errors.append(str(exc))
    if scan_errors:
        raise OSError('Could not scan edit transactions: ' + '; '.join(scan_errors))
    return sorted(candidates.values(), key=lambda path: os.path.normcase(str(path)))


def cleanup_prepared_edit_staging(
    staging_dir: Path,
    payload: dict[str, Any],
) -> None:
    ensure_staging_tree_has_no_reparse_points(staging_dir)
    cleanup_errors = cleanup_edit_staging(
        staging_dir,
        expected_identity=payload['_staging_identity'],
        inventory=payload['_cleanup_inventory'],
    )
    if cleanup_errors:
        raise OSError('Prepared edit staging cleanup failed: ' + '; '.join(cleanup_errors))


def recover_edit_transactions(
    *,
    connect: Callable[[], Any],
    output_root: Path,
) -> list[str]:
    staging_dirs = discover_edit_transaction_staging_dirs(
        connect=connect, output_root=output_root
    )
    if not staging_dirs:
        return []
    with connect() as connection:
        storage_id = edit_storage_id(connection, connect=connect)
        journal_secret = edit_journal_secret(connection, connect=connect)
        library_state = {
            str(row['id']): {
                'revision': int(row['revision_count'] or 0),
                'output_root': Path(str(row['output_dir'])).resolve(),
            }
            for row in connection.execute(
                'SELECT id, revision_count, output_dir FROM library_items'
            ).fetchall()
        }
    loaded: list[tuple[Path, dict[str, Any]]] = []
    prepared: list[tuple[Path, dict[str, Any]]] = []
    fatal_errors: list[str] = []
    warnings_found: list[str] = []

    for staging_dir in staging_dirs:
        manifest = staging_dir / EDIT_TRANSACTION_MANIFEST_NAME
        is_preparing = staging_dir.name.startswith('.edit-preparing-')
        if not manifest.exists() and not manifest.is_symlink():
            marker = staging_dir / EDIT_PREPARATION_MARKER_NAME
            if is_preparing and not marker.exists() and not marker.is_symlink():
                try:
                    ensure_staging_tree_has_no_reparse_points(staging_dir)
                    if any(staging_dir.iterdir()):
                        warnings_found.append(
                            f'Unrecognized preparing directory retained: {staging_dir}'
                        )
                    else:
                        empty_identity = edit_staging_identity(staging_dir)
                        cleanup_errors = cleanup_edit_staging(
                            staging_dir,
                            expected_identity=empty_identity,
                            inventory=capture_edit_cleanup_inventory(staging_dir, {}),
                        )
                        warnings_found.extend(
                            f'{staging_dir}: {message}' for message in cleanup_errors
                        )
                except OSError as exc:
                    warnings_found.append(f'{staging_dir}: {exc}')
                continue
            try:
                prepared.append((
                    staging_dir,
                    load_edit_preparation_marker(
                        staging_dir,
                        expected_storage_id=storage_id,
                        expected_secret=journal_secret,
                    ),
                ))
            except (OSError, ValueError) as exc:
                if is_preparing:
                    warnings_found.append(
                        f'Unrecognized preparing directory retained: {staging_dir}: {exc}'
                    )
                else:
                    fatal_errors.append(f'{staging_dir}: {exc}')
            continue
        try:
            loaded.append((
                staging_dir,
                load_edit_transaction_manifest(
                    staging_dir,
                    expected_storage_id=storage_id,
                    expected_secret=journal_secret,
                ),
            ))
        except (OSError, ValueError) as exc:
            fatal_errors.append(f'{staging_dir}: {exc}')

    item_counts = Counter(
        payload['item_id'] for _, payload in [*loaded, *prepared]
    )
    duplicate_items = {
        item_id for item_id, count in item_counts.items() if count > 1
    }
    if duplicate_items:
        fatal_errors.append(
            'Multiple edit transactions exist for: ' + ', '.join(sorted(duplicate_items))
        )

    for staging_dir, payload in prepared:
        item_id = payload['item_id']
        if item_id in duplicate_items:
            continue
        try:
            if staging_dir.name.startswith('.edit-preparing-'):
                cleanup_prepared_edit_staging(staging_dir, payload)
                continue
            state = library_state.get(item_id)
            if state is None:
                raise OSError('The prepared edit library row is missing.')
            if state['revision'] != payload['expected_revision']:
                raise OSError('The prepared edit database revision has changed.')
            if state['output_root'] != payload['_previous_output_root']:
                raise OSError('The prepared edit does not match the library output directory.')
            cleanup_prepared_edit_staging(staging_dir, payload)
        except (OSError, ValueError) as exc:
            fatal_errors.append(f'{staging_dir}: {exc}')

    for staging_dir, payload in loaded:
        item_id = payload['item_id']
        if item_id in duplicate_items:
            continue
        try:
            state = library_state.get(item_id)
            if state is None:
                raise OSError('The edit transaction library row is missing.')
            current_revision = state['revision']
            expected_revision = payload['expected_revision']
            target_revision = payload['target_revision']
            if current_revision == expected_revision:
                if state['output_root'] != payload['_previous_output_root']:
                    raise OSError('The uncommitted edit does not match the library output directory.')
                rollback_edit_transaction(staging_dir, payload)
            elif current_revision == target_revision:
                if state['output_root'] != payload['_output_root']:
                    raise OSError('The committed edit does not match the library output directory.')
                cleanup_errors = finish_committed_edit_transaction(staging_dir, payload)
                warnings_found.extend(
                    f'{staging_dir}: {message}' for message in cleanup_errors
                )
            elif current_revision > target_revision:
                if state['output_root'] != payload['_output_root']:
                    raise OSError(
                        'A stale edit transaction belongs to a different output directory.'
                    )
                cleanup_errors = cleanup_edit_staging(
                    staging_dir,
                    expected_identity=payload['_staging_identity'],
                    inventory=edit_transaction_cleanup_inventory(staging_dir, payload),
                )
                warnings_found.extend(
                    f'{staging_dir}: {message}' for message in cleanup_errors
                )
            else:
                raise OSError('The database revision predates the edit transaction.')
        except (OSError, ValueError, sqlite3.Error) as exc:
            fatal_errors.append(f'{staging_dir}: {exc}')

    if fatal_errors:
        raise RuntimeError(
            'Unsafe edit transaction recovery; automatic import was stopped: '
            + '; '.join(fatal_errors)
        )
    return warnings_found


def reconcile_edit_transactions_before_mutation(
    item_id: str,
    library_item: sqlite3.Row,
    *,
    connect: Callable[[], Any],
    output_root: Path,
) -> tuple[list[str], list[Path]]:
    errors: list[str] = []
    retained: list[Path] = []
    try:
        staging_dirs = discover_edit_transaction_staging_dirs(
            additional_output_roots=[Path(str(library_item['output_dir']))],
            include_database_outputs=False,
            connect=connect,
            output_root=output_root,
        )
        if not staging_dirs:
            return errors, retained
        with connect() as connection:
            storage_id = edit_storage_id(connection, connect=connect)
            journal_secret = edit_journal_secret(connection, connect=connect)
            row = connection.execute(
                'SELECT revision_count, output_dir FROM library_items WHERE id = ?',
                (item_id,),
            ).fetchone()
        if row is None:
            return ['The library row disappeared before edit reconciliation.'], retained
        current_revision = int(row['revision_count'] or 0)
        current_output_root = Path(str(row['output_dir'])).resolve()
        matches: list[tuple[Path, str, dict[str, Any]]] = []
        for staging_dir in staging_dirs:
            manifest = staging_dir / EDIT_TRANSACTION_MANIFEST_NAME
            try:
                if manifest.exists() or manifest.is_symlink():
                    payload = load_edit_transaction_manifest(
                        staging_dir,
                        expected_storage_id=storage_id,
                        expected_secret=journal_secret,
                    )
                    kind = 'transaction'
                else:
                    payload = load_edit_preparation_marker(
                        staging_dir,
                        expected_storage_id=storage_id,
                        expected_secret=journal_secret,
                    )
                    kind = 'preparation'
            except (OSError, ValueError) as exc:
                if staging_dir.name.startswith('.edit-preparing-'):
                    retained.append(staging_dir)
                    continue
                errors.append(f'{staging_dir}: {exc}')
                retained.append(staging_dir)
                continue
            if payload['item_id'] == item_id:
                matches.append((staging_dir, kind, payload))

        if len(matches) > 1:
            errors.append('Multiple pending edit transactions exist for this library item.')
            retained.extend(staging_dir for staging_dir, _, _ in matches)
            return errors, sorted(set(retained), key=str)

        for staging_dir, kind, payload in matches:
            try:
                if kind == 'preparation':
                    if current_revision != payload['expected_revision']:
                        raise OSError('The prepared edit database revision has changed.')
                    if current_output_root != payload['_previous_output_root']:
                        raise OSError('The prepared edit output directory no longer matches.')
                    cleanup_prepared_edit_staging(staging_dir, payload)
                else:
                    cleanup_errors = reconcile_edit_transaction_with_database(
                        staging_dir,
                        payload,
                        connect=connect,
                    )
                    if cleanup_errors:
                        raise OSError('; '.join(cleanup_errors))
                if staging_dir.exists() or staging_dir.is_symlink():
                    raise OSError('The edit staging directory could not be removed.')
            except (OSError, ValueError, sqlite3.Error) as exc:
                errors.append(f'{staging_dir}: {exc}')
                retained.append(staging_dir)
    except (OSError, ValueError, sqlite3.Error) as exc:
        errors.append(str(exc))
    return errors, sorted(set(retained), key=str)


def reconcile_edit_transactions_before_delete(
    item_id: str,
    library_item: sqlite3.Row,
    *,
    connect: Callable[[], Any],
    output_root: Path,
) -> tuple[list[str], list[Path]]:
    return reconcile_edit_transactions_before_mutation(
        item_id, library_item, connect=connect, output_root=output_root
    )
