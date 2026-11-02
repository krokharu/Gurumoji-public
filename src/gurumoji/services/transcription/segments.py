"""Transcript segment normalization, gap recovery, and display grouping.

The transcription pipeline runs Whisper more than once over quiet or skipped
stretches of audio.  This module owns the rules that decide which of those
supplemental segments are genuinely new, and how word-level speaker changes are
regrouped into the segments the UI and the exports display.

It is deliberately free of Flask and application-global dependencies.
"""

from __future__ import annotations

import difflib
import math
import re
from typing import Any

QUIET_SUPPLEMENT_MIN_DURATION = 0.2
QUIET_SUPPLEMENT_EDGE_PADDING = 0.12
QUIET_SUPPLEMENT_LOW_OVERLAP_RATIO = 0.2
QUIET_SUPPLEMENT_PARTIAL_OVERLAP_RATIO = 0.65
QUIET_SUPPLEMENT_TEXT_WINDOW_SECONDS = 8.0
QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS = 8
QUIET_SUPPLEMENT_MAX_NO_SPEECH_PROB = 0.85
QUIET_SUPPLEMENT_MIN_AVG_LOGPROB = -1.35
QUIET_SUPPLEMENT_MAX_COMPRESSION_RATIO = 3.2
TRIPLE_PASS_MIN_GAP_SECONDS = 3.0
TRIPLE_PASS_GAP_CONTEXT_SECONDS = 0.75
TRIPLE_PASS_MIN_GAP_OVERLAP_RATIO = 0.6
SHORT_SPEAKER_ISLAND_MAX_SECONDS = 0.55
SHORT_SPEAKER_ISLAND_MAX_GAP_SECONDS = 0.2
SPEAKER_BACKCHANNEL_TEXTS = {
    "はい", "ええ", "うん", "そう", "そうです", "なるほど", "確かに",
    "はいはい", "うんうん", "へえ", "ああ", "おお", "ん", "うーん",
}


def segment_bounds(segment: dict[str, Any]) -> tuple[float, float]:
    start = float(segment.get("start", 0) or 0)
    end = float(segment.get("end", start) or start)
    if end < start:
        end = start
    return start, end


