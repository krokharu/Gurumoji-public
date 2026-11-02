"""文字起こしの入力分割、時刻検証、CSV出力に共通する小さな処理。"""
from __future__ import annotations
import hashlib
import json
import math
from typing import Any
from .. import transcript_preparation as preparation

MAX_TIMELINE_SECONDS = 31 * 86400

def bounded_batches(records: list[dict], max_chars: int = 18000, max_items: int = 80) -> list[list[dict]]:
    batches, current, size = [], [], 0
    for record in records:
        length = len(json.dumps(record, ensure_ascii=False))
        if length > max_chars:
            raise ValueError("AIに渡す情報が1回の上限を超えました。")
        if current and (size + length > max_chars or len(current) >= max_items):
            batches.append(current)
            current, size = [], 0
        current.append(record)
        size += length
    if current:
        batches.append(current)
    return batches

def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

def csv_safe(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if not isinstance(value, str):
        return value
    visible = value.lstrip(" \t\r\n")
    if visible.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value

def validated_segment_bounds(segment: dict[str, Any]) -> tuple[float, float, bool]:
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
        and raw_start <= MAX_TIMELINE_SECONDS
        and raw_end <= MAX_TIMELINE_SECONDS
    )
    start = min(max(raw_start, 0.0), float(MAX_TIMELINE_SECONDS))
    end = min(max(raw_end, start), float(MAX_TIMELINE_SECONDS))
    return start, end, valid
