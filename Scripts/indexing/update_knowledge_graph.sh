#!/bin/bash
# Update Knowledge Graph (NetworkX) Only
# Usage: ./update_knowledge_graph.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🔹 Rebuilding Knowledge Graph (NetworkX)..."
echo "   (This is a fast structural scan of your vault)"

# Check if service is running
if ! docker ps | grep -q obsidian-graph-service; then
    echo "❌ Error: obsidian-graph-service container is not running."
    echo "   Run ./Scripts/setup/start_obsidian_rag.sh first."
    exit 1
fi

if ! docker exec -it obsidian-graph-service python /app/src/services/networkx_graph_builder.py --output /app/graph_data/knowledge_graph_full.pkl; then
    echo "❌ Error: NetworkX graph rebuild failed."
    exit 1
fi

# Sync container volume output to local graph_data for the verifier
if [ -f "$REPO_ROOT/data/graph_data/knowledge_graph_full.pkl" ]; then
    mkdir -p "$REPO_ROOT/graph_data"
    cp "$REPO_ROOT/data/graph_data/knowledge_graph_full.pkl" "$REPO_ROOT/graph_data/knowledge_graph_full.pkl"
else
    echo "❌ Error: Expected graph file not found at $REPO_ROOT/data/graph_data/knowledge_graph_full.pkl"
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
