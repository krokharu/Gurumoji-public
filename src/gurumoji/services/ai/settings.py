"""AI provider settings read from config/tokens.json and local-LLM discovery.

Credentials are only read from the token file; the UI never receives them."""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import client as ai_client
from ...jev_review import JEV_DEFAULT_MODEL
from ...text_utils import clean_single_line
from ..durable_files import atomic_write_text


TOKEN_FILE_NAME = "tokens.json"
AI_PROVIDERS = {"none", "openai", "google", "lmstudio"}
AI_MODEL_PROVIDERS = frozenset(AI_PROVIDERS - {"none"})
LMSTUDIO_DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
LMSTUDIO_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})
AI_PROVIDER_LABELS = {
    "openai": "OpenAI",
    "google": "Google Gemini",
    "lmstudio": "LM Studio（ローカル）",
}


@dataclass(frozen=True)
class TokenConfig:
    huggingface_token: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    openai_model: str = "gpt-5.6-luna"
    google_model: str = "gemini-flash-latest"
    lmstudio_api_key: str = ""
    lmstudio_base_url: str = LMSTUDIO_DEFAULT_BASE_URL
    lmstudio_model: str = ""
    typesafe_api_key: str = ""
    typesafe_model: str = JEV_DEFAULT_MODEL

    def availability(self) -> dict[str, Any]:
        return {
            "token_file": TOKEN_FILE_NAME,
            "huggingface": bool(self.huggingface_token),
            "openai": bool(self.openai_api_key),
            "google": bool(self.google_api_key),
            "openai_model": self.openai_model,
            "google_model": self.google_model,
            "lmstudio_base_url": self.lmstudio_base_url,
            "lmstudio_model": self.lmstudio_model,
            "lmstudio_has_api_key": bool(self.lmstudio_api_key),
            "typesafe": bool(self.typesafe_api_key),
            "typesafe_model": self.typesafe_model,
            # Keep the lmstudio_* keys for backwards compatibility. The same
            # loopback-only OpenAI-compatible provider is backed by Ollama in
            # the Colab notebook.
            "local_llm_label": local_llm_label(),
            "local_llm_short_label": local_llm_short_label(),
        }

token_config_lock = threading.Lock()


def is_colab_runtime() -> bool:
    return (
        os.environ.get("MOJIOKOSI_RUNTIME", "").strip().casefold() == "colab"
        or "COLAB_RELEASE_TAG" in os.environ
    )


def clean_secret(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"your_token_here", "your_api_key_here", "hf_xxx", "sk-xxx", "aizaxxx"}:
        return ""
    return text


def load_token_config(path: Path) -> TokenConfig:
    """Read all credentials from tokens.json; credentials are never accepted by the UI."""
    if not path.is_file():
        return TokenConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{path.name} を読み込めません: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path.name} の最上位は JSON オブジェクトにしてください。")
    return TokenConfig(
        huggingface_token=clean_secret(raw.get("huggingface_token", raw.get("hf_token"))),
        openai_api_key=clean_secret(raw.get("openai_api_key")),
        google_api_key=clean_secret(raw.get("google_api_key", raw.get("gemini_api_key"))),
        openai_model=clean_secret(raw.get("openai_model")) or "gpt-5.6-luna",
        google_model=clean_secret(raw.get("google_model")) or "gemini-flash-latest",
        lmstudio_api_key=clean_secret(raw.get("lmstudio_api_key")),
        lmstudio_base_url=clean_single_line(
            raw.get("lmstudio_base_url"), 300
        ) or LMSTUDIO_DEFAULT_BASE_URL,
        lmstudio_model=clean_single_line(raw.get("lmstudio_model"), 200),
        typesafe_api_key=clean_secret(raw.get("typesafe_api_key")),
        typesafe_model=clean_single_line(raw.get("typesafe_model"), 200) or JEV_DEFAULT_MODEL,
    )


def lmstudio_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def lmstudio_model_id(value: Any) -> str:
    model = clean_single_line(value, 200)
    if not model or any(ord(character) < 33 or ord(character) == 127 for character in model):
        raise ValueError("モデルIDの形式が不正です。")
    return model


def configured_ai_credentials(config: TokenConfig, provider: str) -> tuple[str, str]:
    if provider == "openai":
        return config.openai_api_key, config.openai_model
    if provider == "google":
        return config.google_api_key, config.google_model
    if provider == "lmstudio":
        lmstudio_base_url(config.lmstudio_base_url)
        return config.lmstudio_api_key, config.lmstudio_model
    raise ValueError("AI プロバイダーが不正です。")


def local_llm_short_label() -> str:
    return "Ollama" if is_colab_runtime() else "LM Studio"


def local_llm_label() -> str:
    return "Ollama（ColabローカルLLM）" if is_colab_runtime() else "LM Studio（ローカル）"


def local_llm_model_required_message() -> str:
    return (
        f"{local_llm_short_label()} のモデルが未選択です。"
        "上部のローカルLLMライトをクリックして選択してください。"
    )


def ai_provider_label(provider: str) -> str:
    if provider == "lmstudio":
        return local_llm_label()
    return AI_PROVIDER_LABELS.get(provider, "AI")


