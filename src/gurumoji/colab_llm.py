"""Colabの空き資源に合わせた仕上げ用Ollamaモデルの選択。"""

from __future__ import annotations

import csv
import io
import math
import os
from pathlib import Path
import re
import subprocess

from .colab_support import ColabSetupError


# 重みだけでなく入力枠・作業領域を見込み、音声処理用のGPU余裕も別に残す。
# 閾値は実測ベンチマークによる品質順位ではなく、同時利用向けの保守的な推奨値。
GPU_PROFILES = (
    (56, 40, "qwen3:30b-a3b-instruct-2507-q8_0", 32768),
    (28, 24, "qwen3:30b-a3b-instruct-2507-q4_K_M", 32768),
    (16, 8, "qwen3:4b-instruct-2507-q8_0", 32768),
    (8, 6, "qwen3:4b-instruct-2507-q4_K_M", 32768),
    (4, 4, "qwen2.5:3b-instruct", 32768),
    (2, 3, "qwen2.5:1.5b-instruct", 32768),
)


def normalize_ollama_model(model: str) -> str:
    """自由入力を単一のモデル名として扱い、省略したタグはlatestにそろえる。"""
    if not isinstance(model, str):
        raise ColabSetupError("LLM_MODEL", "LOCAL_LLM_MODELはautoまたはOllamaのモデル名で指定してください。")
    model = model.strip()
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", model)
        or "://" in model or "//" in model
        or any(part in {".", "..", ""} for part in model.split("/"))
        or model.endswith(":")
    ):
        raise ColabSetupError("LLM_MODEL", "Ollamaのモデル名を入力してください。例: qwen3:4b-instruct、hf.co/組織/モデル:量子化タグ。URL・空白・コマンドは指定できません。")
    if model.lower().endswith(("-cloud", ":cloud")):
        raise ColabSetupError("LLM_MODEL", "仕上げ用のローカルモデルを指定してください。Ollamaのクラウドモデルには対応していません。")
    return model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"


def ollama_model_matches(actual, requested: str) -> bool:
    try:
        return normalize_ollama_model(actual) == normalize_ollama_model(requested)
    except ColabSetupError:
        return False


def detect_colab_llm_runtime(*, runner=subprocess.run, meminfo_path=Path("/proc/meminfo"), environ=None):
    """モデルを読まずにRAMとNVIDIAの空き容量を取得する。複数GPUは合算しない。"""
    environment = os.environ if environ is None else environ
    ram_available = None
    try:
        memory = {}
        for line in meminfo_path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(":")
            if key in {"MemAvailable", "MemFree"}:
                memory[key] = max(0, int(value.split()[0])) / 1024**2
        ram_available = memory.get("MemAvailable", memory.get("MemFree"))
    except (OSError, ValueError, IndexError):
        pass
    gpus = []
    visible = environment.get("CUDA_VISIBLE_DEVICES")
    detection = "disabled" if visible is not None and visible.strip() in {"", "-1"} else "unavailable"
    if detection != "disabled":
        try:
            result = runner([
                "nvidia-smi", "--query-gpu=index,uuid,name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ], capture_output=True, text=True, check=True, timeout=10)
            detection = "detected"
            allowed = {value.strip() for value in visible.split(",")} if visible is not None else None
            for row in csv.reader(io.StringIO(result.stdout)):
                if len(row) != 5:
                    continue
                index, uuid, name, total, free = (value.strip() for value in row)
                if allowed is not None and index not in allowed and uuid not in allowed:
                    continue
                try:
                    total_gib, free_gib = float(total) / 1024, float(free) / 1024
                    if not math.isfinite(total_gib) or not math.isfinite(free_gib) or not 0 <= free_gib <= total_gib or total_gib <= 0:
                        continue
                except ValueError:
                    continue
                gpus.append({"id": uuid or index, "name": name, "total_gib": total_gib, "free_gib": free_gib})
        except (OSError, subprocess.SubprocessError):
            pass
    return {"ram_available_gib": ram_available, "cpu_count": os.cpu_count() or 1,
            "gpus": gpus, "gpu_detection": detection}


def select_colab_llm(runtime: dict, model="auto", context_length=0) -> dict:
    """直接指定を優先し、autoの場合だけ空き容量に合う推奨モデルを選ぶ。"""
    automatic = isinstance(model, str) and model.strip().lower() in {"", "auto"}
    specified = None if automatic else normalize_ollama_model(model)
    if type(context_length) is not int or context_length != 0 and not 4096 <= context_length <= 32768:
        raise ColabSetupError("LLM_CONTEXT", "LOCAL_LLM_CONTEXT_LENGTHは0（自動）または4096〜32768で指定してください。")
    ram = runtime.get("ram_available_gib")
    gpu = max(runtime.get("gpus", []), key=lambda row: row["free_gib"], default=None)
    reserve = max(4.0, gpu["total_gib"] * 0.10) if gpu else 0.0
    budget = max(0.0, gpu["free_gib"] - reserve) if gpu else 0.0
    # 長い本文・アウトラインと生成結果に使う枠は、従来の既定値を維持する。
    selected, context = "qwen2.5:1.5b-instruct", 32768
    gpu_selected = False
    for required_gpu, required_ram, candidate, candidate_context in GPU_PROFILES:
        if budget >= required_gpu and ram is not None and ram >= required_ram:
            selected, context, gpu_selected = candidate, candidate_context, True
            break
    if not gpu_selected and ram is not None:
        if ram >= 8 and runtime.get("cpu_count", 1) >= 4:
            selected = "qwen2.5:3b-instruct"
        elif ram < 3 and automatic:
            raise ColabSetupError("LLM_MEMORY", "仕上げ用LLMの利用可能RAMが3GiB未満です。メモリーを確保するかUSE_LOCAL_LLMをOFFにして外部AIを選んでください。")
    # 指定モデルの必要容量は推定しない。取得・JSON応答の検査で確認する。
    use_gpu = gpu is not None and (gpu_selected or not automatic)
    device = gpu["id"] if use_gpu else "-1" if runtime.get("gpu_detection") != "unavailable" else None
    reason = "空きGPU容量とRAMから選択（音声処理用の余裕を確保）" if gpu_selected else "CPU・低メモリー向けの軽量候補"
    if ram is None or runtime.get("gpu_detection") == "unavailable":
        reason += "。取得できない資源情報があるため容量の適合は未確認"
    if not automatic:
        reason = "直接指定を優先。モデルの必要容量・入力枠への適合は起動確認で検査"
    return {"model": specified or selected, "context_length": context_length or context,
            "automatic": automatic, "reason": reason, "cuda_visible_devices": device,
            "gpu_name": gpu["name"] if gpu else None, "gpu_free_gib": gpu["free_gib"] if gpu else None,
            "gpu_reserve_gib": reserve, "ram_available_gib": ram}
