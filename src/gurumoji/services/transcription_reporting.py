"""Thread-safe reporting boundary for one transcription pipeline run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TranscriptionReporter:
    """Own mutable job status through the application-provided synchronization."""

    job: Any
    update_job: Callable[..., None]
    jobs_lock: Any
    normalize_usage: Callable[[Any], dict[str, Any]]
    merge_usage: Callable[[Any, Any], dict[str, Any]]

    def status(self, message: str) -> None:
        self.update_job(self.job, message=message)

    def progress(self, value: int) -> None:
        self.update_job(self.job, progress=value)

    def stage(self, key: str, label: str, value: int = 0) -> None:
        self.update_job(
            self.job, stage=key, stage_label=label, stage_progress=value,
        )

    def record_ai_usage(self, sample: dict[str, Any]) -> None:
        usage = self.normalize_usage(sample)
        if not usage:
            return
        with self.jobs_lock:
            current = self.normalize_usage(self.job.ai_usage)
            if current and current["provider"] != usage["provider"]:
                current = {}
            self.job.ai_usage = self.merge_usage(current, usage)

    def check_cancelled(self) -> None:
        if self.job.cancel_event.is_set():
            raise InterruptedError("処理を中止しました。")

    def warning(self, message: str) -> None:
        with self.jobs_lock:
            current = self.job.output_warning.strip()
            self.job.output_warning = f"{current}\n{message}".strip() if current else message
        self.status(message)
