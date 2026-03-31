#!/bin/bash
# Start Obsidian RAG System (Docker Only)
# This startup selects provider behavior from the active runtime profile.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
HOST_OLLAMA_URL="http://localhost:11434"
OLLAMA_BIND_HOST="${OLLAMA_BIND_HOST:-0.0.0.0:11434}"
source "$SCRIPT_DIR/runtime_profile.sh"

mkdir -p "$LOG_DIR"

prepare_runtime_env "$(resolve_runtime_profile)"

resolve_local_provider() {
    canonical_provider_name
}

wait_for_url() {
    local url="$1"
    local label="$2"
    local attempts="${3:-20}"

    for _ in $(seq 1 "$attempts"); do
        if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
            echo "✅ $label is reachable at $url"
            return 0
        fi
        sleep 1
    done

    echo "❌ $label did not become ready at $url"
    return 1
}

ensure_ollama_running() {
    if curl -fsS --max-time 2 "$HOST_OLLAMA_URL/api/tags" >/dev/null 2>&1; then
        echo "✅ Ollama already running on port 11434"
        return 0
    fi

    echo "🚀 Starting Ollama host service..."
    launchctl setenv OLLAMA_HOST "$OLLAMA_BIND_HOST" >/dev/null 2>&1 || true
    if [ -d "/Applications/Ollama.app" ]; then
        open -a Ollama >/dev/null 2>&1 || true
    elif command -v ollama >/dev/null 2>&1; then
        env OLLAMA_HOST="$OLLAMA_BIND_HOST" nohup ollama serve > "$LOG_DIR/ollama-host.log" 2>&1 &
    else
        echo "❌ Ollama is not installed. Expected '/Applications/Ollama.app' or 'ollama' in PATH."
        return 1
    fi

    wait_for_url "$HOST_OLLAMA_URL/api/tags" "Ollama" 30
}

echo "🚀 Starting Obsidian RAG (Docker)..."

# Ensure Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker Desktop."
    exit 1
fi

LOCAL_PROVIDER="$(resolve_local_provider)"
if provider_needs_ollama "$LOCAL_PROVIDER"; then
    ensure_ollama_running
elif [ "$LOCAL_PROVIDER" = "lmstudio" ]; then
    echo "ℹ️ Local provider is set to LM Studio / MLX compatibility mode."
    echo "   Ollama is not required by the selected provider, but may still be useful for local model tools."
else
    echo "ℹ️ Active provider is $LOCAL_PROVIDER."
    echo "   Skipping Ollama startup because this profile does not require it as the primary LLM path."
fi

if [ "$LOCAL_PROVIDER" = "lmstudio" ]; then
    echo "ℹ️ Local provider is set to LM Studio / MLX compatibility mode."
    echo "   Ensure the MLX-compatible endpoint is available if you intend to use that provider."
fi

cd "$PROJECT_ROOT"

# Check if we need to pull data first? 
# No, let the user decide.

echo "📂 Data Directory: ${OBSIDIAN_RAG_DATA_DIR:-Local/Default}"
echo "📂 Vault Path:     $OBSIDIAN_VAULT_PATH"
if provider_needs_ollama "$LOCAL_PROVIDER"; then
    echo "🤖 Ollama Bind:   $OLLAMA_BIND_HOST"
fi
echo "🤖 Active Provider: $LOCAL_PROVIDER"

echo "⬆️  Bringing up services..."
compose "$OBSIDIAN_RAG_PROFILE" up -d

echo "⏳ Waiting for strict readiness across containers and required providers..."
if ! "$SCRIPT_DIR/wait_for_obsidian_rag_ready.sh"; then
    echo "❌ Startup readiness check failed. Review logs for details:"
    echo "   ${LOG_DIR}/ready-check.log"
    echo "   docker compose logs -f"
    exit 1
fi

echo ""
echo "✅ Services started and all required components are healthy."
echo "🌐 WebApp:              http://localhost:3030"
echo "📊 Embedding API:       http://localhost:8000"
echo "🧪 Streamlit UI:        http://localhost:8501"
echo "🕸️  Internal Graph API: http://localhost:8002"
echo "🧠 Internal LightRAG:   http://localhost:8001"
echo "🔌 MCP HTTP:            http://localhost:8811/mcp"
echo "   These graph endpoints remain internal dependencies for cascading/deep-research."
echo ""
echo "📝 Logs:"
echo "   docker compose logs -f"
