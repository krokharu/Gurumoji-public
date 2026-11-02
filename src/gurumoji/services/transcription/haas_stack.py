"""Experimental bridge to the official Haas-ja-v1.0 recognizer (Third Intelligence)."""

from __future__ import annotations

import json
import sys

from pathlib import Path
from typing import Any, Callable

from .wsl_stack import load_wsl_runtime, run_wsl_worker

from .qwen_stack import (
    NEMOTRON_PYTHON,
    NEMOTRON_READY,
    NEMOTRON_WORKER,
    REPOSITORY_ROOT,
    assign_speakers_with_nemotron,
    run_worker,
    venv_python,
)


HAAS_PYTHON = venv_python(".venv-haas")
HAAS_WORKER = REPOSITORY_ROOT / "scripts" / "haas_ja_worker.py"
HAAS_READY = REPOSITORY_ROOT / ".venv-haas" / ".haas-ready"


def haas_setup_message() -> str:
    if sys.platform == "win32":
        return (
            "Haas-jaのWSL2用環境が未準備です。Ubuntu＋NVIDIA GPUを用意し、"
            "scripts\\setup_haas_ja.bat を実行してから再試行してください。"
        )
    return "Haas-ja用環境が未準備です。scripts/setup_haas_ja.sh を実行してください。"


def haas_stack_available() -> bool:
    if sys.platform == "win32" or (REPOSITORY_ROOT / ".venv-haas" / "wsl-runtime.json").is_file():
        return load_wsl_runtime() is not None and HAAS_WORKER.is_file() and NEMOTRON_WORKER.is_file()
    return (
        sys.platform.startswith("linux")
        and HAAS_PYTHON.is_file()
        and HAAS_WORKER.is_file()
        and HAAS_READY.is_file()
        and NEMOTRON_PYTHON.is_file()
        and NEMOTRON_WORKER.is_file()
        and NEMOTRON_READY.is_file()
    )


def run_haas_worker(python, worker, request, log_path, label, status, check_cancelled):
    runtime = load_wsl_runtime()
    if runtime is None:
        run_worker(python, worker, request, log_path, label, status, check_cancelled)
    else:
        run_wsl_worker(runtime, worker, request, log_path, label, status, check_cancelled)


def run_haas_stack(
    *,
    asr_audio_path: Path,
    diarization_audio_path: Path,
    work_dir: Path,
    language: str | None,
    asr_device: str,
    diarization_device: str,
    status: Callable[[str], None],
    check_cancelled: Callable[[], None],
) -> dict[str, Any]:
    if not haas_stack_available():
        raise RuntimeError(haas_setup_message())
    if asr_device != "cuda":
        raise RuntimeError("Haas-ja（公式版）はGPU（CUDA）でのみ実行できます。")

    request_path = work_dir / "haas-asr-request.json"
    result_path = work_dir / "haas-asr-result.json"
    request_path.write_text(
        json.dumps(
            {
                "asr_audio": str(asr_audio_path.resolve()),
                "language": language,
                "result_path": str(result_path.resolve()),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result_path.unlink(missing_ok=True)
    run_haas_worker(
        HAAS_PYTHON,
        HAAS_WORKER,
        request_path,
        work_dir / "haas-asr.log",
        "Haas-ja",
        status,
        check_cancelled,
    )
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Haas-ja が有効な結果を返しませんでした。") from exc
    segments = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(segments, list) or not segments:
        raise RuntimeError("Haas-ja が有効な発話区間を返しませんでした。")

    return assign_speakers_with_nemotron(
        segments=segments,
        language=payload.get("language") or "ja",
        diarization_audio_path=diarization_audio_path,
        work_dir=work_dir,
        diarization_device=diarization_device,
        status=status,
        check_cancelled=check_cancelled,
        worker_runner=run_haas_worker,
    )
