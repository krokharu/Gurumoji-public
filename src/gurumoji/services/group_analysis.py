"""Group (focus-group and interview) analysis computation and CSV export.

This module turns one library row into the analysis payload the UI renders and
the exports serialize: participation metrics, interaction coding, the evidence
inventory, and the method plan.  It states plainly what the recording does and
does not support rather than inferring it.

Reading the library row is the caller's job; the row accessors and the database
connection factory are injected so this module stays free of Flask and of
application globals.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import sqlite3
import unicodedata
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from ..analysis_insights import KWIC_FIELDS, build_session_outline, input_fingerprint, plan_items
from ..analysis_method_registry import METHOD_GROUPS, SEPARATE_RUN_METHODS, method_results
from ..media_formats import ALLOWED_EXTENSIONS, VIDEO_EXTENSIONS
from ..research_analysis import (
    RESEARCH_CSV_FIELDS,
    build_research_analysis,
    enrich_research_analysis,
    is_research_analysis_cached,
    research_csv_sources,
)
from ..segment_classification import (
    CLASSIFICATION_FIELDS,
    CROSSTAB_FIELDS as SEGMENT_CLASSIFICATION_CROSSTAB_FIELDS,
    DIALOGUE_ACTS,
    classification_fingerprint,
    classification_rows,
    crosstab_rows as segment_classification_crosstab_rows,
    summary as segment_classification_summary,
)
from ..text_utils import clean_multiline, clean_single_line, json_load, normalize_tags, utc_now_iso
from ..transformer_analysis import (
    DEFAULT_MODEL as DEFAULT_TRANSFORMER_MODEL,
    MAX_MANUAL_TOPICS,
    transformer_csv_sources,
    transformer_input_fingerprint,
)
from .. import method_experts
from .. import transcript_preparation as preparation
from .emotion import emotion_label_ja
from .analysis_networks import attach_foundations
from .outputs import SPEAKER_THEME_COLORS
from .transcription.segments import default_speaker_name
from .group_analysis_exports import (
    ANALYSIS_CSV_FIELDS,
    analysis_csv_content,
    analysis_csv_rows,
    analysis_csv_safe,
    focus_group_analysis_report_markdown,
)

GROUP_ANALYSIS_ALGORITHM_VERSION = "focus-group-local-7"
ANALYSIS_UNITS = {"turn"}
ANALYSIS_GROUP_FIELDS = {"none", "role", "organization", "department", "job_title"}
ANALYSIS_INTERPRETATION_STATUSES = {"draft", "reviewed"}
ANALYSIS_INTERACTION_TAGS = {
    "agreement": "同意・賛同",
    "disagreement": "不一致・反対",
    "differentiation": "立場の差異化",
    "change": "意見の変化",
    "word_use": "言葉の意味の違い",
    "repetition": "反復・強調",
    "engagement": "関与・発展",
    "silencing": "沈黙・発言抑制",
}
ANALYSIS_ELICITATION_TYPES = {
    "unknown": "不明・未確認",
    "spontaneous": "自発的な発言",
    "moderator_prompted": "司会者の質問・働きかけを受けた発言",
    "participant_prompted": "他の参加者の働きかけを受けた発言",
    "other_prompted": "その他の働きかけを受けた発言",
}
# A relation has to be anchored to another turn before it is treated as evidence
# for interaction.  The single-turn tag is retained separately for backwards
# compatibility and for provisional coding.
ANALYSIS_INTERACTION_RELATIONS = {
    "response": "応答",
    "agreement": "同意・賛同",
    "disagreement": "不一致・反対",
    "differentiation": "立場の差異化",
    "change": "意見の変化",
    "word_use": "言葉の意味の違い",
    "repetition": "反復・強調",
    "engagement": "補足・発展",
}
ANALYSIS_METHODS = {
    "auto": "資料に応じて暫定選定",
    "qualitative_content": "質的内容分析",
    "thematic": "テーマ分析",
    "framework": "フレームワーク分析",
    "scat": "SCAT",
    "mgta": "M-GTA",
    "kj": "KJ法",
    "quantitative_text": "計量テキスト分析（補助）",
    "interaction": "相互作用分析",
}
ANALYSIS_FACILITATOR_ROLES = {
    "moderator", "facilitator", "assistant_moderator", "interviewer", "chair",
}
ANALYSIS_NON_PARTICIPANT_ROLES = ANALYSIS_FACILITATOR_ROLES | {
    "observer", "note_taker",
}
ANALYSIS_MAX_TIMELINE_SECONDS = 31 * 86400
ANALYSIS_MAX_TIME_BINS = 5000
TEXT_MINING_STOP_WORDS = {
    "こと", "これ", "それ", "ため", "よう", "ところ", "もの", "こちら", "さん",
    "です", "ます", "でした", "ました", "する", "いる", "ある", "なる",
    "the", "and", "that", "this", "with", "from", "have", "will", "your",
}

def text_mining_counter(
    segments: list[dict[str, Any]],
    extra_stop_words: set[str] | None = None,
) -> Counter[str]:
    text = " ".join(str(item.get("text") or "") for item in segments)
    candidates = re.findall(
        r"[一-龯々〆ヵヶ]{2,}|[ァ-ヴー]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}",
        text,
    )
    stop_words = TEXT_MINING_STOP_WORDS | {
        str(value).casefold() for value in (extra_stop_words or set()) if str(value).strip()
    }
    return Counter(
        token.casefold() if token.isascii() else token
        for token in candidates
        if token.casefold() not in stop_words
    )


def text_mining_terms(
    segments: list[dict[str, Any]],
    limit: int = 18,
    extra_stop_words: set[str] | None = None,
) -> list[tuple[str, int]]:
    """Extract useful frequent terms without requiring a morphological analyzer."""
    return text_mining_counter(segments, extra_stop_words).most_common(limit)


def analysis_number(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return round(min(max(number, minimum), maximum), 3)


def analysis_bool(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def analysis_optional_score(value: Any) -> int | None:
    """Normalize an explicitly entered screening score without inventing one."""
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(round(min(100.0, max(0.0, number))))


def default_analysis_config() -> dict[str, Any]:
    return {
        "research_question": "",
        "analysis_method": "auto",
        "method_rationale": "",
        "analysis_unit": "turn",
        "exclude_moderator": True,
        "excluded_speakers": [],
        "group_by": "none",
        "long_gap_seconds": 3.0,
        "overlap_seconds": 0.2,
        "low_participation_percent": 10.0,
        "time_bin_seconds": 300,
        "stop_words": [],
        "morph_split_mode": "C",
        "cooccurrence_min_count": 2,
        "cooccurrence_top_terms": 60,
        "statistics_group_by": "speaker",
        "crosstab_terms": [],
        "crosstab_match_mode": "normalized",
        "codebook": [],
        "codebook_version": 0,
        "codebook_change_reason": "",
        "codebook_history": [],
        "transformer_topics": [],
        "analyst_memo": "",
        "interpretation_status": "draft",
    }


def normalize_transformer_topics(raw: Any) -> list[dict[str, Any]]:
    """Keep the researcher's own theme definitions for the manual assignment mode."""
    if not isinstance(raw, list):
        return []
    topics: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for index, value in enumerate(raw[:MAX_MANUAL_TOPICS]):
        if not isinstance(value, dict):
            continue
        label = clean_single_line(value.get("label"), 120)
        if not label:
            continue
        topic_id = clean_single_line(value.get("id"), 80)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", topic_id) or topic_id in used_ids:
            seed = f"gurumoji-transformer-topic:{index}:{label}"
            topic_id = f"topic_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]}"
        used_ids.add(topic_id)
        seed_ids: list[str] = []
        raw_seeds = value.get("seed_segment_ids")
        if not isinstance(raw_seeds, list):
            raw_seeds = re.split(r"[,、;\s]+", str(raw_seeds or ""))
        for raw_seed in raw_seeds[:50]:
            seed_id = clean_single_line(raw_seed, 160)
            if seed_id and seed_id not in seed_ids:
                seed_ids.append(seed_id)
        topics.append({
            "id": topic_id,
            "label": label,
            "cues": normalize_tags(value.get("cues"))[:20],
            "seed_segment_ids": seed_ids,
            "memo": clean_multiline(value.get("memo"), 2000),
        })
    return topics


