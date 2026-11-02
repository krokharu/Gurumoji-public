"""Cancellable subprocess execution for FFmpeg and other external tools."""

from __future__ import annotations

import subprocess
import time
from typing import Any, Callable


def _stop_subprocess(process: subprocess.Popen[str]) -> None:
    """Best-effort termination used for cancellation and timeout paths."""
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except OSError:
        return
    try:
        process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def run_cancellable_subprocess(
    command: list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: float | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a child process while regularly honoring job cancellation."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    started_at = time.monotonic()
    pending_input = input_text
    while True:
        try:
            if check_cancelled is not None:
                check_cancelled()
            remaining = None if timeout is None else timeout - (time.monotonic() - started_at)
            if remaining is not None and remaining <= 0:
                _stop_subprocess(process)
                raise subprocess.TimeoutExpired(command, timeout)
            wait_seconds = 0.25 if remaining is None else min(0.25, remaining)
            communication_input = pending_input
            pending_input = None
            communicate_kwargs: dict[str, Any] = {"timeout": wait_seconds}
            if communication_input is not None:
                communicate_kwargs["input"] = communication_input
            stdout, stderr = process.communicate(**communicate_kwargs)
            if check_cancelled is not None:
                check_cancelled()
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            if timeout is not None and time.monotonic() - started_at >= timeout:
                _stop_subprocess(process)
                raise subprocess.TimeoutExpired(command, timeout)
        except BaseException:
            _stop_subprocess(process)
            raise
