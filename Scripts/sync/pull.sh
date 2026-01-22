#!/bin/bash
# Pull data from iCloud Staging to Local SSD
# Usage: Run this on the Consumer machine (e.g. MacBook)

# Load env to get data dir
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export $(grep -v '^#' "$SCRIPT_DIR/../../.env" | xargs)

LOCAL_DATA_DIR="${OBSIDIAN_RAG_DATA_DIR:-/Users/michel/obsidian_rag_local_data}"
ICLOUD_STAGE_DIR="./data/export_stage"

echo "📥 Pulling data from iCloud Stage ($ICLOUD_STAGE_DIR) to $LOCAL_DATA_DIR..."

if [ ! -d "$ICLOUD_STAGE_DIR/lightrag_db" ]; then
    echo "❌ Error: iCloud stage is empty. Run 'push.sh' on the Indexer first."
    exit 1
fi

echo "🛑 Stopping Docker services to prevent corruption..."
docker-compose down

echo "  - Syncing ChromaDB..."
mkdir -p "$LOCAL_DATA_DIR/chroma_db"
rsync -av --delete "$ICLOUD_STAGE_DIR/chroma_db/" "$LOCAL_DATA_DIR/chroma_db/"

echo "  - Syncing LightRAG..."
mkdir -p "$LOCAL_DATA_DIR/lightrag_db"
rsync -av --delete "$ICLOUD_STAGE_DIR/lightrag_db/" "$LOCAL_DATA_DIR/lightrag_db/"

echo "  - Syncing Graph Data..."
mkdir -p "$LOCAL_DATA_DIR/graph_data"
rsync -av --delete "$ICLOUD_STAGE_DIR/graph_data/" "$LOCAL_DATA_DIR/graph_data/"

echo "🚀 Restarting services..."
docker-compose up -d

echo "✅ Pull complete. You are now using the latest data."
