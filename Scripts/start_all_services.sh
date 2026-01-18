#!/bin/bash
# start_all_services.sh
# Unified startup script for Obsidian RAG (Docker + WebApp)

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/startup.log"
NGROK_LOG="$LOG_DIR/ngrok.log"

echo "╔══════════════════════════════════════════════════════════╗" | tee -a "$LOG_FILE"
echo "║          🚀 Obsidian RAG - Unified Startup               ║" | tee -a "$LOG_FILE"
echo "╚══════════════════════════════════════════════════════════╝" | tee -a "$LOG_FILE"
echo "📅 Date: $(date)" | tee -a "$LOG_FILE"

# Navigate to project root
cd "$PROJECT_ROOT" || exit 1

# Load NGROK_TOKEN and MCP_HTTP_AUTH_MODE from .env without sourcing
NGROK_TOKEN=""
MCP_HTTP_AUTH_MODE_ENV=""
MCP_OAUTH_STORE_PATH_ENV=""
if [ -f "$PROJECT_ROOT/.env" ]; then
    NGROK_TOKEN=$(grep -m1 '^NGROK_TOKEN=' "$PROJECT_ROOT/.env" | cut -d= -f2-)
    MCP_HTTP_AUTH_MODE_ENV=$(grep -m1 '^MCP_HTTP_AUTH_MODE=' "$PROJECT_ROOT/.env" | cut -d= -f2-)
    MCP_OAUTH_STORE_PATH_ENV=$(grep -m1 '^MCP_OAUTH_STORE_PATH=' "$PROJECT_ROOT/.env" | cut -d= -f2-)
    # Strip optional quotes
    NGROK_TOKEN="${NGROK_TOKEN%\"}"
    NGROK_TOKEN="${NGROK_TOKEN#\"}"
    MCP_HTTP_AUTH_MODE_ENV="${MCP_HTTP_AUTH_MODE_ENV%\"}"
    MCP_HTTP_AUTH_MODE_ENV="${MCP_HTTP_AUTH_MODE_ENV#\"}"
    MCP_OAUTH_STORE_PATH_ENV="${MCP_OAUTH_STORE_PATH_ENV%\"}"
    MCP_OAUTH_STORE_PATH_ENV="${MCP_OAUTH_STORE_PATH_ENV#\"}"
fi

# Helper: pick a python for small JSON parsing tasks
PYTHON_BIN="$(command -v python3 || command -v python || true)"

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

# 5. Start MCP HTTP Server (for ChatGPT connectors)
echo "🔌 Starting MCP HTTP server..." | tee -a "$LOG_FILE"
MCP_ENABLE="${MCP_HTTP_ENABLE:-true}"
if [ "$MCP_ENABLE" = "true" ]; then
    MCP_PY="$PROJECT_ROOT/venv/bin/python"
    MCP_SCRIPT="$PROJECT_ROOT/obsidian_rag_unified_mcp.py"
    MCP_HOST="${MCP_HTTP_HOST:-127.0.0.1}"
    MCP_PORT="${MCP_HTTP_PORT:-8811}"
    MCP_PATH="${MCP_HTTP_PATH:-/mcp}"
    MCP_AUTH_MODE="${MCP_HTTP_AUTH_MODE:-${MCP_HTTP_AUTH_MODE_ENV:-none}}"
    MCP_OAUTH_STORE_PATH="${MCP_OAUTH_STORE_PATH:-${MCP_OAUTH_STORE_PATH_ENV:-}}"
    MCP_PUBLIC_URL="${MCP_HTTP_PUBLIC_URL:-}"
    MCP_LOG="$LOG_DIR/mcp_http.log"

    if [ "$MCP_AUTH_MODE" = "oauth" ] && [ -z "$MCP_PUBLIC_URL" ]; then
        echo "   ⚠️ MCP_HTTP_PUBLIC_URL is missing for OAuth mode." | tee -a "$LOG_FILE"
        if command -v ngrok >/dev/null 2>&1; then
            if [ -n "$NGROK_TOKEN" ]; then
                ngrok config add-authtoken "$NGROK_TOKEN" >/dev/null 2>&1 || true
            fi
            nohup ngrok http "$MCP_PORT" > "$NGROK_LOG" 2>&1 &
            sleep 2
            if [ -n "$PYTHON_BIN" ]; then
                MCP_PUBLIC_URL="$($PYTHON_BIN - <<'PY'
import json, sys, urllib.request
try:
    data = json.load(urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2))
    for t in data.get("tunnels", []):
        if t.get("proto") == "https" and t.get("public_url"):
            print(t["public_url"])
            sys.exit(0)
    for t in data.get("tunnels", []):
        if t.get("public_url"):
            print(t["public_url"])
            sys.exit(0)
except Exception:
    pass
PY
)"
            fi
            if [ -n "$MCP_PUBLIC_URL" ]; then
                export MCP_HTTP_PUBLIC_URL="$MCP_PUBLIC_URL"
                echo "   ✅ ngrok started: $MCP_PUBLIC_URL" | tee -a "$LOG_FILE"
            else
                echo "   ❌ ngrok started but public URL not detected. Check $NGROK_LOG" | tee -a "$LOG_FILE"
            fi
        else
            echo "   ❌ ngrok not found. Install ngrok or set MCP_HTTP_PUBLIC_URL manually." | tee -a "$LOG_FILE"
        fi
    fi

    if [ "$MCP_AUTH_MODE" = "oauth" ] && [ -z "$MCP_PUBLIC_URL" ]; then
        echo "   ⚠️ OAuth enabled but MCP_HTTP_PUBLIC_URL is still missing." | tee -a "$LOG_FILE"
    fi

    if [ -x "$MCP_PY" ] && [ -f "$MCP_SCRIPT" ]; then
        MCP_ENV_VARS=()
        if [ -n "$MCP_OAUTH_STORE_PATH" ]; then
            MCP_ENV_VARS+=("MCP_OAUTH_STORE_PATH=$MCP_OAUTH_STORE_PATH")
        fi

        nohup env "${MCP_ENV_VARS[@]}" "$MCP_PY" "$MCP_SCRIPT" \
            --transport http --host "$MCP_HOST" --port "$MCP_PORT" --path "$MCP_PATH" \
            >> "$MCP_LOG" 2>&1 &
        MCP_PID=$!
        echo "   ✅ MCP HTTP server started (PID: $MCP_PID)" | tee -a "$LOG_FILE"
        echo "   📜 MCP log: $MCP_LOG" | tee -a "$LOG_FILE"
    else
        echo "   ❌ MCP server not started; missing $MCP_PY or $MCP_SCRIPT" | tee -a "$LOG_FILE"
    fi
else
    echo "   ⏭️ MCP HTTP server disabled (MCP_HTTP_ENABLE=false)." | tee -a "$LOG_FILE"
fi
