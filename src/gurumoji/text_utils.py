"""Small value-cleaning helpers shared by the application and its services.

These carry no policy of their own; they exist so that a service module can
sanitize stored text or stamp a timestamp without importing the composition
root.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def clean_single_line(value: Any, limit: int) -> str:
    return str(value or "").strip().replace("\r", " ").replace("\n", " ")[:limit]


def clean_multiline(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def normalize_tags(value: Any) -> list[str]:
    raw_values = value if isinstance(value, list) else re.split(r"[,、;\n]", str(value or ""))
    tags: list[str] = []
    for raw in raw_values:
        tag = clean_single_line(raw, 80)
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:100]


def normalize_attributes(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    attributes: dict[str, str] = {}
    for raw_key, raw_value in list(value.items())[:200]:
        key = clean_single_line(raw_key, 120)
        if not key:
            continue
        attributes[key] = clean_multiline(raw_value, 2000)
    return attributes


def validate_json_value(value: Any, *, maximum_nodes: int = 2_000_000) -> None:
    remaining = [maximum_nodes]

    def visit(current: Any, depth: int) -> None:
        remaining[0] -= 1
        if remaining[0] < 0:
            raise ValueError("The JSON payload contains too many values.")
        if depth > 24:
            raise ValueError("The JSON payload is nested too deeply.")
        if current is None or isinstance(current, (bool, int, str)):
            return
        if isinstance(current, float):
            if not math.isfinite(current):
                raise ValueError("NaN and Infinity are not valid input values.")
            return
        if isinstance(current, list):
            for item in current:
                visit(item, depth + 1)
            return
        if isinstance(current, dict):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object keys must be strings.")
                visit(item, depth + 1)
            return
        raise ValueError("The JSON payload contains an unsupported value type.")

    visit(value, 0)
