"""Local Transformer embeddings for evidence-linked focus-group exploration.

The model is loaded lazily so transcription and the existing analysis UI remain
available when the optional model has not been downloaded yet.  Embeddings are
used for similarity only: this module deliberately does not infer agreement,
sentiment, importance, or causality.
"""

from __future__ import annotations

import base64
import math
import os
import re
import threading
from collections import Counter, defaultdict
from importlib import metadata
from typing import Any, Callable

from .analysis_core import EMBEDDING_STANDARD_V1


TRANSFORMER_ANALYSIS_VERSION = "transformer-topics-9"
EMBEDDING_INPUT_VERSION = "contextual-e5-input-1"
MAX_EMBEDDING_TOKENS = 512
DEFAULT_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_MAX_TOPICS = 8
DEFAULT_MIN_TOPIC_SIZE = 2
MAX_SEGMENTS = 5000
MAX_TEXT_CHARACTERS = 6000
TOPIC_MODES = ("auto", "candidate", "manual")
MAX_MANUAL_TOPICS = 12
# The researcher picks the cut-off; 0 keeps every utterance on its nearest theme.
DEFAULT_MANUAL_MIN_SIMILARITY = 0.0
# Two themes within this cosine distance of each other decide the assignment by noise.
LOW_MARGIN_LIMIT = 0.01

TRANSFORMER_CSV_FIELDS = {
    "transformer_input_coverage": [
        "segment_id", "context_segment_ids", "contextual_character_count", "target_character_start",
        "target_character_end", "character_truncated", "character_limit", "token_count_after_character_limit",
        "used_token_count", "token_limit", "token_truncated", "token_measurement_status",
        "retained_character_start", "retained_character_end", "retained_range_status", "target_retention_status",
        "truncation_side",
    ],
    "transformer_topics": [
        "topic_id", "label", "origin", "keywords", "segment_count", "speaker_count",
        "participant_segment_count", "facilitator_segment_count",
        "backchannel_count", "speaking_seconds", "average_similarity", "representative_segment_ids",
    ],
    "transformer_assignments": [
        "segment_id", "topic_id", "topic_label", "speaker", "speaker_name",
        "speaker_group", "start", "end", "duration", "similarity", "margin",
        "outlier_score", "text",
    ],
    "transformer_speakers": [
        "topic_id", "topic_label", "speaker", "speaker_name", "segment_count",
        "speaker_group", "topic_percent", "speaking_seconds",
    ],
    "transformer_timeline": [
        "bin_index", "start", "end", "topic_id", "topic_label",
        "segment_count", "backchannel_count", "speaking_seconds",
    ],
    "transformer_outliers": [
        "rank", "segment_id", "speaker", "speaker_name", "start", "end",
        "outlier_score", "nearest_similarity", "text",
    ],
    "transformer_backchannels": [
        "segment_id", "speaker", "speaker_name", "speaker_group", "kind",
        "start", "end", "text", "topic_id", "topic_label",
        "responds_to_segment_id", "responds_to_speaker", "responds_to_speaker_name",
        "time_gap", "link_method",
    ],
    "transformer_backchannel_speakers": [
        "speaker", "speaker_name", "speaker_group", "topic_id", "topic_label",
        "backchannel_count", "speaker_backchannel_percent",
    ],
    "transformer_backchannel_rates": [
        "scope", "speaker", "speaker_name", "speaker_group", "topic_id", "topic_label",
        "opportunity_count", "responded_target_count", "response_rate_percent",
        "backchannel_count", "backchannels_per_100_opportunities", "linked_count",
        "unlinked_count", "agreement_count", "continuer_count", "confirmation_count",
        "courtesy_count",
    ],
    "transformer_backchannel_tests": [
        "test_id", "test", "dimension", "n", "row_count", "column_count",
        "statistic", "df", "p_value", "effect_name", "effect_size",
        "low_expected_cells", "expected_cell_count", "status", "interpretation",
        "assumption_note",
    ],
    "transformer_speaker_results": [
        "speaker", "speaker_name", "speaker_group", "result_code", "result_label",
        "topic_id", "topic_label", "confidence", "review_status", "researcher_review_required",
        "registered_role", "role_source", "basis", "matched_cues",
        "evidence_segment_ids", "evidence_texts", "first_segment_id", "last_segment_id",
    ],
}

_MODEL_LOCK = threading.RLock()
_MODEL_CACHE: dict[tuple[str, str], tuple[Any, Any, str]] = {}

_CONTENT_CHARACTER_RE = re.compile(r"[0-9A-Za-z\u3040-\u30ff\u3400-\u9fff]")
_REPEATED_FILLER_RE = re.compile(r"^(?:[あいうえおぁぃぅぇぉー]+|[はへ]+|[?？!！。．、,]+)$")
_SHORT_FILLERS = {
    "あ", "ああ", "え", "ええ", "うん", "うーん", "はい", "へえ", "ほう",
    "そう", "そうです", "そうですね", "そうなんです", "なるほど", "たしかに",
    "わかりました", "分かりました", "ありがとう", "ありがとうございます",
    "お願いします", "よろしくお願いします", "以上です", "すみません", "ごめんなさい",
    "です", "でした", "ます", "ました", "します", "しました", "した", "で", "な",
    "ちょっと", "ところです", "という感じ", "みたいな",
}
_LABEL_STOP_TERMS = {
    "一寸", "ちょっと", "御座る", "ござる", "有る", "ある", "居る", "いる",
    "する", "成る", "なる", "思う", "言う", "感じ", "最後", "以上", "今回",
    "今日", "皆", "皆さん", "皆様", "自分", "私", "僕", "俺", "方", "人", "時", "所",
    "もの", "こと", "そう", "うー", "えー", "はい", "ありがとう", "お願い",
    "矢張り", "やはり", "余り", "あまり", "お疲れ様", "えーと", "しょう", "すか",
}
_SHORT_SEMANTIC_TERMS = {
    "好き", "嫌い", "高い", "安い", "辛い", "甘い", "苦い", "良い", "悪い",
    "おいしい", "まずい", "欲しい", "必要", "不要", "賛成", "反対",
}
_BACKCHANNELS = {
    "はい": "agreement", "そう": "agreement", "そうです": "agreement",
    "そうですね": "agreement", "そうなんです": "agreement", "たしかに": "agreement",
    "確かに": "agreement", "その通り": "agreement", "同じです": "agreement",
    "うん": "continuer", "うーん": "continuer", "ああ": "continuer",
    "ええ": "continuer", "へえ": "continuer", "へー": "continuer",
    "ほう": "continuer", "なるほど": "continuer", "なるほどね": "continuer",
    "そうか": "confirmation", "そうなんですね": "confirmation",
    "ですよね": "agreement", "わかる": "agreement", "分かる": "agreement",
    "オッケー": "confirmation", "OK": "confirmation",
    "ありがとう": "courtesy", "ありがとうございます": "courtesy",
    "ありがとうございました": "courtesy",
    "わかりました": "confirmation", "分かりました": "confirmation",
}

_SPEAKER_RESULT_DEFINITIONS = (
    (
        "opinion_changed", "意見・認識が変わった", "explicit",
        (
            re.compile(r"(?:意見|考え|印象|見方|認識|気持ち)(?:が|は|も)?(?:かなり|大きく|少し)?変わ(?!らな|りません|っていな|っていません|らず|らぬ)"),
            re.compile(r"(?:考え直|見直)(?:した|しました|す|すこと|すよう)"),
            re.compile(r"(?:話|説明|意見).{0,24}(?:聞いて|聴いて).{0,24}(?:思う|考える|感じる)ようにな"),
            re.compile(r"(?:最初|初め|以前|もともと|元々).{0,32}(?:でしたが|だったが|だけど|でしたけど|ものの|一方で).{0,32}(?:今|現在|最終的|むしろ|こちら|こっち)"),
            re.compile(r"(?:イメージ|印象|考え)(?:が|は)?(?:あった|ありました|持っていた|持っていました).{0,32}(?:けど|が).{0,40}(?:話を聞|実際|違う|むしろ|一方)"),
        ),
    ),
    (
        "opinion_maintained", "意見・認識が変わらなかった", "explicit",
        (
            re.compile(r"(?:意見|考え|印象|見方|認識|気持ち).{0,12}(?:変わらない|変わりません|変わっていない|変わっていません)"),
            re.compile(r"(?:意見|考え|認識)(?:は|も)?(?:同じ|そのまま)"),
            re.compile(r"(?:やはり|やっぱり|改めて).{0,32}(?:と思う|と感じる|がいい|が良い|を選ぶ|に賛成|必要|不要)"),
        ),
    ),
    (
        "new_insight", "新しい見解・気づきを得た", "explicit",
        (
            re.compile(r"(?:新しい|新たな|別の)(?:見方|見解|視点|考え|気づき|発見)"),
            re.compile(r"(?:気づいた|気付きました|気付いた|発見した|発見しました)"),
            re.compile(r"(?:初めて知った|初めて分かった|初めてわかった|知らなかった|考えたことがなかった)"),
            re.compile(r"(?:勉強|参考|学び)(?:に)?な(?:った|りました)"),
            re.compile(r"(?:そういう|そのような)(?:考え|見方|視点).{0,16}(?:なかった|ある|知った|分かった|わかった)"),
            re.compile(r"(?:話|意見|説明)を(?:聞いて|聴いて).{0,48}(?:分か|わか|知|気づ|気付|イメージ|印象|感じ|見方|考え)"),
            re.compile(r"(?:だ|と)と思ったんですけど.{0,40}(?:違う|分か|わか|知)"),
            re.compile(r"(?:違う|そういう).{0,16}(?:んだな|ことなんだ).{0,16}(?:思|感じ)"),
        ),
    ),
    (
        "preference_formed", "支持・選好が明確になった", "explicit",
        (
            re.compile(r"(?:これ|こちら|こっち|それ|そちら|この案|その案)(?:の方)?(?:が|を).{0,12}(?:いい|良い|よい)(?:と思|と感じ|です|かな)"),
            re.compile(r"[0-9A-Za-zぁ-んァ-ヶ一-龯ー]{1,20}(?:の方)?が(?:いい|良い|よい)と思"),
            re.compile(r"(?:一番|最も).{0,16}(?:いい|良い|よい|魅力|気に入)"),
            re.compile(r"(?:選びたい|採用したい|導入したい|使いたい|試したい|気に入った|魅力を感じ)"),
            re.compile(r"(?:この案|その案|提案|意見|方針)(?:に)?賛成"),
        ),
    ),
)


