"""AIST (kushinada / izanami) utterance emotion analysis.

The models run through S3PRL in a child process, so this module owns the
snapshot download, the S3PRL corpus layout, and the reading back of
predictions.  Application-edge concerns -- where model caches live and how a
cancellable subprocess is spawned -- are injected by the composition root.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable

from ..env_settings import positive_env_int
from .transcription.segments import segment_bounds

AIST_EMOTION_MODELS: dict[str, dict[str, str]] = {
    "kushinada": {
        "label": "くしなだ",
        "display": "くしなだ / HuBERT Large",
        "emotion_repo": "imprt/kushinada-hubert-large-jtes-er",
        "upstream_repo": "imprt/kushinada-hubert-large",
        "upstream_file": "kushinada-hubert-large-s3prl.pt",
        "checkpoint_dir": "kushinada-hubert-large-jtes-er_fold1",
        "fold": "fold1",
        "reference_accuracy": "0.8477",
    },
    "izanami": {
        "label": "いざなみ",
        "display": "いざなみ / wav2vec 2.0 Large",
        "emotion_repo": "imprt/izanami-wav2vec2-large-jtes-er",
        "upstream_repo": "imprt/izanami-wav2vec2-large",
        "upstream_file": "izanami-wav2vec2-large-s3prl.pt",
        "checkpoint_dir": "izanami-wav2vec2-large-jtes-er_fold1",
        "fold": "fold1",
        "reference_accuracy": "0.8012",
    },
}
AIST_EMOTION_LABEL_JA = {
    "ang": "怒り",
    "anger": "怒り",
    "angry": "怒り",
    "hap": "喜び",
    "happy": "喜び",
    "joy": "喜び",
    "sad": "悲しみ",
    "sadness": "悲しみ",
    "neu": "平常",
    "neutral": "平常",
}


def aist_emotion_model_keys(choice: str) -> list[str]:
    if choice == "both":
        return ["kushinada", "izanami"]
    if choice in AIST_EMOTION_MODELS:
        return [choice]
    raise ValueError("感情分析モデルの指定が不正です。")


def emotion_label_ja(label: str | None) -> str:
    text = str(label or "").strip()
    if not text:
        return "不明"
    key = re.sub(r"[^a-zA-Z]", "", text).lower()
    return AIST_EMOTION_LABEL_JA.get(key, text)


def segment_emotion_display(segment: dict[str, Any]) -> str:
    emotions = segment.get("emotions")
    if not isinstance(emotions, dict) or not emotions:
        return ""
    parts: list[str] = []
    ordered_keys = [key for key in ("kushinada", "izanami") if key in emotions]
    ordered_keys.extend(sorted(key for key in emotions if key not in ordered_keys))
    for model_key in ordered_keys:
        data = emotions.get(model_key)
        if not isinstance(data, dict):
            continue
        model_name = str(data.get("model_name") or AIST_EMOTION_MODELS.get(model_key, {}).get("label") or model_key)
        label = str(data.get("label_ja") or emotion_label_ja(data.get("label")))
        confidence = data.get("confidence")
        if isinstance(confidence, (int, float)):
            parts.append(f"{model_name}: {label} {float(confidence):.2f}")
        else:
            parts.append(f"{model_name}: {label}")
    return " / ".join(parts)


def build_emotion_analysis_summary(
    segments: list[dict[str, Any]],
    model_keys: list[str],
    *,
    status: str = "completed",
    error: str = "",
) -> dict[str, Any]:
    model_infos = [
        {
            "key": key,
            "name": AIST_EMOTION_MODELS[key]["display"],
            "repo": AIST_EMOTION_MODELS[key]["emotion_repo"],
            "fold": AIST_EMOTION_MODELS[key]["fold"],
            "reference_accuracy": AIST_EMOTION_MODELS[key]["reference_accuracy"],
        }
        for key in model_keys
        if key in AIST_EMOTION_MODELS
    ]
    label_counts: dict[str, dict[str, dict[str, Any]]] = {}
    by_speaker: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    analyzed_segments = 0
    for segment in segments:
        emotions = segment.get("emotions")
        if not isinstance(emotions, dict) or not emotions:
            continue
        analyzed_segments += 1
        speaker = str(segment.get("speaker") or "UNKNOWN")
        for model_key, data in emotions.items():
            if not isinstance(data, dict):
                continue
            label = str(data.get("label") or "unknown")
            label_ja = str(data.get("label_ja") or emotion_label_ja(label))
            model_bucket = label_counts.setdefault(model_key, {})
            entry = model_bucket.setdefault(label, {"label": label, "label_ja": label_ja, "count": 0})
            entry["count"] += 1
            speaker_bucket = by_speaker.setdefault(speaker, {}).setdefault(model_key, {})
            speaker_entry = speaker_bucket.setdefault(label, {"label": label, "label_ja": label_ja, "count": 0})
            speaker_entry["count"] += 1
    payload: dict[str, Any] = {
        "enabled": True,
        "status": status,
        "source": "audio",
        "unit": "segment",
        "models": model_infos,
        "analyzed_segments": analyzed_segments,
        "label_counts": label_counts,
        "by_speaker": by_speaker,
    }
    if error:
        payload["error"] = error
    return payload


def emotion_segments_for_output(
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(segments):
        emotions = item.get("emotions")
        if not isinstance(emotions, dict):
            emotions = {}
        speaker = item.get("speaker")
        speaker_label = str(speaker) if speaker else ""
        rows.append({
            "index": index,
            "start": round(float(item.get("start", 0)), 3),
            "end": round(float(item.get("end", item.get("start", 0))), 3),
            "speaker": speaker_label,
            "speaker_name": speaker_names.get(speaker_label, "") if speaker_label else "",
            "text": str(item.get("text", "")).strip(),
            "emotions": emotions,
        })
    return rows


def emotion_csv_text(
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    *,
    csv_safe: Callable[[Any], Any],
) -> str:
    buffer = io.StringIO(newline="")
    fieldnames = [
        "index",
        "start",
        "end",
        "speaker",
        "speaker_name",
        "model",
        "model_repo",
        "fold",
        "label",
        "label_ja",
        "confidence",
        "text",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for index, item in enumerate(segments):
        emotions = item.get("emotions")
        if not isinstance(emotions, dict) or not emotions:
            continue
        speaker = str(item.get("speaker") or "")
        for model_key, data in emotions.items():
            if not isinstance(data, dict):
                continue
            row = {
                "index": index,
                "start": round(float(item.get("start", 0)), 3),
                "end": round(float(item.get("end", item.get("start", 0))), 3),
                "speaker": speaker,
                "speaker_name": speaker_names.get(speaker, ""),
                "model": data.get("model_name", model_key),
                "model_repo": data.get("model_repo", ""),
                "fold": data.get("fold", ""),
                "label": data.get("label", ""),
                "label_ja": data.get("label_ja", ""),
                "confidence": "" if data.get("confidence") is None else data.get("confidence"),
                "text": str(item.get("text", "")).strip(),
            }
            writer.writerow({key: csv_safe(value) for key, value in row.items()})
    return buffer.getvalue()

def is_huggingface_access_error(exc: Exception) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    message = str(exc)
    return (
        status_code in {401, 403, 404}
        or exc.__class__.__name__ in {"GatedRepoError", "RepositoryNotFoundError", "HfHubHTTPError"}
        or "Cannot access gated repo" in message
        or "401 Client Error" in message
        or "403 Client Error" in message
    )


def aist_model_access_error_message(repo_id: str) -> str:
    return (
        f"AIST感情分析モデル {repo_id} にアクセスできません。"
        f"Hugging Faceで利用条件に同意し、tokens.jsonのhuggingface_tokenを確認してください。\n"
        f"https://huggingface.co/{repo_id}"
    )


def aist_cache_dir(repo_id: str, *, runtime_directory: Path) -> Path:
    return runtime_directory / "models" / "aist" / repo_id.replace("/", "__")


def snapshot_download_to_local(
    repo_id: str,
    token: str,
    allow_patterns: list[str],
    status: Callable[[str], None],
    *,
    runtime_directory: Path,
) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("huggingface_hub が見つかりません。run.batで環境を再セットアップしてください。") from exc
    local_dir = aist_cache_dir(repo_id, runtime_directory=runtime_directory)
    local_dir.mkdir(parents=True, exist_ok=True)
    status(f"Hugging FaceからAISTモデルを確認しています: {repo_id}")
    try:
        downloaded = snapshot_download(
            repo_id=repo_id,
            token=token,
            local_dir=str(local_dir),
            allow_patterns=allow_patterns,
        )
    except Exception as exc:
        if is_huggingface_access_error(exc):
            raise RuntimeError(aist_model_access_error_message(repo_id)) from exc
        raise RuntimeError(f"AISTモデル {repo_id} の取得に失敗しました: {exc}") from exc
    return Path(downloaded)


def resolve_s3prl_runtime_dir(*, runtime_directory: Path) -> Path:
    candidates: list[Path] = []
    env_root = os.environ.get("MOJIOKOSI_S3PRL_ROOT", "").strip().strip('"')
    if env_root:
        candidates.append(Path(env_root))
    candidates.extend([
        runtime_directory / "models" / "s3prl-v0.4.17",
        runtime_directory / "models" / "s3prl-v0.4.17" / "s3prl",
    ])
    for candidate in candidates:
        expanded = candidate.expanduser()
        if (expanded / "run_downstream.py").is_file():
            return expanded.resolve()
        if (expanded / "s3prl" / "run_downstream.py").is_file():
            return (expanded / "s3prl").resolve()
    raise RuntimeError(
        "AIST感情分析にはS3PRL v0.4.17のソースが必要です。"
        "このフォルダの setup_emotion.bat を一度実行してください。"
    )


def ensure_s3prl_importable(
    runtime_dir: Path,
    check_cancelled: Callable[[], None] | None = None,
    *,
    run_subprocess: Callable[..., Any],
) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_dir.parent) + os.pathsep + env.get("PYTHONPATH", "")
    completed = run_subprocess(
        [
            sys.executable,
            "-c",
            (
                "import s3prl, soundfile, torch, torchaudio, yaml; "
                "assert 'soundfile' in torchaudio.list_audio_backends(), "
                "'TorchAudio SoundFile backend is unavailable'"
            ),
        ],
        cwd=str(runtime_dir),
        env=env,
        timeout=float(os.environ.get("MOJIOKOSI_EMOTION_IMPORT_TIMEOUT_SECONDS", "180")),
        check_cancelled=check_cancelled,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()[-1200:]
        raise RuntimeError(
            "AIST感情分析用のS3PRL依存関係を読み込めません。"
            "setup_emotion.bat を実行してください。\n" + details
        )


def copy_tree_files(source_root: Path, target_root: Path) -> None:
    if not source_root.is_dir():
        return
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        target = target_root / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def prepare_aist_s3prl_files(
    model_key: str,
    hf_token: str,
    runtime_dir: Path,
    status: Callable[[str], None],
    *,
    runtime_directory: Path,
) -> Path:
    config = AIST_EMOTION_MODELS[model_key]
    emotion_snapshot = snapshot_download_to_local(
        config["emotion_repo"],
        hf_token,
        [
            "README.md",
            "s3prl/downstream/emotion/expert.py",
            "s3prl/jtes/Session*/train_meta_data.json",
            "s3prl/jtes/Session*/test_meta_data.json",
            "s3prl/result/downstream/*fold1/dev-best.ckpt",
        ],
        status,
        runtime_directory=runtime_directory,
    )
    upstream_snapshot = snapshot_download_to_local(
        config["upstream_repo"],
        hf_token,
        [f"s3prl/{config['upstream_file']}"],
        status,
        runtime_directory=runtime_directory,
    )
    copy_tree_files(emotion_snapshot / "s3prl", runtime_dir)
    upstream_source = upstream_snapshot / "s3prl" / config["upstream_file"]
    if not upstream_source.is_file():
        raise RuntimeError(
            f"AIST上流モデルファイルが見つかりません: {config['upstream_repo']} / {config['upstream_file']}"
        )
    upstream_target = runtime_dir / "upstream_models" / config["upstream_file"]
    upstream_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(upstream_source, upstream_target)
    return emotion_snapshot


def load_aist_emotion_labels(emotion_snapshot: Path) -> dict[str, int]:
    candidates = [
        emotion_snapshot / "s3prl" / "jtes" / "Session1" / "train_meta_data.json",
        emotion_snapshot / "s3prl" / "jtes" / "Session1" / "test_meta_data.json",
    ]
    for candidate in candidates:
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        labels = data.get("labels") if isinstance(data, dict) else None
        if isinstance(labels, dict) and labels:
            parsed: dict[str, int] = {}
            for label, index in labels.items():
                try:
                    parsed[str(label)] = int(index)
                except (TypeError, ValueError):
                    continue
            if parsed:
                return parsed
    return {"joy": 0, "anger": 1, "sadness": 2, "neutral": 3}


def extract_emotion_segment_wavs(
    audio_path: Path,
    segments: list[dict[str, Any]],
    work_dir: Path,
    check_cancelled: Callable[[], None],
    *,
    run_subprocess: Callable[..., Any],
) -> tuple[Path, list[dict[str, Any]]]:
    wav_root = work_dir / "emotion_segments"
    wav_root.mkdir(parents=True, exist_ok=True)
    planned: list[dict[str, Any]] = []
    extracted: list[dict[str, Any]] = []
    try:
        for index, segment in enumerate(segments):
            check_cancelled()
            start, end = segment_bounds(segment)
            duration = end - start
            if duration < 0.15:
                continue
            padded_start = max(0.0, start - 0.05)
            padded_duration = duration + (start - padded_start) + 0.05
            output_path = wav_root / f"seg_{index:06d}.wav"
            try:
                output_path.unlink()
            except FileNotFoundError:
                pass
            planned.append(
                {
                    "index": index,
                    "path": output_path,
                    "stem": output_path.stem,
                    "start": padded_start,
                    "duration": padded_duration,
                }
            )

        if not planned:
            raise RuntimeError("感情分析できる長さの発話セグメントがありません。")

        # Keep each Windows command comfortably below CreateProcess' command-line
        # limit while decoding the source only once per group instead of once per
        # utterance. The size is configurable for unusually long work paths.
        batch_size = positive_env_int(
            "MOJIOKOSI_FFMPEG_CLIP_BATCH_SIZE",
            24,
            minimum=1,
            maximum=32,
        )
        timeout_seconds = float(
            os.environ.get("MOJIOKOSI_FFMPEG_CLIP_TIMEOUT_SECONDS", "300")
        )
        for batch_start in range(0, len(planned), batch_size):
            check_cancelled()
            batch = planned[batch_start : batch_start + batch_size]
            batch_seek_start = min(float(item["start"]) for item in batch)
            batch_end = max(
                float(item["start"]) + float(item["duration"])
                for item in batch
            )
            # Input-side seeking prevents every later batch from decoding the
            # entire recording prefix. A tiny tail allowance avoids losing the
            # final sample to independent millisecond rounding.
            batch_input_duration = max(0.001, batch_end - batch_seek_start + 0.01)
            filter_parts: list[str] = []
            if len(batch) == 1:
                input_labels = ["[0:a:0]"]
            else:
                input_labels = [f"[split{offset}]" for offset in range(len(batch))]
                filter_parts.append(
                    f"[0:a:0]asplit={len(batch)}{''.join(input_labels)}"
                )
            for offset, (input_label, item) in enumerate(zip(input_labels, batch)):
                relative_start = max(0.0, float(item["start"]) - batch_seek_start)
                filter_parts.append(
                    f"{input_label}atrim=start={relative_start:.3f}:"
                    f"duration={item['duration']:.3f},asetpts=PTS-STARTPTS,"
                    f"aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono"
                    f"[clip{offset}]"
                )
            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-ss",
                f"{batch_seek_start:.3f}",
                "-t",
                f"{batch_input_duration:.3f}",
                "-i",
                str(audio_path),
                "-filter_complex",
                ";".join(filter_parts),
            ]
            for offset, item in enumerate(batch):
                command.extend(
                    [
                        "-map",
                        f"[clip{offset}]",
                        "-vn",
                        "-c:a",
                        "pcm_s16le",
                        str(item["path"]),
                    ]
                )
            completed = run_subprocess(
                command,
                timeout=timeout_seconds,
                check_cancelled=check_cancelled,
            )
            failed_outputs = [
                item
                for item in batch
                if not item["path"].is_file() or item["path"].stat().st_size == 0
            ]
            if completed.returncode != 0 or failed_outputs:
                details = (completed.stderr or completed.stdout or "").strip()[-1000:]
                raise RuntimeError(f"感情分析用の音声切り出しに失敗しました: {details}")
            extracted.extend(
                {"index": item["index"], "path": item["path"], "stem": item["stem"]}
                for item in batch
            )
        return wav_root, extracted
    except BaseException:
        # A later batch may fail after earlier WAVs were completed. Do not leave
        # a partial corpus that a retry or S3PRL run could accidentally consume.
        for item in planned:
            try:
                item["path"].unlink()
            except (FileNotFoundError, OSError):
                pass
        raise


def create_s3prl_emotion_metadata(
    labels: dict[str, int],
    segment_wavs: list[dict[str, Any]],
    metadata_root: Path,
) -> None:
    session_dir = metadata_root / "Session1"
    session_dir.mkdir(parents=True, exist_ok=True)
    first_path = Path(segment_wavs[0]["path"]).name
    label_names = list(labels.keys()) or ["neutral"]
    train_meta = [{"path": first_path, "label": label} for label in label_names]
    test_meta = [
        {"path": Path(item["path"]).name, "label": label_names[0]}
        for item in segment_wavs
    ]
    payload_train = {"labels": labels, "meta_data": train_meta}
    payload_test = {"labels": labels, "meta_data": test_meta}
    (session_dir / "train_meta_data.json").write_text(
        json.dumps(payload_train, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (session_dir / "test_meta_data.json").write_text(
        json.dumps(payload_test, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_s3prl_predictions(prediction_path: Path) -> dict[str, str]:
    predictions: dict[str, str] = {}
    for line in prediction_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            predictions[parts[0]] = parts[-1]
    return predictions


def run_s3prl_emotion_model(
    model_key: str,
    wav_root: Path,
    segment_wavs: list[dict[str, Any]],
    hf_token: str,
    device: str,
    work_dir: Path,
    status: Callable[[str], None],
    check_cancelled: Callable[[], None],
    *,
    runtime_directory: Path,
    run_subprocess: Callable[..., Any],
) -> dict[int, str]:
    config = AIST_EMOTION_MODELS[model_key]
    runtime_dir = resolve_s3prl_runtime_dir(runtime_directory=runtime_directory)
    ensure_s3prl_importable(runtime_dir, check_cancelled, run_subprocess=run_subprocess)
    emotion_snapshot = prepare_aist_s3prl_files(
        model_key, hf_token, runtime_dir, status, runtime_directory=runtime_directory
    )
    labels = load_aist_emotion_labels(emotion_snapshot)
    metadata_root = work_dir / f"{model_key}_meta"
    create_s3prl_emotion_metadata(labels, segment_wavs, metadata_root)
    checkpoint = runtime_dir / "result" / "downstream" / config["checkpoint_dir"] / "dev-best.ckpt"
    if not checkpoint.is_file():
        raise RuntimeError(f"AIST感情分析チェックポイントが見つかりません: {checkpoint}")
    override = ",,".join([
        f"config.downstream_expert.datarc.root={str(wav_root)!r}",
        f"config.downstream_expert.datarc.meta_data={str(metadata_root)!r}",
        "config.downstream_expert.datarc.eval_batch_size=1",
        "config.downstream_expert.datarc.train_batch_size=1",
        "config.downstream_expert.datarc.num_workers=0",
        "config.downstream_expert.datarc.pre_load=False",
        "config.runner.eval_dataloaders=['test']",
    ])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_dir.parent) + os.pathsep + env.get("PYTHONPATH", "")
    env["HF_TOKEN"] = hf_token
    timeout_seconds = float(os.environ.get("MOJIOKOSI_EMOTION_TIMEOUT_SECONDS", "3600"))
    command = [
        sys.executable,
        "run_downstream.py",
        "-m",
        "evaluate",
        "-t",
        "test",
        "-e",
        str(checkpoint),
        "--device",
        device,
        "-o",
        override,
    ]
    expected_prediction = (
        runtime_dir
        / "result"
        / "downstream"
        / config["checkpoint_dir"]
        / f"test_{config['fold']}_predict.txt"
    )
    # The S3PRL result tree is shared by every run. Remove the previous run's
    # predictions so a run that writes elsewhere cannot silently reuse them.
    expected_prediction.unlink(missing_ok=True)
    status(f"AIST感情分析を実行しています: {config['display']} / {config['fold']}")
    check_cancelled()
    started_at = time.time()
    completed = run_subprocess(
        command,
        cwd=str(runtime_dir),
        env=env,
        timeout=timeout_seconds,
        check_cancelled=check_cancelled,
    )
    check_cancelled()
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()[-1800:]
        raise RuntimeError(f"S3PRLでのAIST感情分析に失敗しました: {details}")
    prediction_path = expected_prediction if expected_prediction.is_file() else None
    if prediction_path is None:
        candidates = [
            path
            for path in (runtime_dir / "result" / "downstream").glob("**/test_*_predict.txt")
            if path.stat().st_mtime >= started_at - 5
        ]
        if candidates:
            prediction_path = max(candidates, key=lambda path: path.stat().st_mtime)
    if prediction_path is None:
        raise RuntimeError("S3PRLの感情予測ファイルを取得できませんでした。")
    predictions_by_stem = read_s3prl_predictions(prediction_path)
    indexed: dict[int, str] = {}
    for item in segment_wavs:
        label = predictions_by_stem.get(str(item["stem"]))
        if label:
            indexed[int(item["index"])] = label
    return indexed


def run_aist_emotion_analysis(
    audio_path: Path,
    segments: list[dict[str, Any]],
    model_choice: str,
    hf_token: str,
    device: str,
    work_dir: Path,
    status: Callable[[str], None],
    check_cancelled: Callable[[], None],
    *,
    runtime_directory: Path,
    run_subprocess: Callable[..., Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model_keys = aist_emotion_model_keys(model_choice)
    updated_segments = [dict(segment) for segment in segments]
    status("感情分析用に発話ごとの音声を切り出しています。")
    wav_root, segment_wavs = extract_emotion_segment_wavs(
        audio_path, updated_segments, work_dir, check_cancelled, run_subprocess=run_subprocess
    )
    for model_key in model_keys:
        check_cancelled()
        predictions = run_s3prl_emotion_model(
            model_key,
            wav_root,
            segment_wavs,
            hf_token,
            device,
            work_dir,
            status,
            check_cancelled,
            runtime_directory=runtime_directory,
            run_subprocess=run_subprocess,
        )
        config = AIST_EMOTION_MODELS[model_key]
        for segment_index, label in predictions.items():
            emotions = updated_segments[segment_index].get("emotions")
            if not isinstance(emotions, dict):
                emotions = {}
            emotions[model_key] = {
                "model_key": model_key,
                "model_name": config["label"],
                "model_display": config["display"],
                "model_repo": config["emotion_repo"],
                "fold": config["fold"],
                "source": "audio",
                "label": label,
                "label_ja": emotion_label_ja(label),
                "confidence": None,
            }
            updated_segments[segment_index]["emotions"] = emotions
    summary = build_emotion_analysis_summary(updated_segments, model_keys, status="completed")
    check_cancelled()
    return updated_segments, summary
