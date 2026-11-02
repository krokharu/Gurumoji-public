"""Participant list and agenda text the user supplies before a run.

Both are hints, never facts: they steer recognition and name matching and are
not written into the transcript.
"""
from __future__ import annotations

import json
import re
from typing import Any

MAX_PRIOR_SPEAKERS = 20
MAX_PRIOR_FIELD_CHARACTERS = 40
MAX_PRIOR_OUTLINE_CHARACTERS = 4000
MAX_OUTLINE_HINT_TERMS = 30

# Katakana words, Latin/number words and quoted phrases are the terms Whisper
# most often misses; common kanji words are left out to keep the prompt short.
_OUTLINE_TERM = re.compile(r"[ァ-ヶー]{3,}|[A-Za-z][A-Za-z0-9._-]{2,}|[「『]([^「」『』\n]{2,20})[」』]")


def normalize_prior_speakers(raw: Any) -> tuple[tuple[str, str], ...]:
    """Validate a JSON array of {"name", "role"} objects into (name, role) pairs."""
    if raw is None or raw == "":
        return ()
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError as exc:
        raise ValueError("事前話者情報の形式が不正です。") from exc
    if not isinstance(items, list):
        raise ValueError("事前話者情報の形式が不正です。")
    if len(items) > MAX_PRIOR_SPEAKERS:
        raise ValueError(f"事前話者情報は{MAX_PRIOR_SPEAKERS}人までです。")
    speakers: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("事前話者情報の形式が不正です。")
        name = " ".join(str(item.get("name", "")).split())
        role = " ".join(str(item.get("role", "")).split())
        if not name:
            continue
        if len(name) > MAX_PRIOR_FIELD_CHARACTERS or len(role) > MAX_PRIOR_FIELD_CHARACTERS:
            raise ValueError(f"事前話者情報の名前と役割は{MAX_PRIOR_FIELD_CHARACTERS}文字以内にしてください。")
        if name.casefold() in seen:
            continue
        seen.add(name.casefold())
        speakers.append((name, role))
    return tuple(speakers)


def normalize_prior_outline(raw: Any) -> str:
    text = str(raw or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > MAX_PRIOR_OUTLINE_CHARACTERS:
        raise ValueError(f"事前アウトラインは{MAX_PRIOR_OUTLINE_CHARACTERS}文字以内にしてください。")
    return text


def outline_hint_terms(outline: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for match in _OUTLINE_TERM.finditer(outline or ""):
        term = (match.group(1) or match.group(0)).strip()
        if term and term.casefold() not in seen:
            seen.add(term.casefold())
            terms.append(term)
        if len(terms) >= MAX_OUTLINE_HINT_TERMS:
            break
    return tuple(terms)


def recognition_hint_terms(
    custom_vocabulary: tuple[str, ...],
    prior_speakers: tuple[tuple[str, str], ...],
    prior_outline: str,
) -> tuple[str, ...]:
    """Terms for Whisper's prompt: the user's own words first, then names, then agenda terms."""
    terms: list[str] = []
    seen: set[str] = set()
    for term in (*custom_vocabulary, *(name for name, _ in prior_speakers), *outline_hint_terms(prior_outline)):
        if term.casefold() not in seen:
            seen.add(term.casefold())
            terms.append(term)
    return tuple(terms)
