"""Adapters that publish compact, non-authoritative Vault records.

SQLite and managed artifacts remain authoritative.  Publication errors are
reported but never roll back a completed transcript mutation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class VaultPublicationService:
    registry: Callable[[], Any]
    database_connection: Callable[[], Any]
    preparation_view: Callable[..., dict[str, Any]]
    row_segments: Callable[[Any], list[dict[str, Any]]]
    row_session_profile: Callable[[Any], dict[str, str]]
    database_error: type[Exception]
    warn: Callable[[str, Exception], None]
    # ResearchVault layout; only its deletion status is kept in step with the library.
    research_layout: Callable[[], Any] | None = None

    def publish_input(
        self,
        row: Any,
        whisper: dict[str, Any] | None = None,
        *,
        source_kind: str | None = None,
    ) -> None:
        """Mirror an InputVault ledger; transcript text remains in SQLite."""
        if row is None:
            return
        try:
            with self.database_connection() as connection:
                prep_state = self.preparation_view(connection, row, self.row_segments(row))
            self.registry().publish_input(
                item_id=str(row["id"]),
                title=str(row["source_name"]),
                segments=self.row_segments(row),
                revision=int(row["revision_count"] or 0),
                session_profile=self.row_session_profile(row),
                language=row["language"],
                media_path=Path(row["media_path"]) if row["media_path"] else None,
                created_at=str(row["created_at"] or ""),
                whisper=whisper,
                source_kind="whisper" if whisper else (source_kind or "saved"),
                preparation_state=prep_state,
            )
        except (OSError, ValueError, TypeError, LookupError, self.database_error) as exc:
            self.warn("InputVault を更新できませんでした", exc)
        try:
            item_id = str(row["id"])
        except (TypeError, LookupError, IndexError) as exc:
            self.warn("ResearchVault の削除状態を確認できませんでした", exc)
            return
        self._research_status(item_id, deleted=False)

    def retire_input(self, item_id: str) -> None:
        """Record deletion in the InputVault ledger without deleting provenance."""
        try:
            self.registry().retire_input(item_id)
        except (OSError, ValueError, TypeError, LookupError) as exc:
            self.warn("InputVault に削除を記録できませんでした", exc)
        self._research_status(item_id, deleted=True)

    def _research_status(self, item_id: str, *, deleted: bool) -> None:
        """Mark a deleted conversation in ResearchVault, or clear the mark when it returns."""
        if self.research_layout is None:
            return
        try:
            layout = self.research_layout()
            if deleted:
                layout.mark_deleted(item_id)
            else:
                layout.clear_deleted(item_id)
        except (OSError, ValueError, TypeError, LookupError) as exc:
            self.warn("ResearchVault に削除状態を記録できませんでした", exc)


def whisper_settings(options: Any, language: str | None, *, diarization_model: str) -> dict[str, Any]:
    """Return non-secret transcription provenance suitable for an InputVault."""
    transcription_backend = getattr(options, "transcription_backend", "whisperx")
    vocabulary = list(options.custom_vocabulary) if transcription_backend == "whisperx" else []
    return {
        "transcription_backend": transcription_backend,
        "model": "Qwen/Qwen3-ASR-1.7B" if transcription_backend == "qwen3_nemotron" else options.model_name,
        "language": language,
        "device": options.device,
        "diarization_device": options.diarization_device,
        "diarization_model": diarization_model,
        "audio_preprocess": options.audio_preprocess,
        "triple_pass": options.triple_pass,
        "boost_quiet_speech": options.boost_quiet_speech,
        "vad_onset": options.vad_onset,
        "vad_offset": options.vad_offset,
        "no_speech_threshold": options.no_speech_threshold,
        "min_speakers": options.min_speakers,
        "max_speakers": options.max_speakers,
        "num_speakers": getattr(options, "num_speakers", None),
        "emotion_analysis": options.emotion_analysis,
        "emotion_model": options.emotion_model if options.emotion_analysis else "",
        "conversation_mode": options.conversation_mode,
        "custom_vocabulary_terms": len(vocabulary),
        "custom_vocabulary_sha256": (
            hashlib.sha256(json.dumps(vocabulary, ensure_ascii=False).encode("utf-8")).hexdigest()
            if vocabulary else ""
        ),
    }
