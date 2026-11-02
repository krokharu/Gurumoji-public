"""The user's custom vocabulary: validation, storage and the Whisper prompt built from it."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

from ..vocabulary_store import VocabularyStore

CUSTOM_VOCABULARY_MAX_TERMS = 100
CUSTOM_VOCABULARY_MAX_TERM_LENGTH = 80


# Whisper's initial prompt shares a short context window with the beginning of
# the audio.  Keeping this compact makes registered terms useful without
# crowding out the first utterance, especially for Japanese where one token can
# be close to one visible character.
WHISPER_VOCABULARY_PROMPT_MAX_CHARACTERS = 220


def normalize_custom_vocabulary(values: Any) -> tuple[str, ...]:
    """Validate and deduplicate user terms while preserving their display form."""
    if values is None:
        return ()
    if isinstance(values, str):
        candidates: list[Any] = values.splitlines()
    elif isinstance(values, (list, tuple)):
        candidates = list(values)
    else:
        raise ValueError("登録語は1行ごとの文字列または配列で指定してください。")

    terms: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        if not isinstance(value, str):
            raise ValueError("登録語には文字列だけを指定してください。")
        # NFC preserves the user's intended visible notation while avoiding
        # duplicates created solely by composed/decomposed Unicode forms.
        term = unicodedata.normalize("NFC", value).strip()
        term = re.sub(r"[\t\r\n]+", " ", term)
        if not term:
            continue
        if len(term) > CUSTOM_VOCABULARY_MAX_TERM_LENGTH:
            raise ValueError(
                f"登録語は1語あたり{CUSTOM_VOCABULARY_MAX_TERM_LENGTH}文字以内にしてください。"
            )
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        terms.append(term)
        if len(terms) > CUSTOM_VOCABULARY_MAX_TERMS:
            raise ValueError(
                f"登録語は{CUSTOM_VOCABULARY_MAX_TERMS}語までにしてください。"
            )
    return tuple(terms)


def whisper_vocabulary_prompt(values: Any) -> str:
    """Build a compact initial prompt accepted by Whisper and WhisperX."""
    terms = normalize_custom_vocabulary(values)
    if not terms:
        return ""
    prefix = "用語・固有名詞: "
    suffix = "。"
    available = WHISPER_VOCABULARY_PROMPT_MAX_CHARACTERS - len(prefix) - len(suffix)
    selected: list[str] = []
    used = 0
    for term in terms:
        addition = len(term) + (1 if selected else 0)
        if used + addition > available:
            break
        selected.append(term)
        used += addition
    return f"{prefix}{'、'.join(selected)}{suffix}" if selected else ""


def make_custom_vocabulary_store(
    *, custom_vocabulary_file: Callable[[], Any], custom_vocabulary_lock: Any,
    database_connection: Any,
) -> tuple[Callable[..., Any], ...]:
    store = VocabularyStore(database_connection, custom_vocabulary_file,
                            custom_vocabulary_lock, normalize_custom_vocabulary)
    return store.load, store.save, store.reconcile
