#!/usr/bin/env bash
# 公式HaasとNemotronを、この作業フォルダー専用のLinux環境へ導入する。
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd -P)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HAAS_REVISION="acc614f68769dcbfae9dba96b48439c4a66295af"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info[:2] >= (3, 11)'
command -v nvidia-smi >/dev/null || { echo 'NVIDIA GPUドライバーが必要です。' >&2; exit 1; }
for executable in git gcc g++ ffmpeg; do
  command -v "$executable" >/dev/null || { echo '先に sudo apt-get install build-essential python3-dev python3-venv ffmpeg git を実行してください。' >&2; exit 1; }
done
"$PYTHON_BIN" -c 'import pathlib, sysconfig; assert (pathlib.Path(sysconfig.get_path("include")) / "Python.h").is_file(), "python3-devが必要です"'
nvidia-smi --query-gpu=name --format=csv,noheader
WORKSPACE_KEY="$(printf '%s' "$ROOT" | sha256sum | cut -c1-16)"
ENV_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/gurumoji/haas/$WORKSPACE_KEY"
mkdir -p "$ENV_ROOT" .venv-haas
export UV_CACHE_DIR="$ENV_ROOT/cache"
rm -f .venv-haas/wsl-runtime.json .venv-haas/.haas-ready
[ -x "$ENV_ROOT/bootstrap/bin/python" ] || "$PYTHON_BIN" -m venv "$ENV_ROOT/bootstrap"
"$ENV_ROOT/bootstrap/bin/python" -m pip install --upgrade uv
UV="$ENV_ROOT/bootstrap/bin/uv"
if [ ! -d "$ENV_ROOT/source/.git" ]; then
  git clone https://github.com/third-intelligence/Haas-ASR.git "$ENV_ROOT/source"
fi
git -C "$ENV_ROOT/source" fetch origin "$HAAS_REVISION"
git -C "$ENV_ROOT/source" checkout --detach "$HAAS_REVISION"
# 公式のlockと依存上書きを使い、既存のWhisperX/Qwen環境から分離する。
"$UV" sync --project "$ENV_ROOT/source" --locked --no-dev --python "$PYTHON_BIN"
HAAS_PYTHON="$ENV_ROOT/source/.venv/bin/python"
"$HAAS_PYTHON" -c 'import torch, haas_asr; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_name())'
# 両モデルは別プロセスで順に実行し、公式lockのtorch/transformersを共用する。
NEMOTRON_PYTHON="$HAAS_PYTHON"
"$NEMOTRON_PYTHON" -c 'from transformers import AutoModelForAudioFrameClassification, AutoProcessor'
# モデルを先に取得し、アプリでの初回実行中のダウンロードを避ける。
"$HAAS_PYTHON" -c 'from huggingface_hub import snapshot_download; snapshot_download("third-intelligence/Haas-ja-v1.0")'
"$NEMOTRON_PYTHON" -c 'from huggingface_hub import snapshot_download; snapshot_download("nvidia/Nemotron-3-Diarization")'
"$PYTHON_BIN" - "$ROOT" "$HAAS_PYTHON" "$NEMOTRON_PYTHON" "$HAAS_REVISION" <<'PY'
import json
import os
import pathlib
import subprocess
import sys
root, haas_python, nemotron_python, revision = sys.argv[1:]
workspace = subprocess.check_output(['wslpath', '-w', root], text=True).strip() if os.environ.get('WSL_DISTRO_NAME') else root
config = {'workspace': workspace, 'distribution': os.environ.get('WSL_DISTRO_NAME', ''), 'python': haas_python, 'nemotron_python': nemotron_python, 'revision': revision, 'linux_workspace': root}
path = pathlib.Path(root) / '.venv-haas' / 'wsl-runtime.json'
path.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
PY
echo 'Haas-jaとNemotronの専用環境・モデル取得が完了しました。'