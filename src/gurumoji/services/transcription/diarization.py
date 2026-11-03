"""pyannote speaker-diarization setup and Hugging Face access diagnostics."""

from __future__ import annotations

import inspect
import os
from typing import Any


DIARIZATION_MODEL = os.environ.get(
    "MOJIOKOSI_DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1"
)


DIARIZATION_ACCESS_REPOS = (
    DIARIZATION_MODEL,
    "pyannote/segmentation-3.0",
    "pyannote/speaker-diarization-community-1",
)


def configure_huggingface_hub_compatibility() -> None:
    """Bridge legacy pyannote callers to Hugging Face Hub v1's token API."""
    import huggingface_hub

    original_download = huggingface_hub.hf_hub_download
    if "use_auth_token" in inspect.signature(original_download).parameters:
        return
    if getattr(original_download, "_mojiokosi_compat", False):
        return

    def hf_hub_download_compat(*args: Any, **kwargs: Any) -> Any:
        legacy_token = kwargs.pop("use_auth_token", None)
        if legacy_token is not None:
            kwargs.setdefault("token", legacy_token)
        return original_download(*args, **kwargs)

    hf_hub_download_compat._mojiokosi_compat = True  # type: ignore[attr-defined]
    huggingface_hub.hf_hub_download = hf_hub_download_compat


def configure_speechbrain_lazy_import_compatibility() -> None:
    try:
        from speechbrain.utils.importutils import LazyModule
    except ImportError:
        return
    if getattr(LazyModule, "_mojiokosi_windows_inspect_compat", False):
        return
    original_getattr = LazyModule.__getattr__

    def lazy_module_getattr_compat(self: Any, attr: str) -> Any:
        if attr == "__file__" and self.lazy_module is None:
            raise AttributeError(attr)
        return original_getattr(self, attr)

    LazyModule.__getattr__ = lazy_module_getattr_compat
    LazyModule._mojiokosi_windows_inspect_compat = True


def diarization_access_error_message(model_name: str) -> str:
    repo_lines = "\n".join(f"https://huggingface.co/{repo_id}" for repo_id in dict.fromkeys(DIARIZATION_ACCESS_REPOS))
    token_hint = "tokens.json の Hugging Face read token を確認し、"
    if os.environ.get("MOJIOKOSI_RUNTIME", "").strip().casefold() == "colab" or "COLAB_RELEASE_TAG" in os.environ:
        token_hint = "Colab左側の鍵アイコンでHF_TOKENと「ノートブックからのアクセス」を確認し、セル2を再実行してアプリを起動し直してください。"
    return (
        f"話者分離モデル {model_name} にアクセスできません。\n\n"
        f"{token_hint}以下のモデルページで利用規約への同意を完了してください。"
        "同意したアカウントのread tokenを使用し、fine-grained tokenでは対象モデルの読取権限も確認してください。"
        f"\nトークンの作成: https://huggingface.co/settings/tokens\n\n{repo_lines}"
    )


def is_diarization_access_error(exc: Exception) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    message = str(exc)
    return (
        (exc.__class__.__name__ in {"GatedRepoError", "RepositoryNotFoundError", "HfHubHTTPError"}
         and status_code in {401, 403, 404})
        or "Cannot access gated repo" in message
        or "401 Client Error" in message
        or "403 Client Error" in message
        or "'NoneType' object has no attribute 'to'" in message
    )


def create_diarization_pipeline(pipeline_class: Any, token: str, device: str) -> Any:
    parameters = inspect.signature(pipeline_class).parameters
    kwargs: dict[str, Any] = {"device": device}
    if "model_name" in parameters:
        kwargs["model_name"] = DIARIZATION_MODEL
    if "token" in parameters:
        kwargs["token"] = token
    else:
        kwargs["use_auth_token"] = token
    return pipeline_class(**kwargs)
