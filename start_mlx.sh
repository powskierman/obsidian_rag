#!/bin/bash
# start_mlx.sh
# Script to start the local MLX endpoint on Canmore.
# Runs on port 8090, which is exported directly via Tailscale.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
ENV_FILE="$PROJECT_ROOT/.env"

read_env_value() {
  local key="$1"

  if [ ! -f "$ENV_FILE" ]; then
    return 1
  fi

  awk -F= -v key="$key" '
    $0 ~ "^[[:space:]]*#" { next }
    $1 == key {
      sub(/^[^=]*=/, "", $0)
      print $0
      exit
    }
  ' "$ENV_FILE"
}

if [ -f "$ENV_FILE" ]; then
  MLX_MODEL_FROM_ENV="$(read_env_value "MLX_MODEL" || true)"
  LLM_MODEL_FROM_ENV="$(read_env_value "LLM_MODEL" || true)"
  MLX_HOST_FROM_ENV="$(read_env_value "MLX_HOST" || true)"
  MLX_PORT_FROM_ENV="$(read_env_value "MLX_PORT" || true)"
fi

MODEL_ID="${MLX_MODEL:-${MLX_MODEL_FROM_ENV:-${LLM_MODEL:-${LLM_MODEL_FROM_ENV:-LiquidAI/LFM2-24B-A2B-MLX-4bit}}}}"
MLX_HOST="${MLX_HOST:-${MLX_HOST_FROM_ENV:-127.0.0.1}}"
MLX_PORT="${MLX_PORT:-${MLX_PORT_FROM_ENV:-8090}}"

echo "Starting MLX-LM Server..."
echo "Model: $MODEL_ID"
echo "Bind:  $MLX_HOST:$MLX_PORT"

find_mlx_venv() {
  local candidates=(
    "${MLX_VENV:-}"
    "${PROJECT_ROOT}/venv-lfm2"
    "$HOME/venv-lfm2"
    "/Volumes/Michel/venv-lfm2"
    "/Users/$USER/venv-lfm2"
  )

  for candidate in "${candidates[@]}"; do
    if [ -n "$candidate" ] && [ -f "$candidate/bin/activate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

MLX_VENV_PATH="$(find_mlx_venv || true)"
if [ -z "$MLX_VENV_PATH" ]; then
  echo "⚠️ Warning: no mlx-lm venv found. Continuing with system Python."
  echo "   Checked: ${MLX_VENV:-unset}, ${PROJECT_ROOT}/venv-lfm2, $HOME/venv-lfm2, /Volumes/Michel/venv-lfm2, /Users/$USER/venv-lfm2"
fi

if [ -n "$MLX_VENV_PATH" ] && [ -x "$MLX_VENV_PATH/bin/python" ]; then
  MLX_PYTHON_BIN="$MLX_VENV_PATH/bin/python"
elif command -v python3.14 >/dev/null 2>&1; then
  MLX_PYTHON_BIN="$(command -v python3.14)"
elif command -v python >/dev/null 2>&1; then
  MLX_PYTHON_BIN="$(command -v python)"
else
  echo "❌ Error: python executable not found."
  exit 1
fi

if [ -x "$MLX_VENV_PATH/bin/mlx_lm.server" ]; then
  # Avoid directly executing a potentially stale virtualenv launcher when the env was moved.
  MLX_VENV_PATH="$MLX_VENV_PATH"
fi

if [ -n "$MLX_VENV_PATH" ] && [ -d "$MLX_VENV_PATH/lib" ]; then
  site_packages="$(find "$MLX_VENV_PATH/lib" -maxdepth 2 -type d -name site-packages | head -n 1)"
  if [ -n "$site_packages" ]; then
    exec env PYTHONPATH="$site_packages${PYTHONPATH:+:$PYTHONPATH}" "$MLX_PYTHON_BIN" -m mlx_lm.server --model "$MODEL_ID" --port "$MLX_PORT" --host "$MLX_HOST"
  fi
fi

if command -v mlx_lm.server >/dev/null 2>&1; then
  exec mlx_lm.server --model "$MODEL_ID" --port "$MLX_PORT" --host "$MLX_HOST"
fi

echo "⚠️ Warning: could not resolve MLX launcher from ${MLX_VENV_PATH:-unset}."
echo "   Falling back to system 'mlx_lm.server'."
exec mlx_lm.server --model "$MODEL_ID" --port "$MLX_PORT" --host "$MLX_HOST"