def available_ai_models(
    provider: str,
    config: TokenConfig,
    *,
    timeout: float = 30,
) -> list[dict[str, Any]]:
    provider = str(provider or "").strip().casefold()
    if provider == "google":
        if not config.google_api_key:
            raise ValueError("Google Gemini のAPIキーが設定されていません。")
        request_object = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
            headers={"x-goog-api-key": config.google_api_key, "Accept": "application/json"},
            method="GET",
        )
    elif provider == "openai":
        if not config.openai_api_key:
            raise ValueError("OpenAI のAPIキーが設定されていません。")
        request_object = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={
                "Authorization": f"Bearer {config.openai_api_key}",
                "Accept": "application/json",
            },
            method="GET",
        )
    elif provider == "lmstudio":
        base_url = lmstudio_base_url(config.lmstudio_base_url)
        request_object = urllib.request.Request(
            f"{base_url}/models",
            headers={**lmstudio_headers(config.lmstudio_api_key), "Accept": "application/json"},
            method="GET",
        )
    else:
        raise ValueError("モデル一覧を取得できるAIを選択してください。")
    try:
        with urllib.request.urlopen(request_object, timeout=max(0.2, min(30.0, float(timeout)))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"モデル一覧APIが HTTP {exc.code} を返しました。") from exc
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"モデル一覧を取得できません: {exc}") from exc
    models: list[dict[str, Any]] = []
    if provider == "google":
        raw_models = payload.get("models") if isinstance(payload, dict) else None
        for item in raw_models if isinstance(raw_models, list) else []:
            if not isinstance(item, dict):
                continue
            methods = item.get("supportedGenerationMethods")
            if not isinstance(methods, list) or "generateContent" not in methods:
                continue
            model_id = str(item.get("name") or "").removeprefix("models/").strip()
            if not model_id.startswith("gemini-") or len(model_id) > 200:
                continue
            models.append({
                "id": model_id,
                "label": clean_single_line(item.get("displayName") or model_id, 200),
                "description": clean_single_line(item.get("description"), 300),
            })
    elif provider == "openai":
        raw_models = payload.get("data") if isinstance(payload, dict) else None
        excluded = (
            "embedding", "dall-e", "tts", "transcribe", "whisper", "moderation",
            "realtime", "audio", "image", "search", "computer-use",
        )
        for item in raw_models if isinstance(raw_models, list) else []:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            lowered = model_id.casefold()
            if (
                not model_id
                or len(model_id) > 200
                or not (lowered.startswith("gpt-") or re.fullmatch(r"o\d(?:[-.].+)?", lowered))
                or any(value in lowered for value in excluded)
            ):
                continue
            models.append({"id": model_id, "label": model_id, "description": ""})
    else:
        raw_models = payload.get("data") if isinstance(payload, dict) else None
        for item in raw_models if isinstance(raw_models, list) else []:
            if not isinstance(item, dict):
                continue
            try:
                model_id = lmstudio_model_id(item.get("id"))
            except ValueError:
                continue
            model_type = clean_single_line(item.get("type") or item.get("object"), 80)
            models.append({
                "id": model_id,
                "label": model_id,
                "description": model_type,
            })
    unique = {item["id"]: item for item in models}
    return [unique[key] for key in sorted(unique, key=str.casefold)]


def lmstudio_connection_status(config: TokenConfig) -> dict[str, Any]:
    """Probe only the local model-list endpoint for the UI connection light."""
    try:
        base_url = lmstudio_base_url(config.lmstudio_base_url)
        models = available_ai_models("lmstudio", config, timeout=0.75)
    except (ValueError, RuntimeError):
        if is_colab_runtime():
            message = "起動待ちです。ノートブックの「ColabローカルLLM」セルを実行してください。"
        else:
            message = "起動待ちです。LM Studio の Developer で Start server を有効にしてください。"
        return {
            "reachable": False,
            "model_count": 0,
            "message": message,
        }
    empty_message = (
        "接続済みです。ノートブックでモデルを選択・取得してから、ライトをクリックしてください。"
        if is_colab_runtime()
        else "接続済みです。LM Studio でモデルを読み込み、ライトをクリックして選択してください。"
    )
    return {
        "reachable": True,
        "model_count": len(models),
        "base_url": base_url,
        "message": (
            f"接続済み（{len(models)} モデル）。ライトをクリックして使用モデルを選択してください。"
            if models else empty_message
        ),
    }


def update_token_model(provider: str, model: str, path: Path) -> TokenConfig:
    provider = str(provider or "").strip().casefold()
    if provider not in AI_MODEL_PROVIDERS:
        raise ValueError("OpenAI、Google Gemini、またはローカルLLMを選択してください。")
    model = lmstudio_model_id(model)
    with token_config_lock:
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{path.name} を更新できません: {exc}") from exc
        if not isinstance(raw, dict):
            raise RuntimeError(f"{path.name} の最上位は JSON オブジェクトにしてください。")
        raw[f"{provider}_model"] = model
        atomic_write_text(
            path,
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return load_token_config(path)


def lmstudio_reasoning_settings(base_url: str, api_key: str, model: str) -> dict:
    endpoint = lmstudio_base_url(base_url).removesuffix('/v1') + '/api/v1/models'
    request_object = urllib.request.Request(endpoint, headers=lmstudio_headers(api_key))
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(NoRedirect()).open(request_object, timeout=3) as response:
            payload = json.loads(response.read(2 * 1024 * 1024).decode('utf-8'))
        for row in payload.get('models', []):
            identifiers = [row.get('key')] + [r.get('id') for r in row.get('loaded_instances', [])]
            if model in identifiers:
                return row.get('capabilities', {}).get('reasoning', {})
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return {}


def lmstudio_base_url(value: str) -> str:
    return ai_client.lmstudio_base_url(
        value, LMSTUDIO_DEFAULT_BASE_URL, LMSTUDIO_LOOPBACK_HOSTS
    )