def _content_text(value: Any) -> str:
    return "".join(_CONTENT_CHARACTER_RE.findall(str(value or "")))


def _backchannel_kind(value: Any) -> str | None:
    content = _content_text(value)
    kind = _BACKCHANNELS.get(content)
    if kind:
        return kind
    if re.fullmatch(r"(?:そう){2,4}", content):
        return "agreement"
    if (len(content) <= 16
            and content.endswith(("ありがとうございます", "ありがとうございました"))):
        return "courtesy"
    return None


def _is_meaningful_text(value: Any) -> bool:
    """Reject punctuation, backchannels, and transcription-only filler."""
    text = re.sub(r"\s+", "", str(value or "").strip())
    content = _content_text(text)
    if _backchannel_kind(text) or len(content) < 2 or content in _SHORT_FILLERS:
        return False
    if _REPEATED_FILLER_RE.fullmatch(text) and len(set(content.replace("ー", ""))) <= 2:
        return False
    if (len(content) <= 4 and not re.search(r"[0-9A-Za-z\u3400-\u9fff]", content)
            and content not in _SHORT_SEMANTIC_TERMS):
        return False
    if (len(content) <= 16 and content.endswith(
            ("ありがとうございます", "ありがとうございました", "お疲れ様", "ございました"))):
        return False
    return True


def _contextual_texts(source_segments: list[dict], source_indices: list[int], *,
                      include_manifest: bool = False) -> Any:
    """Add nearby same-speaker text only when the target utterance is fragmentary."""
    values: list[str] = []
    expanded = 0
    manifest = []
    for source_index in source_indices:
        segment = source_segments[source_index]
        current = str(segment.get("text") or "").strip()
        pieces: list[tuple[int, str]] = [(source_index, current)]
        if len(_content_text(current)) < 24:
            speaker = str(segment.get("speaker") or "UNKNOWN")
            for neighbour_index in (source_index - 1, source_index + 1):
                if not 0 <= neighbour_index < len(source_segments):
                    continue
                neighbour = source_segments[neighbour_index]
                if str(neighbour.get("speaker") or "UNKNOWN") != speaker:
                    continue
                gap = (float(segment.get("start") or 0) - float(neighbour.get("end") or 0)
                       if neighbour_index < source_index else
                       float(neighbour.get("start") or 0) - float(segment.get("end") or 0))
                neighbour_text = str(neighbour.get("text") or "").strip()
                if gap <= 3.0 and _is_meaningful_text(neighbour_text):
                    pieces.append((neighbour_index, neighbour_text))
            pieces.sort(key=lambda row: row[0])
        value = " ".join(text for _, text in pieces)
        if len(pieces) > 1:
            expanded += 1
        values.append(value)
        cursor = 0
        target_start = 0
        for piece_index, text in pieces:
            if piece_index == source_index:
                target_start = cursor
            cursor += len(text) + 1
        manifest.append({
            "segment_id": str(segment.get("id") or ""),
            "context_segment_ids": [str(source_segments[index].get("id") or "") for index, _ in pieces],
            "target_character_start": target_start,
            "target_character_end": target_start + len(current),
            "contextual_character_count": len(value),
        })
    return (values, expanded, manifest) if include_manifest else (values, expanded)


def _speaker_weights(segments: list[dict]) -> Any:
    """Reduce domination by a facilitator or fragmented diarization speaker."""
    import numpy as np

    counts = Counter(str(row.get("speaker") or "UNKNOWN") for row in segments)
    weights = np.asarray([1.0 / math.sqrt(counts[str(row.get("speaker") or "UNKNOWN")])
                          for row in segments], dtype="float64")
    return weights / max(float(weights.mean()), 1e-9)


def _dominant_speaker(segments: list[dict]) -> tuple[str | None, float]:
    seconds = Counter()
    for row in segments:
        seconds[str(row.get("speaker") or "UNKNOWN")] += max(
            0.0, float(row.get("end") or 0) - float(row.get("start") or 0),
        )
    total = sum(seconds.values())
    if len(seconds) < 3 or total <= 0:
        return None, 0.0
    speaker, value = seconds.most_common(1)[0]
    share = value / total
    return (speaker if share >= 0.35 else None), share


def _speaker_group(segment: dict, dominant_speaker: str | None) -> str:
    role = str(segment.get("role") or "").strip().lower()
    if role in {"moderator", "facilitator", "interviewer", "host", "司会", "進行"}:
        return "facilitator"
    if role in {"participant", "interviewee", "guest", "参加者", "回答者"}:
        return "participant"
    return "participant"


