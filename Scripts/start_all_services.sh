#!/bin/bash
# start_all_services.sh
# Unified startup script for Obsidian RAG (Docker + WebApp)

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/startup.log"

echo "╔══════════════════════════════════════════════════════════╗" | tee -a "$LOG_FILE"
echo "║          🚀 Obsidian RAG - Unified Startup               ║" | tee -a "$LOG_FILE"
echo "╚══════════════════════════════════════════════════════════╝" | tee -a "$LOG_FILE"
echo "📅 Date: $(date)" | tee -a "$LOG_FILE"

# Navigate to project root
cd "$PROJECT_ROOT" || exit 1

# 1. Start Docker Containers
echo "💎 Starting Docker Backend Services..." | tee -a "$LOG_FILE"
# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "⚠️ Docker is not running. Attempting to start Docker Desktop..." | tee -a "$LOG_FILE"
    open -a Docker
    # Wait for Docker to start
    echo "⏳ Waiting for Docker to initialize..." | tee -a "$LOG_FILE"
    until docker info > /dev/null 2>&1; do
        sleep 5
    done
fi

docker compose up -d --remove-orphans >> "$LOG_FILE" 2>&1
echo "   ✅ Backend services initiated." | tee -a "$LOG_FILE"

# 2. Wait for API Gateway (Health Check)
echo "⏳ Waiting for API Gateway (Port 4000) to be ready..." | tee -a "$LOG_FILE"
MAX_RETRIES=30
RETRY_COUNT=0
until curl -s http://localhost:4000/api/v1/health > /dev/null 2>&1 || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
done
echo ""

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ API Gateway failed to respond within $((MAX_RETRIES*2)) seconds." | tee -a "$LOG_FILE"
    # We still try to start webapp, maybe it's just slow
else
    echo "   ✅ API Gateway is online." | tee -a "$LOG_FILE"
fi

# 3. Start Webapp
echo "🌐 Starting Next.js Webapp..." | tee -a "$LOG_FILE"
# Check if we should start in dev or prod mode (default to prod for startup)
if [ -f "$SCRIPT_DIR/start_webapp.sh" ]; then
    bash "$SCRIPT_DIR/start_webapp.sh" >> "$LOG_FILE" 2>&1 &
    WEBAPP_PID=$!
    echo "   ✅ Webapp triggered (PID: $WEBAPP_PID)" | tee -a "$LOG_FILE"
else
    echo "❌ Error: start_webapp.sh not found." | tee -a "$LOG_FILE"
fi

# 4. Start Vault Watcher
echo "Starting vault watcher..." | tee -a "$LOG_FILE"
if [ -f "$SCRIPT_DIR/start_watcher.sh" ]; then
    bash "$SCRIPT_DIR/start_watcher.sh" >> "$LOG_FILE" 2>&1 &
    WATCHER_PID=$!
    echo "   Watcher triggered (PID: $WATCHER_PID)" | tee -a "$LOG_FILE"
else
    echo "   Watcher script not found." | tee -a "$LOG_FILE"
fi

echo "🎬 Startup script finished. Services are running in the background." | tee -a "$LOG_FILE"
echo "📜 Monitor logs: tail -f $LOG_FILE" | tee -a "$LOG_FILE"
