"""Process-local runtime state shared by request handlers and worker threads.

One RuntimeState exists per process (app.py creates it). It owns the
in-memory transcription jobs, the locks that guard shared data and the
cancel events of running AI/Transformer analyses. Nothing here is
persisted: after a restart the database and files are the source of truth,
and interrupted work is recovered by ApplicationLifecycle, not from here.

Lock responsibilities:
- jobs_lock: the jobs dict and every JobRecord field.
- library_write_lock: writes to library items (transcripts, speakers,
  analysis settings, groups, deletion) and the files derived from them.
- insight_jobs_lock / transformer_jobs_lock: the status of AI-insight and
  Transformer requests (their request rows and cancel events).
- training_lock: the correction-training corpus files.
- file_dialog_lock: at most one native file dialog at a time.
- custom_vocabulary_lock: the custom vocabulary file.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .services.transcription.job_record import JobRecord

TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "cancelled"})


@dataclass
class RuntimeState:
    jobs: dict[str, JobRecord] = field(default_factory=dict)
    jobs_lock: threading.RLock = field(default_factory=threading.RLock)
    library_write_lock: threading.RLock = field(default_factory=threading.RLock)
    insight_jobs_lock: threading.RLock = field(default_factory=threading.RLock)
    insight_cancel_events: dict[str, threading.Event] = field(default_factory=dict)
    transformer_jobs_lock: threading.RLock = field(default_factory=threading.RLock)
    transformer_cancel_events: dict[str, threading.Event] = field(default_factory=dict)
    training_lock: threading.Lock = field(default_factory=threading.Lock)
    file_dialog_lock: threading.Lock = field(default_factory=threading.Lock)
    custom_vocabulary_lock: threading.Lock = field(default_factory=threading.Lock)

    def prune_jobs_locked(
        self,
        now: float | None = None,
        *,
        ttl_seconds: int,
        max_retained: int,
    ) -> None:
        """Forget finished jobs after ttl_seconds and beyond max_retained.

        The caller holds jobs_lock. Active jobs are never removed.
        """
        current = time.time() if now is None else now
        jobs = self.jobs
        for job in jobs.values():
            if job.status in TERMINAL_JOB_STATUSES and job.finished_at is None:
                job.finished_at = current
        expired = [
            job_id
            for job_id, job in jobs.items()
            if job.status in TERMINAL_JOB_STATUSES
            and job.finished_at is not None
            and current - job.finished_at >= ttl_seconds
        ]
        for job_id in expired:
            jobs.pop(job_id, None)
        excess = len(jobs) - max_retained
        if excess <= 0:
            return
        removable = sorted(
            (
                (job.finished_at or job.created_at, job_id)
                for job_id, job in jobs.items()
                if job.status in TERMINAL_JOB_STATUSES
            ),
            key=lambda value: value[0],
        )
        for _created_at, job_id in removable[:excess]:
            jobs.pop(job_id, None)

    def active_job_ids(self, active_statuses: frozenset[str]) -> set[str]:
        with self.jobs_lock:
            return {
                job_id
                for job_id, job in self.jobs.items()
                if job.status in active_statuses
            }

    def update_job(
        self,
        job: JobRecord,
        *,
        max_log_lines: int,
        progress: int | None = None,
        message: str | None = None,
        stage: str | None = None,
        stage_label: str | None = None,
        stage_progress: int | None = None,
    ) -> None:
        """Advance a job's visible progress; progress never moves backwards."""
        with self.jobs_lock:
            if progress is not None:
                job.progress = max(job.progress, min(100, progress))
            if stage is not None:
                job.stage = stage
            if stage_label is not None:
                job.stage_label = stage_label
            if stage_progress is not None:
                job.stage_progress = max(0, min(100, stage_progress))
            if message is not None:
                job.message = message
                job.logs.append(message)
                job.logs = job.logs[-max_log_lines:]
