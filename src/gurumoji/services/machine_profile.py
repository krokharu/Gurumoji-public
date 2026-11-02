"""CPU/RAM/GPU detection, recommended settings and live activity sampling.

The detected profile is cached per process; activity sampling keeps the
previous I/O counters to report rates."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

from ..text_utils import utc_now_iso


machine_profile_lock = threading.Lock()
machine_profile_cache: dict[str, Any] | None = None
system_activity_lock = threading.Lock()
system_activity_previous_io: tuple[float, int, int, int, int] | None = None


def total_system_memory_gib() -> float:
    if sys.platform == "win32":
        try:
            import ctypes

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.ullTotalPhys / (1024**3), 1)
        except (AttributeError, OSError, ValueError):
            pass
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        page_count = int(os.sysconf("SC_PHYS_PAGES"))
        return round(page_size * page_count / (1024**3), 1)
    except (AttributeError, OSError, TypeError, ValueError):
        return 0.0


def recommend_machine_settings(
    cpu_threads: int,
    memory_gib: float,
    cuda_available: bool,
    vram_gib: float = 0.0,
    capability_major: int = 0,
) -> dict[str, str]:
    if cuda_available:
        if capability_major < 7:
            model_name = "base" if vram_gib >= 4 else "tiny"
            reason = "旧世代CUDA GPUのため、互換性を優先した軽量設定です。"
        elif vram_gib >= 11.5:
            model_name = "large-v3"
            reason = "VRAM 12 GB以上のCUDA GPUを活かす最高精度設定です。"
        elif vram_gib >= 7.5:
            model_name = "medium"
            reason = "VRAM 8 GB以上のCUDA GPU向け高精度設定です。"
        elif vram_gib >= 5.5:
            model_name = "small"
            reason = "VRAM容量と精度のバランスを取ったGPU設定です。"
        elif vram_gib >= 3.5:
            model_name = "base"
            reason = "VRAM 4 GB級GPUで安定性を優先した設定です。"
        else:
            model_name = "tiny"
            reason = "GPUメモリが少ないため、最軽量モデルを推奨します。"
        diarization_device = "cuda" if capability_major >= 7 and vram_gib >= 7.5 else "cpu"
        return {
            "model_name": model_name,
            "device": "cuda",
            "diarization_device": diarization_device,
            "reason": reason,
        }

    if memory_gib >= 16 and cpu_threads >= 8:
        model_name = "small"
        reason = "CUDAを利用できないため、CPUとRAMを活かす高精度寄りの設定です。"
    elif memory_gib >= 8 and cpu_threads >= 4:
        model_name = "base"
        reason = "CUDAを利用できないため、CPUで安定しやすい標準設定です。"
    else:
        model_name = "tiny"
        reason = "CUDAを利用できずCPU/RAMも限られるため、最軽量設定です。"
    return {
        "model_name": model_name,
        "device": "cpu",
        "diarization_device": "cpu",
        "reason": reason,
    }


def detect_machine_profile() -> dict[str, Any]:
    cpu_threads = max(1, os.cpu_count() or 1)
    cpu_name = (
        platform.processor()
        or os.environ.get("PROCESSOR_IDENTIFIER", "")
        or platform.machine()
        or "CPU"
    ).strip()
    memory_gib = total_system_memory_gib()
    gpu: dict[str, Any] = {
        "cuda_available": False,
        "name": "",
        "vram_gib": 0.0,
        "cuda_version": "",
        "capability": "",
        "device_count": 0,
        "reason": "PyTorchでCUDAを利用できません。",
    }
    try:
        import torch

        gpu["torch_version"] = str(getattr(torch, "__version__", ""))
        gpu["cuda_version"] = str(getattr(torch.version, "cuda", "") or "")
        gpu["cuda_available"] = bool(torch.cuda.is_available())
        if gpu["cuda_available"]:
            gpu["device_count"] = int(torch.cuda.device_count())
            properties = torch.cuda.get_device_properties(0)
            capability = torch.cuda.get_device_capability(0)
            gpu.update({
                "name": str(properties.name),
                "vram_gib": round(properties.total_memory / (1024**3), 1),
                "capability": f"{capability[0]}.{capability[1]}",
                "capability_major": int(capability[0]),
                "reason": "",
            })
        elif not gpu["cuda_version"]:
            gpu["reason"] = "インストール済みPyTorchがCUDA対応ではありません。"
        else:
            gpu["reason"] = "CUDA対応PyTorchからGPUを使用できません。ドライバーを確認してください。"
    except Exception as exc:
        gpu["reason"] = f"GPU診断に失敗しました: {exc}"

    recommended = recommend_machine_settings(
        cpu_threads,
        memory_gib,
        bool(gpu["cuda_available"]),
        float(gpu["vram_gib"]),
        int(gpu.get("capability_major", 0)),
    )
    return {
        "checked_at": utc_now_iso(),
        "cpu": {
            "available": True,
            "name": cpu_name,
            "logical_threads": cpu_threads,
        },
        "memory_gib": memory_gib,
        "gpu": gpu,
        "recommended": recommended,
    }


def get_machine_profile(*, refresh: bool = False) -> dict[str, Any]:
    global machine_profile_cache
    with machine_profile_lock:
        if machine_profile_cache is None or refresh:
            machine_profile_cache = detect_machine_profile()
        return {
            **machine_profile_cache,
            "cpu": dict(machine_profile_cache["cpu"]),
            "gpu": dict(machine_profile_cache["gpu"]),
            "recommended": dict(machine_profile_cache["recommended"]),
        }


def nvidia_activity_snapshot() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {
            "available": False,
            "utilization_percent": None,
            "memory_used_gib": None,
            "memory_total_gib": None,
            "memory_percent": None,
        }
    try:
        completed = subprocess.run(
            [
                executable,
                "--id=0",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            raise RuntimeError("nvidia-smi failed")
        first_line = next(
            (line.strip() for line in completed.stdout.splitlines() if line.strip()),
            "",
        )
        values = [float(value.strip()) for value in first_line.split(",")]
        if len(values) != 3:
            raise ValueError("unexpected nvidia-smi response")
        utilization, memory_used_mib, memory_total_mib = values
        memory_percent = (
            100.0 * memory_used_mib / memory_total_mib
            if memory_total_mib > 0
            else 0.0
        )
        return {
            "available": True,
            "utilization_percent": round(max(0.0, min(100.0, utilization)), 1),
            "memory_used_gib": round(memory_used_mib / 1024, 2),
            "memory_total_gib": round(memory_total_mib / 1024, 2),
            "memory_percent": round(max(0.0, min(100.0, memory_percent)), 1),
        }
    except (OSError, RuntimeError, StopIteration, subprocess.TimeoutExpired, ValueError):
        return {
            "available": False,
            "utilization_percent": None,
            "memory_used_gib": None,
            "memory_total_gib": None,
            "memory_percent": None,
        }


def system_activity_snapshot() -> dict[str, Any]:
    global system_activity_previous_io
    now = time.monotonic()
    cpu: dict[str, Any] = {"available": False, "utilization_percent": None}
    memory: dict[str, Any] = {
        "available": False,
        "utilization_percent": None,
        "used_gib": None,
        "total_gib": None,
    }
    disk: dict[str, Any] = {
        "available": False,
        "read_active": False,
        "write_active": False,
        "read_mib_per_second": 0.0,
        "write_mib_per_second": 0.0,
    }
    try:
        import psutil

        # Flask's threaded development server may handle every poll on a new
        # thread. psutil keeps the non-blocking baseline per thread, so
        # interval=None can return the meaningless first-call value (0.0) on
        # every request. A short blocking sample is thread-independent.
        cpu_percent = float(psutil.cpu_percent(interval=0.1))
        virtual_memory = psutil.virtual_memory()
        total_bytes = int(virtual_memory.total)
        available_bytes = int(virtual_memory.available)
        cpu = {
            "available": True,
            "utilization_percent": round(max(0.0, min(100.0, cpu_percent)), 1),
        }
        memory = {
            "available": True,
            "utilization_percent": round(
                max(0.0, min(100.0, float(virtual_memory.percent))), 1
            ),
            "used_gib": round((total_bytes - available_bytes) / (1024**3), 1),
            "total_gib": round(total_bytes / (1024**3), 1),
        }
        io_counters = psutil.Process(os.getpid()).io_counters()
        read_bytes = int(getattr(io_counters, "read_bytes", 0) or 0)
        write_bytes = int(getattr(io_counters, "write_bytes", 0) or 0)
        read_count = int(getattr(io_counters, "read_count", 0) or 0)
        write_count = int(getattr(io_counters, "write_count", 0) or 0)
        with system_activity_lock:
            previous = system_activity_previous_io
            system_activity_previous_io = (
                now,
                read_bytes,
                write_bytes,
                read_count,
                write_count,
            )
        if previous is None:
            elapsed = 0.0
            read_delta = 0
            write_delta = 0
        else:
            elapsed = max(0.001, now - previous[0])
            read_delta = max(0, read_bytes - previous[1])
            write_delta = max(0, write_bytes - previous[2])
        disk = {
            "available": True,
            "read_active": read_delta > 0 or (previous is not None and read_count > previous[3]),
            "write_active": write_delta > 0 or (previous is not None and write_count > previous[4]),
            "read_mib_per_second": round(read_delta / elapsed / (1024**2), 2) if elapsed else 0.0,
            "write_mib_per_second": round(write_delta / elapsed / (1024**2), 2) if elapsed else 0.0,
        }
    except (AttributeError, ImportError, OSError, ValueError):
        pass
    return {
        "sampled_at": utc_now_iso(),
        "cpu": cpu,
        "memory": memory,
        "gpu": nvidia_activity_snapshot(),
        "disk": disk,
    }
