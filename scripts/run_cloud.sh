#!/usr/bin/env bash
# Start the existing app in this private cloud workspace, without a public bind.
set -euo pipefail
APP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$APP_ROOT"
PYTHON="$APP_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  printf '%s\n' 'Create .venv and install config/requirements-cloud-core.txt first.' >&2
  exit 2
fi
export PYTHONPATH="$APP_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export MOJIOKOSI_NO_BROWSER=1
export MOJIOKOSI_RUNTIME="${MOJIOKOSI_RUNTIME:-cloud}"
export MOJIOKOSI_HOST=127.0.0.1
export MOJIOKOSI_PORT="${MOJIOKOSI_PORT:-7860}"
export MOJIOKOSI_ALLOW_REMOTE=0
# Use the existing configurable data/output/backup paths. Keep temporary uploads
# in the app's ignored runtime folder: symlinked output paths are intentionally
# rejected by the application's recovery safety checks.
mkdir -p "$APP_ROOT/../runtime"
RUNTIME_ROOT="$(cd -- "$APP_ROOT/../runtime" && pwd -P)"
export MOJIOKOSI_DATA_DIR="$RUNTIME_ROOT/data"
export MOJIOKOSI_OUTPUT_DIR="$RUNTIME_ROOT/output"
export MOJIOKOSI_BACKUP_DIR="$RUNTIME_ROOT/backups"
# Keep model/cache state separate from source code and imported vaults.
export XDG_CACHE_HOME="$RUNTIME_ROOT/models"
export HF_HOME="$RUNTIME_ROOT/models/huggingface"
export MPLCONFIGDIR="$RUNTIME_ROOT/cache/matplotlib"
export NUMBA_CACHE_DIR="$RUNTIME_ROOT/cache/numba"
mkdir -p "$XDG_CACHE_HOME" "$MPLCONFIGDIR" "$NUMBA_CACHE_DIR"
# HF/Transformers downloads and provider telemetry stay disabled. The separate
# OpenAI Whisper loader has its own download path; only tiny is cached here.
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export PYANNOTE_METRICS_ENABLED=0
exec "$PYTHON" -u -m gurumoji.app
