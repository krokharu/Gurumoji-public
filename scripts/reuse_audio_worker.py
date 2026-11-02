"""NVIDIA公式の重み・ネットワークを使ったローカル分割推論。"""
from __future__ import annotations

import json
from pathlib import Path
import sys


def load_model(directory: Path):
    import torch
    from safetensors.torch import load_model as load_weights
    if not torch.cuda.is_available():
        raise RuntimeError("RE-USEには専用Linux環境で利用できるNVIDIA GPUが必要です。")
    sys.path.insert(0, str(directory))
    from models.generator_SEMamba_time_d4 import SEMamba
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    model = SEMamba(cfg=config)
    load_weights(model, str(directory / "model.safetensors"), strict=True)
    return model.to("cuda").eval(), config


def enhance(request: dict):
    import numpy as np
    import soundfile as sf
    import torch
    import torch.nn.functional as functional
    model, config = load_model(Path(request["model_directory"]))
    from models.stfts import mag_phase_stft, mag_phase_istft
    destination = Path(request["result_path"])
    # 部分的な結果を完了ファイルに見せない。
    staged = destination.with_name(destination.stem + ".partial.wav")
    try:
        with sf.SoundFile(request["asr_audio"]) as source:
            if source.channels != 1 or source.samplerate != 16000 or source.frames == 0:
                raise RuntimeError("RE-USEの入力は空でない16kHz mono WAVにしてください。")
            rate, frames = source.samplerate, source.frames
            stft = config["stft_cfg"]
            scaled = lambda name: 2 * round((stft[name] * rate // stft["sampling_rate"]) / 2)
            n_fft, hop_size, win_size = (scaled(name) for name in ("n_fft", "hop_size", "win_size"))
            compression = config["model_cfg"]["compress_factor"]
            chunk = min(5 * rate, frames)
            step = max(1, chunk // 2)
            starts = list(range(0, max(1, frames - chunk + 1), step))
            if starts[-1] != frames - chunk:
                starts.append(frames - chunk)
            output = np.zeros(frames, dtype=np.float32)
            weights = np.zeros(frames, dtype=np.float32)
            window = torch.hann_window(chunk, device="cuda").clamp(min=1e-7)
            with torch.inference_mode():
                for index, start in enumerate(starts):
                    source.seek(start)
                    noisy = torch.from_numpy(source.read(chunk, dtype="float32")).unsqueeze(0).to("cuda")
                    if noisy.shape[1] <= n_fft // 2:
                        noisy = functional.pad(noisy, (0, n_fft - noisy.shape[1]))
                    magnitude, phase, _ = mag_phase_stft(noisy, n_fft, hop_size, win_size,
                                                       compress_factor=compression, center=True, addeps=False)
                    enhanced_mag, enhanced_phase, _ = model(magnitude, phase)
                    silent = (torch.expm1(torch.relu(enhanced_mag)) == 0).float().mean(dim=1) > 0.5
                    enhanced_mag[:, :, silent[0]] = 0
                    enhanced = mag_phase_istft(enhanced_mag, enhanced_phase, n_fft, hop_size, win_size, compression)
                    if enhanced.shape[1] < chunk:
                        enhanced = functional.pad(enhanced, (0, chunk - enhanced.shape[1]))
                    output[start:start + chunk] += (enhanced[0, :chunk] * window).cpu().numpy()
                    weights[start:start + chunk] += window.cpu().numpy()
                    print(f"RE-USE {index + 1}/{len(starts)}", flush=True)
            if not np.isfinite(output).all() or np.any(weights <= 0):
                raise RuntimeError("RE-USEの出力に不正な値または欠落があります。")
            output /= weights
            if not np.isfinite(output).all():
                raise RuntimeError("RE-USEの合成結果が不正です。")
            sf.write(staged, np.clip(output, -1, 1), rate, subtype="PCM_16")
        staged.replace(destination)
    finally:
        staged.unlink(missing_ok=True)


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if request.get("probe"):
        import tempfile
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory(prefix="gurumoji-reuse-probe-") as directory:
            source, output = Path(directory) / "input.wav", Path(directory) / "output.wav"
            sf.write(source, np.zeros(1600, dtype=np.float32), 16000, subtype="PCM_16")
            enhance({"model_directory": request["model_directory"], "asr_audio": str(source), "result_path": str(output)})
            if sf.info(output).frames != 1600:
                raise RuntimeError("RE-USEの準備確認で音声長が一致しません。")
        print("RE-USEのモデル読込み・GPU推論に成功しました。", flush=True)
    else:
        enhance(request)


if __name__ == "__main__":
    main()
