#!/bin/bash
# Boot-time startup for Obsidian RAG Docker services.
# Called by com.obsidianrag.boot LaunchAgent on login.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG="$SCRIPT_DIR/logs/boot_start.log"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "$LOG"; }

log "=== Obsidian RAG boot start ==="

# Wait for Docker Desktop to be ready (up to 60s)
for i in $(seq 1 30); do
    if docker info >/dev/null 2>&1; then
        log "✅ Docker is ready"
        break
    fi
    [ "$i" -eq 30 ] && log "❌ Docker not ready after 60s, aborting" && exit 1
    sleep 2
done

cd "$PROJECT_ROOT"
log "📂 Project: $PROJECT_ROOT"

log "⬆️  Starting services..."
docker compose up -d 2>&1 | tee -a "$LOG"

log "✅ docker compose up -d complete"
