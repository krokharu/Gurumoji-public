"""Read-only prerequisites. Never import a model, authenticate, or download here."""
from __future__ import annotations
import importlib.util
import os
import shutil
from pathlib import Path
from .transcription.qwen_stack import qwen_stack_available

MODELS = ("tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "turbo")


def transcription_readiness() -> dict:
    missing = []
    for module in ("torch", "whisper", "whisperx", "pyannote"):
        try:
            present = importlib.util.find_spec(module) is not None
        except (ValueError, ImportError, ModuleNotFoundError):
            present = False
        if not present:
            missing.append(module)
    blockers = ["必要なPython環境が未準備です: " + ", ".join(missing)] if missing else []
    if not shutil.which("ffmpeg"):
        blockers.append("FFmpegが見つかりません")
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    hf = Path(os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE") or str(Path(os.environ.get("HF_HOME", str(cache / "huggingface"))) / "hub"))
    models = {"cpu": {}, "cuda": {}}
    for model in MODELS:
        cached = (cache / "whisper" / f"{model}.pt").is_file()
        models["cpu"][model] = {"status": "cached" if cached else "missing", "message": f"{model} / CPU: " + ("キャッシュあり（整合性は読込み時に確認）" if cached else "未取得。開始時に配布元からダウンロードされます")}
        snapshots = hf / f"models--Systran--faster-whisper-{model}" / "snapshots"
        gpu_cached = snapshots.is_dir() and any(path.is_file() for path in snapshots.glob("*/model.bin"))
        models["cuda"][model] = {"status": "cached" if gpu_cached else "unknown", "message": f"{model} / CUDA: " + ("キャッシュ候補あり（GPU世代と読込み時に確認）" if gpu_cached else "モデル準備は未確認。GPU世代によりWhisper形式も使用します")}
    return {
        "whisperx": {"blockers": blockers, "models": models, "notes": ["Hugging Faceの利用許諾・トークン権限、話者分離・言語アライメントのモデルは未検証です。開始時に取得や接続が必要な場合があります"]},
        "qwen3_nemotron": {"blockers": [] if qwen_stack_available() else ["Qwen3 / Nemotron 3の独立実行環境が未準備です"], "notes": ["Qwen3 / ForcedAligner / Nemotron 3のモデル取得状況は未確認です。初回はダウンロードが必要な場合があります"]},
    }
