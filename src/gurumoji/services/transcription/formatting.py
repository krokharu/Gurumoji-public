"""Conservative transcript formatting and its reviewable report."""

from __future__ import annotations

import re
from typing import Any, Callable


TRANSCRIPT_FINISHING_MODES = {"off", "recommended", "advanced", "custom"}
TRANSCRIPT_FORMATTING_VERSION = "transcript-formatting-v2"


def normalize_transcript_punctuation(text: Any) -> str:
    """Apply conservative, meaning-preserving whitespace/punctuation fixes."""
    value = re.sub(r"[\r\n\t]+", " ", str(text or ""))
    value = re.sub(r"[ \u3000]+", " ", value).strip()
    value = re.sub(r"\s+([、。！？])", r"\1", value)
    value = re.sub(r"([「『（【])\s+", r"\1", value)
    value = re.sub(r"\s+([」』）】])", r"\1", value)
    value = re.sub(r"([、。！？])\1{1,}", r"\1", value)
    return value


def transcript_formatting_result(
    original_segments: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    *,
    mode: str,
    audio_preprocess: str = "none",
    speaker_names: dict[str, str] | None = None,
    speaker_diagnostics: dict[str, Any] | None = None,
    speaker_repair_summary: dict[str, int] | None = None,
    finishing_stages: dict[str, str] | None = None,
    ai_usage: dict[str, Any] | None = None,
    jev_usage: dict[str, Any] | None = None,
    normalize_ai_usage: Callable[[Any], dict[str, Any]],
    safe_token_count: Callable[[Any], int],
    normalize_detected_speaker_name: Callable[[Any, Any], str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Format safe surface issues and produce a reviewable finishing report.

    The function never deletes a suspected noise fragment and never guesses a
    speaker identity.  Speaker changes are reported only after the separately
    validated identity workflow has supplied aliases/corrections.
    """
    selected_mode = mode if mode in TRANSCRIPT_FINISHING_MODES else "custom"
    apply_local_fixes = selected_mode in {"recommended", "advanced", "custom"}
    speaker_names = speaker_names if isinstance(speaker_names, dict) else {}
    diagnostics = speaker_diagnostics if isinstance(speaker_diagnostics, dict) else {}
    repairs = speaker_repair_summary if isinstance(speaker_repair_summary, dict) else {}
    stages = finishing_stages if isinstance(finishing_stages, dict) else {}
    source_by_id = {
        str(item.get("id") or ""): item for item in original_segments if item.get("id")
    }
    formatted: list[dict[str, Any]] = []
    text_changes: list[dict[str, Any]] = []
    noise_candidates: list[dict[str, Any]] = []
    punctuation_warnings: list[dict[str, Any]] = []
    noise_pattern = re.compile(
        r"(?:\[(?:noise|inaudible)\]|[（(](?:雑音|ノイズ|聞き取り不能)[）)]|"
        r"^(?:雑音|ノイズ|無音)$|ご視聴ありがとうございました)",
        re.IGNORECASE,
    )
    for index, raw in enumerate(segments):
        item = dict(raw)
        before = str(item.get("text") or "")
        after = normalize_transcript_punctuation(before) if apply_local_fixes else before
        if after != before:
            item["text"] = after
            text_changes.append({
                "segment_id": str(item.get("id") or ""),
                "before": before,
                "after": after,
                "reason": "空白・句読点の安全な正規化",
            })
        text_value = str(item.get("text") or "")
        if noise_pattern.search(text_value):
            noise_candidates.append({
                "segment_id": str(item.get("id") or ""),
                "start": float(item.get("start", 0) or 0),
                "text": text_value[:240],
                "reason": "雑音・聞き取り不能・定型的な誤認識表現の候補",
            })
        if re.search(r"[、。！？]{2,}", text_value):
            punctuation_warnings.append({
                "segment_id": str(item.get("id") or ""),
                "type": "repeated_punctuation",
                "message": "句読点が連続しています。",
            })
        opening = sum(text_value.count(value) for value in "「『（【")
        closing = sum(text_value.count(value) for value in "」』）】")
        if opening != closing:
            punctuation_warnings.append({
                "segment_id": str(item.get("id") or ""),
                "type": "unbalanced_bracket",
                "message": "括弧またはかぎ括弧の対応を確認してください。",
            })
        formatted.append(item)

    boundary_warnings: list[dict[str, Any]] = []
    for previous, current in zip(formatted, formatted[1:]):
        previous_text = str(previous.get("text") or "").rstrip()
        gap = float(current.get("start", 0) or 0) - float(previous.get("end", 0) or 0)
        same_speaker = str(previous.get("speaker") or "UNKNOWN") == str(
            current.get("speaker") or "UNKNOWN"
        )
        if same_speaker and gap <= 3.0 and previous_text and not re.search(r"[。！？!?」』）】]$", previous_text):
            boundary_warnings.append({
                "before_segment_id": str(previous.get("id") or ""),
                "after_segment_id": str(current.get("id") or ""),
                "gap_seconds": round(max(0.0, gap), 2),
                "message": "同じ話者の文が不自然な位置で分割された可能性があります。",
            })

    recommended_reviews = []
    for item in formatted:
        review = item.get("recommended_review")
        if not isinstance(review, dict):
            continue
        jev = review.get("jev") if isinstance(review.get("jev"), dict) else {}
        llm = review.get("llm") if isinstance(review.get("llm"), dict) else {}
        recommended_reviews.append({
            "segment_id": str(item.get("id") or ""),
            "jev_flagged": bool(jev.get("flagged")),
            "jev_probability": jev.get("correction_needed_probability"),
            "llm_confirmed": bool(llm.get("confirmed_problem")),
            "replacement_applied": bool(llm.get("replacement_applied")),
            "issue_type": str(llm.get("issue_type") or "none"),
            "original_text": str(llm.get("original_text") or jev.get("original_text") or ""),
            "replacement_text": str(llm.get("replacement_text") or item.get("text") or ""),
            "reason": str(llm.get("reason") or ""),
            "effort": str(llm.get("effort") or ""),
            "context_before_count": int(llm.get("context_before_count", 0) or 0),
            "context_after_count": int(llm.get("context_after_count", 0) or 0),
            "attempt_count": int(llm.get("attempt_count", 0) or 0),
        })

    speaker_changes = []
    for item in formatted:
        segment_id = str(item.get("id") or "")
        original = source_by_id.get(segment_id)
        if original is None:
            continue
        before_speaker = str(original.get("speaker") or "UNKNOWN")
        after_speaker = str(item.get("speaker") or "UNKNOWN")
        if before_speaker != after_speaker:
            speaker_changes.append({
                "segment_id": segment_id,
                "from": before_speaker,
                "to": after_speaker,
            })

    usage = normalize_ai_usage(ai_usage)
    jev_requests = safe_token_count((jev_usage or {}).get("request_count"))
    methods = [
        {"id": "audio_preprocess", "label": "動画・音声前処理", "status": audio_preprocess},
        {"id": "local_rules", "label": "ローカル規則", "status": "completed"},
        {"id": "speaker_identity", "label": "自己紹介・話者連続性", "status": stages.get("speaker_identity", "not_requested")},
        {"id": "recommended_cleanup", "label": "おすすめ：Jev判定＋発話単位LLM整形", "status": stages.get("recommended_cleanup", "not_requested")},
        {"id": "context_cleanup", "label": "LLM文脈再校正", "status": stages.get("cleanup", "not_requested")},
        {"id": "jev", "label": "Jev比較", "status": stages.get("jev_comparison", "not_requested")},
        {"id": "notation", "label": "表記ゆれの統一", "status": stages.get("notation", "off")},
        {"id": "transformer", "label": "ローカルTransformer（分析画面）", "status": "available_after_transcription"},
    ]
    introductions = [
        {"speaker": str(label), "name": str(name), "status": "verified"}
        for label, name in sorted(speaker_names.items()) if str(name).strip()
    ]
    introduction_keys = {(item["speaker"], item["name"]) for item in introductions}
    introduction_patterns = (
        re.compile(r"(?:私は|わたしは|僕は|ぼくは|名前は)[、,\s]*([A-Za-zァ-ヶ一-龯々・]{2,24}?)(?:です|と申します|といいます|と言います)"),
        re.compile(r"(?:^|[。！？!?\s])([A-Za-zァ-ヶ一-龯々・]{2,24}?)(?:と申します|といいます|と言います)"),
    )
    rejected_names = {"よろしく", "ありがとう", "こちら", "それでは", "本日", "今日"}
    for item in formatted:
        text_value = str(item.get("text") or "")
        for pattern in introduction_patterns:
            match = pattern.search(text_value)
            if not match:
                continue
            name = normalize_detected_speaker_name(match.group(1), match.group(0))
            speaker = str(item.get("speaker") or "UNKNOWN")
            if not name or name in rejected_names or (speaker, name) in introduction_keys:
                break
            introductions.append({
                "speaker": speaker,
                "name": name,
                "status": "local_candidate",
                "segment_id": str(item.get("id") or ""),
            })
            introduction_keys.add((speaker, name))
            break
    result = {
        "version": TRANSCRIPT_FORMATTING_VERSION,
        "mode": selected_mode,
        "mode_label": {
            "off": "整形しない",
            "recommended": "おすすめ",
            "advanced": "高度",
            "custom": "個別設定",
        }[selected_mode],
        "methods": methods,
        "summary": {
            "original_segment_count": len(original_segments),
            "formatted_segment_count": len(formatted),
            "text_change_count": len(text_changes),
            "boundary_warning_count": len(boundary_warnings),
            "recommended_candidate_count": len(recommended_reviews),
            "recommended_confirmed_count": sum(1 for item in recommended_reviews if item["llm_confirmed"]),
            "recommended_replacement_count": sum(1 for item in recommended_reviews if item["replacement_applied"]),
            "noise_candidate_count": len(noise_candidates),
            "punctuation_warning_count": len(punctuation_warnings),
            "speaker_alias_count": int(repairs.get("alias_count", 0) or 0),
            "speaker_relabel_count": len(speaker_changes),
            "self_introduction_count": len(introductions),
            "llm_request_count": safe_token_count(usage.get("request_count")) + jev_requests,
        },
        "text_changes": text_changes[:200],
        "boundary_warnings": boundary_warnings[:200],
        "recommended_reviews": recommended_reviews[:200],
        "noise_candidates": noise_candidates[:200],
        "punctuation_warnings": punctuation_warnings[:200],
        "speaker_changes": speaker_changes[:500],
        "speaker_aliases": diagnostics.get("speaker_aliases", {}),
        "self_introductions": introductions,
    }
    return formatted, result
