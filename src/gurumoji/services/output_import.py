"""Import transcripts found in the output folder and track their provenance.

Provenance rows remember which output file produced which library item, so
an edited or deleted item's old file is not imported again."""

from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..text_utils import json_load
from .durable_files import file_sha256
from .outputs import safe_output_stem

LOGGER = logging.getLogger(__name__)

OUTPUT_ARTIFACT_SUFFIXES = (
    "_話者分離.json",
    "_話者分離.txt",
    "_話者分離.srt",
    "_ワードクラウド.svg",
    "_アウトライン.txt",
    "_感情分析.json",
    "_感情分析.csv",
    "_話者カラー字幕.ass",
    "_字幕付き.mp4",
)


def make_output_import(
    *,
    default_output_directory: Callable[[], Any],
    database_connection: Any,
    library_row: Any,
    publish_input_vault: Any,
    upsert_library_item: Any,
) -> tuple[Callable[..., Any], ...]:
    def canonical_output_import_path(path: Path) -> str:
        return os.path.normcase(str(path.resolve()))

    def record_output_import_provenance(
        connection: sqlite3.Connection,
        item_id: str,
        paths: list[Path],
    ) -> None:
        for path in paths:
            if not path.name.endswith("_話者分離.json"):
                continue
            fingerprint = ""
            if path.is_file():
                try:
                    fingerprint = file_sha256(path)
                except OSError:
                    pass
            connection.execute(
                """
                INSERT INTO output_import_provenance (
                    item_id, canonical_path, content_sha256
                ) VALUES (?, ?, ?)
                ON CONFLICT(item_id, canonical_path) DO UPDATE SET
                    content_sha256 = CASE
                        WHEN excluded.content_sha256 <> ''
                        THEN excluded.content_sha256
                        ELSE output_import_provenance.content_sha256
                    END
                """,
                (item_id, canonical_output_import_path(path), fingerprint),
            )


    def existing_output_artifacts(directory: Path, stem: str) -> list[Path]:
        return [
            path
            for suffix in OUTPUT_ARTIFACT_SUFFIXES
            if (path := directory / f"{stem}{suffix}").is_file()
        ]

    def machine_json_owner_for_row(row: sqlite3.Row, files: list[Path]) -> Path | None:
        candidates = [path for path in files if path.name.endswith("_話者分離.json")]
        if not candidates:
            return None
        row_id = str(row["id"])
        id_matches = []
        for candidate in candidates:
            resolved = str(candidate.resolve())
            legacy_id = uuid.uuid5(uuid.NAMESPACE_URL, resolved).hex
            canonical_id = uuid.uuid5(
                uuid.NAMESPACE_URL, canonical_output_import_path(candidate)
            ).hex
            if row_id in {legacy_id, canonical_id}:
                id_matches.append(candidate)
        if len(id_matches) == 1:
            return id_matches[0]
        expected = Path(str(row["output_dir"])) / (
            f"{safe_output_stem(str(row['source_name']))}_話者分離.json"
        )
        expected_canonical = canonical_output_import_path(expected)
        expected_matches = [
            candidate
            for candidate in candidates
            if canonical_output_import_path(candidate) == expected_canonical
        ]
        if len(expected_matches) == 1:
            return expected_matches[0]
        return candidates[0] if len(candidates) == 1 else None

    def repair_output_import_provenance(connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            "SELECT id, source_name, output_dir, files_json FROM library_items"
        ).fetchall()
        for row in rows:
            raw_files = json_load(row["files_json"], [])
            if not isinstance(raw_files, list):
                continue
            files = [Path(str(value)) for value in raw_files]
            owner = machine_json_owner_for_row(row, files)
            if owner is None:
                continue
            fingerprint = ""
            if owner.is_file():
                try:
                    fingerprint = file_sha256(owner)
                except OSError:
                    pass
            connection.execute(
                "INSERT OR IGNORE INTO output_import_provenance "
                "(item_id, canonical_path, content_sha256) VALUES (?, ?, ?)",
                (str(row["id"]), canonical_output_import_path(owner), fingerprint),
            )
            owner_canonical = canonical_output_import_path(owner)
            filtered = [
                value
                for value in raw_files
                if not Path(str(value)).name.endswith("_話者分離.json")
                or canonical_output_import_path(Path(str(value))) == owner_canonical
            ]
            if filtered != raw_files:
                connection.execute(
                    "UPDATE library_items SET files_json = ? WHERE id = ?",
                    (json.dumps(filtered, ensure_ascii=False), str(row["id"])),
                )

    def import_existing_outputs() -> None:
        if not default_output_directory().is_dir():
            return
        with database_connection() as connection:
            rows = connection.execute("SELECT id, files_json FROM library_items").fetchall()
            known = {str(row["id"]) for row in rows}
            referenced_json_owners: dict[str, set[str]] = {}
            for row in rows:
                files = json_load(row["files_json"], [])
                if not isinstance(files, list):
                    continue
                for value in files:
                    path = Path(str(value))
                    if path.name.endswith("_話者分離.json"):
                        referenced_json_owners.setdefault(
                            canonical_output_import_path(path), set()
                        ).add(str(row["id"]))
            for provenance in connection.execute(
                "SELECT provenance.item_id, provenance.canonical_path "
                "FROM output_import_provenance AS provenance "
                "INNER JOIN library_items AS item ON item.id = provenance.item_id"
            ).fetchall():
                referenced_json_owners.setdefault(
                    str(provenance["canonical_path"]), set()
                ).add(str(provenance["item_id"]))
            tombstones = {
                str(row["canonical_path"]): str(row["content_sha256"] or "")
                for row in connection.execute(
                    "SELECT canonical_path, content_sha256 FROM output_import_tombstones"
                ).fetchall()
            }
        for json_path in default_output_directory().rglob("*_話者分離.json"):
            if any(
                part.startswith(('.edit-staging-', '.edit-preparing-', '.edit-cleanup-'))
                for part in json_path.parts
            ):
                continue
            canonical_path = canonical_output_import_path(json_path)
            item_id = uuid.uuid5(uuid.NAMESPACE_URL, canonical_path).hex
            if item_id in known:
                try:
                    known_fingerprint = file_sha256(json_path)
                except OSError:
                    known_fingerprint = ""
                with database_connection() as connection:
                    connection.execute(
                        "INSERT OR IGNORE INTO output_import_provenance "
                        "(item_id, canonical_path, content_sha256) VALUES (?, ?, ?)",
                        (item_id, canonical_path, known_fingerprint),
                    )
                continue
            referenced_owners = referenced_json_owners.get(canonical_path, set())
            if referenced_owners:
                if len(referenced_owners) == 1:
                    owner_id = next(iter(referenced_owners))
                    try:
                        fingerprint = file_sha256(json_path)
                    except OSError:
                        fingerprint = ""
                    with database_connection() as connection:
                        connection.execute(
                            "INSERT OR IGNORE INTO output_import_provenance "
                            "(item_id, canonical_path, content_sha256) VALUES (?, ?, ?)",
                            (owner_id, canonical_path, fingerprint),
                        )
                continue
            try:
                current_fingerprint = file_sha256(json_path)
                tombstone_fingerprint = tombstones.get(canonical_path)
                if tombstone_fingerprint is not None and (
                    not tombstone_fingerprint
                    or secrets.compare_digest(tombstone_fingerprint, current_fingerprint)
                ):
                    continue
                payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
                if not isinstance(payload, dict):
                    raise ValueError("The output JSON must contain an object.")
                # language is bound directly to SQLite; reject malformed JSON
                # scalars here rather than treating a binding error as a DB fault.
                for field in ("language", "source"):
                    if payload.get(field) is not None and not isinstance(payload[field], str):
                        raise ValueError(f"The output JSON {field} must be a string or null.")
                segments = payload.get("segments")
                if not isinstance(segments, list) or any(not isinstance(segment, dict) for segment in segments):
                    raise ValueError("The output JSON must contain a list of segment objects.")
                source_name = Path(str(payload.get("source") or json_path.name.replace("_話者分離.json", ""))).name
                stem = json_path.name[:-len("_話者分離.json")]
                files = existing_output_artifacts(json_path.parent, stem)
                created = datetime.fromtimestamp(json_path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
                with database_connection() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    upsert_library_item(
                        item_id=item_id, source_name=source_name, output_dir=json_path.parent,
                        media_path=None, language=payload.get("language"), segments=segments,
                        speaker_names=payload.get("speaker_names") if isinstance(payload.get("speaker_names"), dict) else {},
                        speaker_profiles=payload.get("speaker_profiles") if isinstance(payload.get("speaker_profiles"), dict) else None,
                        session_profile=payload.get("session_profile") if isinstance(payload.get("session_profile"), dict) else None,
                        meeting_minutes=payload.get("meeting_minutes") if isinstance(payload.get("meeting_minutes"), dict) else None,
                        outline=payload.get("outline") if isinstance(payload.get("outline"), dict) else None,
                        emotion_analysis=payload.get("emotion_analysis") if isinstance(payload.get("emotion_analysis"), dict) else None,
                        formatting_result=(
                            payload.get("formatting_result")
                            if isinstance(payload.get("formatting_result"), dict) else None
                        ),
                        files=files, write_srt=any(path.suffix.lower() == ".srt" for path in files),
                        write_json=True, created_at=created, connection=connection,
                    )
                    connection.execute(
                        "INSERT OR REPLACE INTO output_import_provenance "
                        "(item_id, canonical_path, content_sha256) VALUES (?, ?, ?)",
                        (item_id, canonical_path, current_fingerprint),
                    )
                    connection.execute(
                        "DELETE FROM output_import_tombstones WHERE canonical_path = ?",
                        (canonical_path,),
                    )
                known.add(item_id)
                publish_input_vault(library_row(item_id), source_kind="imported")
            except (OSError, ValueError, TypeError) as exc:
                # Never log transcript contents or abort startup for a bad import.
                LOGGER.warning("出力JSONを取り込めないためスキップしました: %s (%s)",
                               json_path.name, type(exc).__name__)
                continue

    return (
        canonical_output_import_path,
        record_output_import_provenance,
        existing_output_artifacts,
        machine_json_owner_for_row,
        repair_output_import_provenance,
        import_existing_outputs,
    )
