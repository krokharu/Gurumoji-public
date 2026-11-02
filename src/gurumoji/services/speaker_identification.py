"""Speaker-name detection with AI and linking detected names to the registry.

The pure parts (chunking, name normalization, identity repairs) are plain
functions. Parts that need the database or an AI client are built by the
make_* factories so the composition root supplies those dependencies."""

from __future__ import annotations

import json
import math
import re
import unicodedata
import uuid
from collections import defaultdict
from typing import Any, Callable

from ..text_utils import clean_multiline, clean_single_line, utc_now_iso
from .speaker_registry import (
    SPEAKER_ROLES,
    normalize_speaker_registry_record,
    speaker_registry_public,
    speaker_registry_revision,
    speaker_registry_rows,
)
from .transcription.segments import (
    default_speaker_name,
    normalize_text_for_merge,
    segment_bounds,
)


def normalize_detected_speaker_name(value: Any, evidence: Any = "") -> str:
    name = clean_single_line(value, 80).strip(" 　、。,.・:：;；「」『』【】()（）[]")
    evidence_text = clean_single_line(evidence, 300)
    name = re.sub(r"^(?:私は|わたしは|僕は|ぼくは|名前は)\s*", "", name)
    name = re.sub(
        r"\s*(?:と申します|ともうします|といいます|と言います|です|でございます)$",
        "",
        name,
    ).strip()
    for honorific in ("さん", "様", "さま", "君", "くん", "ちゃん"):
        if not name.endswith(honorific) or len(name) <= len(honorific):
            continue
        base = name[:-len(honorific)].strip()
        # ASR often renders a self-introduction as "名字さんです". Remove the
        # honorific only when the evidence contains that exact introductory
        # construction, rather than stripping legitimate name text blindly.
        if re.search(
            rf"{re.escape(base)}\s*{re.escape(honorific)}\s*(?:です|でございます|といいます|と言います|と申します)",
            evidence_text,
        ):
            name = base
        break
    return clean_single_line(name, 80)


def speaker_registry_identity_key(value: Any) -> str:
    """Return a conservative comparison key for a person name.

    This deliberately supports only harmless formatting differences.  It must
    not turn a partial or similar-looking name into a global-person match.
    """
    normalized = unicodedata.normalize("NFKC", clean_single_line(value, 120)).casefold()
    return re.sub(r"[\s\u3000・.．,，、。]", "", normalized)


def speaker_identity_context_records(
    records: list[dict[str, Any]],
    *,
    character_budget: int = 12000,
) -> list[dict[str, Any]]:
    if not records:
        return []
    invitation_pattern = re.compile(
        r"自己紹介|お名前|名前を|名乗|一人ずつ|ひとりずつ|お一人ずつ|順番に.{0,12}紹介"
    )
    identity_cue_pattern = re.compile(
        r"と申します|ともうします|といいます|と言います|出身|所属|担当|務め|"
        r"よろしくお願いします|"
        r"(?:^|[\s、。！？])[^\s、。！？]{1,20}(?:さん|様|くん|ちゃん)?です(?:[\s、。！？]|$)"
    )
    invitation_indexes = [
        index for index, record in enumerate(records)
        if invitation_pattern.search(str(record.get("text") or ""))
    ]
    cue_indexes = [
        index for index, record in enumerate(records)
        if identity_cue_pattern.search(str(record.get("text") or ""))
    ]
    selected_indexes: set[int] = set()

    def select_time_window(center_index: int, before: float, after: float) -> None:
        center = float(records[center_index].get("start", 0) or 0)
        lower = max(0.0, center - before)
        upper = center + after
        for index, record in enumerate(records):
            start = float(record.get("start", 0) or 0)
            end = float(record.get("end", start) or start)
            if end >= lower and start <= upper:
                selected_indexes.add(index)

    if invitation_indexes:
        # An invitation is the strongest boundary. The time window adapts to
        # long turns and many short turns without assuming a fixed turn count.
        for index in invitation_indexes:
            select_time_window(index, 60.0, 180.0)
    if cue_indexes:
        # Include later arrivals and introductions without an explicit request.
        for index in cue_indexes:
            select_time_window(index, 20.0, 35.0)
    if not selected_indexes:
        # With no lexical signal, retain an opening time/character window so
        # unconventional introductions can still be judged by the model.
        opening_start = float(records[0].get("start", 0) or 0)
        for index, record in enumerate(records):
            if float(record.get("start", 0) or 0) - opening_start > 240.0:
                break
            selected_indexes.add(index)

    selected = [records[index] for index in sorted(selected_indexes)]
    result: list[dict[str, Any]] = []
    used_characters = 0
    for record in selected:
        text_length = len(str(record.get("text") or ""))
        if result and used_characters + text_length > max(1000, character_budget):
            break
        result.append(record)
        used_characters += text_length
    return result or records[:1]


