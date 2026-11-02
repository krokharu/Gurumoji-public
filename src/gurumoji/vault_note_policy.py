"""One write policy for the notes Gurumoji generates in an Obsidian Vault (OBS-04).

Every writer (analysis notes, overview and navigation, the workbench status
note, and the Input/Visualization/Orchestrator Vaults) decides here what to do
with the note already on disk, and records the decision in its own ledger:

- new note: write it and keep a copy of this first version in the history;
- unchanged app version on disk: replace it (before the first replacement of
  a note created before this policy, keep the on-disk version as the first);
- researcher-edited (or unknown) file on disk: keep it in the history, then
  write the latest version;
- note deleted by the researcher: recreate navigation notes only; report
  content notes as missing.

History copies live inside the Vault, tagged ``graph/history`` (excluded from
the graph views) and with their own ``note_id``, so they are never mistaken
for the live note. Researcher-owned notes (transcript, operation note, memo,
results) never go through this policy: the app does not overwrite them.
Every change is appended to ``<data>/obsidian_layout/note_changes.jsonl``.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable

import yaml

from .analysis_store import safe_path, write_atomic

CHANGE_LOG_NAME = "note_changes.jsonl"
CHANGE_LOG_LIMIT = 5 * 1024 * 1024
NOTABLE_ACTIONS = ("edit_saved", "missing", "recreated")
_LOG_LOCK = threading.Lock()
# A deleted note stays missing on every later write; log it once per process.
_REPORTED_MISSING: set[tuple[str, str, str]] = set()
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---(?:\n|$)", re.S)


@dataclass(frozen=True)
class HistoryLayout:
    """Where one Vault keeps history copies and how it names them."""

    directory: Callable[[str], str]
    first_label: str
    edit_label: str


@dataclass
class NoteWrite:
    action: str  # created / updated / unchanged / edit_saved / missing / recreated
    path: str
    sha256: str
    previous_sha256: str = ""
    history: list[str] = field(default_factory=list)
    vault: str = "research"

    @property
    def notable(self) -> bool:
        return self.action in NOTABLE_ACTIONS


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stamp(now: datetime) -> str:
    return f"{now:%Y%m%dT%H%M%SZ}"


def _leaf(relative: str) -> str:
    stem = PurePosixPath(relative).stem
    # Bounded length keeps deep interview paths within Windows limits (OBS-14).
    return f"{stem[:40]}-{_sha(relative.encode())[:8]}"


def research_history_directory(relative: str) -> str:
    match = re.match(r"(10-インタビュー/[^/]+)/", relative)
    base = f"{match[1]}/履歴/ノート変更" if match else "90-運用/変更履歴"
    return f"{base}/{_leaf(relative)}"


def generated_history_directory(relative: str) -> str:
    # 99-Archive is the generated Vaults' existing place for replaced notes.
    return f"99-Archive/history/{_leaf(relative)}"


RESEARCH_HISTORY = HistoryLayout(research_history_directory, "最初の版", "研究者の編集")
GENERATED_HISTORY = HistoryLayout(generated_history_directory, "first", "edited")


def history_copy(content: bytes, *, relative: str, label: str, saved_at: str, note_id: str) -> bytes:
    """Mark a copy as history: its own note_id, graph/history tag, link to the live note."""
    text = content.decode("utf-8", errors="replace").removeprefix("﻿").replace("\r\n", "\n")
    props: dict = {}
    body = text
    match = _FRONTMATTER.match(text)
    if match:
        try:
            loaded = yaml.safe_load(match[1]) or {}
        except yaml.YAMLError:
            loaded = None
        if isinstance(loaded, dict):
            props, body = loaded, text[match.end():]
    tags = props.get("tags") or []
    if isinstance(tags, str):
        tags = tags.split()
    original_id = props.get("note_id")
    # aliases would make links resolve to the copy; note_id would make it a second live note.
    props = {key: value for key, value in props.items() if key not in {"note_id", "aliases", "tags"}}
    props.update(
        note_id=note_id,
        note_type="note-history",
        history_of=relative,
        history_of_note_id=original_id if isinstance(original_id, str) else "",
        history_kind=label,
        saved_at=saved_at,
        tags=[tag for tag in tags if isinstance(tag, str) and not tag.startswith("graph/")] + ["graph/history"],
    )
    live = relative[:-3] if relative.endswith(".md") else relative
    header = f"> [!note] {label}の写し（{saved_at}）\n> 元のノート：[[{live}]]\n\n"
    return ("---\n" + yaml.safe_dump(props, allow_unicode=True, sort_keys=False).rstrip()
            + "\n---\n\n" + header + body.lstrip("\n")).encode("utf-8")


def _save_history(vault: Path, relative: str, content: bytes, label: str,
                  layout: HistoryLayout, now: datetime) -> str:
    directory = layout.directory(relative)
    saved_at = now.isoformat(timespec="seconds")
    name = f"{directory}/{_stamp(now)}-{label}.md"
    counter = 1
    while safe_path(vault, name).exists():
        counter += 1
        name = f"{directory}/{_stamp(now)}-{label}-{counter}.md"
    note_id = "history-" + _sha(f"{relative}\n{name}".encode())[:24]
    write_atomic(safe_path(vault, name), history_copy(
        content, relative=relative, label=label, saved_at=saved_at, note_id=note_id), create_only=True)
    return name


def _has_first(vault: Path, relative: str, layout: HistoryLayout) -> bool:
    directory = safe_path(vault, layout.directory(relative))
    return directory.is_dir() and any(directory.glob(f"*-{layout.first_label}*.md"))


def append_change(log_file: Path | None, vault_kind: str, result: NoteWrite, now: datetime) -> None:
    if log_file is None or result.action == "unchanged":
        return
    key = (str(log_file), vault_kind, result.path)
    if result.action == "missing":
        if key in _REPORTED_MISSING:
            return
        _REPORTED_MISSING.add(key)
    else:
        _REPORTED_MISSING.discard(key)
    line = json.dumps({
        "at": now.isoformat(timespec="seconds"), "vault": vault_kind, "path": result.path,
        "action": result.action, "previous_sha256": result.previous_sha256,
        "sha256": result.sha256, "history": result.history,
    }, ensure_ascii=False) + "\n"
    with _LOG_LOCK:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        if log_file.exists() and log_file.stat().st_size > CHANGE_LOG_LIMIT:
            log_file.replace(log_file.with_name(log_file.name + ".1"))
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(line)


def recent_changes(log_file: Path, *, actions: Iterable[str] = NOTABLE_ACTIONS,
                   limit: int = 100, tail_bytes: int = 512 * 1024) -> list[dict]:
    """Newest-first notable changes from the end of the change log."""
    if not log_file.exists():
        return []
    wanted = set(actions)
    with log_file.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - tail_bytes))
        lines = handle.read().decode("utf-8", errors="replace").splitlines()
    if size > tail_bytes:
        lines = lines[1:]  # the first line may be cut
    events = []
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("action") in wanted:
            events.append(event)
            if len(events) >= limit:
                break
    return events


def write_generated_note(
    vault: Path,
    relative: str,
    content: bytes,
    *,
    known_hashes: Iterable[str],
    ever_written: bool,
    recreate_missing: bool,
    history: HistoryLayout = RESEARCH_HISTORY,
    vault_kind: str = "research",
    log_file: Path | None = None,
    before_write: Callable[[str], None] | None = None,
    now: datetime | None = None,
) -> NoteWrite:
    """Apply the shared policy to one generated note; the caller updates its ledger.

    ``before_write(new_sha256)`` runs just before the live note is replaced, so a
    ledger can record the intended hash and recognise an interrupted write.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    target = safe_path(vault, relative)
    new_hash = _sha(content)
    known = {value for value in known_hashes if value}
    saved: list[str] = []

    def write(action: str, previous: str = "") -> NoteWrite:
        if before_write is not None:
            before_write(new_hash)
        write_atomic(target, content)
        result = NoteWrite(action, relative, new_hash, previous, saved, vault_kind)
        append_change(log_file, vault_kind, result, now)
        return result

    if target.exists():
        actual = target.read_bytes()
        actual_hash = _sha(actual)
        if actual_hash == new_hash:
            return NoteWrite("unchanged", relative, new_hash, actual_hash, vault=vault_kind)
        if ever_written and actual_hash in known:
            if not _has_first(vault, relative, history):
                # Notes written before this policy: the on-disk app version is the first.
                saved.append(_save_history(vault, relative, actual, history.first_label, history, now))
            return write("updated", actual_hash)
        saved.append(_save_history(vault, relative, actual, history.edit_label, history, now))
        if not _has_first(vault, relative, history) and not ever_written:
            saved.append(_save_history(vault, relative, content, history.first_label, history, now))
        return write("edit_saved", actual_hash)
    if ever_written:
        if not recreate_missing:
            result = NoteWrite("missing", relative, new_hash, vault=vault_kind)
            append_change(log_file, vault_kind, result, now)
            return result
        return write("recreated")
    saved.append(_save_history(vault, relative, content, history.first_label, history, now))
    return write("created")
