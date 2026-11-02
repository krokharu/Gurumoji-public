"""Windowsから作業フォルダー専用のLinuxモデル環境を呼び出す。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .qwen_stack import REPOSITORY_ROOT, run_worker

RUNTIME_CONFIG = REPOSITORY_ROOT / ".venv-haas" / "wsl-runtime.json"
BRIDGE_WORKER = REPOSITORY_ROOT / "scripts" / "wsl_stack_worker.py"


def load_wsl_runtime() -> dict | None:
    try:
        config = json.loads(RUNTIME_CONFIG.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or not BRIDGE_WORKER.is_file():
            return None
        workspace = config.get("workspace", "") if sys.platform == "win32" else config.get("linux_workspace", config.get("workspace", ""))
        if Path(workspace).resolve() != REPOSITORY_ROOT:
            return None
        for key in ("python", "nemotron_python"):
            if not isinstance(config.get(key), str) or not config[key].startswith("/"):
                return None
        if sys.platform == "win32" and not config.get("distribution"):
            return None
        return config
    except (OSError, ValueError, TypeError):
        return None


def wsl_command(runtime: dict) -> list[str]:
    return ["wsl.exe", "--distribution", runtime["distribution"], "--exec"]


def linux_path(path: Path, runtime: dict) -> str:
    if sys.platform != "win32":
        return str(path.resolve())
    result = subprocess.run(
        [*wsl_command(runtime), "wslpath", "-a", "-u", str(path.resolve())],
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return result.stdout.strip()


def run_wsl_worker(runtime, worker, request, log_path, label, status, check_cancelled):
    check_cancelled()
    payload = json.loads(request.read_text(encoding="utf-8"))
    for key in ("asr_audio", "diarization_audio", "result_path"):
        if key in payload:
            payload[key] = linux_path(Path(payload[key]), runtime)
    translated = request.with_name(request.stem + "-linux.json")
    translated.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    pid_path = request.with_suffix(".pid")
    stopped_path = request.with_suffix(".cancelled")
    pid_path.unlink(missing_ok=True)
    stopped_path.unlink(missing_ok=True)
    python_key = "nemotron_python" if worker.name == "nemotron_diarization_worker.py" else "python"
    command = [
        runtime[python_key], linux_path(BRIDGE_WORKER, runtime),
        linux_path(worker, runtime), linux_path(translated, runtime),
        linux_path(pid_path, runtime), linux_path(stopped_path, runtime),
    ]
    if sys.platform == "win32":
        command = [*wsl_command(runtime), *command]

    def cancel_worker():
        # 起動直後の中止もLinux側へ渡し、GPUプロセスの取り残しを防ぐ。
        stopped_path.touch()
        try:
            pid = int(pid_path.read_text(encoding="ascii").strip())
            if pid <= 1:
                return
            stop = ["/bin/kill", "-TERM", "--", f"-{pid}"]
            if sys.platform == "win32":
                stop = [*wsl_command(runtime), *stop]
            subprocess.run(stop, capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass

    status(f"{label}を専用Linux環境で実行します。")
    run_worker(Path(runtime[python_key]), worker, translated, log_path, label,
               status, check_cancelled, command=command, cancel_worker=cancel_worker)
