"""FFmpeg audio preparation for the transcription pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class AudioProcessor:
    """Application-configured audio processing port."""

    presets: dict[str, dict[str, Any]]
    sample_rate: int
    run_subprocess: Callable[..., Any]

    def label(self, preset: str) -> str:
        return label(preset, self.presets)

    def filters(self, preset: str) -> list[str]:
        return filters(preset, self.presets, self.sample_rate)

    def preprocess(
        self, input_path: Path, output_path: Path, preset: str,
        check_cancelled: Callable[[], None] | None = None,
    ) -> Path:
        return preprocess(
            input_path, output_path, preset, presets=self.presets,
            sample_rate=self.sample_rate, run_subprocess=self.run_subprocess,
            check_cancelled=check_cancelled,
        )

    def preprocess_for_diarization(
        self, input_path: Path, output_path: Path,
        check_cancelled: Callable[[], None] | None = None,
    ) -> Path:
        return preprocess(
            input_path, output_path, DIARIZATION_PRESET_KEY,
            presets={DIARIZATION_PRESET_KEY: DIARIZATION_AUDIO_PRESET},
            sample_rate=self.sample_rate, run_subprocess=self.run_subprocess,
            check_cancelled=check_cancelled,
        )

    def preprocess_interval(
        self, input_path: Path, output_path: Path, start: float, end: float,
        preset: str, check_cancelled: Callable[[], None] | None = None,
    ) -> Path:
        return preprocess_interval(
            input_path, output_path, start, end, preset, presets=self.presets,
            sample_rate=self.sample_rate, run_subprocess=self.run_subprocess,
            check_cancelled=check_cancelled,
        )


def label(preset: str, presets: dict[str, dict[str, Any]]) -> str:
    return str(presets.get(preset, presets["standard"])["label"])


def filters(
    preset: str, presets: dict[str, dict[str, Any]], sample_rate: int
) -> list[str]:
    if preset not in presets:
        raise RuntimeError(f"未対応の音声前処理です: {preset}")
    preset_filters = presets[preset]["filters"]
    if not preset_filters:
        return []
    result = [f"aresample={sample_rate}", "aformat=sample_fmts=fltp:channel_layouts=mono"]
    for audio_filter in preset_filters:
        if audio_filter.startswith("afftdn="):
            delay_samples = 2 * (sample_rate // 80)
            result.extend([
                f"apad=pad_len={delay_samples}", audio_filter,
                f"atrim=start_sample={delay_samples}", "asetpts=PTS-STARTPTS",
            ])
        else:
            result.append(audio_filter)
    return result


def preprocess(
    input_path: Path, output_path: Path, preset: str, *,
    presets: dict[str, dict[str, Any]], sample_rate: int,
    run_subprocess: Callable[..., Any], check_cancelled: Callable[[], None] | None = None,
) -> Path:
    selected_filters = filters(preset, presets, sample_rate)
    if not selected_filters:
        return input_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = run_subprocess(
        ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(input_path),
         "-map", "0:a:0", "-vn", "-af", ",".join(selected_filters), "-ac", "1",
         "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(output_path)],
        timeout=float(os.environ.get("MOJIOKOSI_FFMPEG_TIMEOUT_SECONDS", "7200")),
        check_cancelled=check_cancelled,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"音声前処理に失敗しました: {(completed.stderr or completed.stdout or '').strip()[-1500:]}")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("音声前処理後のファイルが作成されませんでした。")
    return output_path


def preprocess_interval(
    input_path: Path, output_path: Path, start: float, end: float, preset: str, *,
    presets: dict[str, dict[str, Any]], sample_rate: int,
    run_subprocess: Callable[..., Any], check_cancelled: Callable[[], None] | None = None,
) -> Path:
    selected_filters = filters(preset, presets, sample_rate)
    start, end = max(0.0, float(start)), max(max(0.0, float(start)), float(end))
    if end - start < 0.05:
        raise RuntimeError("再文字起こし区間が短すぎます。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-ss", f"{start:.3f}",
               "-t", f"{end - start:.3f}", "-i", str(input_path), "-map", "0:a:0", "-vn"]
    if selected_filters:
        command.extend(["-af", ",".join(selected_filters)])
    command.extend(["-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(output_path)])
    completed = run_subprocess(
        command, timeout=float(os.environ.get("MOJIOKOSI_FFMPEG_CLIP_TIMEOUT_SECONDS", "300")),
        check_cancelled=check_cancelled,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"再文字起こし区間の切り出しに失敗しました: {(completed.stderr or completed.stdout or '').strip()[-1500:]}")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("再文字起こし区間の音声ファイルが作成されませんでした。")
    return output_path


# Speaker diarization input. Unlike the transcription presets this applies no
# band limiting, denoising, or loudness normalization, which would reshape the
# voice characteristics speaker embeddings compare. It only lifts speech that
# is too quiet: half-waves below -6 dBFS peak are raised by at most 4x (+12 dB)
# within about a second; louder speech is never attenuated (c=1), and the noise
# floor below -40 dBFS (t) is not expanded.
DIARIZATION_PRESET_KEY = "diarization"
DIARIZATION_AUDIO_PRESET: dict[str, Any] = {
    "label": "話者分離用（小さすぎる声の持ち上げ）",
    "filters": ["speechnorm=p=0.5:e=4:c=1:t=0.01:r=0.01:l=1"],
}


AUDIO_PREPROCESS_PRESETS: dict[str, dict[str, Any]] = {
    "none": {
        "label": "加工なし",
        "filters": [],
    },
    "light": {
        "label": "軽め",
        "filters": [
            "highpass=f=70",
            "lowpass=f=7800",
            "loudnorm=I=-18:LRA=11:TP=-1.5",
        ],
    },
    "standard": {
        "label": "おすすめ",
        "filters": [
            "highpass=f=70",
            "lowpass=f=7800",
            "afftdn=nr=8:nf=-55:tn=1",
            "speechnorm=e=3:r=0.00001:l=1",
            "loudnorm=I=-18:LRA=11:TP=-1.5",
        ],
    },
    "strong": {
        "label": "強め",
        "filters": [
            "highpass=f=80",
            "lowpass=f=7600",
            "afftdn=nr=14:nf=-50:tn=1",
            "speechnorm=e=6.25:r=0.00001:l=1",
            "loudnorm=I=-18:LRA=11:TP=-1.5",
        ],
    },
}
