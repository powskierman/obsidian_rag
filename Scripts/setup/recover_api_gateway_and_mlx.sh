#!/bin/bash
# Recover MLX and the API gateway after a local-model crash.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
RECOVERY_LOG="$LOG_DIR/recovery.log"
MLX_LOG="$LOG_DIR/mlx-host.log"
LOCK_DIR="$LOG_DIR/recovery.lock"

WATCHDOG_MODE=0
FORCE_MODE=0

for arg in "$@"; do
  case "$arg" in
    --watchdog)
      WATCHDOG_MODE=1
      ;;
    --force)
      FORCE_MODE=1
      ;;
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

mlx_host_healthy() {
  curl -fsS --max-time 3 "http://127.0.0.1:8090/v1/models" >/dev/null 2>&1
}

gateway_healthy() {
  curl -fsS --max-time 5 "http://127.0.0.1:4000/api/v1/health" >/dev/null 2>&1
}

mcp_http_healthy() {
  curl -fsS --max-time 5 "http://127.0.0.1:8811/health" >/dev/null 2>&1
}

gateway_can_reach_mlx() {
  docker compose exec -T api-gateway sh -lc \
    'curl -fsS --max-time 3 http://host.docker.internal:8090/v1/models >/dev/null' \
    >/dev/null 2>&1
}

restart_mlx() {
  log "🔄 Restarting MLX host service..."
  pkill -f 'mlx_lm.server.*8090' >/dev/null 2>&1 || true
  (
    cd "$PROJECT_ROOT"
    nohup "$PROJECT_ROOT/start_mlx.sh" >> "$MLX_LOG" 2>&1 &
  )
  wait_for_url "http://127.0.0.1:8090/v1/models" "MLX" 45
}

recreate_api_gateway() {
  log "🔄 Recreating api-gateway..."
  (
    cd "$PROJECT_ROOT"
    docker compose up -d --force-recreate api-gateway
  ) >> "$RECOVERY_LOG" 2>&1
  wait_for_url "http://127.0.0.1:4000/api/v1/health" "api-gateway" 45
}

recreate_mcp_unified() {
  log "🔄 Recreating mcp-unified..."
  (
    cd "$PROJECT_ROOT"
    docker compose up -d --force-recreate mcp-unified
  ) >> "$RECOVERY_LOG" 2>&1
  wait_for_url "http://127.0.0.1:8811/health" "mcp-unified" 45
}

report_recent_mlx_failure() {
  if [ -f "$MLX_LOG" ]; then
    tail -n 40 "$MLX_LOG" >> "$RECOVERY_LOG" 2>/dev/null || true
  fi
}

main() {
  local need_gateway_recreate=0
  local need_mcp_recreate=0

  if [ "$FORCE_MODE" -eq 1 ]; then
    log "⚙️ Forced recovery requested."
    restart_mlx
    recreate_api_gateway
    recreate_mcp_unified
    return 0
  fi

  if mlx_host_healthy; then
    log "✅ MLX host is healthy."
  else
    log "⚠️ MLX host is down. Attempting recovery."
    report_recent_mlx_failure
    restart_mlx
    need_gateway_recreate=1
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

  if gateway_healthy && mlx_host_healthy; then
    if gateway_can_reach_mlx; then
      log "✅ api-gateway can reach MLX."
    else
      log "⚠️ api-gateway cannot reach MLX. Recreate required."
      need_gateway_recreate=1
    fi
  fi

  if [ "$need_gateway_recreate" -eq 1 ]; then
    recreate_api_gateway
    if gateway_can_reach_mlx; then
      log "✅ Recovery complete: api-gateway can reach MLX."
    else
      log "❌ Recovery incomplete: api-gateway still cannot reach MLX."
      exit 1
    fi
  elif [ "$WATCHDOG_MODE" -eq 0 ]; then
    log "No recovery needed."
  fi

  if [ "$need_mcp_recreate" -eq 1 ]; then
    recreate_mcp_unified
    if mcp_http_healthy; then
      log "✅ Recovery complete: MCP HTTP endpoint is healthy."
    else
      log "❌ Recovery incomplete: MCP HTTP endpoint is still down."
      exit 1
    fi
  fi
}

main
