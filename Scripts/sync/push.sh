#!/bin/bash
# Push local data to iCloud Staging for manual sync
# Usage: Run this on the machine that performed the indexing (e.g. Mac Mini)

# Load env to get data dir
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export $(grep -v '^#' "$SCRIPT_DIR/../../.env" | xargs)

LOCAL_DATA_DIR="${OBSIDIAN_RAG_DATA_DIR:-/Users/michel/obsidian_rag_local_data}"
ICLOUD_STAGE_DIR="./data/export_stage"

echo "📦 Pushing data from $LOCAL_DATA_DIR to iCloud Stage ($ICLOUD_STAGE_DIR)..."
mkdir -p "$ICLOUD_STAGE_DIR"

# Rsync is best for this
echo "  - Syncing ChromaDB..."
rsync -av --delete --exclude '*.lock' "$LOCAL_DATA_DIR/chroma_db/" "$ICLOUD_STAGE_DIR/chroma_db/"

echo "  - Syncing LightRAG..."
rsync -av --delete "$LOCAL_DATA_DIR/lightrag_db/" "$ICLOUD_STAGE_DIR/lightrag_db/"

echo "  - Syncing Graph Data..."
rsync -av --delete "$LOCAL_DATA_DIR/graph_data/" "$ICLOUD_STAGE_DIR/graph_data/"

echo "✅ Push complete. Run 'Scripts/sync/pull.sh' on the other machine to Import."
