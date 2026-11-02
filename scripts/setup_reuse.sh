#!/usr/bin/env bash
# RE-USEを作業フォルダー専用のLinux環境へ導入する。
set -euo pipefail
cd "$(dirname "$0")/.."
TASK_ROOT="$(pwd -P)"
TASK_PYTHON="${PYTHON_BIN:-python3}"
TASK_KEY="$(printf '%s' "$TASK_ROOT" | sha256sum | cut -c1-16)"
TASK_ENV="${XDG_DATA_HOME:-$HOME/.local/share}/gurumoji/reuse/$TASK_KEY"
TASK_REVISION="31f82f2efad1095034492f236e8dac9239ba713b"
command -v nvidia-smi >/dev/null || { echo 'Linux環境でNVIDIA GPUドライバーが必要です。' >&2; exit 1; }
mkdir -p "$TASK_ENV" .venv-reuse
if [ -f .venv-reuse/wsl-runtime.json ]; then
  echo '既存のRE-USE設定があります。更新する場合は設定を退避してから再実行してください。' >&2
  exit 1
fi
[ -x "$TASK_ENV/venv/bin/python" ] || "$TASK_PYTHON" -m venv "$TASK_ENV/venv"
TASK_RUNNER="$TASK_ENV/venv/bin/python"
"$TASK_RUNNER" -m pip install --upgrade pip setuptools wheel packaging ninja
"$TASK_RUNNER" -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
"$TASK_RUNNER" -m pip install 'numpy<3' 'huggingface_hub<1' 'transformers>=4.48,<5' safetensors soundfile einops
# 公式の対応wheelを優先し、ない場合だけソースビルドへ進む。
"$TASK_RUNNER" - <<'PY'
import platform, subprocess, sys, torch
tag = f'cp{sys.version_info.major}{sys.version_info.minor}'
abi = str(torch._C._GLIBCXX_USE_CXX11_ABI).upper()
wheel = f'mamba_ssm-2.2.5+cu12torch2.8cxx11abi{abi}-{tag}-{tag}-linux_{platform.machine()}.whl'
url = 'https://github.com/state-spaces/mamba/releases/download/v2.2.5/' + wheel
constraints = ['torch==2.8.0', 'triton==3.4.0', 'transformers<5']
try:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', url, *constraints])
except subprocess.CalledProcessError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'mamba-ssm==2.2.5', '--no-build-isolation', *constraints])
PY
"$TASK_RUNNER" - "$TASK_ENV/model" "$TASK_REVISION" <<'PY'
from huggingface_hub import snapshot_download
import sys
snapshot_download('nvidia/NVIDIA-NemotronLabs-RE-USE', revision=sys.argv[2], local_dir=sys.argv[1],
                  allow_patterns=['models/*.py', 'model.safetensors', 'config.json', 'LICENSE'])
PY
"$TASK_RUNNER" - "$TASK_ENV" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
(root/'probe.json').write_text(json.dumps({'probe': True, 'model_directory': str(root/'model')}), encoding='utf-8')
PY
"$TASK_RUNNER" "$TASK_ROOT/scripts/reuse_audio_worker.py" "$TASK_ENV/probe.json"
"$TASK_RUNNER" - "$TASK_ROOT" "$TASK_ENV" "$TASK_REVISION" <<'PY'
import json, os, pathlib, subprocess, sys
root, environment, revision = map(str, sys.argv[1:])
windows = subprocess.check_output(['wslpath', '-w', root], text=True).strip() if os.environ.get('WSL_DISTRO_NAME') else root
config = {'workspace': windows, 'linux_workspace': root, 'distribution': os.environ.get('WSL_DISTRO_NAME', ''),
          'python': environment+'/venv/bin/python', 'model_directory': environment+'/model', 'revision': revision, 'ready': True}
(pathlib.Path(root)/'.venv-reuse/wsl-runtime.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
PY
echo 'RE-USEの専用環境・モデル読込み確認が完了しました。アプリで接続状態を再確認してください。'