def normalize_analysis_codebook(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    codebook: list[dict[str, str]] = []
    used_ids: set[str] = set()
    for index, value in enumerate(raw[:100]):
        if not isinstance(value, dict):
            continue
        label = clean_single_line(value.get("label"), 120)
        if not label:
            continue
        code_id = clean_single_line(value.get("id"), 80)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", code_id) or code_id in used_ids:
            seed = f"gurumoji-analysis-code:{index}:{label}"
            code_id = f"code_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]}"
        used_ids.add(code_id)
        color = clean_single_line(value.get("color"), 7).upper()
        if not re.fullmatch(r"#[0-9A-F]{6}", color):
            color = SPEAKER_THEME_COLORS[index % len(SPEAKER_THEME_COLORS)]
        codebook.append({
            "id": code_id,
            "label": label,
            "description": clean_multiline(value.get("description"), 4000),
            "include_example": clean_multiline(value.get("include_example"), 2000),
            "exclude_example": clean_multiline(value.get("exclude_example"), 2000),
            "category": clean_single_line(value.get("category"), 160),
            "theme": clean_single_line(value.get("theme"), 160),
            "color": color,
        })
    return codebook


def normalize_codebook_history(raw: Any) -> list[dict[str, Any]]:
    """Keep a compact, inspectable log of intentional codebook revisions."""
    if not isinstance(raw, list):
        return []
    history: list[dict[str, Any]] = []
    for value in raw[-20:]:
        if not isinstance(value, dict):
            continue
        try:
            version = int(value.get("version", 0))
        except (TypeError, ValueError):
            version = 0
        if version < 1:
            continue
        history.append({
            "version": version,
            "changed_at": clean_single_line(value.get("changed_at"), 80),
            "reason": clean_multiline(value.get("reason"), 2000),
            "summary": clean_multiline(value.get("summary"), 4000),
        })
    return history


def normalize_analysis_group_by(value: Any) -> str:
    group_by = clean_single_line(value, 140)
    if group_by in ANALYSIS_GROUP_FIELDS:
        return group_by
    prefix = "attribute:"
    if group_by.startswith(prefix):
        attribute_key = clean_single_line(group_by[len(prefix):], 120)
        if attribute_key:
            return f"{prefix}{attribute_key}"
    return "none"


def normalize_analysis_config(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    config = default_analysis_config()
    unit = clean_single_line(source.get("analysis_unit", config["analysis_unit"]), 30)
    group_by = normalize_analysis_group_by(source.get("group_by", config["group_by"]))
    morph_split_mode = clean_single_line(
        source.get("morph_split_mode", config["morph_split_mode"]), 1
    ).upper()
    statistics_group_by = clean_single_line(
        source.get("statistics_group_by", config["statistics_group_by"]), 20
    )
    crosstab_match_mode = clean_single_line(source.get("crosstab_match_mode"), 30)
    status = clean_single_line(
        source.get("interpretation_status", config["interpretation_status"]), 30
    )
    analysis_method = clean_single_line(
        source.get("analysis_method", config["analysis_method"]), 40
    )
    try:
        codebook_version = int(source.get("codebook_version", 0))
    except (TypeError, ValueError):
        codebook_version = 0
    config.update({
        "research_question": clean_multiline(source.get("research_question"), 10000),
        "analysis_method": analysis_method if analysis_method in ANALYSIS_METHODS else "auto",
        "method_rationale": clean_multiline(source.get("method_rationale"), 4000),
        "analysis_unit": unit if unit in ANALYSIS_UNITS else "turn",
        "exclude_moderator": analysis_bool(source.get("exclude_moderator"), True),
        "excluded_speakers": [
            clean_single_line(value, 80)
            for value in (source.get("excluded_speakers") or [])[:200]
            if clean_single_line(value, 80)
        ] if isinstance(source.get("excluded_speakers"), list) else [],
        "group_by": group_by,
        "long_gap_seconds": analysis_number(source.get("long_gap_seconds"), 3.0, 0.2, 120.0),
        "overlap_seconds": analysis_number(source.get("overlap_seconds"), 0.2, 0.0, 30.0),
        "low_participation_percent": analysis_number(
            source.get("low_participation_percent"), 10.0, 0.0, 50.0
        ),
        "time_bin_seconds": int(analysis_number(source.get("time_bin_seconds"), 300, 30, 3600)),
        "stop_words": normalize_tags(source.get("stop_words"))[:200],
        "morph_split_mode": (
            morph_split_mode if morph_split_mode in {"A", "B", "C"} else "C"
        ),
        "cooccurrence_min_count": int(analysis_number(
            source.get("cooccurrence_min_count"), 2, 1, 1000
        )),
        "cooccurrence_top_terms": int(analysis_number(
            source.get("cooccurrence_top_terms"), 60, 10, 200
        )),
        "statistics_group_by": (
            statistics_group_by
            if statistics_group_by in {"speaker", "role"}
            else "speaker"
        ),
        "crosstab_terms": normalize_tags(source.get("crosstab_terms"))[:30],
        "crosstab_match_mode": crosstab_match_mode
        if crosstab_match_mode in {"normalized", "surface", "literal"} else "normalized",
        "codebook": normalize_analysis_codebook(source.get("codebook")),
        "transformer_topics": normalize_transformer_topics(source.get("transformer_topics")),
        "codebook_version": max(0, min(codebook_version, 100000)),
        "codebook_change_reason": clean_multiline(source.get("codebook_change_reason"), 2000),
        "codebook_history": normalize_codebook_history(source.get("codebook_history")),
        "analyst_memo": clean_multiline(source.get("analyst_memo"), 30000),
        "interpretation_status": (
            status if status in ANALYSIS_INTERPRETATION_STATUSES else "draft"
        ),
    })
    return config


def normalize_analysis_annotations(
    raw: Any,
    segments: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    source = raw if isinstance(raw, dict) else {}
    segment_ids = {str(item.get("id") or "") for item in segments}
    code_ids = {str(item["id"]) for item in config.get("codebook", [])}
    annotations: dict[str, dict[str, Any]] = {}
    for segment_id, value in list(source.items())[:100000]:
        segment_id = str(segment_id)
        if segment_id not in segment_ids or not isinstance(value, dict):
            continue
        codes = []
        raw_codes = value.get("codes") if isinstance(value.get("codes"), list) else []
        for code_id in raw_codes[:100]:
            code_id = str(code_id)
            if code_id in code_ids and code_id not in codes:
                codes.append(code_id)
        tags = []
        raw_tags = (
            value.get("interaction_tags")
            if isinstance(value.get("interaction_tags"), list)
            else []
        )
        for tag in raw_tags[:50]:
            tag = str(tag)
            if tag in ANALYSIS_INTERACTION_TAGS and tag not in tags:
                tags.append(tag)
        elicitation = clean_single_line(value.get("elicitation"), 40)
        if elicitation not in ANALYSIS_ELICITATION_TYPES:
            elicitation = "unknown"
        links: list[dict[str, str]] = []
        raw_links = (
            value.get("interaction_links")
            if isinstance(value.get("interaction_links"), list)
            else []
        )
        seen_links: set[tuple[str, str, str]] = set()
        for raw_link in raw_links[:50]:
            if not isinstance(raw_link, dict):
                continue
            target_segment_id = clean_single_line(raw_link.get("target_segment_id"), 160)
            relation = clean_single_line(raw_link.get("relation"), 40)
            if (
                not target_segment_id
                or target_segment_id == segment_id
                or relation not in ANALYSIS_INTERACTION_RELATIONS
            ):
                continue
            evidence_memo = clean_multiline(raw_link.get("evidence_memo"), 2000)
            key = (target_segment_id, relation, evidence_memo)
            if key in seen_links:
                continue
            seen_links.add(key)
            links.append({
                "target_segment_id": target_segment_id,
                "relation": relation,
                "evidence_memo": evidence_memo,
            })
        annotation = {
            "codes": codes,
            "interaction_tags": tags,
            "memo": clean_multiline(value.get("memo"), 5000),
            "important": analysis_bool(value.get("important"), False),
            "excluded": analysis_bool(value.get("excluded"), False),
        }
        dialogue_act = clean_single_line(value.get("dialogue_act"), 40)
        if dialogue_act in DIALOGUE_ACTS:
            annotation["dialogue_act"] = dialogue_act
        classification_status = clean_single_line(
            value.get("classification_status"), 30
        )
        if classification_status not in {"unreviewed", "draft", "reviewed"}:
            classification_status = "unreviewed"
        if classification_status != "unreviewed":
            annotation["classification_status"] = classification_status
        classification_note = clean_multiline(value.get("classification_note"), 5000)
        if classification_note:
            annotation["classification_note"] = classification_note
        for field in ("importance_score", "review_score", "sensitivity_score"):
            score = analysis_optional_score(value.get(field))
            if score is not None:
                annotation[field] = score
        if elicitation != "unknown":
            annotation["elicitation"] = elicitation
        if links:
            annotation["interaction_links"] = links
        if any((
            codes, tags, elicitation != "unknown", links, annotation["memo"],
            annotation["important"], annotation["excluded"],
            annotation.get("dialogue_act"),
            annotation.get("importance_score") is not None,
            annotation.get("review_score") is not None,
            annotation.get("sensitivity_score") is not None,
            annotation.get("classification_status") != "unreviewed",
            annotation.get("classification_note"),
        )):
            annotations[segment_id] = annotation
    return annotations


def row_analysis_config(row: sqlite3.Row) -> dict[str, Any]:
    return normalize_analysis_config(json_load(row["analysis_config_json"], {}))


def row_analysis_annotations(
    row: sqlite3.Row,
    segments: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    annotations, _ = row_analysis_annotation_state(row, segments, config)
    return annotations


def row_analysis_annotation_state(
    row: sqlite3.Row,
    segments: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    raw_value = json_load(row["analysis_annotations_json"], {})
    raw = raw_value if isinstance(raw_value, dict) else {}
    annotations = normalize_analysis_annotations(raw, segments, config)
    segment_ids = {str(item.get("id") or "") for item in segments}
    orphaned: dict[str, dict[str, Any]] = {}
    for index, (segment_id, value) in enumerate(raw.items()):
        if index >= 100000:
            break
        segment_id = str(segment_id)
        if segment_id in segment_ids or not isinstance(value, dict):
            continue
        normalized = normalize_analysis_annotations(
            {segment_id: value}, [{"id": segment_id}], config
        )
        if segment_id in normalized:
            orphaned[segment_id] = normalized[segment_id]
    return annotations, orphaned


def analysis_gini(values: list[float]) -> float:
    clean = sorted(max(0.0, float(value)) for value in values)
    total = sum(clean)
    if len(clean) <= 1 or total <= 0:
        return 0.0
    count = len(clean)
    weighted = sum((2 * index - count - 1) * value for index, value in enumerate(clean, 1))
    return weighted / (count * total)


def analysis_evenness(values: list[float]) -> float:
    clean = [max(0.0, float(value)) for value in values]
    total = sum(clean)
    if not clean or total <= 0:
        return 0.0
    if len(clean) == 1:
        return 1.0
    entropy = -sum(
        (value / total) * math.log(value / total)
        for value in clean if value > 0
    )
    return entropy / math.log(len(clean))


def analysis_segment_bounds(segment: dict[str, Any]) -> tuple[float, float, bool]:
    try:
        raw_start = float(segment.get("start", 0) or 0)
        raw_end = float(segment.get("end", raw_start) or raw_start)
    except (TypeError, ValueError, OverflowError):
        return 0.0, 0.0, False
    if not math.isfinite(raw_start) or not math.isfinite(raw_end):
        return 0.0, 0.0, False
    valid = (
        preparation.valid_time(segment)
        and raw_start >= 0
        and raw_end >= raw_start
        and raw_start <= ANALYSIS_MAX_TIMELINE_SECONDS
        and raw_end <= ANALYSIS_MAX_TIMELINE_SECONDS
    )
    start = min(max(raw_start, 0.0), float(ANALYSIS_MAX_TIMELINE_SECONDS))
    end = min(max(raw_end, start), float(ANALYSIS_MAX_TIMELINE_SECONDS))
    return start, end, valid


def analysis_emotion_entries(segment: dict[str, Any]) -> list[dict[str, str]]:
    raw = segment.get("emotions")
    if not isinstance(raw, dict):
        return []
    entries: list[dict[str, str]] = []
    for model_key, value in raw.items():
        if not isinstance(value, dict):
            continue
        raw_label = clean_single_line(value.get("label"), 80)
        explicit_label_ja = clean_single_line(value.get("label_ja"), 80)
        if not raw_label and not explicit_label_ja:
            continue
        label_ja = clean_single_line(
            explicit_label_ja or emotion_label_ja(raw_label), 80
        )
        if not raw_label and not label_ja:
            continue
        entries.append({
            "model": clean_single_line(model_key, 80) or "unknown",
            "model_name": clean_single_line(value.get("model_name"), 120),
            "label": raw_label,
            "label_ja": label_ja or raw_label,
        })
    return entries


FOCUS_GROUP_METHOD_REFERENCES = [
    {
        "method_id": "qualitative_content",
        "citation": "Hsieh & Shannon (2005), Three Approaches to Qualitative Content Analysis",
        "url": "https://doi.org/10.1177/1049732305276687",
    },
    {
        "method_id": "thematic",
        "citation": "Braun & Clarke (2006), Using thematic analysis in psychology",
        "url": "https://doi.org/10.1191/1478088706qp063oa",
    },
    {
        "method_id": "framework",
        "citation": "Gale et al. (2013), Using the framework method for qualitative data analysis",
        "url": "https://doi.org/10.1186/1471-2288-13-117",
    },
    {
        "method_id": "interaction",
        "citation": "Kitzinger (1994), The methodology of focus groups: the importance of interaction",
        "url": "https://doi.org/10.1111/1467-9566.ep11347023",
    },
]


def focus_group_data_inventory(
    row: sqlite3.Row,
    session_profile: dict[str, str],
    config: dict[str, Any],
    timeline: list[dict[str, Any]],
    speaker_metrics: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    original_snapshot_status: str,
) -> list[dict[str, Any]]:
    """Describe only available evidence; blank fields remain explicitly unknown."""
    valid_times = sum(1 for item in timeline if item.get("valid_time"))
    roles = {str(item.get("role") or "") for item in speaker_metrics}
    attributes_present = any(
        profile.get("organization") or profile.get("department")
        or profile.get("job_title") or profile.get("attributes")
        for profile in profiles.values()
    )
    media_value = str(row["media_path"] or "")
    suffix = Path(media_value).suffix.lower()
    try:
        media_exists = bool(media_value and Path(media_value).is_file())
    except OSError:
        media_exists = False
    if suffix in VIDEO_EXTENSIONS:
        video_status = "利用可" if media_exists else "登録あり・所在未確認"
        audio_status = "動画音声として利用可" if media_exists else "登録あり・所在未確認"
    elif suffix in ALLOWED_EXTENSIONS:
        video_status = "不明"
        audio_status = "利用可" if media_exists else "登録あり・所在未確認"
    else:
        video_status = "不明"
        audio_status = "不明"
    return [
        {
            "item": "研究目的",
            "status": "確認済み" if session_profile.get("objective") else "不明",
            "value": session_profile.get("objective") or "不明",
        },
        {
            "item": "研究質問",
            "status": "確認済み" if config.get("research_question") else "不明",
            "value": config.get("research_question") or "不明",
        },
        {
            "item": "インタビューのテーマ・質問項目",
            "status": "確認済み" if session_profile.get("moderator_guide") else "不明",
            "value": session_profile.get("moderator_guide") or "不明",
        },
        {
            "item": "実際のグループID",
            "status": "確認済み" if session_profile.get("interview_group_id") else "不明",
            "value": session_profile.get("interview_group_id") or "不明",
        },
        {
            "item": "グループ数",
            "status": "不明",
            "value": "このレコードだけからは不明（比較対象として扱う回の指定が必要）",
        },
        {
            "item": "このレコードの参加者数",
            "status": "確認済み" if timeline else "不明",
            "value": str(sum(1 for item in speaker_metrics if item.get("role") not in ANALYSIS_NON_PARTICIPANT_ROLES)) if timeline else "不明",
        },
        {
            "item": "参加者属性・比較属性",
            "status": "確認済み" if attributes_present else "不明",
            "value": "話者プロファイルに登録あり" if attributes_present else "不明",
        },
        {
            "item": "発言者・発言順",
            "status": "確認済み" if timeline and all(item.get("id") and item.get("speaker") for item in timeline) else "不明",
            "value": f"{len(timeline)}発話。発言順は保存配列に分析用付番（原資料との確認は別）" if timeline else "不明",
        },
        {
            "item": "時刻または元ファイル内の位置",
            "status": "確認済み" if timeline and valid_times == len(timeline) else ("一部" if valid_times else "不明"),
            "value": f"{valid_times}/{len(timeline)}発話に有効な時刻" if timeline else "不明",
        },
        {
            "item": "司会者の発言・役割",
            "status": "確認済み" if roles & ANALYSIS_FACILITATOR_ROLES else "不明",
            "value": "役割登録あり" if roles & ANALYSIS_FACILITATOR_ROLES else "不明",
        },
        {
            "item": "逐語録",
            "status": "利用可" if timeline else "不明",
            "value": f"{len(timeline)}発話（編集用本文と原文スナップショットは分離）" if timeline else "不明",
        },
        {"item": "原文スナップショットの来歴", "status": original_snapshot_status, "value": original_snapshot_status},
        {"item": "音声", "status": audio_status, "value": audio_status},
        {"item": "動画", "status": video_status, "value": video_status},
    ]


def build_focus_group_analysis_plan(
    row: sqlite3.Row,
    session_profile: dict[str, str],
    config: dict[str, Any],
    timeline: list[dict[str, Any]],
    speaker_metrics: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    original_snapshot_status: str,
) -> dict[str, Any]:
    inventory = focus_group_data_inventory(
        row, session_profile, config, timeline, speaker_metrics, profiles,
        original_snapshot_status,
    )
    has_transcript = bool(timeline)
    has_order = has_transcript and all(item.get("id") and item.get("speaker") for item in timeline)
    has_comparison_axis = config.get("group_by") != "none" or bool(session_profile.get("comparison_group"))
    selected = str(config.get("analysis_method") or "auto")
    primary = "qualitative_content" if selected == "auto" else selected
    provisional = not bool(config.get("research_question") or session_profile.get("objective"))
    method_rows: list[dict[str, Any]] = []

    def add(method_id: str, role: str, sufficient: bool, reason: str, limitation: str) -> None:
        method_rows.append({
            "method_id": method_id,
            "method": ANALYSIS_METHODS[method_id],
            "role": role,
            "data_sufficiency": "要確認（データあり。手法の要件充足は未判定）" if sufficient else "不足",
            "reason": reason,
            "limitation": limitation,
        })

    primary_reason = {
        "qualitative_content": "意見・課題・ニーズを文脈に沿ってコードとカテゴリーへ整理するため。",
        "thematic": "経験や考え方に共通する意味のパターンを検討するため。",
        "framework": "ケース・話者・属性を行列で比較するため。",
        "scat": "少量のデータで段階的な解釈過程を明示するため。",
        "mgta": "認識や関係性が変化する過程を説明するため。",
        "kj": "多様な意見の構造をカード化して検討するため。",
        "quantitative_text": "語彙的傾向を補助的に確認するため。",
        "interaction": "その場の応答を通じた意見形成を検討するため。",
    }[primary]
    primary_limitations = {
        "qualitative_content": "コード・カテゴリーの確定は研究者が原文と文脈を読んで行う。",
        "thematic": "自動クラスタはテーマ分析の代替ではない。",
        "framework": "複数の比較可能なグループ／属性が未設定なら行列比較はできない。",
        "scat": "4段階のコーディング、ストーリーライン、理論記述は研究者が実施する。",
        "mgta": "分析テーマ・分析焦点者・継続比較を設定しなければ理論生成とは呼べない。",
        "kj": "自動類似クラスタリングはKJ法ではなく、カード化と関係づけが必要。",
        "quantitative_text": "頻度・共起から意味や重要性を断定しない。",
        "interaction": "正確な応答関係の確認には話者・順序のある逐語録が必要。",
    }[primary]
    add(primary, "主", has_transcript, primary_reason, primary_limitations)
    if primary != "interaction":
        add(
            "interaction", "補助", has_order,
            "内容分析とは別に、同意・反論・補足・意見変化を根拠発話の連鎖で検討するため。",
            "時刻があっても、声色・沈黙の長さ・重なり・表情は音声／動画と適切な転記なしには解釈しない。",
        )
    if has_comparison_axis and primary != "framework":
        add(
            "framework", "補助", has_transcript,
            "話者または属性による共通点・相違点を、原発話へ戻れる行列で確認するため。",
            "比較対象のグループ数と同一性は研究者が明示する。",
        )
    if primary != "quantitative_text":
        add(
            "quantitative_text", "補助", has_transcript,
            "語彙・共起の偏りを探索し、原発話を読み返す入口にするため。",
            "頻度は支持人数、代表性、重要性の指標ではない。",
        )
    not_selected = [
        {"method_id": method_id, "method": label,
         "reason": "主手法として未選択。研究目的・分析単位・必要な固有手順を研究者が確認してから採用する。"}
        for method_id, label in ANALYSIS_METHODS.items()
        if method_id not in {"auto", *(item["method_id"] for item in method_rows)}
    ]
    return {
        "status": "暫定" if provisional or selected == "auto" else "研究者による選択案",
        "provisional_assumption": (
            "研究目的または研究質問が未入力のため、内容を整理する質的内容分析と相互作用分析を暫定案とする。"
            if provisional else "手法は既定案または研究者の選択。研究目的への適合は自動判定していない。"
        ),
        "researcher_method_rationale": config.get("method_rationale") or "未入力",
        "analysis_unit": "保存逐語録の発話。保存配列の順に分析用付番。発話の区切り・順序が確認済みかは準備記録で区別する。",
        "data_inventory": inventory,
        "methods": method_rows,
        "not_selected_methods": not_selected,
        "integration": "内容分析では何が語られたかをコード・カテゴリー・テーマで扱い、相互作用分析では発話間リンクと連続文脈を別表で扱う。両者を混同せず、同じ根拠発話IDから照合する。",
        "procedure": [
            "原文スナップショットと編集用本文の来歴を確認し、研究目的・質問・比較設計を確定する。",
            "発話単位でコードを付与し、コード定義・適用条件・除外条件・変更理由をコードブックに残す。",
            "コードをカテゴリー・テーマへ統合し、少数意見、反例、矛盾を原文とともに検討する。",
            "同意・反論・補足・変化は、発話間リンクとその連続した文脈を根拠に別途検討する。",
            "比較を行う場合は、同じ質問設計のグループを明示し、行列から原発話へ戻って解釈する。",
        ],
        "references": FOCUS_GROUP_METHOD_REFERENCES,
    }




# Datasets the v1 export contract listed before ANALYSIS_CSV_FIELDS existed; the
# order is kept so the export links serialize as they always have.
_LEGACY_EXPORT_DATASETS = (
    "speakers", "transitions", "gaps", "overlaps", "keywords", "emotions",
    "timeline", "codes", "groups", "coded_segments", "interactions",
    "case_matrix", "context", "summary", "observations", "important_quotes",
)


def _empty_annotation() -> dict[str, Any]:
    return {
        "codes": [], "interaction_tags": [], "elicitation": "unknown",
        "interaction_links": [], "memo": "",
        "important": False, "excluded": False,
        "dialogue_act": "", "importance_score": None,
        "review_score": None, "sensitivity_score": None,
        "classification_status": "unreviewed", "classification_note": "",
    }


def _saved_json(row: sqlite3.Row, column: str) -> Any:
    return json_load(row[column], {}) if column in row.keys() else {}


def _linked_registry_profiles(
    profiles: dict[str, dict[str, Any]],
    list_speaker_registry: Callable[..., list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    linked_ids = {
        str(profile.get("global_speaker_id") or "")
        for profile in profiles.values()
        if str(profile.get("global_speaker_id") or "")
    }
    if not linked_ids:
        return {}
    return {
        record["id"]: record
        for record in list_speaker_registry(include_inactive=True)
        if record["id"] in linked_ids
    }


def _add_recorded_role_measurements(timeline: list[dict[str, Any]], profiles: dict[str, dict[str, Any]],
                                    registry_profiles: dict[str, dict[str, Any]]) -> None:
    """Add measurement provenance without changing participation-analysis defaults.

    Prepared roles override explicit/copied session roles. A registry-only
    profile may use its recorded default; ambiguous legacy participant values
    never silently become an observed session override or a registry value.
    """
    for segment in timeline:
        profile = profiles.get(segment["speaker"], {})
        source = profile.get("session_role_source", "legacy_unknown")
        value = None
        if segment["role_source"] == "preparation":
            value, source = segment["role"], "preparation"
        elif source in ("explicit", "registry"):
            value = profile.get("session_role")
        elif source == "default":
            registry = registry_profiles.get(str(profile.get("global_speaker_id") or ""), {})
            if registry.get("default_role"):
                value, source = registry["default_role"], "registry"
        segment["recorded_role"] = value
        segment["recorded_role_source"] = source


def _tally_speaker_turn(
    buckets: dict[str, dict[str, Any]],
    emotion_rows: dict[tuple[str, str, str], dict[str, Any]],
    item: dict[str, Any],
    start: float,
    end: float,
    duration: float,
) -> None:
    # Unrounded bounds are summed so per-speaker totals do not drift.
    speaker = item["speaker"]
    bucket = buckets.setdefault(speaker, {
        "speaker": speaker,
        "speaker_name": item["speaker_name"],
        "role": item["role"],
        "observed_roles": set(),
        "color": item["color"],
        "turn_count": 0,
        "timed_turn_count": 0,
        "timed_characters": 0,
        "speaking_seconds": 0.0,
        "characters": 0,
        "question_candidates": 0,
        "first_start": start,
        "last_end": end,
        "emotion_counts": Counter(),
        "code_counts": Counter(),
    })
    bucket["turn_count"] += 1
    bucket["observed_roles"].add(item["role"])
    bucket["role"] = next(iter(bucket["observed_roles"])) if len(bucket["observed_roles"]) == 1 else "mixed"
    if item["valid_time"]:
        if not bucket["timed_turn_count"]:
            bucket["first_start"], bucket["last_end"] = start, end
        bucket["timed_turn_count"] += 1
        bucket["speaking_seconds"] += duration
        if duration > 0:
            bucket["timed_characters"] += item["characters"]
        bucket["first_start"] = min(float(bucket["first_start"]), start)
        bucket["last_end"] = max(float(bucket["last_end"]), end)
    bucket["characters"] += item["characters"]
    if item["question_candidate"]:
        bucket["question_candidates"] += 1
    for emotion in item["emotion_details"]:
        bucket["emotion_counts"][emotion["label_ja"]] += 1
        key = (speaker, emotion["model"], emotion["label_ja"])
        emotion_row = emotion_rows.setdefault(key, {
            "speaker": speaker,
            "speaker_name": item["speaker_name"],
            "model": emotion["model"],
            "model_name": emotion["model_name"],
            "label": emotion["label"],
            "emotion": emotion["label_ja"],
            "count": 0,
            "seconds": 0.0,
            "timed_turn_count": 0,
            "missing_time_turn_count": 0,
        })
        emotion_row["count"] += 1
        if item["valid_time"]:
            emotion_row["timed_turn_count"] += 1
            emotion_row["seconds"] += duration
        else:
            emotion_row["missing_time_turn_count"] += 1
    for code_id in item["annotation"].get("codes", []):
        bucket["code_counts"][code_id] += 1


def _analysis_timeline(
    segments: list[dict[str, Any]],
    *,
    prepared: dict[str, Any],
    original_segments: dict[str, dict[str, Any]],
    original_segments_status: str,
    annotations: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    speaker_names: dict[str, Any],
    session_profile: dict[str, str],
    excluded_speakers: set[str],
    registered_roles: set[str] | None = None,
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[tuple[str, str, str], dict[str, Any]],
    dict[str, int],
]:
    """Build one row per saved turn and tally the included turns by speaker.

    Returns the timeline, the per-speaker buckets, the per-speaker emotion rows,
    and data-quality counts.  Missing times are never invented to establish
    conversational order.
    """
    prepared_by_id = {value["segment_id"]: value for value in prepared["rows"]}
    timeline: list[dict[str, Any]] = []
    speaker_buckets: dict[str, dict[str, Any]] = {}
    emotion_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    quality = {"emotion_covered": 0, "empty_text": 0, "zero_duration": 0, "invalid_time": 0}

    for source_index, segment in enumerate(segments, 1):
        segment_id = str(segment.get("id") or "")
        speaker = str(segment.get("speaker") or "UNKNOWN")
        start, end, valid_time = analysis_segment_bounds(segment)
        if not valid_time:
            quality["invalid_time"] += 1
        # Keep the numeric timeline contract, but never count a placeholder or
        # clamped invalid interval as measured speech. Consumers use valid_time
        # to distinguish this placeholder from an observed zero-length turn.
        duration = max(0.0, end - start) if valid_time else 0.0
        text = str(segment.get("text") or "")
        annotation = annotations[segment_id] if segment_id in annotations else _empty_annotation()
        profile = profiles.get(speaker, {})
        display_name = str(
            profile.get("display_name")
            or speaker_names.get(speaker)
            or default_speaker_name(speaker)
        )
        role = str(profile.get("session_role") or "participant")
        role_source = "registered" if speaker in (registered_roles or set()) else "default"
        if prepared_by_id.get(segment_id, {}).get("role", "unknown") != "unknown":
            role = prepared_by_id[segment_id]["role"]
            role_source = "preparation"
        emotion_details = analysis_emotion_entries(segment)
        if emotion_details:
            quality["emotion_covered"] += 1
        if not text:
            quality["empty_text"] += 1
        if valid_time and duration <= 0:
            quality["zero_duration"] += 1
        item = {
            "id": segment_id,
            # Analysis-only numbering of the saved transcript array, not proof
            # that source order or ASR turn boundaries have been verified.
            "utterance_order": source_index,
            "group_id": session_profile.get("interview_group_id") or "不明",
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(duration, 3),
            "speaker": speaker,
            "speaker_name": display_name,
            "role": role,
            "role_source": role_source,
            "role_confirmed": role_source == "preparation" and bool(prepared_by_id[segment_id].get("speaker_verified")),
            "color": str(profile.get("theme_color") or "#1C6B50"),
            "text": text,
            "original_text": str(
                original_segments.get(segment_id, {}).get("text") or ""
            ),
            "original_text_available": segment_id in original_segments,
            "original_text_status": original_segments_status,
            "input_version": prepared["input_version"],
            "source_hash": prepared["source_hash"],
            "analysis_needs_review": prepared["analysis_needs_review"],
            "characters": len(re.sub(r"\s+", "", text)),
            "emotions": list(dict.fromkeys(entry["label_ja"] for entry in emotion_details)),
            "emotion_details": emotion_details,
            "question_candidate": bool(
                re.search(r"[?？]|(?:です|ます|でしょう)か[。．]?$", text)
            ),
            "valid_time": valid_time,
            "annotation": annotation,
            "excluded": bool(annotation.get("excluded")) or speaker in excluded_speakers,
        }
        timeline.append(item)
        if not item["excluded"]:
            _tally_speaker_turn(speaker_buckets, emotion_rows, item, start, end, duration)

    # Adjacency is based on all ordered turns, including excluded ones, so a
    # reviewer can return to the original conversational context.
    for index, item in enumerate(timeline):
        item["previous_segment_id"] = timeline[index - 1]["id"] if index else ""
        item["next_segment_id"] = (
            timeline[index + 1]["id"] if index + 1 < len(timeline) else ""
        )
    return timeline, speaker_buckets, emotion_rows, quality


def _speaking_total(speaker_buckets: dict[str, dict[str, Any]], labels: list[str]) -> float:
    return sum(float(speaker_buckets[label]["speaking_seconds"]) for label in labels)


def _timing_coverage(rows) -> dict[str, int]:
    """Count observed and missing timing without adding unobserved speakers."""
    turns = sum(int(row["turn_count"]) for row in rows)
    timed = sum(int(row["timed_turn_count"]) for row in rows)
    return {"turn_count": turns, "timed_turn_count": timed,
            "missing_time_turn_count": turns - timed}


def _observed_seconds(seconds: float, coverage: dict[str, int]) -> float | None:
    # Empty input has a genuine empty sum; recorded but wholly untimed input does not.
    return round(seconds, 3) if coverage["timed_turn_count"] or not coverage["turn_count"] else None


def _speaker_profile_fields(
    profile: dict[str, Any], registry_profile: dict[str, Any]
) -> dict[str, Any]:
    """Session-level attributes win; the linked registry fills the blanks."""
    return {
        "organization": str(
            profile.get("organization") or registry_profile.get("organization") or ""
        ),
        "department": str(
            profile.get("department") or registry_profile.get("department") or ""
        ),
        "job_title": str(
            profile.get("job_title") or registry_profile.get("job_title") or ""
        ),
        "conditions": str(profile.get("conditions") or ""),
        "tags": list(registry_profile.get("tags") or []),
        "attributes": dict(registry_profile.get("attributes") or {}),
    }


def _speaker_metrics(
    speaker_buckets: dict[str, dict[str, Any]],
    *,
    profiles: dict[str, dict[str, Any]],
    registry_profiles: dict[str, dict[str, Any]],
    balance_labels: list[str],
    balance_population: list[str],
    balance_role_valid: bool,
    total_speaking: float,
) -> list[dict[str, Any]]:
    balance_total = _speaking_total(speaker_buckets, balance_labels)
    all_coverage = _timing_coverage(list(speaker_buckets.values()))
    balance_coverage = _timing_coverage([speaker_buckets[label] for label in balance_population])
    all_ratio_valid = total_speaking > 0 and all_coverage["missing_time_turn_count"] == 0
    balance_ratio_valid = balance_role_valid and balance_total > 0 and balance_coverage["missing_time_turn_count"] == 0
    metrics: list[dict[str, Any]] = []
    for label, bucket in sorted(
        speaker_buckets.items(),
        key=lambda pair: (-float(pair[1]["speaking_seconds"]), pair[1]["speaker_name"]),
    ):
        seconds = float(bucket["speaking_seconds"])
        turns = int(bucket["turn_count"])
        timed_turns = int(bucket["timed_turn_count"])
        characters = int(bucket["characters"])
        participant_share = (
            (seconds / balance_total if label in balance_labels else 0.0)
            if balance_ratio_valid and timed_turns else None
        )
        profile = profiles.get(label, {})
        registry_profile = registry_profiles.get(
            str(profile.get("global_speaker_id") or ""), {}
        )
        metrics.append({
            "speaker": label,
            "speaker_name": bucket["speaker_name"],
            "role": bucket["role"],
            "role_status": "mixed" if len(bucket["observed_roles"]) > 1 else "single",
            "observed_roles": sorted(bucket["observed_roles"]),
            "color": bucket["color"],
            "turn_count": turns,
            "timed_turn_count": timed_turns,
            "missing_time_turn_count": turns - timed_turns,
            "timed_characters": int(bucket["timed_characters"]),
            "speaking_seconds": round(seconds, 3) if timed_turns else None,
            "speaking_percent": round(100 * seconds / total_speaking, 2) if all_ratio_valid else None,
            "participant_percent": round(100 * participant_share, 2) if participant_share is not None else None,
            "average_turn_seconds": round(seconds / timed_turns, 3) if timed_turns else None,
            "characters": characters,
            "characters_per_minute": round(60 * bucket["timed_characters"] / seconds, 2) if seconds else None,
            "question_candidates": int(bucket["question_candidates"]),
            "first_start": round(float(bucket["first_start"]), 3) if timed_turns else None,
            "last_end": round(float(bucket["last_end"]), 3) if timed_turns else None,
            "emotion_counts": dict(bucket["emotion_counts"]),
            "code_counts": dict(bucket["code_counts"]),
            "included_in_balance": label in balance_labels,
            "profile": _speaker_profile_fields(profile, registry_profile),
        })
    return metrics


def _dominant_speaker(speaker_metrics: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(
        (item for item in speaker_metrics if item["included_in_balance"] and item["participant_percent"] is not None),
        key=lambda item: item["participant_percent"],
        default=None,
    )


def _participation_balance(
    speaker_buckets: dict[str, dict[str, Any]],
    speaker_metrics: list[dict[str, Any]],
    *,
    participant_labels: list[str],
    balance_labels: list[str],
    balance_population: list[str],
    mixed_role_speaker_count: int,
    exclude_moderator: bool,
    prepared: dict[str, Any] | None = None,
) -> dict[str, Any]:
    balance_seconds = [
        float(speaker_buckets[label]["speaking_seconds"]) for label in balance_labels
    ]
    balance_total = _speaking_total(speaker_buckets, balance_labels)
    balance_shares = [
        value / balance_total for value in balance_seconds if balance_total > 0
    ]
    dominant = _dominant_speaker(speaker_metrics)
    participant_coverage = _timing_coverage([speaker_buckets[label] for label in participant_labels])
    balance_coverage = _timing_coverage([speaker_buckets[label] for label in balance_population])
    role_valid = not exclude_moderator or mixed_role_speaker_count == 0
    complete = role_valid and balance_total > 0 and balance_coverage["missing_time_turn_count"] == 0
    return {
        "participant_count": (prepared or {}).get("participant_count"),
        "observed_participant_count": None if mixed_role_speaker_count else len(participant_labels),
        "mixed_role_speaker_count": mixed_role_speaker_count,
        "unobserved_participant_count": None,
        "participant_roster_available": False,
        "unknown_speaker_turn_count": int(speaker_buckets.get("UNKNOWN", {}).get("turn_count", 0)),
        "missing_time_turn_count": sum(int(row["turn_count"]) - int(row["timed_turn_count"]) for row in speaker_buckets.values()),
        "participant_speaking_seconds": _observed_seconds(
            _speaking_total(speaker_buckets, participant_labels), participant_coverage
        ) if not mixed_role_speaker_count else None,
        "participant_timed_turn_count": participant_coverage["timed_turn_count"],
        "participant_missing_time_turn_count": participant_coverage["missing_time_turn_count"],
        "balance_speaker_count": len(balance_labels),
        "balance_speaking_seconds": _observed_seconds(balance_total, balance_coverage) if role_valid else None,
        "balance_timed_turn_count": balance_coverage["timed_turn_count"],
        "balance_missing_time_turn_count": balance_coverage["missing_time_turn_count"],
        "max_participant_percent": dominant["participant_percent"] if dominant else None,
        "max_participant_name": dominant["speaker_name"] if dominant else "",
        "gini": round(analysis_gini(balance_seconds), 4) if complete else None,
        "normalized_evenness": round(analysis_evenness(balance_seconds), 4) if complete else None,
        "hhi": round(sum(value * value for value in balance_shares), 4) if complete else None,
        "denominator": "observed_participant_speakers" if exclude_moderator else "observed_speakers",
        "denominator_label": "有効な時刻がある観測発言者内（司会等を除く）" if exclude_moderator else "有効な時刻がある全観測話者内（UNKNOWNを除く・司会等を含む）",
        "denominator_note": "実参加人数とは別の集合です。確認済み名簿がないため未発言者を0秒として補完しません。UNKNOWNと時刻欠測だけの話者は分母人数から除きますが、対象話者に時刻欠測があれば割合・均等度を算出しません。時間は時刻あり発話の小計です。",
        "metric_status": "computed" if complete else "not_computable",
        "unavailable_reason": ("mixed_roles" if not role_valid else "missing_time" if balance_coverage["missing_time_turn_count"]
                               else "zero_total" if not balance_total else ""),
    }


def _speaker_transitions(
    valid_included: list[dict[str, Any]], overlap_threshold: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Count speaker changes between consecutive timed, included turns.

    Returns the transition rows and the turn-taking counts the moderator summary
    and overview report.
    """
    transitions: dict[tuple[str, str], dict[str, Any]] = {}
    turn_taking: dict[str, Any] = {
        "consecutive_gaps": [],
        "moderator_response_gaps": [],
        "moderator_to_participant": 0,
        "participant_to_participant": 0,
        "cross_speaker_transitions": 0,
    }
    for previous, current in zip(valid_included, valid_included[1:]):
        if previous["speaker"] == current["speaker"]:
            continue
        gap = float(current["start"]) - float(previous["end"])
        turn_taking["cross_speaker_transitions"] += 1
        turn_taking["consecutive_gaps"].append(gap)
        key = (str(previous["speaker"]), str(current["speaker"]))
        transition = transitions.setdefault(key, {
            "from_speaker": previous["speaker"],
            "from_name": previous["speaker_name"],
            "from_role": previous["role"],
            "to_speaker": current["speaker"],
            "to_name": current["speaker_name"],
            "to_role": current["role"],
            "count": 0,
            "gap_total": 0.0,
            "overlap_candidates": 0,
        })
        transition["count"] += 1
        transition["gap_total"] += gap
        overlap_end = min(float(previous["end"]), float(current["end"]))
        overlap_seconds = max(0.0, overlap_end - float(current["start"]))
        if overlap_seconds > 0 and overlap_seconds >= overlap_threshold:
            transition["overlap_candidates"] += 1
        current_participant = current["role"] not in ANALYSIS_NON_PARTICIPANT_ROLES
        if previous["role"] in ANALYSIS_FACILITATOR_ROLES and current_participant:
            turn_taking["moderator_to_participant"] += 1
            if previous["question_candidate"]:
                turn_taking["moderator_response_gaps"].append(gap)
        if previous["role"] not in ANALYSIS_NON_PARTICIPANT_ROLES and current_participant:
            turn_taking["participant_to_participant"] += 1

    rows = []
    for value in transitions.values():
        count = int(value["count"])
        rows.append({
            **{key: item for key, item in value.items() if key != "gap_total"},
            "average_gap_seconds": round(float(value["gap_total"]) / count, 3) if count else 0.0,
        })
    rows.sort(key=lambda item: (-item["count"], item["from_name"], item["to_name"]))
    return rows, turn_taking


def _timing_view(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Observed timing, including true zero-duration events, in a sorted copy."""
    return sorted(
        (item for item in timeline if item.get("valid_time", preparation.valid_time(item))
         and preparation.valid_time(item)),
        key=lambda item: (float(item["start"]), float(item["end"]), str(item.get("id") or "")),
    )


def _physical_time_view(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Positive-duration intervals only; preserve existing relation calculations."""
    return [item for item in _timing_view(timeline) if float(item["end"]) > float(item["start"])]


def _overlap_candidates(
    physical_timeline: list[dict[str, Any]], overlap_threshold: float
) -> tuple[list[dict[str, Any]], bool]:
    """Find time overlaps between different speakers; returns (rows, truncated)."""
    candidates: list[dict[str, Any]] = []
    truncated = False
    active_segments: list[dict[str, Any]] = []
    for current in _physical_time_view(physical_timeline):
        current_start = float(current["start"])
        active_segments = [
            item for item in active_segments if float(item["end"]) > current_start
        ]
        if len(active_segments) > 1000:
            active_segments = active_segments[-1000:]
            truncated = True
        for previous in active_segments:
            if previous["speaker"] == current["speaker"]:
                continue
            overlap_end = min(float(previous["end"]), float(current["end"]))
            overlap_start = max(float(previous["start"]), current_start)
            seconds = max(0.0, overlap_end - overlap_start)
            if seconds <= 0 or seconds < overlap_threshold:
                continue
            if len(candidates) >= 10000:
                truncated = True
                continue
            candidates.append({
                "start": round(overlap_start, 3),
                "end": round(overlap_end, 3),
                "seconds": round(seconds, 3),
                "from_segment_id": previous.get("id", ""),
                "to_segment_id": current.get("id", ""),
                "from_speaker": previous["speaker"],
                "from_name": previous["speaker_name"],
                "to_speaker": current["speaker"],
                "to_name": current["speaker_name"],
            })
        active_segments.append(current)
    return candidates, truncated


def _long_gaps(
    physical_timeline: list[dict[str, Any]], long_gap_threshold: float
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    coverage_end = 0.0
    previous_name = "開始"
    for segment in _physical_time_view(physical_timeline):
        start = float(segment["start"])
        if start > coverage_end:
            duration = start - coverage_end
            if duration >= long_gap_threshold:
                gaps.append({
                    "start": round(coverage_end, 3),
                    "end": round(start, 3),
                    "seconds": round(duration, 3),
                    "previous_name": previous_name,
                    "next_name": segment["speaker_name"],
                })
        if float(segment["end"]) >= coverage_end:
            coverage_end = float(segment["end"])
            previous_name = str(segment["speaker_name"])
    return gaps


def _time_bins(
    valid_included: list[dict[str, Any]],
    *,
    session_duration: float | None,
    requested_bin_seconds: int,
    speaker_buckets: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Spread speaking time over fixed bins; returns (bins, effective bin seconds).

    The bin width grows when the requested width would exceed
    ANALYSIS_MAX_TIME_BINS for this session.
    """
    bin_seconds = requested_bin_seconds
    if not valid_included:
        return [], bin_seconds
    if session_duration and math.ceil(session_duration / bin_seconds) > ANALYSIS_MAX_TIME_BINS:
        bin_seconds = max(
            requested_bin_seconds,
            int(math.ceil(session_duration / ANALYSIS_MAX_TIME_BINS)),
        )
    bin_count = max(1, int(math.ceil(session_duration / bin_seconds))) if session_duration else 1
    bins = [
        {
            "index": index,
            "start": index * bin_seconds,
            "end": min((index + 1) * bin_seconds, session_duration) if session_duration is not None else bin_seconds,
            "speaking_seconds": 0.0,
            "turn_count": 0,
            "speakers": Counter(),
        }
        for index in range(bin_count)
    ]
    for segment in valid_included:
        start = float(segment["start"])
        end = float(segment["end"])
        first_bin = min(int(start // bin_seconds), bin_count - 1)
        bins[first_bin]["turn_count"] += 1
        if end == start:
            bins[first_bin]["speakers"][segment["speaker"]] += 0.0
            continue
        last_bin = min(int(max(start, end - 0.000001) // bin_seconds), bin_count - 1)
        for index in range(first_bin, last_bin + 1):
            piece_start = max(start, index * bin_seconds)
            piece_end = min(end, (index + 1) * bin_seconds)
            seconds = max(0.0, piece_end - piece_start)
            bins[index]["speaking_seconds"] += seconds
            bins[index]["speakers"][segment["speaker"]] += seconds
    serialized = [{
        **{key: value for key, value in item.items() if key != "speakers"},
        "speaking_seconds": round(float(item["speaking_seconds"]), 3),
        "speakers": [
            {
                "speaker": key,
                "speaker_name": speaker_buckets.get(key, {}).get("speaker_name", key),
                "seconds": round(value, 3),
            }
            for key, value in item["speakers"].items()
        ],
    } for item in bins]
    return serialized, bin_seconds


def _keyword_rows(
    included: list[dict[str, Any]],
    speaker_metrics: list[dict[str, Any]],
    stop_words: set[str],
) -> list[dict[str, Any]]:
    speaker_segments: dict[str, list[dict[str, Any]]] = {}
    for item in included:
        speaker_segments.setdefault(item["speaker"], []).append(item)
    speaker_term_counts = {
        speaker: text_mining_counter(values, stop_words)
        for speaker, values in speaker_segments.items()
    }
    keywords = []
    for term, count in text_mining_terms(included, limit=30, extra_stop_words=stop_words):
        by_speaker = []
        for metric in speaker_metrics:
            occurrences = int(speaker_term_counts.get(metric["speaker"], Counter()).get(term, 0))
            if occurrences:
                by_speaker.append({
                    "speaker": metric["speaker"],
                    "speaker_name": metric["speaker_name"],
                    "count": occurrences,
                })
        keywords.append({"term": term, "count": count, "by_speaker": by_speaker})
    return keywords


def _code_metrics(
    codebook: dict[str, dict[str, Any]],
    included: list[dict[str, Any]],
    session_profile: dict[str, str],
) -> list[dict[str, Any]]:
    metrics = []
    for code_id, code in codebook.items():
        coded = [item for item in included if code_id in item["annotation"].get("codes", [])]
        timed = [item for item in coded if item["valid_time"]]
        coverage = {"turn_count": len(coded), "timed_turn_count": len(timed), "missing_time_turn_count": len(coded) - len(timed)}
        metrics.append({
            **code,
            "segment_count": len(coded),
            "speaking_seconds": _observed_seconds(float(sum(float(item["duration"]) for item in timed)), coverage),
            "timed_turn_count": coverage["timed_turn_count"],
            "missing_time_turn_count": coverage["missing_time_turn_count"],
            "characters": sum(int(item["characters"]) for item in coded),
            "speaker_count": len({item["speaker"] for item in coded if item["speaker"] != "UNKNOWN"}),
            "unknown_speaker_turns": sum(item["speaker"] == "UNKNOWN" for item in coded),
            "group_count": 1 if coded and session_profile.get("interview_group_id") else None,
            "important_count": sum(1 for item in coded if item["annotation"].get("important")),
        })
    return metrics


def _interaction_summary(included: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(
        tag
        for item in included
        for tag in item["annotation"].get("interaction_tags", [])
    )
    return [
        {"tag": key, "label": label, "count": int(counts.get(key, 0))}
        for key, label in ANALYSIS_INTERACTION_TAGS.items()
    ]


def _interaction_link_rows(
    timeline: list[dict[str, Any]], analysis_needs_review: bool
) -> list[dict[str, Any]]:
    """Resolve each recorded relation to its target turn and the turns between."""
    positions = {item["id"]: index for index, item in enumerate(timeline)}
    by_id = {item["id"]: item for item in timeline}
    links: list[dict[str, Any]] = []
    for item in timeline:
        for link in item["annotation"].get("interaction_links", []):
            target_id = str(link.get("target_segment_id") or "")
            target = by_id.get(target_id)
            if target is None:
                links.append({
                    "source_segment_id": item["id"],
                    "target_segment_id": target_id,
                    "source_order": item["utterance_order"],
                    "target_order": 0,
                    "relation": link.get("relation"),
                    "relation_label": ANALYSIS_INTERACTION_RELATIONS.get(link.get("relation"), ""),
                    "evidence_memo": link.get("evidence_memo", ""),
                    "status": "missing_target",
                    "context_segment_ids": [],
                    "analysis_needs_review": True,
                })
                continue
            first, last = sorted((positions[target_id], positions[item["id"]]))
            # A bounded run is exported as auditable context.  If the two
            # turns are far apart, the endpoint turns are still retained but
            # we do not imply that all omitted intervening turns were read.
            context_ids = [value["id"] for value in timeline[first:last + 1]]
            relation = str(link.get("relation") or "")
            links.append({
                "status": "needs_review" if analysis_needs_review else "recorded",
                "analysis_needs_review": analysis_needs_review,
                "relation": relation,
                "relation_label": ANALYSIS_INTERACTION_RELATIONS.get(relation, relation),
                "source_segment_id": item["id"],
                "source_order": item["utterance_order"],
                "source_speaker": item["speaker"],
                "source_speaker_name": item["speaker_name"],
                "source_role": item["role"],
                "source_text": item["text"],
                "target_segment_id": target["id"],
                "target_order": target["utterance_order"],
                "target_speaker": target["speaker"],
                "target_speaker_name": target["speaker_name"],
                "target_role": target["role"],
                "target_text": target["text"],
                "context_segment_ids": context_ids,
                "context_truncated": last - first + 1 > len(context_ids),
                "evidence_memo": str(link.get("evidence_memo") or ""),
            })
    links.sort(key=lambda value: (value["source_order"], value["target_order"], value["relation"]))
    return links


def _case_code_matrix(
    speaker_metrics: list[dict[str, Any]], codebook: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {
            "speaker": metric["speaker"],
            "speaker_name": metric["speaker_name"],
            "role": metric["role"],
            "codes": [
                {
                    "code_id": code_id,
                    "code_label": code["label"],
                    "count": int(metric["code_counts"].get(code_id, 0)),
                }
                for code_id, code in codebook.items()
            ],
        }
        for metric in speaker_metrics
    ]


def _comparison_group_name(metric: dict[str, Any], group_by: str) -> str:
    profile_value = metric.get("profile")
    profile = profile_value if isinstance(profile_value, dict) else {}
    if group_by == "role":
        return "役割混在（話者単位）" if metric.get("role_status") == "mixed" else str(metric["role"] or "未設定")
    if group_by.startswith("attribute:"):
        attributes = profile.get("attributes")
        attribute_value = (
            attributes.get(group_by[len("attribute:"):])
            if isinstance(attributes, dict)
            else ""
        )
        return str(attribute_value or "").strip() or "未回答"
    return str(profile.get(group_by) or "未設定")


def _comparison_group_rows(
    speaker_metrics: list[dict[str, Any]], group_by: str, total_speaking: float
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    role_incomplete = group_by == "role" and any(row.get("role_status") == "mixed" for row in speaker_metrics)
    if group_by != "none":
        for metric in speaker_metrics:
            group_name = _comparison_group_name(metric, group_by)
            group = groups.setdefault(group_name, {
                "group": group_name, "speaker_count": 0, "turn_count": 0,
                "speaking_seconds": 0.0, "characters": 0,
                "timed_turn_count": 0, "missing_time_turn_count": 0,
            })
            group["speaker_count"] += 1
            group["turn_count"] += int(metric["turn_count"])
            group["speaking_seconds"] += float(metric["speaking_seconds"] or 0)
            group["timed_turn_count"] += int(metric["timed_turn_count"])
            group["missing_time_turn_count"] += int(metric["missing_time_turn_count"])
            group["characters"] += int(metric["characters"])
    complete = total_speaking > 0 and not any(row["missing_time_turn_count"] for row in speaker_metrics)
    return [{
        **value,
        "speaking_seconds": _observed_seconds(float(value["speaking_seconds"]), value) if not role_incomplete else None,
        "speaking_percent": round(100 * float(value["speaking_seconds"]) / total_speaking, 2) if complete and not role_incomplete else None,
        "role_aggregation_status": "mixed" if role_incomplete else "consistent",
    } for value in groups.values()]


def _moderator_summary(
    speaker_metrics: list[dict[str, Any]],
    total_speaking: float,
    turn_taking: dict[str, Any],
) -> dict[str, Any]:
    facilitators = [
        item for item in speaker_metrics if item["role"] in ANALYSIS_FACILITATOR_ROLES
    ]
    role_incomplete = any(row.get("role_status") == "mixed" for row in speaker_metrics)
    moderator_seconds = sum(float(item["speaking_seconds"] or 0) for item in facilitators)
    coverage = _timing_coverage(facilitators)
    complete = total_speaking > 0 and not any(row["missing_time_turn_count"] for row in speaker_metrics)
    response_gaps = turn_taking["moderator_response_gaps"]
    return {
        "assigned": bool(facilitators) if not role_incomplete else None,
        **coverage,
        "speaking_seconds": _observed_seconds(moderator_seconds, coverage) if not role_incomplete else None,
        "speaking_percent": round(100 * moderator_seconds / total_speaking, 2) if complete and not role_incomplete else None,
        "question_candidates": sum(int(item["question_candidates"]) for item in facilitators) if not role_incomplete else None,
        "role_aggregation_status": "mixed" if role_incomplete else "consistent",
        "participant_responses": len(response_gaps),
        "moderator_to_participant_transitions": turn_taking["moderator_to_participant"],
        "average_response_gap_seconds": round(
            sum(response_gaps) / len(response_gaps), 3
        ) if response_gaps else None,
        "participant_to_participant_transitions": turn_taking["participant_to_participant"],
        "cross_speaker_transitions": turn_taking["cross_speaker_transitions"],
    }


def _observations(
    speaker_metrics: list[dict[str, Any]],
    *,
    moderator: dict[str, Any],
    long_gaps: list[dict[str, Any]],
    overlap_candidates: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, str]]:
    """Points worth a researcher's look; none of them is a judgement."""
    observations: list[dict[str, str]] = []
    dominant = _dominant_speaker(speaker_metrics)
    if any(row.get("role_status") == "mixed" for row in speaker_metrics):
        observations.append({"level": "info", "label": "話者内の役割混在",
                             "message": "同じ話者に複数の役割が記録されています。全体の発話時間は保持し、役割に依存する割合・司会・役割別集計は算出しません。発話ごとの役割は元記録で確認できます。"})
    population_label = "参加者内" if config["exclude_moderator"] else "観測話者内"
    if dominant and float(dominant["participant_percent"]) >= 50:
        observations.append({
            "level": "attention",
            "label": "発話時間の集中候補",
            "message": f"{dominant['speaker_name']}の{population_label}発話時間が{dominant['participant_percent']:.1f}%です。重要性や影響力を意味する値ではありません。",
        })
    low_names = [
        item["speaker_name"] for item in speaker_metrics
        if item["included_in_balance"] and item["participant_percent"] is not None
        and float(item["participant_percent"]) < float(config["low_participation_percent"])
    ]
    if low_names:
        observations.append({
            "level": "attention",
            "label": "発言機会の確認候補",
            "message": f"設定した{config['low_participation_percent']:g}%未満: {', '.join(low_names)}。沈黙の意味は記録・文脈と合わせて判断してください。",
        })
    if moderator["speaking_percent"] is not None and moderator["speaking_percent"] >= 40:
        observations.append({
            "level": "attention",
            "label": "司会発話比率の確認",
            "message": f"司会・進行役の発話時間は全体の{moderator['speaking_percent']:.1f}%です。進行品質の得点ではありません。",
        })
    if long_gaps:
        observations.append({
            "level": "info", "label": "長い無音候補",
            "message": f"{config['long_gap_seconds']:g}秒以上の無音候補が{len(long_gaps)}件あります。無音の理由は自動判定できません。",
        })
    if overlap_candidates:
        observations.append({
            "level": "info", "label": "発話重なり候補",
            "message": f"{config['overlap_seconds']:g}秒以上の時間重なり候補が{len(overlap_candidates)}件あります。遮りとは断定しません。",
        })
    return observations


def _context_checks(
    *,
    config: dict[str, Any],
    session_profile: dict[str, str],
    moderator_assigned: bool,
    speaker_metrics: list[dict[str, Any]],
    raw_profiles: dict[str, Any],
    codebook: dict[str, dict[str, Any]],
    annotations: dict[str, dict[str, Any]],
    original_segments_status: str,
    interaction_links: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {"id": "research_question", "label": "研究質問", "ready": bool(config["research_question"]), "kind": "manual"},
        {"id": "objective", "label": "会話目的", "ready": bool(session_profile.get("objective")), "kind": "manual"},
        {
            "id": "comparison_group",
            "label": "インタビュー比較グループ",
            "ready": bool(session_profile.get("comparison_group") or session_profile.get("moderator_guide")),
            "kind": "manual",
        },
        {"id": "moderator", "label": "司会・進行役", "ready": moderator_assigned, "kind": "manual"},
        {
            "id": "participant_roles",
            "label": "話者役割",
            "ready": bool(speaker_metrics) and all(
                isinstance(raw_profiles.get(item["speaker"]), dict)
                and bool(raw_profiles[item["speaker"]].get("session_role"))
                for item in speaker_metrics
            ),
            "kind": "manual",
        },
        {"id": "guide", "label": "質問ガイド・議題", "ready": bool(session_profile.get("moderator_guide")), "kind": "manual"},
        {"id": "conditions", "label": "参加条件・グループ条件", "ready": bool(session_profile.get("group_conditions")), "kind": "manual"},
        {"id": "field_notes", "label": "観察・フィールドノート", "ready": bool(session_profile.get("field_notes")), "kind": "manual"},
        {"id": "codebook", "label": "コードブック", "ready": bool(codebook), "kind": "manual"},
        {
            "id": "coding",
            "label": "手動コーディング",
            "ready": any(
                value.get("codes") or value.get("interaction_tags")
                for value in annotations.values()
            ),
            "kind": "manual",
        },
        {
            "id": "original_snapshot",
            "label": "原文スナップショット",
            "ready": original_segments_status in {"initial_import", "migrated_current_snapshot"},
            "kind": "automatic",
        },
        {
            "id": "interaction_links",
            "label": "根拠発話を結ぶ相互作用記録",
            "ready": bool(interaction_links),
            "kind": "manual",
        },
    ]


def _apply_preparation_to_inventory(
    inventory: list[dict[str, Any]],
    prepared: dict[str, Any],
    timeline: list[dict[str, Any]],
) -> None:
    """Replace inventory entries the preparation screen has confirmed."""
    for entry in inventory:
        if entry["item"] == "このレコードの参加者数":
            known = prepared["participant_count"] is not None
            entry.update(
                status="確認済み" if known else "不明",
                value=str(prepared["participant_count"]) if known else "不明（発言した話者数と実参加人数は別）",
            )
        elif entry["item"] == "発言者・発言順":
            entry.update(
                status="確認済み" if timeline and prepared["order_verified"] and not prepared["unknown_speaker_turns"] else "不明",
                value=f"話者未確認 {prepared['unknown_speaker_turns']}発言。順序確認: {prepared['order_verified']}",
            )
        elif entry["item"] == "司会者の発言・役割":
            ready = any(r["role"] == "moderator" and r["speaker_verified"] for r in prepared["rows"])
            entry.update(status="確認済み" if ready else "不明", value="準備画面で確認済み" if ready else "不明")


def _analysis_export_links(item_id: Any) -> dict[str, str]:
    base = f"/api/library/{item_id}/analysis"
    links = {"json": f"{base}/export.json", "xlsx": f"{base}/export.xlsx"}
    for dataset in _LEGACY_EXPORT_DATASETS:
        links[dataset] = f"{base}/export.csv?dataset={dataset}"
    return links


def _attach_research(
    analysis: dict[str, Any], *, execute: bool, include_research_rows: bool
) -> dict[str, Any]:
    """Run (or reuse the cached) local research analysis, or mark it pending."""
    if execute or is_research_analysis_cached(analysis):
        analysis = enrich_research_analysis(analysis, include_rows=include_research_rows)
        analysis["executed"] = True
    else:
        analysis["executed"] = False
        analysis["research"] = None
        analysis["insights"] = {
            "local": None, "ai": None, "stale": False, "fingerprint": ""
        }
    return analysis


def _attach_saved_results(
    analysis: dict[str, Any], row: sqlite3.Row, session_profile: dict[str, str]
) -> None:
    """Attach saved AI insights, transformer topics and classification with staleness."""
    saved = _saved_json(row, "analysis_insights_json")
    if isinstance(saved, dict) and saved:
        analysis["insights"]["ai"] = saved
        analysis["insights"]["stale"] = saved.get("fingerprint") != analysis["insights"]["fingerprint"]

    transformer_saved = _saved_json(row, "transformer_analysis_json")
    transformer_result = (
        {key: value for key, value in transformer_saved.items() if key != "vectors"}
        if isinstance(transformer_saved, dict) and transformer_saved else None
    )
    transformer_stale = bool(transformer_result) and transformer_result.get("fingerprint") != transformer_input_fingerprint(
        analysis, model=str(transformer_result.get("engine", {}).get("name") or DEFAULT_TRANSFORMER_MODEL),
        parameters=transformer_result.get("parameters"),
    )
    analysis["transformer"] = {"result": transformer_result, "stale": transformer_stale}
    analysis["session_outline"] = build_session_outline(
        outline=json_load(row["outline_json"], None),
        transformer=transformer_result,
        session_profile=session_profile,
        transformer_stale=transformer_stale,
    )

    classification_saved = _saved_json(row, "segment_classification_json")
    classification_result = (
        classification_saved if isinstance(classification_saved, dict) and classification_saved else None
    )
    classification_expected = classification_fingerprint(
        analysis["segments"], analysis["config"].get("codebook", []),
        transformer_result if transformer_result and not transformer_stale else None,
    )
    classification_stale = bool(classification_result) and any((
        classification_result.get("fingerprint") != classification_expected,
        classification_result.get("source_revision") != int(analysis["item"]["revision_count"]),
        classification_result.get("analysis_revision") != int(analysis["item"]["analysis_revision"]),
    ))
    analysis["segment_classification"] = {
        "result": classification_result,
        "stale": classification_stale,
        "summary": segment_classification_summary(classification_result),
        "dialogue_acts": DIALOGUE_ACTS,
    }


def _attach_method_experts(analysis: dict[str, Any], *, catalog=None) -> None:
    # Only the experts named by the analysis plan are read (docs/program-vault/50-Analysis-Methods/10-Experts).
    analysis["experts"] = method_experts.review_for_analysis(analysis, catalog=catalog)
    expert_procedure = method_experts.plan_procedure(analysis["experts"])
    if expert_procedure:
        analysis["manual"]["focus_group_plan"]["procedure"] = expert_procedure
    if analysis["experts"]["ai"].get("mode") == "expert":
        # Method-specific AI drafts depend on the expert knowledge, so an updated note makes them stale.
        analysis["insights"]["fingerprint"] = input_fingerprint(analysis)
        if analysis["insights"].get("ai"):
            analysis["insights"]["stale"] = (
                analysis["insights"]["ai"].get("fingerprint") != analysis["insights"]["fingerprint"])


def group_analysis_for_row(
    row: sqlite3.Row,
    *,
    include_research_rows: bool = False,
    execute: bool = True,
    defer_research: bool = False,
    connect: Callable[[], Any],
    row_segments: Callable[[Any], list[dict[str, Any]]],
    row_original_segments: Callable[[Any], tuple[dict[str, dict[str, Any]], str]],
    row_speaker_profiles: Callable[..., dict[str, Any]],
    row_session_profile: Callable[[Any], dict[str, str]],
    list_speaker_registry: Callable[..., list[dict[str, Any]]],
) -> dict[str, Any]:
    segments = row_segments(row)
    with connect() as connection:
        prepared = preparation.view(connection, row, segments)
    original_segments, original_segments_status = row_original_segments(row)
    config = row_analysis_config(row)
    annotations, orphaned_annotations = row_analysis_annotation_state(
        row, segments, config
    )
    raw_names = json_load(row["speaker_names_json"], {})
    speaker_names = raw_names if isinstance(raw_names, dict) else {}
    raw_profiles_value = json_load(row["speaker_profiles_json"], {})
    raw_profiles = raw_profiles_value if isinstance(raw_profiles_value, dict) else {}
    profiles = row_speaker_profiles(row, segments, speaker_names)
    registry_profiles = _linked_registry_profiles(profiles, list_speaker_registry)
    session_profile = row_session_profile(row)
    codebook = {str(item["id"]): item for item in config["codebook"]}

    timeline, speaker_buckets, emotion_rows, quality = _analysis_timeline(
        segments,
        prepared=prepared,
        original_segments=original_segments,
        original_segments_status=original_segments_status,
        annotations=annotations,
        profiles=profiles,
        speaker_names=speaker_names,
        session_profile=session_profile,
        excluded_speakers=set(config["excluded_speakers"]),
        registered_roles={speaker for speaker, profile in profiles.items()
                          if (isinstance(raw_profiles.get(speaker), dict) and raw_profiles[speaker].get("session_role"))
                          or registry_profiles.get(str(profile.get("global_speaker_id") or ""), {}).get("default_role")},
    )
    _add_recorded_role_measurements(timeline, profiles, registry_profiles)
    included = [item for item in timeline if not item["excluded"]]
    valid_included = _physical_time_view(included)
    physical_timeline = _physical_time_view(timeline)

    # Participation.
    total_speaking = sum(float(item["speaking_seconds"]) for item in speaker_buckets.values())
    participant_labels = [
        label for label, item in speaker_buckets.items()
        if item["role"] not in ANALYSIS_NON_PARTICIPANT_ROLES and label != "UNKNOWN" and len(item["observed_roles"]) == 1
    ]
    mixed_role_speaker_count = sum(label != "UNKNOWN" and len(item["observed_roles"]) > 1 for label, item in speaker_buckets.items())
    timing_coverage = _timing_coverage(list(speaker_buckets.values()))
    eligible_balance_labels = participant_labels if config["exclude_moderator"] else list(speaker_buckets)
    balance_population = [label for label in eligible_balance_labels if label != "UNKNOWN"]
    balance_labels = [label for label in eligible_balance_labels
                      if label != "UNKNOWN" and speaker_buckets[label]["timed_turn_count"] > 0]
    speaker_metrics = _speaker_metrics(
        speaker_buckets,
        profiles=profiles,
        registry_profiles=registry_profiles,
        balance_labels=balance_labels,
        balance_population=balance_population,
        balance_role_valid=not config["exclude_moderator"] or mixed_role_speaker_count == 0,
        total_speaking=total_speaking,
    )
    balance = _participation_balance(
        speaker_buckets,
        speaker_metrics,
        participant_labels=participant_labels,
        balance_labels=balance_labels,
        balance_population=balance_population,
        mixed_role_speaker_count=mixed_role_speaker_count,
        exclude_moderator=config["exclude_moderator"],
        prepared=prepared,
    )

    # Turn-taking and timing.
    transition_rows, turn_taking = _speaker_transitions(
        valid_included, float(config["overlap_seconds"])
    )
    overlap_candidates, overlap_truncated = _overlap_candidates(
        physical_timeline, float(config["overlap_seconds"])
    )
    long_gaps = _long_gaps(physical_timeline, float(config["long_gap_seconds"]))
    timing_timeline = _timing_view(timeline)
    timing_included = _timing_view(included)
    session_duration = max((float(item["end"]) for item in timing_timeline), default=None)
    requested_bin_seconds = int(config["time_bin_seconds"])
    time_bins, bin_seconds = _time_bins(
        timing_included,
        session_duration=session_duration,
        requested_bin_seconds=requested_bin_seconds,
        speaker_buckets=speaker_buckets,
    )
    moderator = _moderator_summary(speaker_metrics, total_speaking, turn_taking)
    consecutive_gaps = turn_taking["consecutive_gaps"]

    # Researcher coding.
    interaction_links = _interaction_link_rows(timeline, prepared["analysis_needs_review"])
    focus_group_plan = build_focus_group_analysis_plan(
        row, session_profile, config, timeline, speaker_metrics, profiles,
        original_segments_status,
    )
    _apply_preparation_to_inventory(focus_group_plan["data_inventory"], prepared, timeline)

    analysis = {
        # Additive fields preserve the v1 export contract for existing tools.
        "schema_version": 1,
        "algorithm_version": GROUP_ANALYSIS_ALGORITHM_VERSION,
        "generated_at": utc_now_iso(),
        "item": {
            "id": row["id"],
            "source_name": row["source_name"],
            "revision_count": int(row["revision_count"] or 0),
            "analysis_revision": int(row["analysis_revision"] or 0),
            "analysis_updated_at": row["analysis_updated_at"],
            "updated_at": row["updated_at"],
            "session_profile": session_profile,
        },
        "config": config,
        "annotations": annotations,
        "classification": {
            "automatic": ["発話量", "参加バランス", "話者遷移", "無音・重なり候補", "簡易頻出語", "感情分布"],
            "configured": ["司会除外", "比較属性", "判定しきい値", "ストップワード", "手動選択単語", "コードブック"],
            "manual": ["コード適用", "テーマ構築", "相互作用の意味", "司会影響", "重要引用", "研究上の解釈"],
        },
        "cautions": [
            "発話時間の多さは重要性・影響力を意味しません。",
            "簡易頻出語は重要テーマではありません。",
            "発話遷移は影響関係を意味しません。",
            "無音や重なりの意味、合意・対立、テーマは研究者が文脈とともに確認してください。",
            "音声感情モデルの推定は本人の感情を確定するものではありません。",
            "COREQは研究品質の得点ではなく、報告項目の確認に用います。",
        ],
        "automatic": {
            "overview": {
                "session_duration": round(session_duration, 3) if session_duration is not None else None,
                "session_timed_turn_count": len(timing_timeline),
                "session_missing_time_turn_count": len(timeline) - len(timing_timeline),
                "segment_count": len(timeline),
                "included_segment_count": len(included),
                "speaker_count": len(speaker_metrics),
                "participant_count": prepared.get("participant_count"),
                "observed_participant_count": None if mixed_role_speaker_count else len(participant_labels),
                "mixed_role_speaker_count": mixed_role_speaker_count,
                "observed_speaker_count": sum(row["speaker"] != "UNKNOWN" for row in speaker_metrics),
                "total_speaking_seconds": _observed_seconds(total_speaking, timing_coverage),
                "timed_turn_count": timing_coverage["timed_turn_count"],
                "missing_time_turn_count": timing_coverage["missing_time_turn_count"],
                "average_cross_speaker_gap_seconds": round(sum(consecutive_gaps) / len(consecutive_gaps), 3) if consecutive_gaps else None,
            },
            "speaker_metrics": speaker_metrics,
            "balance": balance,
            "moderator": moderator,
            "transitions": transition_rows,
            "long_gaps": long_gaps,
            "overlap_candidates": overlap_candidates,
            "time_bins": time_bins,
            "requested_time_bin_seconds": requested_bin_seconds,
            "effective_time_bin_seconds": bin_seconds,
            "timing_order_basis": "validated_start_end_id_sorted_copy",
            "keywords": _keyword_rows(included, speaker_metrics, set(config["stop_words"])),
            "emotions": [{**value, "seconds": round(float(value["seconds"]), 3) if value["timed_turn_count"] else None} for value in emotion_rows.values()],
            "groups": _comparison_group_rows(speaker_metrics, config["group_by"], total_speaking),
            "observations": _observations(
                speaker_metrics,
                moderator=moderator,
                long_gaps=long_gaps,
                overlap_candidates=overlap_candidates,
                config=config,
            ),
            "data_quality": {
                "unknown_speaker_segments": sum(1 for item in timeline if item["speaker"] == "UNKNOWN"),
                "empty_text_segments": quality["empty_text"],
                "zero_duration_segments": quality["zero_duration"],
                "invalid_time_segments": quality["invalid_time"],
                "overlap_candidates_truncated": overlap_truncated,
                "emotion_coverage_percent": round(100 * quality["emotion_covered"] / len(timeline), 2) if timeline else 0.0,
                "excluded_segments": sum(1 for item in timeline if item["excluded"]),
            },
        },
        "manual": {
            "preparation": prepared,
            "codebook": list(codebook.values()),
            "codebook_version": config["codebook_version"],
            "codebook_history": config["codebook_history"],
            "code_metrics": _code_metrics(codebook, included, session_profile),
            "interaction_tags": [
                {"id": key, "label": label} for key, label in ANALYSIS_INTERACTION_TAGS.items()
            ],
            "interaction_summary": _interaction_summary(included),
            "interaction_links": interaction_links,
            "case_code_matrix": _case_code_matrix(speaker_metrics, codebook),
            "coded_segment_count": sum(1 for item in included if item["annotation"].get("codes")),
            "important_quote_count": sum(1 for item in included if item["annotation"].get("important")),
            "context_checks": _context_checks(
                config=config,
                session_profile=session_profile,
                moderator_assigned=moderator["assigned"],
                speaker_metrics=speaker_metrics,
                raw_profiles=raw_profiles,
                codebook=codebook,
                annotations=annotations,
                original_segments_status=original_segments_status,
                interaction_links=interaction_links,
            ),
            "analyst_memo": config["analyst_memo"],
            "interpretation_status": config["interpretation_status"],
            "orphaned_annotation_count": len(orphaned_annotations),
            "orphaned_annotations": [
                {"segment_id": segment_id, **value}
                for segment_id, value in orphaned_annotations.items()
            ],
            "focus_group_plan": focus_group_plan,
        },
        "segments": timeline,
        "exports": _analysis_export_links(row["id"]),
    }
    if quality["invalid_time"]:
        analysis["cautions"].append(
            "時間の合計・平均・発話速度は時刻が有効な発話だけを対象にします。"
            "時刻不明の発話は0秒の観測とは扱わず、本文の件数・文字数には含めます。"
        )
    with connect() as connection:
        attach_foundations(analysis, connection, registry_profiles)
    if defer_research:
        # A genuine boundary: never consult the process research cache here.
        return analysis
    analysis = _attach_research(
        analysis, execute=execute, include_research_rows=include_research_rows
    )
    return finish_group_analysis(analysis, row)


def finish_group_analysis(analysis: dict[str, Any], row: Any, *, expert_catalog=None) -> dict[str, Any]:
    """Attach saved views after research, shared by monolithic and staged builds."""
    session_profile = analysis["item"]["session_profile"]
    _attach_saved_results(analysis, row, session_profile)
    # The planned agenda, parsed the same way the workspace outline block reads it,
    # so themes imported from it match the plan items line for line.
    analysis["plan_items"] = plan_items(analysis["item"].get("session_profile"))
    _attach_method_experts(analysis, catalog=expert_catalog)
    # Added last so links the research step already set keep their position.
    for dataset in ANALYSIS_CSV_FIELDS:
        analysis["exports"][dataset] = f"/api/library/{row['id']}/analysis/export.csv?dataset={dataset}"
    return analysis
