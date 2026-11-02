"""The cross-session speaker registry and its CSV interchange.

One person may appear in many recordings, so their identity, role, consent, and
attendance are kept here rather than on any single transcript.  The CSV import
accepts the header spellings people actually paste in, which is why the alias
tables are as large as they are.

The database connection factory and the revision-guarded save are injected, so
this module holds no application state of its own.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import unicodedata
import uuid
from typing import Any, Callable

from ..handlers.speaker_registry import SpeakerRegistryConflictError
from .group_analysis import analysis_csv_safe
from ..text_utils import clean_multiline, clean_single_line, json_load, normalize_attributes, normalize_tags, utc_now_iso

SPEAKER_REGISTRATION_STATUSES = {
    "registered", "temporary_single_group", "unidentified",
}
SPEAKER_ROLES = {
    "participant", "moderator", "facilitator", "assistant_moderator", "observer",
    "note_taker", "interviewer", "chair", "presenter", "decision_maker",
    "attendee", "guest", "other",
}
SPEAKER_REGISTRATION_STATUSES = {
    "registered", "temporary_single_group", "unidentified",
}
CONSENT_STATUSES = {"unknown", "pending", "granted", "declined", "not_required"}
ATTENDANCE_STATUSES = {"unknown", "planned", "attended", "absent", "left_early", "remote"}

def speaker_registry_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "participant_code": row["participant_code"],
        "display_name": row["display_name"],
        "pseudonym": row["pseudonym"],
        "default_role": row["default_role"],
        "organization": row["organization"],
        "department": row["department"],
        "job_title": row["job_title"],
        "consent_status": row["consent_status"],
        "recording_consent": row["recording_consent"],
        "confidentiality_status": row["confidentiality_status"],
        "tags": json_load(row["tags_json"], []),
        "attributes": json_load(row["attributes_json"], {}),
        "notes": row["notes"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def normalize_speaker_registry_record(
    raw: Any,
    *,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("話者データの形式が不正です。")
    base = existing or {}
    record_id = clean_single_line(raw.get("id") or base.get("id") or uuid.uuid4().hex, 80)
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", record_id):
        record_id = uuid.uuid4().hex
    default_role = clean_single_line(raw.get("default_role", base.get("default_role", "participant")), 40)
    if default_role not in SPEAKER_ROLES:
        default_role = "participant"

    def consent(field_name: str) -> str:
        value = clean_single_line(raw.get(field_name, base.get(field_name, "unknown")), 30)
        return value if value in CONSENT_STATUSES else "unknown"

    display_name = clean_single_line(raw.get("display_name", base.get("display_name", "")), 120)
    pseudonym = clean_single_line(raw.get("pseudonym", base.get("pseudonym", "")), 120)
    participant_code = clean_single_line(
        raw.get("participant_code", base.get("participant_code", "")), 120
    )
    if not (display_name or pseudonym or participant_code):
        raise ValueError("話者には氏名、仮名、参加者コードのいずれかを入力してください。")
    return {
        "id": record_id,
        "participant_code": participant_code,
        "display_name": display_name,
        "pseudonym": pseudonym,
        "default_role": default_role,
        "organization": clean_single_line(raw.get("organization", base.get("organization", "")), 200),
        "department": clean_single_line(raw.get("department", base.get("department", "")), 200),
        "job_title": clean_single_line(raw.get("job_title", base.get("job_title", "")), 200),
        "consent_status": consent("consent_status"),
        "recording_consent": consent("recording_consent"),
        "confidentiality_status": consent("confidentiality_status"),
        "tags": normalize_tags(raw.get("tags", base.get("tags", []))),
        "attributes": normalize_attributes(raw.get("attributes", base.get("attributes", {}))),
        "notes": clean_multiline(raw.get("notes", base.get("notes", "")), 10000),
        "active": bool(raw.get("active", base.get("active", True))),
    }


def speaker_registry_revision(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT value FROM application_metadata WHERE key = ?",
        ("speaker_registry_revision",),
    ).fetchone()
    if row is None:
        raise RuntimeError("Speaker registry metadata is missing; initialize the database first.")
    try:
        revision = int(row["value"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Speaker registry revision metadata is invalid.") from exc
    if revision < 0:
        raise RuntimeError("Speaker registry revision metadata is invalid.")
    return revision


def speaker_registry_rows(
    connection: sqlite3.Connection,
    *,
    include_inactive: bool = True,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM speaker_registry"
    if not include_inactive:
        query += " WHERE active = 1"
    query += " ORDER BY active DESC, pseudonym, display_name, participant_code, updated_at DESC"
    return connection.execute(query).fetchall()


def speaker_registry_snapshot(
    *,
    include_inactive: bool = True,
    connect: Callable[[], Any],
) -> tuple[list[dict[str, Any]], int]:
    with connect() as connection:
        revision = speaker_registry_revision(connection)
        rows = speaker_registry_rows(connection, include_inactive=include_inactive)
    return [speaker_registry_public(row) for row in rows], revision


def list_speaker_registry(
    *,
    include_inactive: bool = True,
    connect: Callable[[], Any],
) -> list[dict[str, Any]]:
    records, _revision = speaker_registry_snapshot(
        include_inactive=include_inactive, connect=connect
    )
    return records


def persist_speaker_registry_record(
    connection: sqlite3.Connection,
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    now: str,
    *, origin: str = "researcher", process: str = "speaker_registry_save",
) -> None:
    """Insert one normalized registry record without changing the revision."""
    from . import change_log
    with change_log.tracking(connection, [("speaker_registry", record["id"])], origin=origin, process=process), \
            change_log.tracking(connection, [("attribute_definitions", "global")],
                origin="rule", process="speaker_attribute_discovery"):
        connection.execute(
            """
            INSERT INTO speaker_registry (
                id, participant_code, display_name, pseudonym, default_role,
                organization, department, job_title, consent_status,
                recording_consent, confidentiality_status, tags_json,
                attributes_json, notes, active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                participant_code=excluded.participant_code,
                display_name=excluded.display_name,
                pseudonym=excluded.pseudonym,
                default_role=excluded.default_role,
                organization=excluded.organization,
                department=excluded.department,
                job_title=excluded.job_title,
                consent_status=excluded.consent_status,
                recording_consent=excluded.recording_consent,
                confidentiality_status=excluded.confidentiality_status,
                tags_json=excluded.tags_json,
                attributes_json=excluded.attributes_json,
                notes=excluded.notes,
                active=excluded.active,
                updated_at=excluded.updated_at
            """,
            (
                record["id"], record["participant_code"], record["display_name"],
                record["pseudonym"], record["default_role"], record["organization"],
                record["department"], record["job_title"], record["consent_status"],
                record["recording_consent"], record["confidentiality_status"],
                json.dumps(record["tags"], ensure_ascii=False),
                json.dumps(record["attributes"], ensure_ascii=False), record["notes"],
                int(record["active"]), previous["created_at"] if previous else now, now,
            ),
        )


def prepare_speaker_registry_records(raw_records: Any, existing_records: dict[str, Any], *, merge_by_participant_code: bool = False) -> list[dict[str, Any]]:
    """The same validation/merge for a preview and an atomic save; no writes."""
    if not isinstance(raw_records, list) or len(raw_records) > 10000:
        raise ValueError("Speaker registry data must be an array of at most 10000 records.")
    prepared_records = raw_records
    if merge_by_participant_code:
        by_code = {
            item["participant_code"].casefold(): item
            for item in existing_records.values()
            if item["participant_code"]
        }
        prepared_records = []
        for raw in raw_records:
            if not isinstance(raw, dict):
                prepared_records.append(raw)
                continue
            code = clean_single_line(raw.get("participant_code"), 120).casefold()
            previous = by_code.get(code) if code else None
            if previous is None:
                prepared_records.append(dict(raw))
                continue
            merged_attributes = {
                **previous.get("attributes", {}),
                **(raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}),
            }
            prepared_records.append({
                **previous,
                **raw,
                "id": previous["id"],
                "attributes": merged_attributes,
            })

    normalized = [
        normalize_speaker_registry_record(
            raw,
            existing=existing_records.get(str(raw.get("id"))) if isinstance(raw, dict) else None,
        )
        for raw in prepared_records
    ]
    return normalized


def _save_speaker_registry_records_locked(raw_records: Any, *, delete_ids: Any = None,
    expected_revision: int | None = None, merge_by_participant_code: bool = False,
    connect: Callable[[], Any],
) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(raw_records, list) or len(raw_records) > 10000:
        raise ValueError("Speaker registry data must be an array of at most 10000 records.")
    requested_delete_ids = {
        clean_single_line(value, 80)
        for value in (delete_ids if isinstance(delete_ids, list) else [])
        if clean_single_line(value, 80)
    }
    now = utc_now_iso()
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        current_revision = speaker_registry_revision(connection)
        if expected_revision is not None and current_revision != expected_revision:
            raise SpeakerRegistryConflictError(current_revision)

        existing_records = {
            item["id"]: item
            for item in (
                speaker_registry_public(row)
                for row in speaker_registry_rows(connection, include_inactive=True)
            )
        }
        normalized = prepare_speaker_registry_records(
            raw_records, existing_records, merge_by_participant_code=merge_by_participant_code,
        )
        for record in normalized:
            previous = existing_records.get(record["id"])
            persist_speaker_registry_record(connection, record, previous, now)
        if requested_delete_ids:
            from . import change_log
            placeholders = ",".join("?" for _ in requested_delete_ids)
            with change_log.tracking(connection, [("speaker_registry", identity) for identity in sorted(requested_delete_ids)], process="speaker_registry_delete"):
                connection.execute(
                    f"DELETE FROM speaker_registry WHERE id IN ({placeholders})",
                    tuple(sorted(requested_delete_ids)),
                )
        new_revision = current_revision + 1
        connection.execute(
            "UPDATE application_metadata SET value = ? WHERE key = ?",
            (str(new_revision), "speaker_registry_revision"),
        )
        rows = speaker_registry_rows(connection, include_inactive=True)
        records = [speaker_registry_public(row) for row in rows]
    return records, new_revision

def normalized_csv_header(value: Any) -> str:
    return re.sub(r"[\s_\-（）()\[\]【】]+", "", str(value or "").strip().casefold())


SPEAKER_CSV_FIELD_ALIASES = {
    "タイムスタンプ": "",
    "timestamp": "",
    "id": "participant_code",
    "参加者id": "participant_code",
    "回答者id": "participant_code",
    "参加者コード": "participant_code",
    "participantid": "participant_code",
    "participantcode": "participant_code",
    "氏名": "display_name",
    "名前": "display_name",
    "お名前": "display_name",
    "name": "display_name",
    "displayname": "display_name",
    "仮名": "pseudonym",
    "匿名名": "pseudonym",
    "pseudonym": "pseudonym",
    "役割": "default_role",
    "デフォルト役割": "default_role",
    "role": "default_role",
    "defaultrole": "default_role",
    "組織": "organization",
    "会社": "organization",
    "所属組織": "organization",
    "organization": "organization",
    "company": "organization",
    "部署": "department",
    "所属部署": "department",
    "department": "department",
    "役職": "job_title",
    "職位": "job_title",
    "jobtitle": "job_title",
    "title": "job_title",
    "研究同意": "consent_status",
    "参加同意": "consent_status",
    "consent": "consent_status",
    "consentstatus": "consent_status",
    "録音同意": "recording_consent",
    "recordingconsent": "recording_consent",
    "守秘同意": "confidentiality_status",
    "confidentiality": "confidentiality_status",
    "confidentialitystatus": "confidentiality_status",
    "タグ": "tags",
    "tags": "tags",
    "備考": "notes",
    "メモ": "notes",
    "notes": "notes",
    "有効": "active",
    "active": "active",
}

SPEAKER_ROLE_ALIASES = {
    "参加者": "participant",
    "司会": "moderator",
    "モデレーター": "moderator",
    "進行": "facilitator",
    "ファシリテーター": "facilitator",
    "副司会": "assistant_moderator",
    "観察者": "observer",
    "記録者": "note_taker",
    "書記": "note_taker",
    "インタビュアー": "interviewer",
    "議長": "chair",
    "発表者": "presenter",
    "意思決定者": "decision_maker",
    "出席者": "attendee",
    "ゲスト": "guest",
    "その他": "other",
}


def normalize_csv_role(value: Any) -> str:
    cleaned = clean_single_line(value, 40)
    mapped = SPEAKER_ROLE_ALIASES.get(cleaned, cleaned)
    return mapped if mapped in SPEAKER_ROLES else "participant"


def normalize_csv_consent(value: Any) -> str:
    cleaned = clean_single_line(value, 40).casefold()
    if cleaned in {"yes", "y", "true", "1", "同意", "同意済み", "許可", "済", "承諾"}:
        return "granted"
    if cleaned in {"no", "n", "false", "0", "拒否", "非同意", "不許可"}:
        return "declined"
    if cleaned in {"pending", "保留", "確認中", "未回答"}:
        return "pending"
    if cleaned in {"notrequired", "不要", "対象外"}:
        return "not_required"
    return cleaned if cleaned in CONSENT_STATUSES else "unknown"


def speaker_csv_field_for_header(header: str) -> str | None:
    if header.startswith("属性:"):
        return None
    normalized = normalized_csv_header(header)
    exact = SPEAKER_CSV_FIELD_ALIASES.get(normalized)
    if exact is not None:
        return exact
    if "録音" in normalized and ("同意" in normalized or "許可" in normalized):
        return "recording_consent"
    if "守秘" in normalized and ("同意" in normalized or "確認" in normalized):
        return "confidentiality_status"
    if ("研究" in normalized or "参加" in normalized) and "同意" in normalized:
        return "consent_status"
    if "参加者" in normalized and ("コード" in normalized or "id" in normalized):
        return "participant_code"
    return None


def speaker_attribute_csv_headers(keys, fixed_headers) -> dict[str, str]:
    """Escape reserved names reversibly without changing researcher attributes."""
    fixed = set(fixed_headers)
    return {key: "属性:" + key if (key in fixed or key.startswith("属性:")
            or speaker_csv_field_for_header(key) is not None) else key
            for key in sorted(keys)}


def preview_speaker_registry_records(raw_records: Any, *, expected_revision: int,
    merge_by_participant_code: bool = False, connect: Callable[[], Any],
) -> tuple[list[dict[str, Any]], int]:
    with connect() as connection:
        connection.execute("BEGIN")
        revision = speaker_registry_revision(connection)
        if revision != expected_revision:
            raise SpeakerRegistryConflictError(revision)
        existing = {item["id"]: item for item in (
            speaker_registry_public(row) for row in speaker_registry_rows(connection)
        )}
        normalized = prepare_speaker_registry_records(
            raw_records, existing, merge_by_participant_code=merge_by_participant_code,
        )
        return list({**existing, **{item["id"]: item for item in normalized}}.values()), revision


def speaker_csv_columns(content: bytes) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp932")
    return [{"column": str(header), "field": "attributes" if speaker_csv_field_for_header(str(header)) is None else speaker_csv_field_for_header(str(header)) or "ignored"}
            for header in (csv.DictReader(io.StringIO(text)).fieldnames or [])]


def import_speaker_registry_csv(
    content: bytes,
    *,
    expected_revision: int,
    max_upload_bytes: int,
    save_records: Callable[..., tuple[list[dict[str, Any]], int]],
) -> tuple[list[dict[str, Any]], int, int]:
    if len(content) > max_upload_bytes:
        raise ValueError("CSVは10MB以内にしてください。")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("cp932")
        except UnicodeDecodeError as exc:
            raise ValueError("CSVの文字コードはUTF-8またはWindows日本語にしてください。") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSVに見出し行がありません。")
    imported: list[dict[str, Any]] = []
    for row_index, row in enumerate(reader, 2):
        if row_index > 10001:
            raise ValueError("一度に取り込める話者は10000件までです。")
        fixed: dict[str, Any] = {"attributes": {}}
        for raw_header, raw_value in row.items():
            escaped_attribute = isinstance(raw_header, str) and raw_header.startswith("属性:")
            header = clean_single_line(raw_header[3:] if escaped_attribute else raw_header, 120)
            value = clean_multiline(raw_value, 10000)
            if not header:
                continue
            field_name = None if escaped_attribute else speaker_csv_field_for_header(header)
            if field_name == "":
                continue
            if field_name:
                if not value:
                    continue
                fixed[field_name] = value
            else:
                if header in fixed["attributes"]:
                    raise ValueError("CSVの追加属性の列名が重複しています。")
                fixed["attributes"][header] = value
        if not any(fixed.get(key) for key in ("participant_code", "display_name", "pseudonym")):
            continue
        if fixed.get("default_role"):
            fixed["default_role"] = normalize_csv_role(fixed["default_role"])
        for field_name in ("consent_status", "recording_consent", "confidentiality_status"):
            if fixed.get(field_name):
                fixed[field_name] = normalize_csv_consent(fixed[field_name])
        if "active" in fixed:
            fixed["active"] = str(fixed["active"]).strip().casefold() not in {
                "0", "false", "no", "n", "無効",
            }
        imported.append(fixed)
    if not imported:
        raise ValueError("取り込める話者行がありませんでした。見出しと値を確認してください。")
    records, revision = save_records(
        imported,
        expected_revision=expected_revision,
        merge_by_participant_code=True,
    )
    return records, len(imported), revision


def speaker_registry_csv_bytes(records: list[dict[str, Any]]) -> bytes:
    custom_headers = sorted({
        key
        for record in records
        for key in (record.get("attributes") or {})
    })
    fixed_headers = [
        "参加者コード", "氏名", "仮名", "役割", "組織", "部署", "役職",
        "守秘同意", "タグ", "備考", "有効",
    ]
    attribute_headers = speaker_attribute_csv_headers(custom_headers, fixed_headers)
    custom_headers = list(attribute_headers.values())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fixed_headers + custom_headers)
    writer.writerow({header: analysis_csv_safe(header) for header in fixed_headers + custom_headers})
    for record in records:
        row = {
            "参加者コード": record["participant_code"],
            "氏名": record["display_name"],
            "仮名": record["pseudonym"],
            "役割": record["default_role"],
            "組織": record["organization"],
            "部署": record["department"],
            "役職": record["job_title"],
            "守秘同意": record["confidentiality_status"],
            "タグ": ",".join(record["tags"]),
            "備考": record["notes"],
            "有効": "1" if record["active"] else "0",
            **{attribute_headers[key]: value for key, value in record["attributes"].items()},
        }
        writer.writerow({key: analysis_csv_safe(value) for key, value in row.items()})
    return ("\ufeff" + stream.getvalue()).encode("utf-8")
