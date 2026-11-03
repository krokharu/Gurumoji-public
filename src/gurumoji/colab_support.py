"""Colabのシークレット読込と、秘密値を表示しない準備時の診断。"""

from __future__ import annotations

from contextlib import contextmanager
import errno
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import urllib.error

from .services.durable_files import atomic_write_text


HF_TOKEN_URL = "https://huggingface.co/settings/tokens"
HF_MODELS = (
    "pyannote/speaker-diarization-community-1",
    "pyannote/speaker-diarization-3.1",
    "pyannote/segmentation-3.0",
)
SECRET_FIELDS = (
    ("huggingface_token", ("HF_TOKEN", "HUGGINGFACE_TOKEN"), True),
    ("openai_api_key", ("OPENAI_API_KEY",), False),
    ("google_api_key", ("GOOGLE_API_KEY", "GEMINI_API_KEY"), False),
    ("typesafe_api_key", ("TYPESAFE_API_KEY",), False),
)


class ColabSetupError(RuntimeError):
    """原因別の固定メッセージだけをノートブックへ表示する。"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def read_colab_secret(userdata, names: tuple[str, ...], *, current="", required=False):
    """許可済みシークレットを優先し、未登録の場合だけ既存設定を使う。"""
    for name in names:
        try:
            value = userdata.get(name)
        except userdata.SecretNotFoundError:
            continue
        except userdata.NotebookAccessError:
            raise ColabSetupError(
                "SECRET_ACCESS", f"左側の鍵アイコンで {name} の「ノートブックからのアクセス」をONにし、セル2を再実行してください。"
            ) from None
        except userdata.TimeoutException:
            raise ColabSetupError(
                "SECRET_TIMEOUT", "シークレットの読込がタイムアウトしました。Colabの画面へ接続した状態でセル2を再実行してください。"
            ) from None
        except Exception:
            raise ColabSetupError(
                "SECRET_READ", "シークレットを読み込めません。Colabへの接続と、左側のシークレット設定を確認してください。"
            ) from None
        value = str(value or "").strip()
        if value:
            return value, f"シークレット {name}"
    current = str(current or "").strip()
    if current:
        return current, "既存設定"
    if required:
        raise ColabSetupError(
            "SECRET_MISSING", f"左側の鍵アイコンで {names[0]} を追加してアクセスをONにしてください。Hugging Faceのread token作成: {HF_TOKEN_URL}"
        ) from None
    return "", "未設定（任意）"


def load_colab_tokens(token_path: Path, userdata, *, manual_input=None):
    """全項目を読めてから保存する。既存の接続情報・任意項目を保持する。"""
    try:
        tokens = json.loads(token_path.read_text(encoding="utf-8-sig")) if token_path.is_file() else {}
        if not isinstance(tokens, dict):
            raise ValueError
    except (OSError, ValueError):
        raise ColabSetupError(
            "TOKEN_FILE", "既存のconfig/tokens.jsonを読めません。設定を保全してJSON形式と書込権限を確認してください。自動上書きはしていません。"
        ) from None
    sources = {}
    for field, names, required in SECRET_FIELDS:
        if manual_input is None:
            value, source = read_colab_secret(userdata, names, current=tokens.get(field), required=required)
        else:
            value = str(manual_input(f"{names[0]}（Enterで既存値を維持）: ") or "").strip()
            value = value or str(tokens.get(field) or "").strip()
            if required and not value:
                raise ColabSetupError("SECRET_MISSING", f"{names[0]} は話者分離に必要です。{HF_TOKEN_URL}") from None
            source = "非表示の手入力" if value else "未設定（任意）"
        tokens[field] = value
        sources[names[0]] = source
    for field, default in (("openai_model", "gpt-5.6-luna"), ("google_model", "gemini-3.5-flash"), ("typesafe_model", "jev-latest")):
        tokens[field] = tokens.get(field) or default
    try:
        atomic_write_text(token_path, json.dumps(tokens, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        raise ColabSetupError("TOKEN_WRITE", "接続設定を保存できません。ランタイムの空き容量とconfigフォルダーの書込権限を確認してください。") from None
    return tokens, sources


def diagnose_colab_error(exc: Exception, stage: str) -> ColabSetupError:
    """元の例外本文は分類だけに使い、キー・応答本文・個人パスを再表示しない。"""
    if isinstance(exc, ColabSetupError):
        return exc
    if isinstance(getattr(exc, "reason", None), Exception) and exc.reason is not exc:
        return diagnose_colab_error(exc.reason, stage)
    status = getattr(exc, "code", None)
    if not isinstance(status, int):
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    name = type(exc).__name__
    message = str(exc).lower()
    if status == 400:
        return ColabSetupError("REQUEST_400", "キー・モデル名・要求の形式が受け付けられませんでした。提供元の設定と、選択したモデルの対応機能を確認してください。")
    if status == 401:
        return ColabSetupError("AUTH_401", "キーが無効・失効、または認証に失敗しました。左側のシークレットを更新し、同じアカウントのキーでセル2を再実行してください。")
    if status == 403 or name == "GatedRepoError":
        return ColabSetupError("PERMISSION_403", "モデルの利用条件への同意、キーのread権限・対象モデルへの権限、APIのプロジェクト・提供地域を確認してください。Hugging Faceは同意したアカウントのトークンを使います。")
    if status == 404:
        return ColabSetupError("MODEL_404", "モデル名・URLが違うか、アクセス権がありません。モデルの公開ページと、選択したアカウント・モデル名を確認してください。")
    if status == 429:
        return ColabSetupError("LIMIT_429", "要求回数・利用枠・残高のいずれかの制限です。提供元の利用状況を確認してください。回数制限は待って再実行し、残高・利用枠の不足は設定を見直してください。")
    if isinstance(status, int) and status >= 500:
        return ColabSetupError("SERVICE_5XX", "接続先で一時的な障害が発生しています。提供元の稼働状況を確認し、時間をおいて再実行してください。")
    if isinstance(exc, ssl.SSLError) or "certificate_verify_failed" in message:
        return ColabSetupError("TLS", "証明書の検証に失敗しました。接続先・ネットワークを確認してください。証明書の検証は無効化しないでください。")
    if isinstance(exc, (TimeoutError, socket.timeout)) or "timeout" in name.lower():
        return ColabSetupError("TIMEOUT", "処理が時間内に完了しませんでした。接続状態と直前の進捗を確認し、初回モデル取得中は完了を待って再実行してください。")
    if isinstance(exc, urllib.error.URLError) or "connectionerror" in name.lower():
        return ColabSetupError("NETWORK", "接続できません。ネットワークと配布元を確認してください。ローカルLLMの場合はセル4でOllamaを起動し直してください。")
    if getattr(exc, "errno", None) == errno.ENOSPC or "no space left" in message:
        return ColabSetupError("DISK_FULL", "ランタイムの空き容量が不足しています。必要な結果をDriveへ保存してから空き容量を確保してください。")
    if isinstance(exc, MemoryError) or "out of memory" in message or name == "OutOfMemoryError":
        return ColabSetupError("GPU_MEMORY", "メモリーが不足しています。小さい音声・LLMモデルを選び、LLMのコンテキスト長を下げるかUSE_LOCAL_LLMをOFFにしてください。")
    if "cuda" in message or "nvidia" in message:
        return ColabSetupError("GPU_RUNTIME", "GPUを利用できません。ランタイムの種類でGPUを選び、再接続してセル1から実行してください。GPU割当の制限も確認してください。")
    if stage == "ENVIRONMENT" or isinstance(exc, (ImportError, subprocess.CalledProcessError)) and stage != "LOCAL_LLM":
        return ColabSetupError("ENVIRONMENT", "環境準備に失敗しました。直前のapt/pip出力と空き容量・通信を確認し、最新版のセル1を再実行してください。旧版で標準環境を変更した場合は、結果を保存してランタイムを作り直してください。")
    if stage == "DRIVE":
        return ColabSetupError("DRIVE", "Google Driveの接続に失敗しました。Googleアカウントとアクセス許可を確認してください。Driveを使わない場合はUSE_GOOGLE_DRIVEをOFFにし、一時保存になることを確認してください。")
    if stage == "LOCAL_LLM":
        return ColabSetupError("LOCAL_LLM", "Ollamaの起動・モデル取得・JSON応答の確認に失敗しました。モデル名・通信・GPU容量を確認してセル4を再実行してください。音声処理だけを始める場合はUSE_LOCAL_LLMをOFFにできます。")
    if stage == "HUGGINGFACE":
        return ColabSetupError("HF_CHECK", f"Hugging Faceの接続を確認できません。通信、トークン、モデルページの利用条件を確認してセル2を再実行してください。{HF_TOKEN_URL}")
    if stage == "SECRETS":
        return ColabSetupError("SECRET_READ", "接続設定を準備できません。左側のシークレット名・アクセス許可と、configフォルダーの書込権限を確認してください。")
    return ColabSetupError("APP_START", "アプリを起動できません。セル1〜4が完了しているか確認し、終了セルで停止してから起動し直してください。エラーが続く場合は、キー・録音内容を除いて発生セルとエラー分類を報告してください。")


@contextmanager
def colab_step(stage: str):
    try:
        yield
    except Exception as exc:
        raise diagnose_colab_error(exc, stage) from None


def check_huggingface_access(token: str, *, api=None, metadata=None):
    """認証と既定話者モデルのHEADのみ確認し、モデル重みは取得しない。"""
    from huggingface_hub import HfApi, get_hf_file_metadata, hf_hub_url

    api = api or HfApi()
    metadata = metadata or get_hf_file_metadata
    try:
        api.whoami(token=token)
    except Exception as exc:
        raise diagnose_colab_error(exc, "HUGGINGFACE") from None
    model = HF_MODELS[0]
    try:
        metadata(hf_hub_url(model, "config.yaml"), token=token, timeout=15)
    except Exception as exc:
        error = diagnose_colab_error(exc, "HUGGINGFACE")
        raise ColabSetupError(error.code, f"{error.message}\n利用条件: https://huggingface.co/{model}\nトークン設定: {HF_TOKEN_URL}") from None


def main() -> int:
    try:
        token_path = Path(sys.argv[1])
        tokens = json.loads(token_path.read_text(encoding="utf-8-sig"))
        token = str(tokens.get("huggingface_token") or "").strip()
        if not token:
            raise ColabSetupError("SECRET_MISSING", "HF_TOKENを設定してセル2を再実行してください。")
        check_huggingface_access(token)
    except Exception as exc:
        print(diagnose_colab_error(exc, "HUGGINGFACE"))
        return 1
    print("[OK] Hugging Face認証・既定話者モデルへのアクセス（モデル推論は未確認）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
