"""Isolated worker bridge for the optional Qwen3/Nemotron stack."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
QWEN_PYTHON = REPOSITORY_ROOT / ".venv-qwen" / "Scripts" / "python.exe"
NEMOTRON_PYTHON = REPOSITORY_ROOT / ".venv-nemotron" / "Scripts" / "python.exe"
QWEN_WORKER = REPOSITORY_ROOT / "scripts" / "qwen_stack_worker.py"
NEMOTRON_WORKER = REPOSITORY_ROOT / "scripts" / "nemotron_diarization_worker.py"
QWEN_READY = REPOSITORY_ROOT / ".venv-qwen" / ".qwen-stack-ready"
NEMOTRON_READY = REPOSITORY_ROOT / ".venv-nemotron" / ".qwen-stack-ready"


def qwen_stack_setup_message() -> str:
    return (
        "Qwen3 / Nemotron 3 用の独立環境がありません。WhisperX環境を変更せずに、"
        "scripts\\setup_qwen_stack.bat を実行してから再試行してください。"
    )


def qwen_stack_available() -> bool:
    return (
        QWEN_PYTHON.is_file()
        and NEMOTRON_PYTHON.is_file()
        and QWEN_WORKER.is_file()
        and NEMOTRON_WORKER.is_file()
        and QWEN_READY.is_file()
        and NEMOTRON_READY.is_file()
    )


def run_qwen_stack(
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
    if not qwen_stack_available():
        raise RuntimeError(qwen_stack_setup_message())

    asr_request_path = work_dir / "qwen-asr-request.json"
    asr_result_path = work_dir / "qwen-asr-result.json"
    diarization_request_path = work_dir / "nemotron-request.json"
    result_path = work_dir / "qwen-stack-result.json"

    def write_request(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    write_request(
        asr_request_path,
        {
            "asr_audio": str(asr_audio_path.resolve()),
            "language": language,
            "asr_device": asr_device,
            "result_path": str(asr_result_path.resolve()),
        },
    )

    asr_result_path.unlink(missing_ok=True)
    run_worker(
        QWEN_PYTHON,
        QWEN_WORKER,
        asr_request_path,
        work_dir / "qwen-asr.log",
        "Qwen3-ASR / ForcedAligner",
        status,
        check_cancelled,
    )
    try:
        asr_payload = json.loads(asr_result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Qwen3-ASR / ForcedAligner が有効な結果を返しませんでした。") from exc
    asr_segments = asr_payload.get("segments") if isinstance(asr_payload, dict) else None
    if not isinstance(asr_segments, list) or not asr_segments:
        raise RuntimeError("Qwen3 / ForcedAligner が有効な発話区間を返しませんでした。")

    write_request(
        diarization_request_path,
        {
            "diarization_audio": str(diarization_audio_path.resolve()),
            "diarization_device": diarization_device,
            "language": asr_payload.get("language"),
            "segments": asr_segments,
            "result_path": str(result_path.resolve()),
        },
    )
    result_path.unlink(missing_ok=True)
    run_worker(
        NEMOTRON_PYTHON,
        NEMOTRON_WORKER,
        diarization_request_path,
        work_dir / "nemotron.log",
        "Nemotron 3 Diarization",
        status,
        check_cancelled,
    )
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Nemotron 3 worker が有効な結果を返しませんでした。") from exc
    segments = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(segments, list) or not segments:
        raise RuntimeError("Qwen3 / Nemotron 3 worker が有効な結果を返しませんでした。")
    return payload


def run_worker(
    python: Path,
    worker: Path,
    request: Path,
    log_path: Path,
    label: str,
    status: Callable[[str], None],
    check_cancelled: Callable[[], None],
) -> None:
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [str(python), str(worker), str(request)],
            cwd=str(REPOSITORY_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        last_status = time.monotonic()
        try:
            while process.poll() is None:
                check_cancelled()
                if time.monotonic() - last_status >= 15:
                    status(f"{label} を実行しています…")
                    last_status = time.monotonic()
                time.sleep(0.25)
        except BaseException:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            raise

    if process.returncode != 0:
        try:
            details = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
        except OSError:
            details = []
        detail = "\n".join(details).strip()
        raise RuntimeError(
            f"{label} の処理に失敗しました。モデル環境・GPUメモリを確認してください。"
            + (f"\n{detail}" if detail else "")
        )
