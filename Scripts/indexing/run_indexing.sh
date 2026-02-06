#!/bin/bash
# Unified Indexing Script for Obsidian RAG
# Runs all indexing processes: LightRAG, Kimi Graph, and ChromaDB

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source .env if present
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

cd "$REPO_ROOT"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║             Obsidian RAG Unified Indexer                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "This script will index your Obsidian vault into:"
echo "  1. Vector DB (Chroma)      - Semantic Search"
echo "  2. Knowledge Graph (Kimi)  - Structural/NetworkX"
echo "  3. LightRAG (Entities)     - Deep Thinking"
echo ""

# Check if Docker services are running
if ! docker ps | grep -q obsidian-api-gateway; then
    echo "⚠️  Services not running. Starting Docker stack..."
    docker-compose up -d
    echo "Using wait-for-it..."
    sleep 10
fi

read -p "Run Full Re-Index (deletes old data)? (y/N) " -n 1 -r
echo ""
FORCE_FLAG=""
CLEAR_FLAG=""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    FORCE_FLAG="--force" 
    CLEAR_FLAG="--clear"
    echo "⚠️  Full re-index selected."
else
    echo "ℹ️  Incremental update selected."
fi

echo ""
echo "🔹 Step 1/3: Indexing Vector DB (Chroma)..."
# Determine python interpreter
if [ -f "$REPO_ROOT/venv/bin/python" ]; then
    PYTHON_CMD="$REPO_ROOT/venv/bin/python"
elif [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$REPO_ROOT/.venv/bin/python"
else
    PYTHON_CMD="python"
fi

# Vector indexing runs locally with python against the service
PYTHONPATH="$REPO_ROOT" "$PYTHON_CMD" "$REPO_ROOT/src/indexing/index_vault.py" --refresh $CLEAR_FLAG || echo "⚠️ Vector indexing warning"

echo ""
echo "🔹 Step 2/3: Indexing Knowledge Graph (Kimi/NetworkX)..."
# Kimi Graph runs inside the container
docker exec -it obsidian-graph-service python /app/src/services/kimi_graph_builder.py || echo "⚠️ Kimi Graph indexing warning"

echo ""
echo "🔹 Step 3/3: Indexing LightRAG (Entities)..."
# LightRAG runs via its own script/endpoint
"$SCRIPT_DIR/index_with_lightrag.sh" $FORCE_FLAG || echo "⚠️ LightRAG indexing warning"

echo ""
echo "✅ Indexing Complete!"
echo ""
