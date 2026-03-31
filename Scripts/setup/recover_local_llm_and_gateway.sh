#!/bin/bash
# Recover the configured local LLM path, api-gateway, and MCP HTTP service.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
RECOVERY_LOG="$LOG_DIR/recovery.log"
OLLAMA_LOG="$LOG_DIR/ollama-host.log"
MLX_LOG="$LOG_DIR/mlx-host.log"
LOCK_DIR="$LOG_DIR/recovery.lock"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434/api/tags}"
MLX_URL="${MLX_URL:-http://127.0.0.1:8090/v1/models}"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:4000/api/v1/health}"
MCP_HTTP_URL="${MCP_HTTP_URL:-http://127.0.0.1:8811/health}"
OLLAMA_BIND_HOST="${OLLAMA_BIND_HOST:-0.0.0.0:11434}"
source "$SCRIPT_DIR/runtime_profile.sh"

WATCHDOG_MODE=0
FORCE_MODE=0

for arg in "$@"; do
  case "$arg" in
    --watchdog) WATCHDOG_MODE=1 ;;
    --force) FORCE_MODE=1 ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--watchdog] [--force]" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$LOG_DIR"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  if [ "$WATCHDOG_MODE" -eq 0 ]; then
    echo "Recovery already in progress: $LOCK_DIR" >&2
  fi
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

log() {
  local message="$1"
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$message" | tee -a "$RECOVERY_LOG"
}

prepare_runtime_env "$(resolve_runtime_profile)"

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts="${3:-30}"

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      log "✅ $label reachable: $url"
      return 0
    fi
    sleep 1
  done

  log "❌ $label not ready: $url"
  return 1
}

resolve_local_provider() {
  canonical_provider_name
}

ollama_healthy() {
  curl -fsS --max-time 3 "$OLLAMA_URL" >/dev/null 2>&1
}

mlx_healthy() {
  curl -fsS --max-time 3 "$MLX_URL" >/dev/null 2>&1
}

gateway_healthy() {
  curl -fsS --max-time 5 "$GATEWAY_URL" >/dev/null 2>&1
}

mcp_http_healthy() {
  curl -fsS --max-time 5 "$MCP_HTTP_URL" >/dev/null 2>&1
}

gateway_can_reach_ollama() {
  compose "$OBSIDIAN_RAG_PROFILE" exec -T api-gateway sh -lc \
    'curl -fsS --max-time 3 http://host.docker.internal:11434/api/tags >/dev/null' \
    >/dev/null 2>&1
}

gateway_can_reach_mlx() {
  compose "$OBSIDIAN_RAG_PROFILE" exec -T api-gateway sh -lc \
    'curl -fsS --max-time 3 http://host.docker.internal:8090/v1/models >/dev/null' \
    >/dev/null 2>&1
}

restart_ollama() {
  log "🔄 Ensuring Ollama is running..."
  launchctl setenv OLLAMA_HOST "$OLLAMA_BIND_HOST" >/dev/null 2>&1 || true
  if [ -d "/Applications/Ollama.app" ]; then
    open -a Ollama >/dev/null 2>&1 || true
  elif command -v ollama >/dev/null 2>&1; then
    pkill -f 'ollama serve' >/dev/null 2>&1 || true
    env OLLAMA_HOST="$OLLAMA_BIND_HOST" nohup ollama serve >> "$OLLAMA_LOG" 2>&1 &
  else
    log "❌ Ollama is not installed."
    return 1
  fi
  wait_for_url "$OLLAMA_URL" "Ollama" 45
}

restart_mlx() {
  log "🔄 Restarting MLX compatibility host..."
  pkill -f 'mlx_lm.server.*8090' >/dev/null 2>&1 || true
  (
    cd "$PROJECT_ROOT"
    nohup "$PROJECT_ROOT/start_mlx.sh" >> "$MLX_LOG" 2>&1 &
  )
  wait_for_url "$MLX_URL" "MLX compatibility endpoint" 45
}

recreate_api_gateway() {
  log "🔄 Recreating api-gateway..."
  (
    cd "$PROJECT_ROOT"
    compose "$OBSIDIAN_RAG_PROFILE" up -d --force-recreate api-gateway
  ) >> "$RECOVERY_LOG" 2>&1
  wait_for_url "$GATEWAY_URL" "api-gateway" 45
}

recreate_mcp_unified() {
  log "🔄 Recreating mcp-unified..."
  (
    cd "$PROJECT_ROOT"
    compose "$OBSIDIAN_RAG_PROFILE" up -d --force-recreate mcp-unified
  ) >> "$RECOVERY_LOG" 2>&1
  wait_for_url "$MCP_HTTP_URL" "mcp-unified" 45
}

main() {
  local provider need_gateway_recreate=0 need_mcp_recreate=0
  provider="$(resolve_local_provider)"

  if [ "$FORCE_MODE" -eq 1 ]; then
    log "⚙️ Forced recovery requested for provider=$provider."
    if provider_needs_ollama "$provider"; then
      restart_ollama
    fi
    if [ "$provider" = "lmstudio" ]; then
      restart_mlx
    fi
    recreate_api_gateway
    recreate_mcp_unified
    return 0
  fi

  if provider_needs_ollama "$provider"; then
    if ollama_healthy; then
      log "✅ Ollama is healthy."
    else
      log "⚠️ Ollama is down. Attempting recovery."
      restart_ollama
      need_gateway_recreate=1
    fi
  fi

  if [ "$provider" = "lmstudio" ]; then
    if mlx_healthy; then
      log "✅ LM Studio / MLX compatibility endpoint is healthy."
    else
      log "⚠️ LM Studio / MLX compatibility endpoint is down. Attempting recovery."
      restart_mlx
      need_gateway_recreate=1
    fi
  fi

  if gateway_healthy; then
    log "✅ api-gateway health endpoint is healthy."
  else
    log "⚠️ api-gateway health endpoint is down. Recreate required."
    need_gateway_recreate=1
  fi

  if mcp_http_healthy; then
    log "✅ MCP HTTP endpoint is healthy."
  else
    log "⚠️ MCP HTTP endpoint is down. Recreate required."
    need_mcp_recreate=1
  fi

  if provider_needs_ollama "$provider" && gateway_healthy && ! gateway_can_reach_ollama; then
    log "⚠️ api-gateway cannot reach Ollama. Recreate required."
    need_gateway_recreate=1
  fi

  if [ "$provider" = "lmstudio" ] && gateway_healthy && ! gateway_can_reach_mlx; then
    log "⚠️ api-gateway cannot reach LM Studio / MLX compatibility endpoint. Recreate required."
    need_gateway_recreate=1
  fi

  if [ "$need_gateway_recreate" -eq 1 ]; then
    recreate_api_gateway
  elif [ "$WATCHDOG_MODE" -eq 0 ]; then
    log "No api-gateway recovery needed."
  fi

  if [ "$need_mcp_recreate" -eq 1 ]; then
    recreate_mcp_unified
  fi
}

main
