"""Assign Nemotron 3 speaker turns to Qwen3-ForcedAligner timestamps."""

from __future__ import annotations

import gc
import json
import math
import sys
import traceback
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from transformers import AutoModelForAudioFrameClassification, AutoProcessor


MODEL_ID = "nvidia/Nemotron-3-Diarization"
SAMPLE_RATE = 16_000


def load_audio(path: str) -> np.ndarray:
    audio, sample_rate = sf.read(path, dtype="float32", always_2d=False)
    if sample_rate != SAMPLE_RATE:
        raise RuntimeError(f"Audio must be {SAMPLE_RATE} Hz; got {sample_rate} Hz")
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1, dtype=np.float32)
    if audio.ndim != 1 or not len(audio):
        raise RuntimeError("Audio is empty or has an unsupported number of channels")
    return np.asarray(audio, dtype=np.float32)


def speaker_name(value) -> str:
    text = str(value)
    suffix = text.rsplit("_", 1)[-1]
    try:
        return f"SPEAKER_{int(suffix):02d}"
    except ValueError:
        return text.upper().replace(" ", "_")


def main(request_path: Path) -> None:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    device = request["diarization_device"]
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable for Nemotron 3 Diarization")
    model_device = "cuda:0" if device == "cuda" else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    audio = load_audio(request["diarization_audio"])
    print("Loading Nemotron 3 Diarization", flush=True)
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForAudioFrameClassification.from_pretrained(
        MODEL_ID,
        device_map=model_device,
        torch_dtype=dtype,
    )
    model.eval()
    inputs = processor(audio, sampling_rate=SAMPLE_RATE).to(model.device, dtype=model.dtype)
    with torch.inference_mode():
        logits = model(**inputs).logits
    raw_turns = processor.extract_speaker_dict(logits, inputs.attention_mask)[0]

    turns = []
    for row in raw_turns:
        try:
            start, end = float(row.get("Start")), float(row.get("End"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(start) and math.isfinite(end) and end > start:
            turns.append((start, end, speaker_name(row.get("Speaker", "UNKNOWN"))))
    del model, processor, inputs, logits
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    segments = request.get("segments")
    if not isinstance(segments, list):
        raise RuntimeError("Qwen transcript segments are missing")
    for segment in segments:
        start, end = float(segment["start"]), float(segment["end"])
        midpoint = (start + end) / 2
        overlapping = []
        for turn_start, turn_end, name in turns:
            overlap = min(end, turn_end) - max(start, turn_start)
            if overlap > 0:
                overlapping.append((overlap, turn_start <= midpoint <= turn_end, name))
        if overlapping:
            overlapping.sort(key=lambda row: (row[0], row[1]), reverse=True)
            segment["speaker"] = overlapping[0][2]
        else:
            segment["speaker"] = None

    result = {"language": request.get("language"), "segments": segments}
    Path(request["result_path"]).write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Assigned speakers to {len(segments)} aligned segments", flush=True)


if __name__ == "__main__":
    try:
        main(Path(sys.argv[1]))
    except Exception:
        traceback.print_exc()
        raise
