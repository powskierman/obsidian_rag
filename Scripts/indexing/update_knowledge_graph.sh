#!/bin/bash
# Update Knowledge Graph (NetworkX) Only
# Usage: ./update_knowledge_graph.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi
DATA_ROOT="${OBSIDIAN_RAG_DATA_DIR:-/Users/michel/obsidian_rag_local_data}"
GRAPH_FILE="$DATA_ROOT/graph_data/knowledge_graph_full.pkl"

echo "🔹 Rebuilding Knowledge Graph (NetworkX)..."
echo "   (This is a fast structural scan of your vault)"

# Check if service is running
if ! docker ps | grep -q obsidian-graph-service; then
    echo "❌ Error: obsidian-graph-service container is not running."
    echo "   Run ./Scripts/setup/start_obsidian_rag.sh first."
    exit 1
fi

if ! docker exec -it -w /app obsidian-graph-service python -m src.services.networkx_graph_builder --output /app/graph_data/knowledge_graph_full.pkl; then
    echo "❌ Error: NetworkX graph rebuild failed."
    exit 1
fi

# Validate centralized output location
if [ ! -f "$GRAPH_FILE" ]; then
    echo "❌ Error: Expected graph file not found at $GRAPH_FILE"
    exit 1
fi

echo "🔄 Restarting graph-service to load updated graph..."
if docker compose version >/dev/null 2>&1; then
    if ! (cd "$REPO_ROOT" && docker compose restart graph-service); then
        echo "❌ Error: Failed to restart graph-service."
        exit 1
    fi
else
    if ! (cd "$REPO_ROOT" && docker-compose restart graph-service); then
        echo "❌ Error: Failed to restart graph-service."
        exit 1
    fi
fi

echo "✅ Knowledge graph rebuilt and graph-service restarted."
