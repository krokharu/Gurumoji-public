"""Run the official Haas-ja-v1.0 recognizer (Third Intelligence) in isolation.

Haas returns text only, so the audio is cut at quiet points into pieces of at
most MAX_PIECE_SECONDS and each piece becomes one timestamped segment.
"""

from __future__ import annotations

import gc
import json
import sys
import traceback
from pathlib import Path


MODEL_ID = "third-intelligence/Haas-ja-v1.0"
SAMPLE_RATE = 16_000
FRAME_SECONDS = 0.02
MAX_PIECE_SECONDS = 25.0
MIN_PIECE_SECONDS = 1.0
TARGET_PIECE_SECONDS = 4.0
MIN_SILENCE_SECONDS = 0.35
SILENCE_RATIO = 0.08
BATCH_SIZE = 16


def frame_energy(samples):
    import numpy as np

    frame = int(SAMPLE_RATE * FRAME_SECONDS)
    count = len(samples) // frame
    if count == 0:
        return np.zeros(0, dtype=np.float32)
    framed = samples[: count * frame].reshape(count, frame)
    return np.sqrt(np.mean(framed * framed, axis=1))


def split_points(samples):
    """Return (start, end) sample ranges that end at quiet points."""
    import numpy as np

    energy = frame_energy(samples)
    total = len(samples)
    if not len(energy):
        return [(0, total)] if total else []
    frame_samples = int(SAMPLE_RATE * FRAME_SECONDS)
    threshold = max(float(np.percentile(energy, 95)) * SILENCE_RATIO, 1e-4)

    cuts = []
    run_start = None
    min_frames = int(MIN_SILENCE_SECONDS / FRAME_SECONDS)
    for index, is_quiet in enumerate([bool(value) for value in energy < threshold] + [False]):
        if is_quiet and run_start is None:
            run_start = index
        elif not is_quiet and run_start is not None:
            if index - run_start >= min_frames:
                cuts.append((run_start + index) // 2 * frame_samples)
            run_start = None

    max_samples = int(MAX_PIECE_SECONDS * SAMPLE_RATE)
    min_samples = int(MIN_PIECE_SECONDS * SAMPLE_RATE)
    target_samples = int(TARGET_PIECE_SECONDS * SAMPLE_RATE)
    pieces = []
    start = 0
    while total - start > max_samples:
        end = next((cut for cut in cuts if start + target_samples <= cut <= start + max_samples), None)
        if end is None:
            # No quiet point in range: cut at the quietest frame instead.
            lo = (start + min_samples) // frame_samples
            hi = (start + max_samples) // frame_samples
            end = (lo + int(np.argmin(energy[lo:hi]))) * frame_samples
        pieces.append((start, end))
        start = end
    pieces.append((start, total))
    return pieces


def is_speech(samples):
    import numpy as np

    energy = frame_energy(samples)
    if not len(energy):
        return False
    return float(np.percentile(energy, 90)) > 3e-3


def main(request_path: Path) -> None:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    language = request.get("language")
    if language not in (None, "ja"):
        raise RuntimeError("Haas-ja supports Japanese only")

    import numpy as np
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("Haas-ja requires an NVIDIA GPU (CUDA is unavailable)")
    import haas_asr

    audio = haas_asr.load_audio(request["asr_audio"])
    samples = np.asarray(audio, dtype=np.float32)
    ranges = [(start, end) for start, end in split_points(samples) if is_speech(samples[start:end])]
    if not ranges:
        raise RuntimeError("No speech was found in the audio")

    print("Loading Haas-ja-v1.0", flush=True)
    model = haas_asr.load_model(MODEL_ID)
    segments = []
    for offset in range(0, len(ranges), BATCH_SIZE):
        batch = ranges[offset:offset + BATCH_SIZE]
        print(f"Transcribing pieces {offset + 1}-{offset + len(batch)} of {len(ranges)}", flush=True)
        outputs = model.transcribe([audio[start:end] for start, end in batch])
        for (start, end), output in zip(batch, outputs, strict=True):
            text = str(getattr(output, "text", output) or "").strip()
            if text:
                segments.append(
                    {"start": start / SAMPLE_RATE, "end": end / SAMPLE_RATE, "text": text}
                )
    del model
    gc.collect()
    torch.cuda.empty_cache()
    if not segments:
        raise RuntimeError("Haas-ja returned no text")

    Path(request["result_path"]).write_text(
        json.dumps({"language": "ja", "segments": segments}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved {len(segments)} segments", flush=True)


if __name__ == "__main__":
    try:
        main(Path(sys.argv[1]))
    except Exception:
        traceback.print_exc()
        raise
