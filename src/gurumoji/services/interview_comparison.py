"""Descriptive comparison across interview sessions."""

from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Any, Callable


def comparison_rate(count: int | float, denominator: int | float) -> float:
    return round(1000 * float(count) / float(denominator), 2) if denominator else 0.0


def build_interview_comparison(
    rows: list[sqlite3.Row], *, allow_different_content: bool,
    row_session_profile: Callable[[sqlite3.Row], dict[str, str]],
    interview_comparison_identity: Callable[[dict[str, Any]], tuple[str, str, str]],
    group_analysis_for_row: Callable[[sqlite3.Row], dict[str, Any]],
    text_mining_counter: Callable[..., Counter[str]],
) -> dict[str, Any]:
    """Build a descriptive, evidence-preserving comparison across sessions.

    The calculation intentionally compares normalised descriptive measures, not
    participant-level hypothesis tests: turns within a group interview are not
    independent samples.  This keeps the result useful without overstating
    what a cross-session transcript comparison can establish.
    """
    profiles = [row_session_profile(row) for row in rows]
    identities = [interview_comparison_identity(profile) for profile in profiles]
    keys = [identity[0] for identity in identities]
    same_content = bool(keys and keys[0]) and all(key == keys[0] for key in keys)
    if not allow_different_content and not same_content:
        raise ValueError(
            "通常比較では、全インタビューに同じ「比較グループ」を設定してください。"
            "既存データは質問ガイドが完全一致する場合のみ自動照合されます。"
            "異なる内容を比較する場合は、画面のチェックを入れてください。"
        )

    interviews: list[dict[str, Any]] = []
    term_counters: dict[str, Counter[str]] = {}
    term_totals: dict[str, int] = {}
    code_counts: dict[str, dict[str, int]] = {}
    emotion_counts: dict[str, dict[str, int]] = {}

    for row, profile, identity in zip(rows, profiles, identities):
        analysis = group_analysis_for_row(row)
        item_id = str(row["id"])
        included = [
            segment for segment in analysis["segments"]
            if not segment.get("excluded") and str(segment.get("text") or "").strip()
        ]
        counter = text_mining_counter(
            included, set(analysis["config"].get("stop_words") or [])
        )
        term_counters[item_id] = counter
        term_totals[item_id] = sum(counter.values())
        overview = analysis["automatic"]["overview"]
        interviews.append({
            "item_id": item_id,
            "source_name": str(row["source_name"]),
            "comparison_label": identity[1],
            "comparison_source": identity[2],
            "session_type": profile.get("session_type", "focus_group"),
            "session_date": profile.get("session_date", ""),
            "objective": profile.get("objective", ""),
            "included_segment_count": len(included),
            "speaker_count": int(overview.get("speaker_count") or 0),
            "participant_count": overview.get("participant_count"),
            "observed_participant_count": overview.get("observed_participant_count"),
            "session_duration": overview.get("session_duration"),
            "session_timed_turn_count": overview.get("session_timed_turn_count"),
            "session_missing_time_turn_count": overview.get("session_missing_time_turn_count"),
            "total_speaking_seconds": overview.get("total_speaking_seconds"),
            "timed_turn_count": overview.get("timed_turn_count"),
            "missing_time_turn_count": overview.get("missing_time_turn_count"),
            "term_count": term_totals[item_id],
            "excluded_segment_count": int(
                analysis["automatic"]["data_quality"].get("excluded_segments") or 0
            ),
        })
        code_counts[item_id] = {
            str(code.get("label") or code.get("id") or "未設定"):
            int(code.get("segment_count") or 0)
            for code in analysis["manual"].get("code_metrics", [])
            if int(code.get("segment_count") or 0) > 0
        }
        emotions: Counter[str] = Counter()
        for emotion in analysis["automatic"].get("emotions", []):
            model = str(emotion.get("model_name") or emotion.get("model") or "感情モデル")
            label = str(emotion.get("emotion") or emotion.get("label") or "未設定")
            emotions[f"{model}: {label}"] += int(emotion.get("count") or 0)
        emotion_counts[item_id] = dict(emotions)

    item_ids = [item["item_id"] for item in interviews]
    common_terms: list[dict[str, Any]] = []
    if term_counters:
        shared = set.intersection(*(set(counter) for counter in term_counters.values()))
        for term in shared:
            counts = [term_counters[item_id][term] for item_id in item_ids]
            if min(counts) < 2:
                continue
            common_terms.append({
                "term": term,
                "minimum_count": min(counts),
                "interviews": [
                    {
                        "item_id": item_id,
                        "count": term_counters[item_id][term],
                        "rate_per_1000_terms": comparison_rate(
                            term_counters[item_id][term], term_totals[item_id]
                        ),
                    }
                    for item_id in item_ids
                ],
            })
    common_terms.sort(key=lambda value: (-value["minimum_count"], value["term"]))

    characteristic_terms: list[dict[str, Any]] = []
    all_terms = set().union(*(set(counter) for counter in term_counters.values()))
    for item in interviews:
        item_id = item["item_id"]
        other_ids = [candidate for candidate in item_ids if candidate != item_id]
        # Keep the per-term calculation explicit: the other-session denominator
        # is the sum of every selected transcript, not the number of sessions.
        other_total = sum(term_totals[candidate] for candidate in other_ids)
        for term in all_terms:
            count = term_counters[item_id][term]
            if count < 2:
                continue
            other_count = sum(term_counters[candidate][term] for candidate in other_ids)
            own_rate = comparison_rate(count, term_totals[item_id])
            other_rate = comparison_rate(other_count, other_total)
            characteristic_terms.append({
                "item_id": item_id,
                "source_name": item["source_name"],
                "term": term,
                "count": count,
                "rate_per_1000_terms": own_rate,
                "other_count": other_count,
                "other_rate_per_1000_terms": other_rate,
                "difference_per_1000_terms": round(own_rate - other_rate, 2),
            })
    characteristic_terms.sort(
        key=lambda value: (-abs(value["difference_per_1000_terms"]), -value["count"], value["term"])
    )

    def categorical_rows(
        values_by_item: dict[str, dict[str, int]], *, key: str,
    ) -> list[dict[str, Any]]:
        labels = set().union(*(set(values) for values in values_by_item.values()))
        result = []
        for label in labels:
            counts = [int(values_by_item[item_id].get(label, 0)) for item_id in item_ids]
            if not any(counts):
                continue
            result.append({
                key: label,
                "interviews": [
                    {
                        "item_id": item_id,
                        "count": int(values_by_item[item_id].get(label, 0)),
                        "rate_per_100_segments": comparison_rate(
                            values_by_item[item_id].get(label, 0),
                            next(item["included_segment_count"] for item in interviews if item["item_id"] == item_id),
                        ) / 10,
                    }
                    for item_id in item_ids
                ],
                "max_count": max(counts),
            })
        return sorted(result, key=lambda value: (-value["max_count"], value[key]))[:20]

    mode = "same_content" if same_content else "different_content"
    cautions = [
        "発話・語・コードの割合は記述的な比較です。個々の発話を独立した標本として検定していません。",
        "発話時間や頻度の差だけで、重要性・原因・参加者全体への一般化を判断しないでください。",
    ]
    if mode == "different_content":
        cautions.insert(
            0,
            "内容が異なる比較です。共通語・特徴語は探索の手がかりであり、質問や対象者条件の差を統制した結論ではありません。",
        )
    return {
        "schema_version": 1,
        "mode": mode,
        "allow_different_content": allow_different_content,
        "same_content": same_content,
        "comparison_key": keys[0] if same_content else "",
        "interviews": interviews,
        "common_terms": common_terms[:20],
        "characteristic_terms": characteristic_terms[:30],
        "code_comparison": categorical_rows(code_counts, key="code"),
        "emotion_comparison": categorical_rows(emotion_counts, key="emotion"),
        "cautions": cautions,
    }
