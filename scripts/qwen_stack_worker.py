"""Run the optional Qwen3 ASR/aligner and Nemotron 3 diarizer in isolation."""

from __future__ import annotations

import gc
import json
import math
import sys
import traceback
from pathlib import Path


ASR_MODEL_ID = "Qwen/Qwen3-ASR-1.7B"
ALIGNER_MODEL_ID = "Qwen/Qwen3-ForcedAligner-0.6B"
SAMPLE_RATE = 16_000
ASR_CHUNK_SECONDS = 290

LANGUAGE_NAMES = {
    "ja": "Japanese",
    "en": "English",
    "zh": "Chinese",
    "ko": "Korean",
}


def read_audio(path: str):
    import numpy as np
    import soundfile as sf

    audio, sample_rate = sf.read(path, dtype="float32", always_2d=False)
    if sample_rate != SAMPLE_RATE:
        raise RuntimeError(f"Audio must be {SAMPLE_RATE} Hz; got {sample_rate} Hz")
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1, dtype=np.float32)
    if audio.ndim != 1 or not len(audio):
        raise RuntimeError("Audio is empty or has an unsupported number of channels")
    return np.asarray(audio, dtype=np.float32)


def read_timestamp(item):
    if isinstance(item, dict):
        text = item.get("text", "")
        start = item.get("start_time", item.get("start"))
        end = item.get("end_time", item.get("end"))
    else:
        text = getattr(item, "text", "")
        start = getattr(item, "start_time", getattr(item, "start", None))
        end = getattr(item, "end_time", getattr(item, "end", None))
    try:
        start, end = float(start), float(end)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(start) or not math.isfinite(end) or end <= start or not str(text).strip():
        return None
    return {"start": start, "end": end, "text": str(text).strip()}


def transcribe_and_align(audio, language, device):
    import torch
    from qwen_asr import Qwen3ASRModel

    model_device = "cuda:0" if device == "cuda" else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    print("Loading Qwen3-ASR and Qwen3-ForcedAligner", flush=True)
    model = Qwen3ASRModel.from_pretrained(
        ASR_MODEL_ID,
        dtype=dtype,
        device_map=model_device,
        forced_aligner=ALIGNER_MODEL_ID,
        forced_aligner_kwargs={"dtype": dtype, "device_map": model_device},
        max_inference_batch_size=1,
        max_new_tokens=4096,
    )
    language_name = LANGUAGE_NAMES.get(language) if language else None
    chunk_samples = ASR_CHUNK_SECONDS * SAMPLE_RATE
    segments = []
    detected_language = language
    for offset in range(0, len(audio), chunk_samples):
        chunk = audio[offset:offset + chunk_samples]
        print(f"Transcribing and aligning audio at {offset / SAMPLE_RATE:.1f}s", flush=True)
        result = model.transcribe(
            audio=(chunk, SAMPLE_RATE),
            language=language_name,
            return_time_stamps=True,
        )[0]
        detected_language = detected_language or getattr(result, "language", None)
        timestamps = getattr(result, "time_stamps", None) or []
        for item in timestamps:
            timestamp = read_timestamp(item)
            if timestamp is None:
                continue
            timestamp["start"] += offset / SAMPLE_RATE
            timestamp["end"] += offset / SAMPLE_RATE
            segments.append(timestamp)
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if not segments:
        raise RuntimeError("Qwen3-ForcedAligner returned no usable timestamps")
    if detected_language and not isinstance(detected_language, str):
        detected_language = str(detected_language)
    detected_language = {
        "Japanese": "ja", "English": "en", "Chinese": "zh", "Korean": "ko",
    }.get(detected_language, detected_language)
    return segments, detected_language


def main(request_path: Path) -> None:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    import torch

    if request["asr_device"] == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable for Qwen3-ASR")
    asr_audio = read_audio(request["asr_audio"])
    segments, language = transcribe_and_align(
        asr_audio,
        request.get("language"),
        request["asr_device"],
    )
    output_path = Path(request["result_path"])
    output_path.write_text(
        json.dumps({"language": language, "segments": segments}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved {len(segments)} aligned segments", flush=True)


if __name__ == "__main__":
    try:
        main(Path(sys.argv[1]))
    except Exception:
        traceback.print_exc()
        raise
