"""専用Linux環境でRE-USEのローカル前処理を実行する。"""
from __future__ import annotations

import json
import shutil
import sys
import wave
from pathlib import Path
from typing import Callable

from .qwen_stack import REPOSITORY_ROOT

RUNTIME_CONFIG = REPOSITORY_ROOT / ".venv-reuse" / "wsl-runtime.json"
WORKER = REPOSITORY_ROOT / "scripts" / "reuse_audio_worker.py"
MODEL_REVISION = "31f82f2efad1095034492f236e8dac9239ba713b"


def reuse_setup_message() -> str:
    return "RE-USEの専用環境が未準備です。Windowsは scripts\\setup_reuse.bat、Linuxは bash scripts/setup_reuse.sh を実行してください。"


def load_reuse_runtime() -> dict | None:
    try:
        config = json.loads(RUNTIME_CONFIG.read_text(encoding="utf-8"))
        workspace = config.get("workspace") if sys.platform == "win32" else config.get("linux_workspace")
        if not isinstance(workspace, str) or Path(workspace).resolve() != REPOSITORY_ROOT:
            return None
        if config.get("revision") != MODEL_REVISION or config.get("ready") is not True:
            return None
        if not all(isinstance(config.get(k), str) and config[k].startswith("/") for k in ("python", "model_directory")):
            return None
        if sys.platform == "win32":
            if not config.get("distribution") or not shutil.which("wsl.exe"):
                return None
        elif not Path(config["python"]).is_file() or not Path(config["model_directory"], "model.safetensors").is_file():
            return None
        if not WORKER.is_file() or not (REPOSITORY_ROOT / "scripts" / "wsl_stack_worker.py").is_file():
            return None
        return config
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def reuse_available() -> bool:
    return load_reuse_runtime() is not None


def run_reuse(input_path: Path, output_path: Path, check_cancelled: Callable[[], None] | None = None) -> Path:
    from .wsl_stack import run_wsl_worker
    runtime = load_reuse_runtime()
    if runtime is None:
        raise RuntimeError(reuse_setup_message())
    check = check_cancelled or (lambda: None)
    check()
    request = output_path.with_name(output_path.stem + "-reuse-request.json")
    request.write_text(json.dumps({
        "asr_audio": str(input_path.resolve()), "result_path": str(output_path.resolve()),
        "model_directory": runtime["model_directory"],
    }, ensure_ascii=False), encoding="utf-8")
    # 既存ブリッジのパス変換とプロセスグループ中止を利用する。
    run_wsl_worker(runtime, WORKER, request, output_path.with_suffix(".reuse.log"),
                   "NemotronLabs RE-USE", lambda _message: None, check)
    check()
    try:
        with wave.open(str(input_path), "rb") as source, wave.open(str(output_path), "rb") as result:
            if (result.getnchannels(), result.getsampwidth(), result.getframerate(), result.getnframes()) != (
                1, 2, source.getframerate(), source.getnframes()
            ):
                raise RuntimeError("RE-USEの出力形式または音声長が一致しません。")
    except (OSError, EOFError, wave.Error) as exc:
        raise RuntimeError("RE-USEが有効な音声ファイルを作成しませんでした。") from exc
    return output_path
