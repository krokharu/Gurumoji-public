"""Pure conversions between library_items rows and API/analysis values.

Nothing here touches the database, files or Flask; callers pass rows in."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
import uuid
from typing import Any

from ..analysis_insights import build_session_outline
from ..text_utils import clean_multiline, clean_single_line, json_load
from .emotion import emotion_label_ja
from .meeting_minutes import normalize_meeting_minutes
from .outputs import SPEAKER_THEME_COLORS
from .speaker_registry import (
    ATTENDANCE_STATUSES,
    CONSENT_STATUSES,
    SPEAKER_REGISTRATION_STATUSES,
    SPEAKER_ROLES,
)


SESSION_TYPES = {"focus_group", "meeting", "interview", "workshop", "chat", "other"}


def normalize_source_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid source name.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Source names cannot contain control characters.")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 255:
        raise ValueError("Source names must contain between 1 and 255 characters.")
    return cleaned


def stable_segment_id(item_id: str, index: int, segment: dict[str, Any]) -> str:
    existing = str(segment.get("id") or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", existing):
        return existing
    seed = f"{item_id}:{index}:{segment.get('start', 0)}:{segment.get('end', 0)}"
    return uuid.uuid5(uuid.NAMESPACE_URL, seed).hex


def ensure_segment_ids(item_id: str, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    used: set[str] = set()
    for index, raw in enumerate(segments):
        if not isinstance(raw, dict):
            continue
        segment = dict(raw)
        segment_id = stable_segment_id(item_id, index, segment)
        if segment_id in used:
            segment_id = uuid.uuid4().hex
        segment["id"] = segment_id
        used.add(segment_id)
        normalized.append(segment)
    return normalized


def row_segments(row: sqlite3.Row) -> list[dict[str, Any]]:
    raw = json_load(row["segments_json"], [])
    return ensure_segment_ids(row["id"], raw if isinstance(raw, list) else [])


def row_original_segments(row: sqlite3.Row) -> tuple[dict[str, dict[str, Any]], str]:
    """Return the immutable-at-import transcript snapshot, if one is available.

    This deliberately does not fall back to the editable `segments_json` value:
    doing so would hide a missing original source.  Legacy records migrated to
    this schema retain a separate snapshot, but its status is labelled so it is
    not mistaken for the pre-edit transcript.
    """
    if "original_segments_json" not in row.keys():
        return {}, "unavailable"
    raw = json_load(row["original_segments_json"], [])
    if not isinstance(raw, list):
        return {}, "unavailable"
    values = {
        str(segment.get("id") or ""): dict(segment)
        for segment in raw
        if isinstance(segment, dict) and str(segment.get("id") or "")
    }
    status = (
        clean_single_line(row["original_segments_status"], 80)
        if "original_segments_status" in row.keys() else ""
    )
    return values, status or "unavailable"


def normalize_session_profile(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raw = {}
    session_type = clean_single_line(raw.get("session_type", "focus_group"), 40)
    if session_type not in SESSION_TYPES:
        session_type = "other"
    session_date = clean_single_line(raw.get("session_date"), 40)
    session_date_source = clean_single_line(raw.get("session_date_source"), 30)
    if session_date_source not in {"media_metadata", "manual"}:
        session_date_source = "manual" if session_date else ""
    if not session_date:
        session_date_source = ""
    return {
        "session_type": session_type,
        "session_date": session_date,
        "session_date_source": session_date_source,
        "location": clean_single_line(raw.get("location"), 300),
        # This is intentionally separate from the research objective.  A single
        # objective can be phrased similarly across studies even when the guide
        # and the questions are not comparable.
        "comparison_group": clean_single_line(raw.get("comparison_group"), 300),
        # A comparison group identifies sessions that can be compared.  This
        # field identifies the actual group in a particular session and must
        # not be inferred from the file name or speaker labels.
        "interview_group_id": clean_single_line(raw.get("interview_group_id"), 120),
        "objective": clean_multiline(raw.get("objective"), 10000),
        "moderator_guide": clean_multiline(raw.get("moderator_guide"), 20000),
        "group_conditions": clean_multiline(raw.get("group_conditions"), 10000),
        "field_notes": clean_multiline(raw.get("field_notes"), 30000),
    }


def normalized_comparison_group(value: Any) -> str:
    """Return a stable, human-entered key for compatible interview sessions."""
    value = unicodedata.normalize("NFKC", clean_single_line(value, 300)).casefold()
    return re.sub(r"\s+", " ", value).strip()


def interview_comparison_identity(profile: dict[str, Any]) -> tuple[str, str, str]:
    """Get a privacy-preserving compatibility key and its display metadata.

    An explicitly entered comparison group is authoritative.  For existing
    records that predate that field, an identical moderator guide is a safe
    fallback; a missing guide is deliberately not treated as compatible.
    """
    group = clean_single_line(profile.get("comparison_group"), 300)
    normalized_group = normalized_comparison_group(group)
    if normalized_group:
        return (f"group:{normalized_group}", group, "comparison_group")
    guide = clean_multiline(profile.get("moderator_guide"), 20000)
    normalized_guide = re.sub(r"\s+", "", unicodedata.normalize("NFKC", guide)).casefold()
    if normalized_guide:
        digest = hashlib.sha256(normalized_guide.encode("utf-8")).hexdigest()[:24]
        return (f"guide:{digest}", "質問ガイドから自動照合", "moderator_guide")
    return ("", "未設定", "")


def normalize_conversation_speaker_profiles(
    raw: Any,
    labels: set[str],
    speaker_names: dict[str, str],
) -> dict[str, dict[str, Any]]:
    source = raw if isinstance(raw, dict) else {}
    profiles: dict[str, dict[str, Any]] = {}
    for index, label in enumerate(sorted(labels)):
        value = source.get(label)
        value = value if isinstance(value, dict) else {}
        supplied_role = clean_single_line(value.get("session_role", "participant"), 40)
        role = supplied_role if supplied_role in SPEAKER_ROLES else "participant"
        marker = value.get("session_role_source")
        if marker in ("explicit", "registry", "default", "legacy_unknown"):
            role_source = marker
            if "session_role" not in value or supplied_role not in SPEAKER_ROLES or marker == "default" and role != "participant":
                role_source = "legacy_unknown"
        elif "session_role_source" in value:
            role_source = "legacy_unknown"
        elif "session_role" not in value:
            role_source = "default"
        elif supplied_role in SPEAKER_ROLES and supplied_role != "participant":
            # Only participant was ever inserted as the historical fallback.
            role_source = "explicit"
        else:
            # Reading or round-tripping legacy participant cannot certify
            # whether it was entered by a person or inserted by normalization.
            role_source = "legacy_unknown"
        consent_status = clean_single_line(value.get("consent_status", "unknown"), 30)
        recording_consent = clean_single_line(value.get("recording_consent", "unknown"), 30)
        attendance_status = clean_single_line(value.get("attendance_status", "attended"), 30)
        registration_status = clean_single_line(value.get("registration_status"), 40)
        theme_color = clean_single_line(value.get("theme_color"), 7).upper()
        if not re.fullmatch(r"#[0-9A-F]{6}", theme_color):
            theme_color = SPEAKER_THEME_COLORS[index % len(SPEAKER_THEME_COLORS)]
        global_speaker_id = clean_single_line(value.get("global_speaker_id"), 80)
        display_name = clean_single_line(
            value.get("display_name") or speaker_names.get(label), 120
        )
        if global_speaker_id:
            registration_status = "registered"
        elif registration_status not in SPEAKER_REGISTRATION_STATUSES:
            registration_status = "temporary_single_group" if display_name else "unidentified"
        profiles[label] = {
            "speaker_label": label,
            "global_speaker_id": global_speaker_id,
            "registration_status": registration_status,
            "display_name": display_name,
            "theme_color": theme_color,
            "session_role": role,
            "session_role_source": role_source,
            "organization": clean_single_line(value.get("organization"), 200),
            "department": clean_single_line(value.get("department"), 200),
            "job_title": clean_single_line(value.get("job_title"), 200),
            "consent_status": (
                consent_status if consent_status in CONSENT_STATUSES else "unknown"
            ),
            "recording_consent": (
                recording_consent if recording_consent in CONSENT_STATUSES else "unknown"
            ),
            "attendance_status": (
                attendance_status if attendance_status in ATTENDANCE_STATUSES else "unknown"
            ),
            "conditions": clean_multiline(value.get("conditions"), 10000),
            "notes": clean_multiline(value.get("notes"), 10000),
        }
    return profiles


def row_session_profile(row: sqlite3.Row) -> dict[str, str]:
    return normalize_session_profile(json_load(row["session_profile_json"], {}))


def row_meeting_minutes(row: sqlite3.Row) -> dict[str, Any]:
    try:
        raw = row["meeting_minutes_json"]
    except (KeyError, IndexError):
        raw = "{}"
    return normalize_meeting_minutes(json_load(raw, {}))


def row_session_outline(row: sqlite3.Row, session_profile: dict[str, Any]) -> dict[str, Any]:
    """Join the planned agenda, the saved agenda sections and the saved themes."""
    try:
        saved = json_load(row["transformer_analysis_json"], {})
    except (KeyError, IndexError):
        saved = {}
    transformer = saved if isinstance(saved, dict) else {}
    # The analysis screen owns the exact staleness check; here the saved revisions
    # answer the question this block asks: was this run made from the current text?
    saved_revisions = tuple(
        value if isinstance(value, int) and not isinstance(value, bool) else None
        for value in (transformer.get("source_revision"), transformer.get("analysis_revision"))
    )
    stale = bool(transformer) and saved_revisions != (
        int(row["revision_count"] or 0), int(row["analysis_revision"] or 0),
    )
    return build_session_outline(
        outline=json_load(row["outline_json"], None), transformer=transformer,
        session_profile=session_profile, transformer_stale=stale,
    )


def row_speaker_profiles(
    row: sqlite3.Row,
    segments: list[dict[str, Any]] | None = None,
    speaker_names: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    segments = segments if segments is not None else row_segments(row)
    if speaker_names is None:
        raw_names = json_load(row["speaker_names_json"], {})
        speaker_names = raw_names if isinstance(raw_names, dict) else {}
    labels = {str(item.get("speaker") or "UNKNOWN") for item in segments}
    return normalize_conversation_speaker_profiles(
        json_load(row["speaker_profiles_json"], {}),
        labels,
        speaker_names,
    )


def emotion_values(segment: dict[str, Any]) -> list[str]:
    emotions = segment.get("emotions")
    if not isinstance(emotions, dict):
        return []
    values: list[str] = []
    for data in emotions.values():
        if not isinstance(data, dict):
            continue
        raw_value = data.get("label_ja") or data.get("label")
        if not raw_value:
            continue
        value = str(data.get("label_ja") or emotion_label_ja(str(raw_value))).strip()
        if value and value not in values:
            values.append(value)
    return values
