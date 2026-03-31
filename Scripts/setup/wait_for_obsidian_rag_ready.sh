#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
READY_FLAG_FILE="$SCRIPT_DIR/obsidian-rag.ready"
READY_LOG="$LOG_DIR/ready-check.log"
source "$SCRIPT_DIR/runtime_profile.sh"

mkdir -p "$LOG_DIR"
: > "$READY_LOG"

STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-300}"
CHECK_INTERVAL="${CHECK_INTERVAL:-3}"
MLX_URL="${MLX_URL:-http://127.0.0.1:8090/v1/models}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434/api/tags}"
MCP_HTTP_HEALTH_URL="${MCP_HTTP_HEALTH_URL:-http://127.0.0.1:8811/health}"

prepare_runtime_env "$(resolve_runtime_profile)"

resolve_local_provider() {
  canonical_provider_name
}

REQUIRED_CONTAINERS=(
  obsidian-embedding
  obsidian-lightrag
  obsidian-graph-service
  obsidian-api-gateway
  obsidian-mcp-unified
  obsidian-ui
  obsidian-webapp
)

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$READY_LOG"
}

is_container_ready() {
  local name="$1"
  local status health

  if ! docker inspect "$name" >/dev/null 2>&1; then
    return 1
  fi

  status="$(docker inspect -f '{{.State.Status}}' "$name")"
  if [ "$status" != "running" ]; then
    return 1
  fi

  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$name")"
  if [ "$health" = "healthy" ] || [ "$health" = "no-healthcheck" ]; then
    return 0
  fi

  return 1
}

is_ollama_ready() {
  curl -sf --max-time 3 "$OLLAMA_URL" >/dev/null 2>&1
}

is_mlx_ready() {
  curl -sf --max-time 3 "$MLX_URL" >/dev/null 2>&1
}

mcp_http_ready() {
  curl -sf --max-time 3 "$MCP_HTTP_HEALTH_URL" >/dev/null 2>&1
}

wait_for_ready() {
  local deadline=$((SECONDS + STARTUP_TIMEOUT))
  local local_provider
  local_provider="$(resolve_local_provider)"

  while [ "$SECONDS" -lt "$deadline" ]; do
    local all_ready=1

    for container in "${REQUIRED_CONTAINERS[@]}"; do
      if is_container_ready "$container"; then
        log "OK: $container running"
      else
        log "Waiting: $container not ready"
        all_ready=0
      fi
    done

    if provider_needs_ollama "$local_provider"; then
      if is_ollama_ready; then
        log "OK: Ollama endpoint reachable at $OLLAMA_URL"
      else
        log "Waiting: Ollama endpoint not reachable at $OLLAMA_URL"
        all_ready=0
      fi
    fi

    if [ "$local_provider" = "lmstudio" ]; then
      if is_mlx_ready; then
        log "OK: LM Studio / MLX compatibility endpoint reachable at $MLX_URL"
      else
        log "Waiting: LM Studio / MLX compatibility endpoint not reachable at $MLX_URL"
        all_ready=0
      fi
    fi

    if mcp_http_ready; then
      log "OK: MCP HTTP endpoint reachable at $MCP_HTTP_HEALTH_URL"
    else
      log "Waiting: MCP HTTP endpoint not reachable at $MCP_HTTP_HEALTH_URL"
      all_ready=0
    fi

    if [ "$all_ready" -eq 1 ]; then
      touch "$READY_FLAG_FILE"
      log "READY: all containers and profile-required services are healthy"
      return 0
    fi

    sleep "$CHECK_INTERVAL"
  done

  log "FAILED: startup readiness timeout (${STARTUP_TIMEOUT}s)"
  return 1
}

if ! wait_for_ready; then
  log "Startup check failed"
  rm -f "$READY_FLAG_FILE" 2>/dev/null || true
  exit 1
fi
