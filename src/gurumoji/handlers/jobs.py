"""Transcription job use cases, independent from Flask."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


class JobRequestError(RuntimeError):
    def __init__(
        self, message: str, status: int, *, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.details = details or {}


@dataclass(frozen=True)
class JobArtifact:
    path: Path
    download_name: str


class JobHandler:
    """Coordinate admission, runtime state, edits, and job-owned artifacts."""

    def __init__(
        self,
        *,
        jobs: dict[str, Any],
        lock: Any,
        active_statuses: set[str] | frozenset[str],
        prune: Callable[[], None],
        admission_id: Callable[[], str | None],
        admission_public: Callable[[str], dict[str, Any]],
        start_job: Callable[..., tuple[dict[str, Any], int]],
        update_job: Callable[..., None],
        update_transcript: Callable[[str, Any], dict[str, Any]],
        path_is_within: Callable[[Path, Path], bool],
    ) -> None:
        self._jobs = jobs
        self._lock = lock
        self._active_statuses = active_statuses
        self._prune = prune
        self._admission_id = admission_id
        self._admission_public = admission_public
        self._start_job = start_job
        self._update_job = update_job
        self._update_transcript = update_transcript
        self._path_is_within = path_is_within

    def start(
        self,
        form: Mapping[str, Any],
        upload: Any,
        *,
        admission_id: str | None,
    ) -> tuple[dict[str, Any], int]:
        return self._start_job(form, upload, admission_id=admission_id)

    def get(self, job_id: str) -> tuple[dict[str, Any], int]:
        with self._lock:
            self._prune()
            job = self._jobs.get(job_id)
            admitting = job is None and self._admission_id() == job_id
            if job is not None:
                return job.public(), 200
        if admitting:
            return self._admission_public(job_id), 202
        raise JobRequestError("ジョブが見つかりません。", 404)

    def active(self) -> dict[str, Any]:
        with self._lock:
            self._prune()
            active = [
                job for job in self._jobs.values()
                if job.status in self._active_statuses
            ]
            job = max(active, key=lambda value: value.created_at) if active else None
            admitting_id = self._admission_id() if job is None else None
            public_job = (
                job.public()
                if job is not None
                else self._admission_public(admitting_id) if admitting_id else None
            )
        return {"job": public_job}

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobRequestError("ジョブが見つかりません。", 404)
            if job.status not in {"queued", "running"}:
                raise JobRequestError("このジョブは既に終了しています。", 409)
            job.cancel_event.set()
        self._update_job(
            job, message="中止を要求しました。現在の処理区切りで停止します…"
        )
        return {"ok": True}

    def save_transcript(self, job_id: str, payload: Any) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobRequestError("ジョブが見つかりません。", 404)
        if job.status != "completed":
            raise JobRequestError("完了したジョブだけを編集できます。", 409)
        result = self._update_transcript(job_id, payload)
        self._update_job(
            job, message="手動編集を保存し、修正差分を学習データへ蓄積しました。"
        )
        return result

    def artifact(self, job_id: str, filename: str) -> JobArtifact:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobRequestError("ジョブが見つかりません。", 404)
            matching = next(
                (
                    path for path in job.files
                    if path.name == filename
                    and self._path_is_within(path, job.output_dir)
                ),
                None,
            )
        if matching is None or not matching.is_file():
            raise JobRequestError("出力ファイルが見つかりません。", 404)
        return JobArtifact(matching, matching.name)
