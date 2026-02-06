#!/bin/bash
# Start Obsidian RAG System (Docker Only)
# This script ensures a consistent environment across Mac Mini and MacBook.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Safely source .env handling spaces in paths
if [ -f "$SCRIPT_DIR/../../.env" ]; then
    set -a
    source "$SCRIPT_DIR/../../.env"
    set +a
fi

echo "🚀 Starting Obsidian RAG (Docker)..."

# Ensure Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker Desktop."
    exit 1
fi

cd "$SCRIPT_DIR/../.."

# Check if we need to pull data first? 
# No, let the user decide.

echo "📂 Data Directory: ${OBSIDIAN_RAG_DATA_DIR:-Local/Default}"
echo "📂 Vault Path:     $OBSIDIAN_VAULT_PATH"

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
