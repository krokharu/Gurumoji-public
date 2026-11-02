"""以前に保存した感情ラベルの表示互換。推論処理は含まない。"""
from __future__ import annotations
import re
from typing import Any

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