def normalize_asr_segments(raw_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in raw_segments:
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        start, end = segment_bounds(raw)
        item = dict(raw)
        item["start"] = start
        item["end"] = end
        item["text"] = text
        normalized.append(item)
    normalized.sort(key=lambda item: (float(item.get("start", 0)), float(item.get("end", 0))))
    return normalized


def find_long_asr_gaps(
    raw_segments: list[dict[str, Any]],
    audio_duration: float,
    min_gap_seconds: float = TRIPLE_PASS_MIN_GAP_SECONDS,
) -> list[tuple[float, float]]:
    duration = max(0.0, float(audio_duration))
    minimum = max(0.05, float(min_gap_seconds))
    covered: list[tuple[float, float]] = []
    for segment in normalize_asr_segments(raw_segments):
        start, end = segment_bounds(segment)
        start = min(duration, max(0.0, start))
        end = min(duration, max(start, end))
        if end > start:
            covered.append((start, end))

    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in covered:
        if start > cursor and start - cursor >= minimum:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if duration > cursor and duration - cursor >= minimum:
        gaps.append((cursor, duration))
    return gaps


def offset_asr_segments_to_gap(
    raw_segments: list[dict[str, Any]],
    clip_start: float,
    gap_start: float,
    gap_end: float,
) -> list[dict[str, Any]]:
    shifted: list[dict[str, Any]] = []
    for raw in normalize_asr_segments(raw_segments):
        item = dict(raw)
        local_start, local_end = segment_bounds(raw)
        global_start = clip_start + local_start
        global_end = clip_start + local_end
        overlap_start = max(global_start, gap_start)
        overlap_end = min(global_end, gap_end)
        overlap_duration = overlap_end - overlap_start
        segment_duration = max(global_end - global_start, 0.001)
        if (
            overlap_duration <= 0.05
            or overlap_duration / segment_duration < TRIPLE_PASS_MIN_GAP_OVERLAP_RATIO
        ):
            continue
        # The clip includes context on both sides so Whisper does not start in
        # the middle of a phoneme. Never let that context become a duplicate
        # transcript segment outside the gap we are trying to recover.
        item["start"] = overlap_start
        item["end"] = overlap_end
        words: list[dict[str, Any]] = []
        raw_words = raw.get("words")
        if (
            not raw_words
            and overlap_duration / segment_duration < 0.85
        ):
            # Without word timestamps the text cannot be trimmed safely. A
            # context-heavy segment would duplicate or tear the neighbouring
            # conversation, so retain only segments located almost entirely
            # inside the gap.
            continue
        for raw_word in raw_words or []:
            word = dict(raw_word)
            word_start = (
                clip_start + float(word["start"])
                if word.get("start") is not None
                else global_start
            )
            word_end = (
                clip_start + float(word["end"])
                if word.get("end") is not None
                else global_end
            )
            if min(word_end, gap_end) - max(word_start, gap_start) <= 0.0:
                continue
            word["start"] = max(word_start, gap_start)
            word["end"] = min(word_end, gap_end)
            words.append(word)
        if isinstance(raw_words, list) and raw_words and not words:
            continue
        if words:
            item["words"] = words
            word_text = _joined_word_text([
                str(word.get("word", word.get("text", "")))
                for word in words
            ])
            if word_text:
                item["text"] = word_text
        shifted.append(item)
    return shifted


def merged_interval_coverage(
    candidate: dict[str, Any],
    accepted: list[dict[str, Any]],
    padding: float = QUIET_SUPPLEMENT_EDGE_PADDING,
) -> float:
    candidate_start, candidate_end = segment_bounds(candidate)
    duration = max(candidate_end - candidate_start, 0.001)
    intervals: list[tuple[float, float]] = []
    for segment in accepted:
        start, end = segment_bounds(segment)
        overlap_start = max(candidate_start, start - padding)
        overlap_end = min(candidate_end, end + padding)
        if overlap_end > overlap_start:
            intervals.append((overlap_start, overlap_end))
    if not intervals:
        return 0.0
    intervals.sort()
    covered = 0.0
    current_start, current_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            covered += current_end - current_start
            current_start, current_end = start, end
    covered += current_end - current_start
    return min(1.0, covered / duration)


def normalize_text_for_merge(text: str) -> str:
    text = re.sub(r"[\s\u3000、。,.!?！？「」『』（）()【】\[\]・…:：;；\"'`~〜\-ー]+", "", text)
    return text.lower()


def has_near_duplicate_text(
    candidate: dict[str, Any],
    accepted: list[dict[str, Any]],
    window_seconds: float = QUIET_SUPPLEMENT_TEXT_WINDOW_SECONDS,
) -> bool:
    candidate_text = normalize_text_for_merge(str(candidate.get("text", "")))
    if not candidate_text:
        return False
    candidate_start, candidate_end = segment_bounds(candidate)
    for segment in accepted:
        start, end = segment_bounds(segment)
        if end < candidate_start - window_seconds or start > candidate_end + window_seconds:
            continue
        text = normalize_text_for_merge(str(segment.get("text", "")))
        if not text:
            continue
        if (
            candidate_text == text
            and min(len(candidate_text), len(text)) < QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS
        ):
            temporal_distance = max(start - candidate_end, candidate_start - end, 0.0)
            if temporal_distance <= 1.25:
                return True
            continue
        if (
            len(candidate_text) < QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS
            or len(text) < QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS
        ):
            continue
        if candidate_text in text or text in candidate_text:
            return True
        temporal_distance = max(start - candidate_end, candidate_start - end, 0.0)
        if (
            temporal_distance <= window_seconds
            and difflib.SequenceMatcher(None, candidate_text, text).ratio() >= 0.86
        ):
            return True
    return False


def asr_segment_quality_ok(segment: dict[str, Any]) -> bool:
    start, end = segment_bounds(segment)
    if end - start < QUIET_SUPPLEMENT_MIN_DURATION:
        return False
    no_speech_prob = segment.get("no_speech_prob")
    if no_speech_prob is not None and float(no_speech_prob) > QUIET_SUPPLEMENT_MAX_NO_SPEECH_PROB:
        return False
    avg_logprob = segment.get("avg_logprob")
    if avg_logprob is not None and float(avg_logprob) < QUIET_SUPPLEMENT_MIN_AVG_LOGPROB:
        return False
    compression_ratio = segment.get("compression_ratio")
    if compression_ratio is not None and float(compression_ratio) > QUIET_SUPPLEMENT_MAX_COMPRESSION_RATIO:
        return False
    return True


def should_add_supplemental_segment(
    candidate: dict[str, Any],
    accepted: list[dict[str, Any]],
) -> bool:
    if not asr_segment_quality_ok(candidate):
        return False
    if has_near_duplicate_text(candidate, accepted):
        return False
    overlap_ratio = merged_interval_coverage(candidate, accepted)
    if overlap_ratio <= QUIET_SUPPLEMENT_LOW_OVERLAP_RATIO:
        return True
    return overlap_ratio <= QUIET_SUPPLEMENT_PARTIAL_OVERLAP_RATIO


def merge_supplemental_asr_segments(
    primary_segments: list[dict[str, Any]],
    supplemental_runs: list[tuple[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    accepted = normalize_asr_segments(primary_segments)
    added_counts: dict[str, int] = {}
    for label, raw_segments in supplemental_runs:
        added = 0
        for candidate in normalize_asr_segments(raw_segments):
            if should_add_supplemental_segment(candidate, accepted):
                accepted.append(candidate)
                accepted.sort(key=lambda item: (float(item.get("start", 0)), float(item.get("end", 0))))
                added += 1
        added_counts[label] = added
    return accepted, added_counts


def display_time(seconds: float) -> str:
    total = int(max(0.0, float(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def default_speaker_name(label: str | None) -> str:
    if not label:
        return "話者（未判定）"
    suffix = label.rsplit("_", 1)[-1]
    return f"話者 {int(suffix) + 1}" if suffix.isdigit() else label


def segment_speaker(segment: dict[str, Any]) -> str | None:
    if segment.get("speaker"):
        return str(segment["speaker"])
    for word in segment.get("words") or []:
        if word.get("speaker"):
            return str(word["speaker"])
    return None


def _finite_word_time(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _joined_word_text(parts: list[str]) -> str:
    """Join WhisperX words without adding visible spaces to Japanese text."""
    if not parts:
        return ""
    if any(part[:1].isspace() or part[-1:].isspace() for part in parts):
        return "".join(parts).strip()
    if any(re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", part) for part in parts):
        return "".join(parts).strip()
    text = ""
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if not text or re.fullmatch(r"[,.;:!?%\)\]\}]", token):
            text += token
        elif text.endswith(("(", "[", "{")):
            text += token
        else:
            text += " " + token
    return text.strip()


def _continuous_speaker_island(previous: dict[str, Any], current: dict[str, Any],
                               following: dict[str, Any]) -> bool:
    """Only smooth a fragment inside one continuous, known speaker's turn."""
    return bool(
        previous.get("speaker")
        and previous["speaker"] == following.get("speaker")
        and current.get("speaker") != previous["speaker"]
        and abs(float(current["start"]) - float(previous["end"]))
        <= SHORT_SPEAKER_ISLAND_MAX_GAP_SECONDS
        and abs(float(following["start"]) - float(current["end"]))
        <= SHORT_SPEAKER_ISLAND_MAX_GAP_SECONDS
    )


def _word_speaker_segments(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Split one WhisperX segment at word-level speaker transitions."""
    raw_words = raw.get("words")
    if not isinstance(raw_words, list):
        return []
    words: list[dict[str, Any]] = []
    for value in raw_words:
        if not isinstance(value, dict):
            continue
        text = str(value.get("word", value.get("text", "")))
        if text.strip():
            words.append({**value, "_text": text})
    explicit_speakers = [str(word["speaker"]) for word in words if word.get("speaker")]
    if not words or not explicit_speakers:
        return []

    fallback_speaker = str(raw["speaker"]) if raw.get("speaker") else explicit_speakers[0]
    next_speakers: list[str | None] = [None] * len(words)
    next_speaker: str | None = None
    for index in range(len(words) - 1, -1, -1):
        if words[index].get("speaker"):
            next_speaker = str(words[index]["speaker"])
        next_speakers[index] = next_speaker

    segment_start, segment_end = segment_bounds(raw)
    resolved: list[dict[str, Any]] = []
    previous_speaker: str | None = None
    previous_end = segment_start
    for index, word in enumerate(words):
        speaker = (
            str(word["speaker"])
            if word.get("speaker")
            else previous_speaker or next_speakers[index] or fallback_speaker
        )
        start = _finite_word_time(word.get("start"))
        end = _finite_word_time(word.get("end"))
        start = max(segment_start, start if start is not None else previous_end)
        if end is None:
            next_start = None
            for following in words[index + 1:]:
                next_start = _finite_word_time(following.get("start"))
                if next_start is not None:
                    break
            end = next_start if next_start is not None else segment_end
        end = max(start, end)
        resolved.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "text": word["_text"],
        })
        previous_speaker = speaker
        previous_end = end

    groups: list[dict[str, Any]] = []
    for word in resolved:
        if groups and groups[-1]["speaker"] == word["speaker"]:
            groups[-1]["end"] = max(groups[-1]["end"], word["end"])
            groups[-1]["_parts"].append(word["text"])
        else:
            groups.append({
                "start": word["start"],
                "end": word["end"],
                "speaker": word["speaker"],
                "_parts": [word["text"]],
            })

    # Diarization occasionally assigns one short word in the middle of a
    # continuous utterance to another speaker. Collapse only A-B-A islands;
    # keep common Japanese backchannels because those are often real turns.
    for index in range(1, len(groups) - 1):
        previous = groups[index - 1]
        current = groups[index]
        following = groups[index + 1]
        duration = max(0.0, float(current["end"]) - float(current["start"]))
        island_text = normalize_text_for_merge(_joined_word_text(current["_parts"]))
        if (
            _continuous_speaker_island(previous, current, following)
            and duration <= SHORT_SPEAKER_ISLAND_MAX_SECONDS
            and island_text not in SPEAKER_BACKCHANNEL_TEXTS
        ):
            current["speaker"] = previous["speaker"]

    smoothed: list[dict[str, Any]] = []
    for group in groups:
        if smoothed and smoothed[-1]["speaker"] == group["speaker"]:
            smoothed[-1]["end"] = max(smoothed[-1]["end"], group["end"])
            smoothed[-1]["_parts"].extend(group["_parts"])
        else:
            smoothed.append(group)
    groups = smoothed
    for group in groups:
        group["text"] = _joined_word_text(group.pop("_parts"))
    return [group for group in groups if group["text"]]


def make_display_segments(raw_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Preserve word speaker turns, then safely merge adjacent same-speaker chunks."""
    normalized: list[dict[str, Any]] = []
    for raw in raw_segments:
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        word_segments = _word_speaker_segments(raw)
        if len({item["speaker"] for item in word_segments}) > 1:
            normalized.extend(word_segments)
            continue
        start, end = segment_bounds(raw)
        normalized.append({
            "start": start,
            "end": end,
            "speaker": word_segments[0]["speaker"] if word_segments else segment_speaker(raw),
            "text": text,
        })

    normalized.sort(key=lambda item: (item["start"], item["end"]))
    # Detailed quiet-speech recovery can expose a very short A-B-A speaker
    # island across ASR segment boundaries. Repair only a non-backchannel
    # fragment surrounded by the same speaker; substantive short turns remain.
    for index in range(1, len(normalized) - 1):
        previous = normalized[index - 1]
        current = normalized[index]
        following = normalized[index + 1]
        duration = max(0.0, float(current["end"]) - float(current["start"]))
        island_text = normalize_text_for_merge(str(current.get("text") or ""))
        if (
            _continuous_speaker_island(previous, current, following)
            and island_text not in SPEAKER_BACKCHANNEL_TEXTS
            and (
                duration <= SHORT_SPEAKER_ISLAND_MAX_SECONDS
                or (duration <= 1.2 and len(island_text) <= 8)
            )
        ):
            current["speaker"] = previous.get("speaker")
    merged: list[dict[str, Any]] = []
    for current in normalized:
        if (
            merged
            and current["speaker"] is not None
            and merged[-1]["speaker"] == current["speaker"]
            and current["start"] >= merged[-1]["start"]
            and current["start"] - merged[-1]["end"] <= 1.2
        ):
            merged[-1]["end"] = max(merged[-1]["end"], current["end"])
            merged[-1]["text"] += " " + current["text"]
        else:
            merged.append(dict(current))
    return merged
