"""Parsers for submitted form fields (a werkzeug MultiDict or any mapping with get/getlist)."""

from __future__ import annotations

import math
from typing import Any

from ..services.transcription.audio import AUDIO_PREPROCESS_PRESETS


def parse_bool(name: str, default: bool = False, *, form: Any) -> bool:
    values = form.getlist(name)
    if not values:
        return default
    return any(value.lower() in {"1", "true", "yes", "on"} for value in values)


def parse_optional_int(name: str, *, form: Any) -> int | None:
    raw = form.get(name, "").strip()
    if not raw or raw == "0":
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} は整数で指定してください。") from exc
    if not 1 <= value <= 20:
        raise ValueError(f"{name} は 1～20 で指定してください。")
    return value


def parse_optional_float(
    name: str, default: float, min_value: float, max_value: float, *, form: Any = None
) -> float:
    raw = form.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} は数値で指定してください。") from exc
    if not math.isfinite(value) or not min_value <= value <= max_value:
        raise ValueError(f"{name} は {min_value:g}～{max_value:g} で指定してください。")
    return value


def parse_audio_preprocess(*, form: Any) -> str:
    preset = form.get("audio_preprocess", "standard").strip() or "standard"
    if preset not in AUDIO_PREPROCESS_PRESETS:
        raise ValueError("音声前処理の指定が不正です。")
    return preset