def apply_speaker_identity_repairs(
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    diagnostics: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, int]]:
    """Apply strictly validated AI alias and short-fragment corrections."""
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    raw_aliases = diagnostics.get("speaker_aliases")
    aliases = raw_aliases if isinstance(raw_aliases, dict) else {}
    raw_corrections = diagnostics.get("segment_speaker_corrections")
    corrections = raw_corrections if isinstance(raw_corrections, dict) else {}

    def canonical(label: str) -> str:
        current = label
        visited: set[str] = set()
        while current in aliases and current not in visited:
            visited.add(current)
            target = str(aliases[current])
            if not target or target == current:
                break
            current = target
        return current

    repaired: list[dict[str, Any]] = []
    corrected_count = 0
    aliased_count = 0
    for index, raw_segment in enumerate(segments):
        segment = dict(raw_segment)
        original = str(segment.get("speaker") or "UNKNOWN")
        corrected = str(corrections.get(index) or original)
        if corrected != original:
            corrected_count += 1
        final_label = canonical(corrected)
        if final_label != corrected:
            aliased_count += 1
        if segment.get("speaker") or final_label != "UNKNOWN":
            segment["speaker"] = final_label
        repaired.append(segment)

    canonical_names: dict[str, str] = {}
    conflicting: set[str] = set()
    for raw_label, raw_name in speaker_names.items():
        label = canonical(str(raw_label))
        name = clean_single_line(raw_name, 80)
        if not name:
            continue
        if label in canonical_names and canonical_names[label] != name:
            conflicting.add(label)
        else:
            canonical_names[label] = name
    for label in conflicting:
        canonical_names.pop(label, None)

    return repaired, canonical_names, {
        "alias_count": len(aliases),
        "aliased_segments": aliased_count,
        "corrected_segments": corrected_count,
    }


def display_speaker_for_ai(label: str | None, speaker_names: dict[str, str]) -> str:
    if label and speaker_names.get(label, "").strip():
        return speaker_names[label].strip()
    return default_speaker_name(label)


