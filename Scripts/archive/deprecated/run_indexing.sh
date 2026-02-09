#!/bin/bash
# Unified Indexing Script for Obsidian RAG
# Runs all indexing processes in Docker containers (Consistent & SOTA)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export $(grep -v '^#' "$SCRIPT_DIR/../.env" | xargs)

echo "╔════════════════════════════════════════════════════════════╗"
echo "║             Obsidian RAG Unified Indexer                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "This script will indexed your Obsidian vault into:"
echo "  1. LightRAG (Entities & Relations) - Port 8001"
echo "  2. Knowledge Graph (WikiLinks)     - Port 8002"
echo "  3. Vector DB (Semantic Chunks)     - Port 8000"
echo ""

# Check Docker
if ! docker ps | grep -q obsidian-api-gateway; then
    echo "⚠️  Services not running. Starting Docker stack..."
    docker-compose up -d
    echo "Using wait-for-it..."
    sleep 10
fi

read -p "Run Full Re-Index (deletes old data)? (y/N) " -n 1 -r
echo ""
FORCE_FLAG=""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    FORCE_FLAG="--force" 
    # For LightRAG API
    FORCE_JSON='{"vault_path": "/app/vault", "force": true}'
else
    FORCE_JSON='{"vault_path": "/app/vault", "force": false}'
fi

echo ""
echo "🔹 Step 1/3: Indexing LightRAG (Entities)..."
curl -X POST http://localhost:8001/index-vault \
     -H "Content-Type: application/json" \
     -d "$FORCE_JSON"
echo ""

echo ""
echo "🔹 Step 2/3: Indexing Vector DB (Chroma)..."
# Copy scanner script to container to run with correct python environment
docker cp "$SCRIPT_DIR/vault_management/watching_scanner.py" obsidian-embedding:/app/scanner.py
docker exec obsidian-embedding python scanner.py --non-interactive $FORCE_FLAG || echo "⚠️ Vector indexing warning (check logs)"

echo ""
echo "🔹 Step 3/3: Indexing Knowledge Graph (NetworkX)..."
# Uses existing helper which does user/docker cp logic
# We call it directly here to keep flow unified
docker cp src/services/build_graph.py obsidian-graph-service:/app/build_graph.py
docker exec obsidian-graph-service python /app/build_graph.py $FORCE_FLAG || echo "⚠️ Graph indexing warning (check logs)"

echo ""
echo "✅ Indexing Complete!"
echo ""
echo "👉 If you are on the Mini, run 'Scripts/sync/push.sh' to sync data to iCloud."
