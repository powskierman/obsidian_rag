#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
READY_FLAG_FILE="$SCRIPT_DIR/obsidian-rag.ready"
READY_LOG="$LOG_DIR/ready-check.log"

mkdir -p "$LOG_DIR"

STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-300}"
CHECK_INTERVAL="${CHECK_INTERVAL:-3}"
MLX_URL="${MLX_URL:-http://127.0.0.1:8090/v1/models}"

REQUIRED_CONTAINERS=(
  obsidian-embedding
  obsidian-lightrag
  obsidian-graph-service
  obsidian-api-gateway
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

is_mlx_ready() {
  curl -sf --max-time 3 "$MLX_URL" >/dev/null 2>&1
}

wait_for_ready() {
  local deadline=$((SECONDS + STARTUP_TIMEOUT))

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

    if is_mlx_ready; then
      log "OK: MLX endpoint reachable at $MLX_URL"
    else
      log "Waiting: MLX endpoint not reachable at $MLX_URL"
      all_ready=0
    fi

    if [ "$all_ready" -eq 1 ]; then
      touch "$READY_FLAG_FILE"
      log "READY: all containers and MLX are healthy"
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

