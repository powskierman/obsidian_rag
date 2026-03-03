#!/bin/bash
# Start Obsidian RAG System (Docker Only)
# This script ensures a consistent environment across Mac Mini and MacBook.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
LOG_DIR="$SCRIPT_DIR/logs"
HOST_OLLAMA_URL="http://localhost:11434"
HOST_MLX_MODELS_URL="http://localhost:8090/v1/models"
OLLAMA_BIND_HOST="${OLLAMA_BIND_HOST:-0.0.0.0:11434}"

mkdir -p "$LOG_DIR"

load_env_file() {
    local env_file="$1"
    local line key value

    [ -f "$env_file" ] || return 0

    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ''|'#'*) continue ;;
        esac

        key="${line%%=*}"
        value="${line#*=}"
        key="${key#export }"

        if [ -z "$key" ] || [ "$key" = "$line" ]; then
            continue
        fi

        export "$key=$value"
    done < "$env_file"
}

load_env_file "$PROJECT_ROOT/.env"

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

ensure_mlx_running() {
    if curl -fsS --max-time 2 "$HOST_MLX_MODELS_URL" >/dev/null 2>&1; then
        echo "✅ MLX already running on port 8090"
        return 0
    fi

    echo "🚀 Starting MLX host service..."
    nohup "$PROJECT_ROOT/start_mlx.sh" > "$LOG_DIR/mlx-host.log" 2>&1 &
    wait_for_url "$HOST_MLX_MODELS_URL" "MLX" 30
}

echo "🚀 Starting Obsidian RAG (Docker)..."

# Ensure Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker Desktop."
    exit 1
fi

ensure_ollama_running
ensure_mlx_running

cd "$PROJECT_ROOT"

# Check if we need to pull data first? 
# No, let the user decide.

echo "📂 Data Directory: ${OBSIDIAN_RAG_DATA_DIR:-Local/Default}"
echo "📂 Vault Path:     $OBSIDIAN_VAULT_PATH"
echo "🤖 Ollama Bind:   $OLLAMA_BIND_HOST"

echo "⬆️  Bringing up services..."
docker-compose up -d

echo ""
echo "✅ Services Started!"
echo "🌐 WebApp:    http://localhost:3000"
echo "📊 Embedding: http://localhost:8000"
echo "🕸️  Graph:     http://localhost:8002"
echo "🧠 LightRAG:  http://localhost:8001"
echo "🧪 Streamlit: http://localhost:8501"
echo ""
echo "📝 Logs:"
echo "   docker-compose logs -f"