def _link_backchannels(
    backchannel_segments: list[dict], source_segments: list[dict], assignments: list[dict],
    dominant_speaker: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Link listener responses to a nearby substantive utterance without claiming agreement."""
    assignment_by_id = {str(row["segment_id"]): row for row in assignments}
    source_position = {str(row["id"]): index for index, row in enumerate(source_segments)}
    rows: list[dict[str, Any]] = []
    for segment in backchannel_segments:
        segment_id = str(segment["id"])
        position = source_position[segment_id]
        speaker = str(segment.get("speaker") or "UNKNOWN")
        start = float(segment.get("start") or 0)
        target = None
        link_method = "unassigned"
        gap = None
        for candidate in reversed(source_segments[:position]):
            candidate_row = assignment_by_id.get(str(candidate["id"]))
            if not candidate_row or candidate_row["speaker"] == speaker:
                continue
            candidate_gap = max(0.0, start - float(candidate.get("end") or 0))
            if candidate_gap > 12.0:
                break
            target, link_method, gap = candidate_row, "previous_other_speaker", candidate_gap
            break
        if target is None:
            end = float(segment.get("end") or start)
            for candidate in source_segments[position + 1:]:
                candidate_row = assignment_by_id.get(str(candidate["id"]))
                if not candidate_row or candidate_row["speaker"] == speaker:
                    continue
                candidate_gap = max(0.0, float(candidate.get("start") or 0) - end)
                if candidate_gap > 3.0:
                    break
                target, link_method, gap = candidate_row, "next_other_speaker", candidate_gap
                break
        rows.append({
            "segment_id": segment_id, "speaker": speaker,
            "speaker_name": str(segment.get("speaker_name") or speaker),
            "speaker_group": _speaker_group(segment, dominant_speaker),
            "kind": _backchannel_kind(segment.get("text")) or "acknowledgement",
            "start": round(start, 3), "end": round(float(segment.get("end") or start), 3),
            "text": str(segment.get("text") or ""),
            "topic_id": target["topic_id"] if target else "",
            "topic_label": target["topic_label"] if target else "紐付けなし",
            "responds_to_segment_id": target["segment_id"] if target else "",
            "responds_to_speaker": target["speaker"] if target else "",
            "responds_to_speaker_name": target["speaker_name"] if target else "",
            "time_gap": round(float(gap), 3) if gap is not None else None,
            "link_method": link_method,
        })
    totals = Counter(row["speaker"] for row in rows)
    grouped = Counter((row["speaker"], row["topic_id"]) for row in rows)
    samples = {(row["speaker"], row["topic_id"]): row for row in rows}
    speaker_rows = []
    for (speaker, topic_id), count in sorted(grouped.items(), key=lambda item: (-item[1], item[0])):
        sample = samples[(speaker, topic_id)]
        speaker_rows.append({
            "speaker": speaker, "speaker_name": sample["speaker_name"],
            "speaker_group": sample["speaker_group"], "topic_id": topic_id,
            "topic_label": sample["topic_label"], "backchannel_count": count,
            "speaker_backchannel_percent": round(100 * count / totals[speaker], 3),
        })
    return rows, speaker_rows


def _backchannel_test(
    test_id: str, title: str, dimension: str, matrix: list[list[int]],
    row_labels: list[str], column_labels: list[str],
) -> dict[str, Any]:
    """Run an exploratory chi-square test and retain sparse-cell diagnostics."""
    result = {
        "test_id": test_id, "test": title, "dimension": dimension,
        "n": int(sum(sum(row) for row in matrix)), "row_count": len(row_labels),
        "column_count": len(column_labels), "statistic": None, "df": None,
        "p_value": None, "effect_name": "cramers_v", "effect_size": None,
        "low_expected_cells": None, "expected_cell_count": None,
        "status": "not_computable", "interpretation": "比較に必要な件数または分類数が不足しています。",
        "assumption_note": (
            "同じ話者の反復相づちは独立観測とは限りません。期待度数5未満のセルが多い場合、"
            "カイ二乗検定のp値は参考値として扱ってください。非応答は音声上の相づちがないことから"
            "推定した値で、多重比較補正は行っていません。"
        ),
    }
    nonzero_rows = [(label, row) for label, row in zip(row_labels, matrix) if sum(row) > 0]
    nonzero_columns = [
        index for index in range(len(column_labels))
        if sum(row[index] for _, row in nonzero_rows) > 0
    ]
    cleaned = [[row[index] for index in nonzero_columns] for _, row in nonzero_rows]
    result["row_count"] = len(cleaned)
    result["column_count"] = len(nonzero_columns)
    result["n"] = int(sum(sum(row) for row in cleaned))
    if len(cleaned) < 2 or len(nonzero_columns) < 2 or result["n"] <= 0:
        return result
    try:
        from scipy import stats
    except Exception:
        result.update({
            "status": "unavailable", "interpretation": "SciPyを読み込めないため検定できません。",
        })
        return result
    try:
        statistic, p_value, dof, expected = stats.chi2_contingency(cleaned, correction=False)
        minimum_dimension = min(len(cleaned) - 1, len(nonzero_columns) - 1)
        effect_size = (math.sqrt(float(statistic) / (result["n"] * minimum_dimension))
                       if result["n"] > 0 and minimum_dimension > 0 else 0.0)
        expected_values = [float(value) for row in expected for value in row]
        low_expected = sum(value < 5 for value in expected_values)
        sparse = low_expected / max(1, len(expected_values)) > 0.2
        result.update({
            "statistic": round(float(statistic), 6), "df": int(dof),
            "p_value": float(p_value), "effect_size": round(effect_size, 6),
            "low_expected_cells": low_expected, "expected_cell_count": len(expected_values),
            "status": "computed_sparse" if sparse else "computed",
            "interpretation": (
                "期待度数条件を満たさないため、p値から差を判定しません。記述統計と効果量を確認してください。"
                if sparse else (
                    "分布差の可能性があります。効果量と原文を確認してください。"
                    if float(p_value) < 0.05 else
                    "このデータでは統計的な分布差を確認できませんでした。"
                )
            ),
        })
    except Exception as error:
        result.update({
            "status": "error", "interpretation": "検定計算に失敗しました。",
            "assumption_note": result["assumption_note"] + " " + str(error)[:200],
        })
    return result


def _backchannel_statistics(
    source_segments: list[dict], assignments: list[dict], backchannels: list[dict],
    dominant_speaker: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize listener responses by observable other-speaker utterance opportunities."""
    samples: dict[str, dict] = {}
    speaker_order: list[str] = []
    for row in sorted(source_segments, key=lambda value: float(value.get("start") or 0)):
        speaker = str(row.get("speaker") or "UNKNOWN")
        if speaker not in samples:
            samples[speaker] = row
            speaker_order.append(speaker)
    topic_labels = {str(row.get("topic_id") or ""): str(row.get("topic_label") or "")
                    for row in assignments if row.get("topic_id")}
    topic_ids = sorted(topic_labels)
    rate_rows: list[dict[str, Any]] = []
    for speaker in speaker_order:
        sample = samples[speaker]
        speaker_name = str(sample.get("speaker_name") or speaker)
        speaker_group = _speaker_group(sample, dominant_speaker)
        for topic_id in ["", *topic_ids]:
            scoped_assignments = [
                row for row in assignments
                if str(row.get("speaker") or "UNKNOWN") != speaker
                and (not topic_id or str(row.get("topic_id") or "") == topic_id)
            ]
            scoped_backchannels = [
                row for row in backchannels
                if row["speaker"] == speaker
                and (not topic_id or row["topic_id"] == topic_id)
            ]
            responded_targets = {
                str(row["responds_to_segment_id"]) for row in scoped_backchannels
                if row.get("responds_to_segment_id")
            }
            opportunity_count = len(scoped_assignments)
            backchannel_count = len(scoped_backchannels)
            kind_counts = Counter(row["kind"] for row in scoped_backchannels)
            rate_rows.append({
                "scope": "overall" if not topic_id else "topic",
                "speaker": speaker, "speaker_name": speaker_name,
                "speaker_group": speaker_group, "topic_id": topic_id or "ALL",
                "topic_label": topic_labels.get(topic_id, "全話題"),
                "opportunity_count": opportunity_count,
                "responded_target_count": len(responded_targets),
                "response_rate_percent": round(100 * len(responded_targets) / opportunity_count, 3)
                                         if opportunity_count else None,
                "backchannel_count": backchannel_count,
                "backchannels_per_100_opportunities": round(100 * backchannel_count / opportunity_count, 3)
                                                     if opportunity_count else None,
                "linked_count": sum(bool(row.get("responds_to_segment_id")) for row in scoped_backchannels),
                "unlinked_count": sum(not row.get("responds_to_segment_id") for row in scoped_backchannels),
                "agreement_count": kind_counts["agreement"],
                "continuer_count": kind_counts["continuer"],
                "confirmation_count": kind_counts["confirmation"],
                "courtesy_count": kind_counts["courtesy"],
            })

    participant_totals = [
        row for row in rate_rows
        if row["scope"] == "overall" and row["speaker_group"] == "participant"
        and row["speaker"] != "UNKNOWN" and row["opportunity_count"] > 0
    ]
    response_matrix = [[
        row["responded_target_count"],
        max(0, row["opportunity_count"] - row["responded_target_count"]),
    ] for row in participant_totals]
    tests = [_backchannel_test(
        "response_by_speaker", "話者別の相づち応答率", "話者 × 応答有無",
        response_matrix, [row["speaker_name"] for row in participant_totals], ["応答あり", "応答なし"],
    )]

    kinds = ["agreement", "continuer", "confirmation", "courtesy"]
    kind_matrix = [[row[f"{kind}_count"] for kind in kinds] for row in participant_totals]
    tests.append(_backchannel_test(
        "kind_by_speaker", "話者別の相づち種類分布", "話者 × 相づち種類",
        kind_matrix, [row["speaker_name"] for row in participant_totals], kinds,
    ))
    participant_backchannels = [
        row for row in backchannels
        if row["speaker"] != "UNKNOWN"
        and _speaker_group(samples.get(row["speaker"], row), dominant_speaker) == "participant"
        and row.get("topic_id")
    ]
    topic_kind_matrix = [[
        sum(1 for row in participant_backchannels
            if row["topic_id"] == topic_id and row["kind"] == kind)
        for kind in kinds
    ] for topic_id in topic_ids]
    tests.append(_backchannel_test(
        "kind_by_topic", "話題別の相づち種類分布", "話題 × 相づち種類",
        topic_kind_matrix, [topic_labels[topic_id] for topic_id in topic_ids], kinds,
    ))
    return rate_rows, tests


def _detect_speaker_results(value: Any) -> list[dict[str, str]]:
    """Find unverified wording candidates; lexical matches never establish personal outcomes."""
    text = re.sub(r"\s+", "", str(value or ""))
    detected: dict[str, dict[str, str]] = {}
    for sentence in re.split(r"(?<=[。！？!?])", text):
        # Conservative lexical guards. These are exclusions, not a semantic validator:
        # an omitted subject still needs researcher review, as do all retained matches.
        if not sentence or re.search(r'[「」『』“”"?？]', sentence):
            continue
        if re.search(r"(?:彼女?|他の人|その人|参加者|先生|上司|友人)(?:たち)?(?:は|が)|"
                     r"(?:と言|と話|と聞|らしい|そうです|そうだ|とのこと)|"
                     r"(?:もし|仮に)|(?:なら|たら|れば)", sentence):
            continue
        for code, label, _confidence, patterns in _SPEAKER_RESULT_DEFINITIONS:
            for pattern in patterns:
                for match in pattern.finditer(sentence):
                    suffix = sentence[match.end():match.end() + 28]
                    negated = re.search(
                        r"^(?:(?![。！？!?、]).){0,24}(?:ない|なかった|ません|ぬ|ず|なく|否定|反対)", suffix)
                    # The unchanged cue includes its own negation. A later negation
                    # still blocks it (e.g. '変わらないとは言えません').
                    if negated:
                        continue
                    detected.setdefault(code, {
                        "result_code": code, "result_label": label + "（表現候補）",
                        "confidence": "unverified_candidate", "matched_cue": match.group(0),
                    })
    if {"opinion_changed", "opinion_maintained"} <= detected.keys():
        changed = detected.pop("opinion_changed")
        maintained = detected.pop("opinion_maintained")
        detected["outcome_ambiguous"] = {
            "result_code": "outcome_ambiguous", "result_label": "変化・維持の表現が混在（要確認）",
            "confidence": "unverified_candidate",
            "matched_cue": changed["matched_cue"] + " / " + maintained["matched_cue"],
        }
    return list(detected.values())


def _speaker_results(
    source_segments: list[dict], assignments: list[dict], dominant_speaker: str | None,
) -> list[dict[str, Any]]:
    """Build one or more evidence-linked meeting outcomes for every speaker."""
    ordered_source = sorted(source_segments, key=lambda row: (
        float(row.get("start") or 0), float(row.get("end") or 0), str(row.get("id") or ""),
    ))
    sources_by_speaker: dict[str, list[dict]] = defaultdict(list)
    for row in ordered_source:
        sources_by_speaker[str(row.get("speaker") or "UNKNOWN")].append(row)
    assignments_by_speaker: dict[str, list[dict]] = defaultdict(list)
    for row in sorted(assignments, key=lambda value: (
        float(value.get("start") or 0), float(value.get("end") or 0), str(value.get("segment_id") or ""),
    )):
        assignments_by_speaker[str(row.get("speaker") or "UNKNOWN")].append(row)

    results: list[dict[str, Any]] = []
    for speaker, source_rows in sources_by_speaker.items():
        speaker_assignments = assignments_by_speaker.get(speaker, [])
        sample = speaker_assignments[0] if speaker_assignments else source_rows[0]
        speaker_group = str(sample.get("speaker_group") or _speaker_group(sample, dominant_speaker))
        first_segment_id = str(source_rows[0].get("id") or source_rows[0].get("segment_id") or "")
        last_segment_id = str(source_rows[-1].get("id") or source_rows[-1].get("segment_id") or "")
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for assignment in speaker_assignments if speaker_group == "participant" else []:
            for detected in _detect_speaker_results(assignment.get("text")):
                key = (detected["result_code"], str(assignment.get("topic_id") or ""))
                target = grouped.setdefault(key, {
                    "speaker": speaker,
                    "speaker_name": str(sample.get("speaker_name") or speaker),
                    "speaker_group": speaker_group,
                    "result_code": detected["result_code"],
                    "result_label": detected["result_label"],
                    "topic_id": str(assignment.get("topic_id") or ""),
                    "topic_label": str(assignment.get("topic_label") or "紐付けなし"),
                    "confidence": detected["confidence"],
                    "review_status": "unreviewed", "researcher_review_required": True,
                    "registered_role": str(source_rows[0].get("role") or "unknown"),
                    "role_source": str(source_rows[0].get("role_source") or ("registered" if source_rows[0].get("role") else "unknown")),
                    "basis": "語句に一致した未確認の表現候補です。否定・引用・主語・前後文脈を研究者が照合し、本人の変化と解釈できるか確認してください。",
                    "matched_cues": [], "evidence_segment_ids": [], "evidence_texts": [],
                    "first_segment_id": first_segment_id, "last_segment_id": last_segment_id,
                })
                segment_id = str(assignment.get("segment_id") or "")
                if segment_id and segment_id not in target["evidence_segment_ids"]:
                    target["evidence_segment_ids"].append(segment_id)
                    target["evidence_texts"].append(str(assignment.get("text") or ""))
                cue = detected["matched_cue"]
                if cue not in target["matched_cues"]:
                    target["matched_cues"].append(cue)
        if grouped:
            results.extend(grouped.values())
            continue

        topic_counts = Counter(str(row.get("topic_id") or "") for row in speaker_assignments)
        main_topic_id = topic_counts.most_common(1)[0][0] if topic_counts else ""
        topic_sample = next((row for row in reversed(speaker_assignments)
                             if str(row.get("topic_id") or "") == main_topic_id), None)
        evidence_row = speaker_assignments[-1] if speaker_assignments else None
        not_applicable = speaker_group == "facilitator"
        results.append({
            "speaker": speaker,
            "speaker_name": str(sample.get("speaker_name") or speaker),
            "speaker_group": speaker_group,
            "result_code": "not_applicable" if not_applicable else "undetermined",
            "result_label": "進行役のため参加者リザルト対象外" if not_applicable else "明示的な結果は未判定",
            "topic_id": main_topic_id,
            "topic_label": str((topic_sample or {}).get("topic_label") or "紐付けなし"),
            "confidence": "not_applicable" if not_applicable else "insufficient_evidence",
            "review_status": "not_applicable" if not_applicable else "unreviewed",
            "researcher_review_required": not not_applicable,
            "registered_role": str(source_rows[0].get("role") or "unknown"),
            "role_source": str(source_rows[0].get("role_source") or ("registered" if source_rows[0].get("role") else "unknown")),
            "basis": ("登録された進行役・司会者のため、参加者の態度変化としては判定しません。"
                      if not_applicable else
                      "意見の変化・維持、新しい気づき、支持・選好を示す明示表現を検出できませんでした。"),
            "matched_cues": [],
            "evidence_segment_ids": ([str(evidence_row.get("segment_id"))] if evidence_row else []),
            "evidence_texts": ([str(evidence_row.get("text") or "")] if evidence_row else []),
            "first_segment_id": first_segment_id, "last_segment_id": last_segment_id,
        })
    return results


def _fingerprint(payload: dict) -> str:
    import hashlib
    import json

    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def transformer_embedding_fingerprint(analysis: dict, *, model: str = DEFAULT_MODEL,
                                      revision: str = "") -> str:
    """Only dependencies of contextual input vectors, separate from analysis settings."""
    return _fingerprint({
        "embedding_input_version": EMBEDDING_INPUT_VERSION, "model": model, "revision": revision,
        "max_characters": MAX_TEXT_CHARACTERS, "max_tokens": MAX_EMBEDDING_TOKENS,
        "segments": [{key: row.get(key) for key in
                      ("id", "speaker", "start", "end", "text", "excluded")}
                     for row in analysis.get("segments", [])],
    })


def transformer_input_fingerprint(analysis: dict, *, model: str = DEFAULT_MODEL,
                                  parameters: dict | None = None) -> str:
    """Fingerprint all result dependencies, including settings and theme definitions."""
    prepared = analysis.get("manual", {}).get("preparation", {})
    return _fingerprint({
        "algorithm": TRANSFORMER_ANALYSIS_VERSION, "model": model,
        "parameters": parameters or {}, "config": analysis.get("config", {}),
        "input_version": prepared.get("input_version"), "source_hash": prepared.get("source_hash"),
        "source_revision": analysis.get("item", {}).get("revision_count"),
        "analysis_revision": analysis.get("item", {}).get("analysis_revision"),
        "segments": [{key: row.get(key) for key in
                      ("id", "speaker", "speaker_name", "role", "role_source", "start", "end",
                       "valid_time", "time_unknown", "text", "excluded")}
                     for row in analysis.get("segments", [])],
    })


def transformer_source_provenance(analysis: dict) -> dict[str, Any]:
    """Immutable generation input identity. Unknown legacy fields must remain unknown."""
    from copy import deepcopy

    item = analysis.get("item", {})
    prepared = analysis.get("manual", {}).get("preparation", {})
    return {
        "status": "recorded", "item_id": item.get("id"), "source_name": item.get("source_name"),
        "source_revision": item.get("revision_count"), "analysis_revision": item.get("analysis_revision"),
        "analysis_updated_at": item.get("analysis_updated_at"),
        "input_version": prepared.get("input_version"), "source_hash": prepared.get("source_hash"),
        "analysis_needs_review": prepared.get("analysis_needs_review", True),
        "config": deepcopy(analysis.get("config", {})),
    }


def _package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return ""


def _load_model(model_name: str, revision: str = "") -> tuple[Any, Any, str]:
    if model_name == DEFAULT_MODEL:
        standard_revision = EMBEDDING_STANDARD_V1["model_revision"]
        if revision and revision != standard_revision:
            raise ValueError("埋め込み標準 v1 のモデルrevisionと一致しません。再計算してください。")
        revision = standard_revision
    key = (model_name, revision)
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except Exception as error:
            raise RuntimeError(
                "Transformer本文分析の実行環境がありません。run.batを再実行して依存関係を更新してください。"
            ) from error
        kwargs = {"revision": revision} if revision else {}
        model = AutoModel.from_pretrained(model_name, **kwargs)
        resolved = str(getattr(getattr(model, "config", None), "_commit_hash", "") or revision)
        if revision and resolved != revision:
            raise ValueError("要求したモデルrevisionと読み込んだモデルrevisionが一致しません。")
        tokenizer = AutoTokenizer.from_pretrained(model_name, **({"revision": resolved} if resolved else kwargs))
        requested_device = os.environ.get("MOJIOKOSI_TRANSFORMER_DEVICE", "cpu").strip().lower()
        if requested_device not in {"cpu", "cuda", "auto"}:
            raise RuntimeError("MOJIOKOSI_TRANSFORMER_DEVICEはcpu、cuda、autoのいずれかで指定してください。")
        device = "cuda" if requested_device in {"cuda", "auto"} and torch.cuda.is_available() else "cpu"
        if requested_device == "cuda" and device != "cuda":
            raise RuntimeError("Transformer本文分析にCUDAが指定されていますが利用できません。")
        model.to(device)
        model.eval()
        cached = (tokenizer, model, device)
        _MODEL_CACHE[key] = cached
        resolved_revision = str(getattr(getattr(model, "config", None), "_commit_hash", "") or "")
        if resolved_revision:
            _MODEL_CACHE[(model_name, resolved_revision)] = cached
        return cached


def encode_texts(
    texts: list[str], *, model_name: str = DEFAULT_MODEL, revision: str = "",
    kind: str = "passage", progress: Callable[[int, str], None] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Encode and L2-normalize texts using E5 mean pooling."""
    import numpy as np
    import torch

    tokenizer, model, device = _load_model(model_name, revision)
    batch_size = 24 if device == "cuda" else 8
    vectors = []
    input_diagnostics = []
    prefix = "query: " if kind == "query" else "passage: "
    for offset in range(0, len(texts), batch_size):
        if check_cancelled:
            check_cancelled()
        batch = [prefix + value[:MAX_TEXT_CHARACTERS] for value in texts[offset:offset + batch_size]]
        full_inputs = tokenizer(batch, padding=False, truncation=False)
        try:
            inputs = tokenizer(batch, max_length=MAX_EMBEDDING_TOKENS, padding=True,
                               truncation=True, return_tensors="pt", return_offsets_mapping=True)
        except (NotImplementedError, TypeError):
            inputs = tokenizer(batch, max_length=MAX_EMBEDDING_TOKENS, padding=True,
                               truncation=True, return_tensors="pt")
        offsets = inputs.pop("offset_mapping", None)
        for index, original in enumerate(texts[offset:offset + batch_size]):
            token_count = len(full_inputs["input_ids"][index])
            used_tokens = int(inputs["attention_mask"][index].sum().item())
            retained_start, retained_end = None, None
            if offsets is not None:
                positions = offsets[index].tolist() if hasattr(offsets[index], "tolist") else offsets[index]
                positions = [(int(start), int(end)) for start, end in positions if int(end) > len(prefix)]
                if positions:
                    retained_start = max(0, min(start for start, _ in positions) - len(prefix))
                    retained_end = max(0, max(end for _, end in positions) - len(prefix))
            elif token_count <= used_tokens:
                retained_start, retained_end = 0, min(len(original), MAX_TEXT_CHARACTERS)
            input_diagnostics.append({
                "input_index": offset + index, "character_count": len(original),
                "character_limit": MAX_TEXT_CHARACTERS,
                "character_truncated": len(original) > MAX_TEXT_CHARACTERS,
                "token_count_after_character_limit": token_count, "used_token_count": used_tokens,
                "token_limit": MAX_EMBEDDING_TOKENS, "token_truncated": token_count > used_tokens,
                "retained_character_start": retained_start, "retained_character_end": retained_end,
                "retained_range_status": "measured" if retained_end is not None else "unavailable",
                "truncation_side": str(getattr(tokenizer, "truncation_side", "right")),
            })
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.inference_mode():
            hidden = model(**inputs).last_hidden_state
            mask = inputs["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
        vectors.append(pooled.detach().cpu().numpy().astype("float32"))
        if progress:
            done = min(len(texts), offset + len(batch))
            progress(10 + int(50 * done / max(1, len(texts))), f"発話を意味ベクトル化しています（{done}/{len(texts)}）")
    matrix = np.concatenate(vectors, axis=0) if vectors else np.empty((0, 0), dtype="float32")
    commit = str(getattr(getattr(model, "config", None), "_commit_hash", "") or revision)
    if model_name == DEFAULT_MODEL and texts:
        if (commit != EMBEDDING_STANDARD_V1["model_revision"]
                or matrix.shape[1] != EMBEDDING_STANDARD_V1["dimensions"]):
            raise ValueError("埋め込み標準 v1 のモデル版・次元が一致しません。再計算してください。")
    return matrix, {
        "name": model_name,
        "revision": commit,
        "framework": "Transformers",
        "framework_version": _package_version("transformers"),
        "device": device,
        "dimensions": int(matrix.shape[1]) if matrix.ndim == 2 and matrix.size else 0,
        "revision_pinned": bool(commit), "input_diagnostics": input_diagnostics,
    }


def _choose_labels(
    vectors: Any, max_topics: int, min_topic_size: int, *, topic_count: int | None = None,
    sample_weights: Any | None = None,
) -> tuple[Any, float | None, list[dict[str, Any]]]:
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    count = len(vectors)
    if count < max(4, min_topic_size * 2) and topic_count is None:
        return np.zeros(count, dtype=int), None, []
    maximum = min(max_topics, count // min_topic_size, count - 1)
    if maximum < 2 and topic_count is None:
        return np.zeros(count, dtype=int), None, []
    # Every candidate is scored even when one count is requested, so the researcher
    # keeps seeing the list the choice came from.
    candidates = sorted({*range(2, maximum + 1), *([topic_count] if topic_count else [])})
    best_labels, best_score = None, -2.0
    chosen_labels, chosen_score = None, None
    scores: list[dict[str, Any]] = []
    for clusters in candidates:
        if clusters is None or not 2 <= clusters < count:
            continue
        estimator = KMeans(n_clusters=clusters, random_state=42, n_init=10)
        estimator.fit(vectors, sample_weight=sample_weights)
        labels = estimator.labels_
        actual_count = len(set(int(value) for value in labels))
        if actual_count != clusters:
            scores.append({"topic_count": int(clusters), "actual_topic_count": actual_count,
                           "silhouette_cosine": None, "status": "invalid_topic_count",
                           "reason": "指定テーマ数に必要な異なるクラスタが成立しませんでした。"})
            continue
        score = float(silhouette_score(
            vectors, labels, metric="cosine", sample_size=min(1000, count), random_state=42,
        ))
        scores.append({"topic_count": int(clusters), "actual_topic_count": actual_count,
                       "silhouette_cosine": round(score, 6), "status": "valid"})
        if clusters == topic_count:
            chosen_labels, chosen_score = labels, score
        # Prefer the simpler solution when scores are effectively equal.
        if score > best_score + 0.005:
            best_labels, best_score = labels, score
    if topic_count is not None:
        if chosen_labels is None:
            raise ValueError(
                "指定したテーマ数ではクラスタを作れませんでした。テーマ数を減らすか、対象の発話を増やしてください。"
            )
        return chosen_labels, chosen_score, scores
    return (best_labels if best_labels is not None else np.zeros(count, dtype=int),
            best_score if best_labels is not None else None, scores)


def _manual_theme_vectors(
    manual_topics: list[dict], segments: list[dict], vectors: Any, *,
    model_name: str, revision: str,
    progress: Callable[[int, str], None] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[Any, list[int], dict[str, Any] | None]:
    """Build one vector per researcher-defined theme from its wording and seed utterances."""
    import numpy as np

    position = {str(row["id"]): index for index, row in enumerate(segments)}
    descriptors: list[str] = []
    descriptor_rows: dict[int, int] = {}
    for index, topic in enumerate(manual_topics):
        cues = " ".join(str(value) for value in (topic.get("cues") or []))
        text = " ".join(part for part in (str(topic.get("label") or ""), cues) if part).strip()
        if text:
            descriptor_rows[index] = len(descriptors)
            descriptors.append(text)
    descriptor_vectors, engine = None, None
    if descriptors:
        if not revision:
            raise ValueError("発話ベクトルのモデルrevisionが不明です。再計算してください。")
        descriptor_vectors, engine = encode_texts(
            descriptors, model_name=model_name, revision=revision, kind="query",
            progress=progress, check_cancelled=check_cancelled,
        )
        if not revision or str(engine.get("revision") or "") != revision or str(engine.get("name") or "") != model_name:
            raise ValueError("テーマと発話のモデルrevisionが一致しません。保存済みベクトルを再計算してください。")
        if descriptor_vectors.shape[1] != vectors.shape[1]:
            raise ValueError("テーマの説明文と発話の意味ベクトルの次元が一致しません。")
    theme_vectors = np.zeros((len(manual_topics), vectors.shape[1]), dtype="float32")
    seed_counts: list[int] = []
    for index, topic in enumerate(manual_topics):
        parts = []
        if index in descriptor_rows:
            parts.append(descriptor_vectors[descriptor_rows[index]])
        seeds = [position[str(value)] for value in (topic.get("seed_segment_ids") or [])
                 if str(value) in position]
        seed_counts.append(len(seeds))
        if seeds:
            parts.append(vectors[seeds].mean(axis=0))
        if not parts:
            name = topic.get("label") or index + 1
            raise ValueError(
                f"テーマ「{name}」のシード発話IDが分析対象に見つかりません。手がかり語を入れるか、"
                "分析対象の発話IDを指定してください。"
                if topic.get("seed_segment_ids") else
                f"テーマ「{name}」に手がかり語もシード発話もありません。"
            )
        vector = np.asarray(parts, dtype="float32").mean(axis=0)
        theme_vectors[index] = vector / max(float(np.linalg.norm(vector)), 1e-9)
    return theme_vectors, seed_counts, engine


def _manual_labels(vectors: Any, theme_vectors: Any, min_similarity: float) -> Any:
    """Put every utterance on its nearest researcher-defined theme, or leave it unassigned."""
    import numpy as np

    similarity = vectors @ theme_vectors.T
    best = similarity.argmax(axis=1)
    best_score = similarity[np.arange(len(vectors)), best]
    return np.where(best_score >= float(min_similarity), best, -1).astype(int)


def _assignment_silhouette(vectors: Any, labels: Any) -> float | None:
    """Describe how separated the assigned groups are; never a check on their meaning."""
    import numpy as np
    from sklearn.metrics import silhouette_score

    mask = labels >= 0
    assigned = vectors[mask]
    values = labels[mask]
    distinct = len(set(int(value) for value in values))
    if len(assigned) < 4 or not 2 <= distinct <= len(assigned) - 1:
        return None
    return float(silhouette_score(
        assigned, values, metric="cosine", sample_size=min(1000, len(assigned)), random_state=42,
    ))


def _topic_terms(segment_ids: set[str], morphemes: list[dict], total_segments: int) -> list[str]:
    by_term: dict[str, set[str]] = defaultdict(set)
    global_by_term: dict[str, set[str]] = defaultdict(set)
    for token in morphemes:
        if token.get("excluded") or not token.get("is_content") or token.get("is_stop"):
            continue
        term = str(token.get("normalized") or token.get("lemma") or token.get("surface") or "").strip()
        segment_id = str(token.get("segment_id") or "")
        if not term or not segment_id or term in _LABEL_STOP_TERMS or _REPEATED_FILLER_RE.fullmatch(term):
            continue
        global_by_term[term].add(segment_id)
        if segment_id in segment_ids:
            by_term[term].add(segment_id)
    scored = []
    for term, ids in by_term.items():
        if len(global_by_term[term]) / max(1, total_segments) >= 0.35:
            continue
        score = len(ids) * (math.log((total_segments + 1) / (len(global_by_term[term]) + 1)) + 1)
        scored.append((score, len(ids), term))
    scored.sort(key=lambda row: (-row[0], -row[1], row[2]))
    return [row[2] for row in scored[:5]]


def _representative_indices(
    indices: Any, similarities: dict[int, float], segments: list[dict], dominant_speaker: str | None,
) -> list[int]:
    """Prefer substantive evidence and distinct participant voices."""
    candidates = []
    for raw_index in indices:
        index = int(raw_index)
        segment = segments[index]
        speaker = str(segment.get("speaker") or "UNKNOWN")
        text = str(segment.get("text") or "")
        content_length = len(_content_text(text))
        if content_length < 12 or re.search(r"(.)\1{5,}", text):
            continue
        length_bonus = min(content_length, 120) / 2000
        role = str(segment.get("role") or "").lower()
        participant_bonus = 0.025 if role in {"participant", "interviewee", "guest"} else 0.0
        dominant_penalty = 0.04 if _speaker_group(segment, dominant_speaker) == "facilitator" else 0.0
        candidates.append((similarities[index] + length_bonus + participant_bonus - dominant_penalty,
                           similarities[index], index, speaker))
    candidates.sort(key=lambda row: (-row[0], -row[1], row[2]))
    if not candidates:
        candidates = [(similarities[int(index)], similarities[int(index)], int(index),
                       str(segments[int(index)].get("speaker") or "UNKNOWN"))
                      for index in indices if _is_meaningful_text(segments[int(index)].get("text"))]
        candidates.sort(key=lambda row: (-row[0], row[2]))
    chosen: list[int] = []
    speakers: set[str] = set()
    for _, _, index, speaker in candidates:
        if speaker in speakers:
            continue
        chosen.append(index)
        speakers.add(speaker)
        if len(chosen) == 3:
            return chosen
    for _, _, index, _ in candidates:
        if index not in chosen:
            chosen.append(index)
        if len(chosen) == 3:
            break
    return chosen


def _pack_vectors(vectors: Any, segment_ids: list[str]) -> dict[str, Any]:
    import numpy as np

    quantized = np.clip(np.rint(vectors * 127), -127, 127).astype(np.int8)
    return {
        "encoding": "base64-int8", "scale": 127, "dimensions": int(quantized.shape[1]),
        "segment_ids": segment_ids,
        "data": base64.b64encode(quantized.tobytes()).decode("ascii"),
    }


def _unpack_vectors(payload: dict) -> Any:
    import numpy as np

    dimensions = int(payload.get("dimensions") or 0)
    segment_ids = list(payload.get("segment_ids") or [])
    if payload.get("encoding") != "base64-int8" or dimensions <= 0:
        raise ValueError("保存済み意味ベクトルの形式が正しくありません。")
    raw = base64.b64decode(str(payload.get("data") or ""), validate=True)
    values = np.frombuffer(raw, dtype=np.int8)
    if values.size != len(segment_ids) * dimensions:
        raise ValueError("保存済み意味ベクトルの件数が一致しません。")
    vectors = values.reshape(len(segment_ids), dimensions).astype("float32") / float(payload.get("scale") or 127)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-9)


def saved_embeddings(
    saved: Any, analysis: dict, *, model: str = DEFAULT_MODEL,
) -> tuple[Any, list[str], dict[str, Any]] | None:
    """Return stored vectors when they still describe the current input, else None."""
    if not isinstance(saved, dict) or not isinstance(saved.get("vectors"), dict):
        return None
    engine = saved.get("engine") if isinstance(saved.get("engine"), dict) else {}
    if str(engine.get("name") or model) != model:
        return None
    revision = str(engine.get("revision") or "")
    if not revision:
        return None
    if str(saved.get("embedding_fingerprint") or "") != transformer_embedding_fingerprint(
            analysis, model=model, revision=revision):
        return None
    try:
        vectors = _unpack_vectors(saved["vectors"])
    except (ValueError, TypeError):
        return None
    segment_ids = [str(value) for value in (saved["vectors"].get("segment_ids") or [])]
    if len(segment_ids) != len(vectors):
        return None
    return vectors, segment_ids, {**engine, "vector_source": "saved-int8"}


def analyze_transformer_topics(
    analysis: dict, morphemes: list[dict], *, model_name: str = DEFAULT_MODEL,
    revision: str = "", max_topics: int = DEFAULT_MAX_TOPICS,
    min_topic_size: int = DEFAULT_MIN_TOPIC_SIZE, topic_count: int | None = None,
    mode: str = "auto", manual_topics: list[dict] | None = None,
    manual_min_similarity: float = DEFAULT_MANUAL_MIN_SIMILARITY,
    embeddings: Any | None = None,
    embedding_segment_ids: list[str] | None = None,
    engine: dict[str, Any] | None = None,
    previous_candidates: list[dict] | None = None,
    progress: Callable[[int, str], None] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Group utterances by mode—automatic, a chosen candidate count, or researcher themes."""
    import numpy as np

    max_topics = min(12, max(2, int(max_topics)))
    min_topic_size = min(20, max(2, int(min_topic_size)))
    mode = str(mode or "auto")
    if mode not in TOPIC_MODES:
        raise ValueError("テーマの決め方は自動・候補・手動のいずれかで指定してください。")
    manual_topics = [row for row in (manual_topics or []) if isinstance(row, dict)]
    manual_min_similarity = min(0.95, max(0.0, float(manual_min_similarity)))
    if mode == "manual":
        if not 2 <= len(manual_topics) <= MAX_MANUAL_TOPICS:
            raise ValueError(f"手動のテーマは2〜{MAX_MANUAL_TOPICS}件で定義してください。")
        topic_count = None
    elif topic_count is not None:
        # A requested count is the researcher's choice, whatever the caller named the mode.
        mode = "candidate"
    elif mode == "candidate":
        raise ValueError("候補から選ぶときは、テーマ数を指定してください。")
    if topic_count is not None:
        topic_count = int(topic_count)
        if not 2 <= topic_count <= 12:
            raise ValueError("固定するテーマ数は2〜12で指定してください。")
    source_segments = [row for row in analysis.get("segments", [])
                       if not row.get("excluded") and str(row.get("text") or "").strip()]
    if not source_segments:
        raise ValueError("Transformer分析に利用できる発話がありません。")
    if len(source_segments) > MAX_SEGMENTS:
        raise ValueError(f"Transformer分析は1回{MAX_SEGMENTS}発話までです。対象を分割してください。")
    source_indices = [index for index, row in enumerate(source_segments)
                      if _is_meaningful_text(row.get("text"))]
    analyzed_index_set = set(source_indices)
    backchannel_segments = [row for index, row in enumerate(source_segments)
                            if index not in analyzed_index_set
                            and _backchannel_kind(row.get("text"))]
    backchannel_ids = {str(row["id"]) for row in backchannel_segments}
    ignored_segments = [row for index, row in enumerate(source_segments)
                        if index not in analyzed_index_set and str(row["id"]) not in backchannel_ids]
    segments = [source_segments[index] for index in source_indices]
    if len(segments) < 2:
        raise ValueError("相づちや空文字を除くと、Transformer分析に利用できる発話が不足しています。")
    if topic_count is not None and topic_count >= len(segments):
        raise ValueError("固定するテーマ数は分析対象発話数より少なくしてください。")
    texts, context_expanded_count, context_manifest = _contextual_texts(
        source_segments, source_indices, include_manifest=True)
    reused_embeddings = embeddings is not None
    if embedding_segment_ids is not None:
        if list(embedding_segment_ids) != [str(row["id"]) for row in segments]:
            raise ValueError("保存済み意味ベクトルの対象発話が現在の対象と一致しません。")
    if embeddings is None:
        embeddings, engine = encode_texts(
            texts, model_name=model_name, revision=revision, kind="passage",
            progress=progress, check_cancelled=check_cancelled,
        )
    vectors = np.asarray(embeddings, dtype="float32")
    if (vectors.ndim == 2 and vectors.shape[0] == len(source_segments)
            and len(segments) != len(source_segments)):
        vectors = vectors[source_indices]
    if vectors.ndim != 2 or vectors.shape[0] != len(segments) or vectors.shape[1] < 2:
        raise ValueError("発話数と意味ベクトルの件数が一致しません。")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms <= 1e-9) or not np.all(np.isfinite(vectors)):
        raise ValueError("意味ベクトルに解析できない値があります。")
    vectors = vectors / norms
    engine = engine or {"name": model_name, "framework": "test", "dimensions": int(vectors.shape[1])}
    vector_revision = str(engine.get("revision") or "")
    if revision and vector_revision != revision:
        raise ValueError("発話ベクトルのモデルrevisionが要求と一致しません。")
    theme_vectors = None
    seed_counts: list[int] = []
    if mode == "manual":
        if progress:
            progress(65, "研究者が定義したテーマへ発話を割り当てています。")
        theme_vectors, seed_counts, descriptor_engine = _manual_theme_vectors(
            manual_topics, segments, vectors, model_name=model_name, revision=vector_revision,
            check_cancelled=check_cancelled,
        )
        engine = engine or descriptor_engine
        labels = _manual_labels(vectors, theme_vectors, manual_min_similarity)
        silhouette = _assignment_silhouette(vectors, labels)
        cluster_candidates = [row for row in (previous_candidates or []) if isinstance(row, dict)]
        cluster_order = list(range(len(manual_topics)))
    else:
        if progress:
            progress(65, "テーマ候補をクラスタリングしています。")
        sample_weights = _speaker_weights(segments)
        labels, silhouette, cluster_candidates = _choose_labels(
            vectors, max_topics, min_topic_size, topic_count=topic_count,
            sample_weights=sample_weights,
        )
        counts = Counter(int(value) for value in labels)
        retained = (set(counts) if topic_count is not None
                    else {label for label, count in counts.items() if count >= min_topic_size})
        if not retained:
            retained = {counts.most_common(1)[0][0]}
        cluster_order = sorted(retained, key=lambda label: (-counts[label], label))
    topic_ids = {label: f"T{index:02d}" for index, label in enumerate(cluster_order, 1)}
    unassigned_label = "どのテーマにも近くない" if mode == "manual" else "小規模クラスタ候補"
    dominant_speaker, dominant_share = _dominant_speaker(segments)
    topic_data: dict[int, dict[str, Any]] = {}
    for label in cluster_order:
        indices = np.where(labels == label)[0]
        if mode == "manual":
            centroid = theme_vectors[label]
        else:
            centroid = vectors[indices].mean(axis=0)
            centroid /= max(float(np.linalg.norm(centroid)), 1e-9)
        similarities = vectors[indices] @ centroid
        segment_ids = {str(segments[index]["id"]) for index in indices}
        participant_segment_ids = {
            str(segments[index]["id"]) for index in indices
            if _speaker_group(segments[index], dominant_speaker) == "participant"
        }
        keyword_segment_ids = (participant_segment_ids
                               if len(participant_segment_ids) >= min(3, len(segment_ids))
                               else segment_ids)
        keywords = _topic_terms(keyword_segment_ids, morphemes, len(segments))
        similarity_map = {int(index): float(score) for index, score in zip(indices, similarities)}
        manual_topic = manual_topics[label] if mode == "manual" else {}
        manual_cues = [str(value) for value in (manual_topic.get("cues") or [])]
        topic_data[label] = {
            "id": topic_ids[label], "indices": indices, "centroid": centroid,
            "similarities": similarity_map,
            "representatives": _representative_indices(indices, similarity_map, segments, dominant_speaker),
            "keywords": manual_cues or keywords,
            "origin": "manual" if mode == "manual" else "kmeans",
            "label": (str(manual_topic.get("label") or "").strip()
                      or ("・".join(keywords[:3]) if keywords
                          else f"テーマ候補 {topic_ids[label][1:]}")),
            "seed_segment_count": seed_counts[label] if mode == "manual" else 0,
            "auto_keywords": keywords,
        }

    assignments = []
    evidence = {}
    topic_rows = []
    speaker_rows = []
    for label in cluster_order:
        data = topic_data[label]
        indices = data["indices"]
        speaker_counts = Counter(str(segments[index].get("speaker") or "UNKNOWN") for index in indices)
        group_counts = Counter(_speaker_group(segments[index], dominant_speaker) for index in indices)
        topic_seconds = sum(max(0.0, float(segments[index].get("end") or 0) - float(segments[index].get("start") or 0)) for index in indices)
        topic_rows.append({
            "topic_id": data["id"], "label": data["label"], "origin": data["origin"],
            "keywords": data["keywords"],
            "segment_count": len(indices), "speaker_count": len(speaker_counts),
            "participant_segment_count": group_counts["participant"],
            "facilitator_segment_count": (group_counts["facilitator"]
                                           + group_counts["facilitator_candidate"]),
            "speaking_seconds": round(topic_seconds, 3),
            "average_similarity": (
                round(float(np.mean([data["similarities"][int(index)] for index in indices])), 6)
                if len(indices) else None),
            "representative_segment_ids": [str(segments[index]["id"]) for index in data["representatives"]],
            "seed_segment_count": data["seed_segment_count"],
            "auto_keywords": data["auto_keywords"],
        })
        for speaker, count in speaker_counts.most_common():
            speaker_indices = [int(index) for index in indices if str(segments[index].get("speaker") or "UNKNOWN") == speaker]
            sample = segments[speaker_indices[0]]
            seconds = sum(max(0.0, float(segments[index].get("end") or 0) - float(segments[index].get("start") or 0)) for index in speaker_indices)
            speaker_rows.append({
                "topic_id": data["id"], "topic_label": data["label"], "speaker": speaker,
                "speaker_name": sample.get("speaker_name") or speaker, "segment_count": count,
                "speaker_group": _speaker_group(sample, dominant_speaker),
                "topic_percent": round(100 * count / len(indices), 3), "speaking_seconds": round(seconds, 3),
            })

    similarities = vectors @ vectors.T
    np.fill_diagonal(similarities, -1.0)
    nearest = similarities.max(axis=1) if len(segments) > 1 else np.zeros(1, dtype="float32")
    outlier_scores = 1 - nearest
    outlier_limit = min(10, max(1, math.ceil(len(segments) * 0.1)))
    outlier_indices = [int(value) for value in np.argsort(-outlier_scores)[:outlier_limit]]
    outlier_rows = []
    for rank, index in enumerate(outlier_indices, 1):
        segment = segments[index]
        outlier_rows.append({
            "rank": rank, "segment_id": str(segment["id"]),
            "speaker": str(segment.get("speaker") or "UNKNOWN"),
            "speaker_name": str(segment.get("speaker_name") or segment.get("speaker") or "UNKNOWN"),
            "start": segment.get("start", 0), "end": segment.get("end", 0),
            "outlier_score": round(float(outlier_scores[index]), 6),
            "nearest_similarity": round(float(nearest[index]), 6), "text": str(segment.get("text") or ""),
        })

    # How much closer the chosen theme is than the next one: a small margin means the
    # assignment could have gone either way.
    centroids = (np.stack([topic_data[label]["centroid"] for label in cluster_order])
                 if cluster_order else np.zeros((0, vectors.shape[1]), dtype="float32"))
    centroid_similarity = vectors @ centroids.T if len(centroids) else None
    centroid_position = {label: position for position, label in enumerate(cluster_order)}
    low_margin_count = 0
    for index, segment in enumerate(segments):
        label = int(labels[index])
        topic = topic_data.get(label)
        margin = None
        if topic is not None and centroid_similarity is not None and len(cluster_order) > 1:
            row = centroid_similarity[index].copy()
            own = float(row[centroid_position[label]])
            row[centroid_position[label]] = -2.0
            margin = round(own - float(row.max()), 6)
            if margin < LOW_MARGIN_LIMIT:
                low_margin_count += 1
        start, end = float(segment.get("start") or 0), float(segment.get("end") or 0)
        assignment = {
            "segment_id": str(segment["id"]), "topic_id": topic["id"] if topic else "",
            "topic_label": topic["label"] if topic else unassigned_label,
            "speaker": str(segment.get("speaker") or "UNKNOWN"),
            "speaker_name": str(segment.get("speaker_name") or segment.get("speaker") or "UNKNOWN"),
            "speaker_group": _speaker_group(segment, dominant_speaker),
            "start": round(start, 3), "end": round(end, 3), "duration": round(max(0, end - start), 3),
            "similarity": round(topic["similarities"][index], 6) if topic else None,
            "margin": margin,
            "outlier_score": round(float(outlier_scores[index]), 6), "text": str(segment.get("text") or ""),
        }
        assignments.append(assignment)
        evidence[assignment["segment_id"]] = {key: segment.get(key) for key in
            ("id", "speaker", "speaker_name", "role", "start", "end", "text")}

    for segment in ignored_segments:
        segment_id = str(segment["id"])
        evidence[segment_id] = {key: segment.get(key) for key in
            ("id", "speaker", "speaker_name", "role", "start", "end", "text")}

    for segment in backchannel_segments:
        segment_id = str(segment["id"])
        evidence[segment_id] = {key: segment.get(key) for key in
            ("id", "speaker", "speaker_name", "role", "start", "end", "text")}
    backchannels, speaker_backchannels = _link_backchannels(
        backchannel_segments, source_segments, assignments, dominant_speaker,
    )
    backchannel_rates, backchannel_tests = _backchannel_statistics(
        source_segments, assignments, backchannels, dominant_speaker,
    )
    speaker_results = _speaker_results(source_segments, assignments, dominant_speaker)
    backchannel_counts = Counter(row["topic_id"] for row in backchannels if row["topic_id"])
    for topic in topic_rows:
        topic["backchannel_count"] = backchannel_counts[topic["topic_id"]]

    duration = max((float(row.get("end") or 0) for row in source_segments), default=0)
    bin_seconds = max(60, int(analysis.get("config", {}).get("time_bin_seconds") or 300))
    bins: dict[tuple[int, str], dict[str, Any]] = {}
    topic_label_by_id = {row["topic_id"]: row["label"] for row in topic_rows}
    for row in assignments:
        if not row["topic_id"]:
            continue
        start, end = float(row["start"]), float(row["end"])
        first = int(start // bin_seconds)
        last = max(first, int(math.ceil(end / bin_seconds)) - 1)
        for index in range(first, last + 1):
            key = (index, row["topic_id"])
            target = bins.setdefault(key, {
                "bin_index": index, "start": index * bin_seconds,
                "end": min((index + 1) * bin_seconds, duration), "topic_id": row["topic_id"],
                "topic_label": topic_label_by_id[row["topic_id"]], "segment_count": 0,
                "backchannel_count": 0, "speaking_seconds": 0.0,
            })
            target["segment_count"] += int(index == first)
            target["speaking_seconds"] += max(0.0, min(end, target["end"]) - max(start, target["start"]))
    for row in backchannels:
        if not row["topic_id"]:
            continue
        index = int(float(row["start"]) // bin_seconds)
        key = (index, row["topic_id"])
        target = bins.setdefault(key, {
            "bin_index": index, "start": index * bin_seconds,
            "end": min((index + 1) * bin_seconds, duration), "topic_id": row["topic_id"],
            "topic_label": topic_label_by_id[row["topic_id"]], "segment_count": 0,
            "backchannel_count": 0, "speaking_seconds": 0.0,
        })
        target["backchannel_count"] += 1
    timeline = [{**row, "speaking_seconds": round(row["speaking_seconds"], 3)}
                for row in sorted(bins.values(), key=lambda value: (value["bin_index"], value["topic_id"]))]
    if progress:
        progress(90, "テーマ候補と根拠発話を整理しています。")
    limitations = [
        ("テーマ名は研究者が定義した見出しで、発話の割り当ては意味の近さによる候補です。"
         if mode == "manual" else
         "テーマ名はクラスタ内の特徴語から付けた候補であり、研究者が原文と照合して確定します。"),
        "短い相づちはテーマ分類と意味検索から外し、話者・対象テーマ別に別集計します。",
        "相づちの対象テーマは時系列上で近い別話者の発話から推定し、賛同とは断定しません。",
        "相づち応答率の分母は他者の有意味発話数であり、実際に聞いていた機会を完全には表しません。",
        "相づちの検定は同一話者内の反復と期待度数の小ささを伴うため探索的に扱います。",
        "話者別リザルトは語句に基づく未確認の候補です。否定・引用・主語の検出は限定的であり、本人の変化・支持の確定には研究者の原文照合が必要です。",
        "話者別リザルトは会議前調査との比較ではありません。発話時間の多さだけで進行役とみなしたり参加者分析から除外したりしません。",
        "時間推移の件数は発話の開始bin、秒数は各binと発話区間の重なりへ分配します。",
        "相づちの種類は辞書上の表現分類であり、賛同・進行品質を確定するものではありません。",
        "意味的な近さは賛成・反対、合意、因果関係、重要性を意味しません。",
        "例外候補は他の発話との埋め込み類似度が低い発話であり、少数意見とは限りません。",
        f"文脈付き入力は先頭{MAX_TEXT_CHARACTERS}文字、その後{MAX_EMBEDDING_TOKENS}token（接頭辞・特殊tokenを含む）までです。切詰めと対象発話の保持範囲はinput_manifestに記録します。",
    ]
    if mode == "manual":
        limitations[1:1] = [
            "手動のテーマは、見出し・手がかり語・シード発話から作ったベクトルへの最近傍割り当てです。テーマの妥当性を検証した結果ではありません。",
            f"割り当てのしきい値{manual_min_similarity:.2f}は実装上の目安で、文献に基づく基準ではありません。",
            f"上位2テーマの差が{LOW_MARGIN_LIMIT}未満の発話は、どちらのテーマにも入りうる境界例です。",
        ]
        if silhouette is not None:
            limitations.insert(4, "シルエット係数は割り当て後の幾何的なまとまりの記述で、研究者のテーマの妥当性ではありません。")
    else:
        limitations.insert(
            7, "話者ごとの発話量を重み付けして、司会者など一人の発話量による偏りを抑えます。")
    if mode == "candidate":
        limitations.insert(1, "テーマ数は研究者が候補一覧から選んだ値で、silhouetteの最大値とは限りません。")
    if reused_embeddings:
        limitations.append(
            "この実行は保存済みの意味ベクトル（int8で量子化）を再利用しており、埋め込みの再計算は行っていません。")
    diagnostics = {int(row["input_index"]): row for row in engine.get("input_diagnostics", [])}
    input_manifest = []
    for index, context in enumerate(context_manifest):
        measured = diagnostics.get(index)
        entry = {**context, **(measured or {}), "token_measurement_status": "measured" if measured else "unavailable"}
        entry["character_truncated"] = len(texts[index]) > MAX_TEXT_CHARACTERS
        start, end = entry.get("retained_character_start"), entry.get("retained_character_end")
        target_start, target_end = context["target_character_start"], context["target_character_end"]
        if target_start >= MAX_TEXT_CHARACTERS:
            retained = "omitted"
        elif start is None or end is None:
            retained = "unknown"
        elif start <= target_start and end >= target_end:
            retained = "fully_retained"
        elif end <= target_start or start >= target_end:
            retained = "omitted"
        else:
            retained = "partially_retained"
        entry["target_retention_status"] = retained
        input_manifest.append(entry)
    character_truncated_ids = [row["segment_id"] for row in input_manifest if row["character_truncated"]]
    token_truncated_ids = [row["segment_id"] for row in input_manifest if row.get("token_truncated")]
    truncated_ids = sorted(set(character_truncated_ids + token_truncated_ids))
    measured_all = len(diagnostics) == len(segments)
    if not measured_all:
        limitations.append("token切詰めは未計測です。注入ベクトルまたは旧キャッシュのため、切詰めなしと解釈しないでください。")
    parameters = {"mode": mode, "max_topics": max_topics, "min_topic_size": min_topic_size,
                  "topic_count": topic_count, "time_bin_seconds": bin_seconds,
                  "speaker_balancing": mode != "manual", "model_revision": vector_revision,
                  "timeline_count_unit": "utterance_start", "timeline_duration_unit": "interval_overlap",
                  "manual_min_similarity": manual_min_similarity if mode == "manual" else None,
                  "manual_topics": [
                      {"id": str(row.get("id") or ""), "label": str(row.get("label") or ""),
                       "cues": [str(value) for value in (row.get("cues") or [])],
                       "seed_segment_ids": [str(value) for value in (row.get("seed_segment_ids") or [])]}
                      for row in manual_topics]}
    return {
        "schema_version": 6, "algorithm_version": TRANSFORMER_ANALYSIS_VERSION,
        "analysis_unit": "文脈付き発話", "fingerprint": transformer_input_fingerprint(
            analysis, model=model_name, parameters=parameters),
        "embedding_fingerprint": transformer_embedding_fingerprint(analysis, model=model_name, revision=vector_revision),
        "source_provenance": transformer_source_provenance(analysis),
        "interpretation_status": "unverified_candidate", "researcher_review_required": True,
        "engine": engine, "parameters": parameters, "input_manifest": input_manifest,
        "coverage": {"segment_count": len(segments), "source_segment_count": len(source_segments),
                     "ignored_noise_segment_count": len(ignored_segments),
                     "backchannel_segment_count": len(backchannel_segments),
                     "linked_backchannel_segment_count": sum(1 for row in backchannels if row["topic_id"]),
                     "speaker_result_count": len({row["speaker"] for row in speaker_results}),
                     "explicit_speaker_result_count": len({row["speaker"] for row in speaker_results
                                                            if row["confidence"] == "explicit"}),
                     "candidate_speaker_result_count": len({row["speaker"] for row in speaker_results
                                                             if row["confidence"] == "unverified_candidate"}),
                     "context_expanded_segment_count": context_expanded_count,
                     "topic_count": len(topic_rows),
                     "truncated_segment_count": len(truncated_ids) if measured_all else None,
                     "truncated_segment_ids": truncated_ids,
                     "character_truncated_segment_count": len(character_truncated_ids),
                     "character_truncated_segment_ids": character_truncated_ids,
                     "token_truncated_segment_count": len(token_truncated_ids) if measured_all else None,
                     "token_truncated_segment_ids": token_truncated_ids,
                     "token_measurement_status": "measured" if measured_all else "unavailable",
                     "target_truncated_segment_ids": [row["segment_id"] for row in input_manifest
                                                      if row["target_retention_status"] in {"omitted", "partially_retained"}],
                     "small_cluster_segment_count": sum(1 for row in assignments if not row["topic_id"]),
                     "unassigned_segment_count": (sum(1 for row in assignments if not row["topic_id"])
                                                  if mode == "manual" else 0),
                     "low_margin_segment_count": low_margin_count,
                     "reused_embeddings": bool(reused_embeddings)},
        "quality": {"silhouette_cosine": round(float(silhouette), 6) if silhouette is not None else None,
                    "cluster_candidates": cluster_candidates,
                    "topic_mode": mode, "requested_topic_count": topic_count,
                    "actual_topic_count": len(topic_rows),
                    "topic_count_status": "satisfied" if topic_count is not None else "not_fixed",
                    "dominant_speaker": dominant_speaker,
                    "dominant_speaker_percent": round(100 * dominant_share, 3)},
        "topics": topic_rows, "assignments": assignments, "speaker_topics": speaker_rows,
        "backchannels": backchannels, "speaker_backchannels": speaker_backchannels,
        "backchannel_rates": backchannel_rates, "backchannel_tests": backchannel_tests,
        "speaker_results": speaker_results,
        "timeline": timeline, "outliers": outlier_rows, "evidence": evidence,
        "vectors": _pack_vectors(vectors, [str(row["id"]) for row in segments]),
        "limitations": limitations,
    }


def semantic_search(
    saved: dict, query: str, *, limit: int = 20,
    query_embedding: Any | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    import numpy as np

    query = str(query or "").strip()
    if not query or len(query) > 500:
        raise ValueError("意味検索語は1〜500文字で入力してください。")
    limit = min(100, max(1, int(limit)))
    vectors_payload = saved.get("vectors") if isinstance(saved.get("vectors"), dict) else {}
    vectors = _unpack_vectors(vectors_payload)
    if query_embedding is None:
        model = str(saved.get("engine", {}).get("name") or DEFAULT_MODEL)
        revision = str(saved.get("engine", {}).get("revision") or "")
        if not revision:
            raise ValueError("保存済みベクトルのモデルrevisionが不明です。テーマ分析を再実行してください。")
        if model == DEFAULT_MODEL and revision != EMBEDDING_STANDARD_V1["model_revision"]:
            raise ValueError("埋め込み標準 v1 と一致しません。テーマ分析を再計算してください。")
        query_vectors, query_engine = encode_texts([query], model_name=model, revision=revision,
                                                   kind="query", check_cancelled=check_cancelled)
        if str(query_engine.get("revision") or "") != revision or str(query_engine.get("name") or "") != model:
            raise ValueError("検索語と保存済みベクトルのモデルrevisionが一致しません。")
        query_vector = query_vectors[0]
    else:
        query_vector = np.asarray(query_embedding, dtype="float32").reshape(-1)
        query_vector /= max(float(np.linalg.norm(query_vector)), 1e-9)
    if query_vector.shape[0] != vectors.shape[1]:
        raise ValueError("検索語と保存済みベクトルの次元が一致しません。")
    scores = vectors @ query_vector
    assignments = {str(row["segment_id"]): row for row in saved.get("assignments", [])}
    hits = []
    for index in np.argsort(-scores):
        segment_id = str(vectors_payload["segment_ids"][int(index)])
        row = assignments.get(segment_id)
        if row and _is_meaningful_text(row.get("text")):
            hits.append({**row, "score": round(float(scores[int(index)]), 6)})
            if len(hits) >= limit:
                break
    return hits


def transformer_csv_sources(saved: dict | None) -> dict[str, list[dict[str, Any]]]:
    value = saved if isinstance(saved, dict) else {}
    return {
        "transformer_input_coverage": list(value.get("input_manifest") or []),
        "transformer_topics": list(value.get("topics") or []),
        "transformer_assignments": list(value.get("assignments") or []),
        "transformer_speakers": list(value.get("speaker_topics") or []),
        "transformer_timeline": list(value.get("timeline") or []),
        "transformer_outliers": list(value.get("outliers") or []),
        "transformer_backchannels": list(value.get("backchannels") or []),
        "transformer_backchannel_speakers": list(value.get("speaker_backchannels") or []),
        "transformer_backchannel_rates": list(value.get("backchannel_rates") or []),
        "transformer_backchannel_tests": list(value.get("backchannel_tests") or []),
        "transformer_speaker_results": list(value.get("speaker_results") or []),
    }
