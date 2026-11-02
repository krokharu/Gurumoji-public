"""In-memory record of one transcription job, as shown to the browser.

JobRecord holds progress, logs and (once completed) the result of a job
while the process runs. public() is the only view sent to clients: local
paths and diagnostics are hidden unless the request may see local paths.
"""

from __future__ import annotations

import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar

from ...diagnostics import public_diagnostic_text
from ..ai.client import normalize_ai_usage
from ..ai.settings import AI_MODEL_PROVIDERS
from ..durable_files import path_is_within
from ..media_files import media_kind


@dataclass
class JobRecord:
    id: str
    source_name: str
    output_dir: Path
    write_srt: bool
    write_json: bool
    conversation_mode: str = "meeting"
    burn_subtitled_video: bool = False
    status: str = "queued"
    progress: int = 0
    stage: str = "queued"
    stage_label: str = "開始準備"
    stage_progress: int = 0
    message: str = "開始を待っています…"
    logs: list[str] = field(default_factory=list)
    segments: list[dict[str, Any]] = field(default_factory=list)
    speaker_names: dict[str, str] = field(default_factory=dict)
    session_profile: dict[str, Any] = field(default_factory=dict)
    speaker_profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    speaker_registration: dict[str, Any] = field(default_factory=dict)
    outline: dict[str, Any] | None = None
    meeting_minutes: dict[str, Any] | None = None
    emotion_analysis: dict[str, Any] | None = None
    formatting_result: dict[str, Any] = field(default_factory=dict)
    ai_usage: dict[str, Any] = field(default_factory=dict)
    media_path: Path | None = None
    files: list[Path] = field(default_factory=list)
    language: str | None = None
    error: str = ""
    output_warning: str = ""
    revision_count: int = 0
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    # Bound once by the composition root (app.py): the lock that guards every
    # job and the current request's local-path policy. The defaults are safe
    # for a record used on its own (paths hidden).
    state_lock: ClassVar[Any] = threading.RLock()
    reveal_local_paths: ClassVar[Callable[[], bool]] = staticmethod(lambda: False)

    def public(self) -> dict[str, Any]:
        cls = type(self)
        with cls.state_lock:
            reveal_local_paths = cls.reveal_local_paths()
            return {
                "id": self.id,
                "source_name": self.source_name,
                "conversation_mode": self.conversation_mode,
                "output_dir": str(self.output_dir) if reveal_local_paths else "",
                "status": self.status,
                "progress": self.progress,
                "stage": self.stage,
                "stage_label": self.stage_label,
                "stage_progress": self.stage_progress,
                "message": public_diagnostic_text(
                    self.message, reveal_local_paths=reveal_local_paths
                ),
                "logs": [
                    public_diagnostic_text(item, reveal_local_paths=reveal_local_paths)
                    for item in self.logs
                ],
                "segments": [dict(item) for item in self.segments] if self.status == "completed" else [],
                "speaker_names": dict(self.speaker_names) if self.status == "completed" else {},
                "session_profile": (
                    dict(self.session_profile) if self.status == "completed" else {}
                ),
                "speaker_profiles": (
                    {key: dict(value) for key, value in self.speaker_profiles.items()}
                    if self.status == "completed" else {}
                ),
                "speaker_registration": (
                    dict(self.speaker_registration) if self.status == "completed" else {}
                ),
                "write_srt": self.write_srt,
                "write_json": True,
                "burn_subtitled_video": self.burn_subtitled_video,
                "outline": dict(self.outline) if self.status == "completed" and self.outline else None,
                "meeting_minutes": (
                    dict(self.meeting_minutes)
                    if self.status == "completed" and self.meeting_minutes
                    else None
                ),
                "emotion_analysis": (
                    dict(self.emotion_analysis)
                    if self.status == "completed" and self.emotion_analysis
                    else None
                ),
                "formatting_result": (
                    dict(self.formatting_result) if self.status == "completed" else {}
                ),
                "ai_usage": normalize_ai_usage(self.ai_usage, AI_MODEL_PROVIDERS),
                "media_url": f"/api/library/{self.id}/media" if self.status == "completed" and self.media_path else None,
                "media_kind": media_kind(self.media_path) if self.status == "completed" and self.media_path else None,
                "files": [
                    {
                        "name": path.name,
                        "url": f"/api/library/{self.id}/files/{urllib.parse.quote(path.name)}",
                    }
                    for path in self.files
                    if path_is_within(path, self.output_dir) and path.is_file()
                ],
                "error": public_diagnostic_text(
                    self.error, reveal_local_paths=reveal_local_paths
                ),
                "output_warning": public_diagnostic_text(
                    self.output_warning, reveal_local_paths=reveal_local_paths
                ),
                "revision_count": self.revision_count,
            }