def make_speaker_registration(
    *,
    database_connection: Any,
    library_write_lock: Any,
    list_speaker_registry: Any,
    persist_speaker_registry_record: Any,
) -> tuple[Callable[..., Any], ...]:
    def link_detected_speakers_to_registry(
        speaker_profiles: dict[str, dict[str, Any]],
        speaker_names: dict[str, str],
        registry_records: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        """Link verified self-introductions to one registered person when safe.

        A name with no unique active registry match remains scoped to this
        conversation as a temporary single-group speaker.  We intentionally do
        not create a global registry record or guess from a partial-name match.
        """
        if not speaker_names:
            return speaker_profiles, {
                "linked": {}, "temporary": {}, "ambiguous": {}, "changed": False,
            }
        records = registry_records if registry_records is not None else list_speaker_registry(
            include_inactive=False
        )
        matches_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            if not isinstance(record, dict) or record.get("active") is False:
                continue
            keys = {
                speaker_registry_identity_key(record.get(field))
                for field in ("display_name", "pseudonym")
            }
            for key in keys - {""}:
                matches_by_name[key].append(record)

        linked: dict[str, str] = {}
        temporary: dict[str, str] = {}
        ambiguous: dict[str, list[str]] = {}
        changed = False
        for label, raw_name in speaker_names.items():
            name = clean_single_line(raw_name, 120)
            profile = speaker_profiles.get(str(label))
            if not name or not isinstance(profile, dict):
                continue
            # A user-selected link is authoritative; auto-identification must not
            # replace it based on a name collision.
            if clean_single_line(profile.get("global_speaker_id"), 80):
                if profile.get("registration_status") != "registered":
                    profile["registration_status"] = "registered"
                    changed = True
                continue
            candidates = matches_by_name.get(speaker_registry_identity_key(name), [])
            unique = {str(item.get("id") or ""): item for item in candidates if item.get("id")}
            if len(unique) == 1:
                record = next(iter(unique.values()))
                profile["global_speaker_id"] = str(record["id"])
                profile["registration_status"] = "registered"
                profile["display_name"] = (
                    clean_single_line(record.get("pseudonym"), 120)
                    or clean_single_line(record.get("display_name"), 120)
                    or name
                )
                profile["session_role"] = clean_single_line(
                    record.get("default_role"), 40
                ) if clean_single_line(record.get("default_role"), 40) in SPEAKER_ROLES else "participant"
                for field in ("organization", "department", "job_title"):
                    profile[field] = clean_single_line(record.get(field), 200)
                attributes = record.get("attributes")
                profile["conditions"] = "; ".join(
                    f"{clean_single_line(key, 120)}={clean_multiline(value, 2000)}"
                    for key, value in attributes.items()
                    if clean_single_line(key, 120)
                ) if isinstance(attributes, dict) else ""
                linked[str(label)] = str(record["id"])
                changed = True
            else:
                if profile.get("global_speaker_id") or profile.get("registration_status") != "temporary_single_group":
                    profile["global_speaker_id"] = ""
                    profile["registration_status"] = "temporary_single_group"
                    changed = True
                profile["display_name"] = name
                temporary[str(label)] = name
                if len(unique) > 1:
                    ambiguous[str(label)] = sorted(unique)
        return speaker_profiles, {
            "linked": linked,
            "temporary": temporary,
            "ambiguous": ambiguous,
            "changed": changed,
        }

    def register_detected_speakers(
        speaker_profiles: dict[str, dict[str, Any]],
        speaker_names: dict[str, str],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        """Link verified introductions and register unambiguous new speakers.

        This is deliberately called only from the AI self-introduction workflow,
        never from a manually edited display name.  Existing duplicate or inactive
        records remain for a person to resolve rather than creating another global
        speaker with the same name.
        """
        if not speaker_names:
            profiles, summary = link_detected_speakers_to_registry(
                speaker_profiles, speaker_names, []
            )
            return profiles, {
                **summary,
                "created": {},
                "inactive": {},
                "duplicate_identifications": {},
            }

        # The registry's ordinary editor uses the same lock, so a transcription
        # cannot create a duplicate while someone is saving speaker management.
        with library_write_lock:
            with database_connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                revision = speaker_registry_revision(connection)
                all_records = [
                    speaker_registry_public(row)
                    for row in speaker_registry_rows(connection, include_inactive=True)
                ]
                active_records = [
                    record for record in all_records if record.get("active") is not False
                ]
                profiles, summary = link_detected_speakers_to_registry(
                    speaker_profiles, speaker_names, active_records
                )

                inactive_matches: dict[str, list[str]] = defaultdict(list)
                for record in all_records:
                    if record.get("active") is not False:
                        continue
                    for field in ("display_name", "pseudonym"):
                        key = speaker_registry_identity_key(record.get(field))
                        if key and record.get("id"):
                            inactive_matches[key].append(str(record["id"]))

                labels_by_name: dict[str, list[str]] = defaultdict(list)
                for label, name in summary["temporary"].items():
                    key = speaker_registry_identity_key(name)
                    if key:
                        labels_by_name[key].append(label)

                inactive: dict[str, list[str]] = {}
                duplicate_identifications: dict[str, list[str]] = {}
                new_records: list[tuple[str, str, dict[str, Any]]] = []
                for label, name in summary["temporary"].items():
                    key = speaker_registry_identity_key(name)
                    if not key:
                        continue
                    if label in summary["ambiguous"]:
                        continue
                    if inactive_matches.get(key):
                        inactive[label] = sorted(set(inactive_matches[key]))
                        continue
                    duplicate_labels = sorted(labels_by_name[key])
                    if len(duplicate_labels) > 1:
                        duplicate_identifications[label] = duplicate_labels
                        continue
                    record = normalize_speaker_registry_record({
                        "id": f"speaker_auto_{uuid.uuid4().hex}",
                        "display_name": name,
                        "default_role": "participant",
                        "active": True,
                    })
                    new_records.append((label, name, record))

                created: dict[str, str] = {}
                if new_records:
                    now = utc_now_iso()
                    for label, _name, record in new_records:
                        persist_speaker_registry_record(connection, record, None, now,
                            origin="rule", process="speaker_registry_auto_registration")
                        created[label] = record["id"]
                    connection.execute(
                        "UPDATE application_metadata SET value = ? WHERE key = ?",
                        (str(revision + 1), "speaker_registry_revision"),
                    )
                    all_records.extend(record for _label, _name, record in new_records)

            if created:
                # Reuse the normal profile mapping so newly registered names get
                # the same display and role semantics as pre-existing speakers.
                profiles, refreshed = link_detected_speakers_to_registry(
                    profiles, speaker_names, all_records
                )
                summary = {
                    **refreshed,
                    "changed": bool(summary["changed"] or refreshed["changed"]),
                }

        return profiles, {
            **summary,
            "created": created,
            "inactive": inactive,
            "duplicate_identifications": duplicate_identifications,
        }

    return (link_detected_speakers_to_registry, register_detected_speakers)


def detect_speaker_names_with_ai(
    segments: list[dict[str, Any]],
    provider: str,
    api_key: str,
    model: str,
    check_cancelled: Callable[[], None] | None = None,
    usage_callback: Callable[[dict[str, Any]], None] | None = None,
    status_callback: Callable[[str], None] | None = None,
    diagnostics_callback: Callable[[dict[str, Any]], None] | None = None,
    base_url: str = "",
    ai_efforts: dict | None = None,
    *,
    call_ai_json: Callable[..., dict[str, Any]],
) -> dict[str, str]:
    if check_cancelled is not None:
        check_cancelled()
    labels = sorted({str(item["speaker"]) for item in segments if item.get("speaker")})
    if not labels:
        return {}
    early: list[dict[str, Any]] = []
    chars = 0
    for index, item in enumerate(segments):
        if float(item.get("start", 0)) > 900 or len(early) >= 120 or chars >= 24000:
            break
        record = {
            "id": index,
            "speaker": item.get("speaker") or "UNKNOWN",
            "start": round(float(item.get("start", 0) or 0), 2),
            "end": round(float(item.get("end", item.get("start", 0)) or 0), 2),
            "text": item.get("text", ""),
        }
        early.append(record)
        chars += len(str(record["text"]))
    identity_context = speaker_identity_context_records(early)
    schema = {
        "type": "object",
        "properties": {
            "speaker_names": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker": {"type": "string", "enum": labels},
                        "name": {"type": "string"},
                        "evidence": {"type": "string"},
                        "evidence_segment_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                    "required": ["speaker", "name", "evidence", "evidence_segment_ids"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["speaker_names"],
        "additionalProperties": False,
    }
    if status_callback is not None:
        status_callback("話者特定 1/2: 自己紹介の候補を抽出しています…")
    first_result = call_ai_json(
        provider,
        api_key,
        model,
        (
            "これは文字校正とは独立した話者特定処理です。会話冒頭付近の明示的な自己紹介から、"
            "氏名候補と、その名前を発話した音声話者ラベルを抽出してください。"
            "『私は田中です』『○○と申します』は例であり、固定表現の完全一致を条件にしません。"
            "人によって名乗り方が異なるため、直前の『自己紹介をお願いします』、発話順、話者交代、"
            "氏名らしい語の後に続く出身地・所属・役割・『よろしくお願いします』などを組み合わせ、"
            "その発話が本人の自己紹介であるかを文脈で判断してください。『片割さんです、出身は静岡です』"
            "のような敬称混入、助詞欠落、句読点欠落、名前と次の文の連結など音声認識特有の揺れも許容します。"
            "本人の名乗りに付いた『さん』『様』『くん』『ちゃん』は氏名本体から除いて返してください。"
            "ただし、他人を呼んだだけの名前、話題に出ただけの名前、会社名だけ、文脈根拠のない推測は採用しません。"
            "自己紹介が複数発話に分割されている場合は前後の発話をつなげて判断してください。"
            "根拠に使った発話の id を evidence_segment_ids に必ず入れてください。"
            "この段階では候補を漏らさないことを優先します。"
        ),
        "話者ラベル付きの発話です。\n" + json.dumps(identity_context, ensure_ascii=False),
        "speaker_identity_extraction",
        schema,
        check_cancelled,
        usage_callback,
        base_url,
        **({"ai_efforts": ai_efforts} if ai_efforts else {}),
    )
    if check_cancelled is not None:
        check_cancelled()

    def normalized_evidence_ids(value: Any) -> list[int]:
        result: list[int] = []
        if not isinstance(value, list):
            return result
        for raw_id in value:
            if isinstance(raw_id, bool) or not isinstance(raw_id, int):
                continue
            if 0 <= raw_id < len(early) and raw_id not in result:
                result.append(raw_id)
        return result[:12]

    first_candidates: list[dict[str, Any]] = []
    for item in first_result.get("speaker_names") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("speaker", ""))
        evidence = clean_single_line(item.get("evidence"), 240)
        name = normalize_detected_speaker_name(item.get("name"), evidence)
        if label in labels and name:
            first_candidates.append({
                "speaker": label,
                "name": name,
                "evidence": evidence,
                "evidence_segment_ids": normalized_evidence_ids(
                    item.get("evidence_segment_ids")
                ),
            })

    verification_schema = {
        "type": "object",
        "properties": {
            "speaker_names": schema["properties"]["speaker_names"],
            "speaker_aliases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "canonical_speaker": {"type": "string", "enum": labels},
                        "alias_speaker": {"type": "string", "enum": labels},
                        "confidence": {"type": "number"},
                        "evidence_segment_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                    "required": [
                        "canonical_speaker", "alias_speaker", "confidence",
                        "evidence_segment_ids",
                    ],
                    "additionalProperties": False,
                },
            },
            "segment_speaker_corrections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "segment_id": {"type": "integer"},
                        "speaker": {"type": "string", "enum": labels},
                        "confidence": {"type": "number"},
                        "evidence_segment_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                    "required": [
                        "segment_id", "speaker", "confidence",
                        "evidence_segment_ids",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "speaker_names", "speaker_aliases", "segment_speaker_corrections",
        ],
        "additionalProperties": False,
    }

    if status_callback is not None:
        status_callback("話者特定 2/2: 候補を音声話者ラベルへリンクして再確認しています…")
    try:
        verified_result = call_ai_json(
            provider,
            api_key,
            model,
            (
                "これは独立した話者リンクの最終確認です。一次候補を鵜呑みにせず、発話時刻、"
                "自己紹介文、speaker ラベルを再確認してください。固定の言い回しだけで判定せず、"
                "自己紹介依頼の直後という位置、発話順、出身地・所属・役割・挨拶の連続などから、"
                "本人の自己紹介と文脈上確認できた氏名を、"
                "その氏名部分を発話した speaker ラベルへリンクします。自己紹介が発話境界で分割された"
                "場合は隣接発話を復元して判断してください。一次処理が見落とした明示的な自己紹介も追加し、"
                "音声認識による『名前＋さんです』、助詞や句読点の欠落も許容し、敬称は氏名から除いてください。"
                "根拠がない候補や別人へのリンクは除外してください。根拠発話の id を"
                " evidence_segment_ids に必ず返してください。最終的に確認できた全話者を返してください。"
                "同じ人物が複数の speaker ラベルに分裂していることを強い文脈根拠で確認できる場合だけ、"
                "代表ラベルと別名ラベルを speaker_aliases に返してください。単に発話が隣接するだけでは"
                "同一人物と判定しません。また、短い発話だけ別 speaker になった A-B-A 型の断裂で、"
                "前後と同一人物だと確実に判断できる場合だけ segment_speaker_corrections に返してください。"
                "修復候補には対象発話と前後発話の id、0から1の confidence を入れてください。"
            ),
            (
                "一次候補:\n" + json.dumps(first_candidates, ensure_ascii=False)
                + "\n\n話者ラベル付き発話:\n" + json.dumps(identity_context, ensure_ascii=False)
            ),
            "speaker_identity_link_verification",
            verification_schema,
            check_cancelled,
            usage_callback,
            base_url,
        **({"ai_efforts": ai_efforts} if ai_efforts else {}),
        )
    except InterruptedError:
        raise
    except Exception:
        verified_result = {
            "speaker_names": first_candidates,
            "speaker_aliases": [],
            "segment_speaker_corrections": [],
        }
    if check_cancelled is not None:
        check_cancelled()

    resolved_candidates: list[tuple[str, str]] = []
    for item in verified_result.get("speaker_names") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("speaker", ""))
        evidence = clean_single_line(item.get("evidence"), 240)
        name = normalize_detected_speaker_name(item.get("name"), evidence)
        if label not in labels or not name:
            continue
        evidence_ids = normalized_evidence_ids(item.get("evidence_segment_ids"))
        evidence_labels = {
            str(early[evidence_id].get("speaker") or "UNKNOWN")
            for evidence_id in evidence_ids
        }
        # An explicit evidence id is more reliable than a free-form speaker
        # field generated by the model. Only keep the model choice when the
        # evidence genuinely spans more than one diarization label.
        if len(evidence_labels) == 1:
            label = next(iter(evidence_labels))
        elif evidence_labels and label not in evidence_labels:
            continue
        elif not evidence_ids:
            matching_labels = {
                str(record.get("speaker") or "UNKNOWN")
                for record in early
                if name in str(record.get("text") or "")
            }
            if len(matching_labels) == 1:
                label = next(iter(matching_labels))
        resolved_candidates.append((label, name))

    candidates_by_label: dict[str, list[str]] = defaultdict(list)
    for label, name in resolved_candidates:
        if name not in candidates_by_label[label]:
            candidates_by_label[label].append(name)
    ambiguous_labels = {
        label: values
        for label, values in candidates_by_label.items()
        if len(values) > 1
    }
    names = {
        label: values[0]
        for label, values in candidates_by_label.items()
        if len(values) == 1
    }

    def confidence_value(value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        return parsed if math.isfinite(parsed) else 0.0

    proposed_aliases: dict[str, set[str]] = defaultdict(set)
    for item in verified_result.get("speaker_aliases") or []:
        if not isinstance(item, dict) or confidence_value(item.get("confidence")) < 0.92:
            continue
        canonical_label = str(item.get("canonical_speaker") or "")
        alias_label = str(item.get("alias_speaker") or "")
        if (
            canonical_label not in labels
            or alias_label not in labels
            or canonical_label == alias_label
        ):
            continue
        evidence_ids = normalized_evidence_ids(item.get("evidence_segment_ids"))
        evidence_labels = {
            str(early[evidence_id].get("speaker") or "UNKNOWN")
            for evidence_id in evidence_ids
        }
        if not {canonical_label, alias_label}.issubset(evidence_labels):
            continue
        if (
            names.get(canonical_label)
            and names.get(alias_label)
            and names[canonical_label] != names[alias_label]
        ):
            continue
        proposed_aliases[alias_label].add(canonical_label)
    speaker_aliases = {
        alias: next(iter(targets))
        for alias, targets in proposed_aliases.items()
        if len(targets) == 1 and alias not in targets
    }
    speaker_aliases = {
        alias: target
        for alias, target in speaker_aliases.items()
        if speaker_aliases.get(target) != alias
    }

    def canonical_label(label: str) -> str:
        current = label
        visited: set[str] = set()
        while current in speaker_aliases and current not in visited:
            visited.add(current)
            current = speaker_aliases[current]
        return current

    canonical_names: dict[str, str] = {}
    name_conflicts: set[str] = set()
    for label, name in names.items():
        canonical = canonical_label(label)
        if canonical in canonical_names and canonical_names[canonical] != name:
            name_conflicts.add(canonical)
        else:
            canonical_names[canonical] = name
    for label in name_conflicts:
        canonical_names.pop(label, None)
    names = canonical_names

    segment_speaker_corrections: dict[int, str] = {}
    for item in verified_result.get("segment_speaker_corrections") or []:
        if not isinstance(item, dict) or confidence_value(item.get("confidence")) < 0.92:
            continue
        segment_id = item.get("segment_id")
        proposed_speaker = str(item.get("speaker") or "")
        if (
            isinstance(segment_id, bool)
            or not isinstance(segment_id, int)
            or not 0 < segment_id < len(early) - 1
            or proposed_speaker not in labels
        ):
            continue
        previous_speaker = str(early[segment_id - 1].get("speaker") or "UNKNOWN")
        current_speaker = str(early[segment_id].get("speaker") or "UNKNOWN")
        following_speaker = str(early[segment_id + 1].get("speaker") or "UNKNOWN")
        start, end = segment_bounds(early[segment_id])
        normalized_text = normalize_text_for_merge(str(early[segment_id].get("text") or ""))
        evidence_ids = set(normalized_evidence_ids(item.get("evidence_segment_ids")))
        if (
            previous_speaker == following_speaker == proposed_speaker
            and current_speaker != proposed_speaker
            and (end - start <= 4.0 or len(normalized_text) <= 28)
            and segment_id in evidence_ids
            and evidence_ids.intersection({segment_id - 1, segment_id + 1})
        ):
            segment_speaker_corrections[segment_id] = proposed_speaker
    labels_by_name: dict[str, list[str]] = defaultdict(list)
    for label, name in names.items():
        labels_by_name[name].append(label)
    duplicate_names = {
        name: linked_labels
        for name, linked_labels in labels_by_name.items()
        if len(linked_labels) > 1
    }
    if duplicate_names:
        names = {
            label: name
            for label, name in names.items()
            if name not in duplicate_names
        }
    if diagnostics_callback is not None:
        diagnostics_callback({
            "source_segment_count": len(early),
            "context_segment_count": len(identity_context),
            "candidate_count": len(resolved_candidates),
            "linked_count": len(names),
            "ambiguous_labels": ambiguous_labels,
            "duplicate_names": duplicate_names,
            "speaker_aliases": speaker_aliases,
            "segment_speaker_corrections": segment_speaker_corrections,
        })
    return names
