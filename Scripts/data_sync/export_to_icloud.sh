#!/bin/bash
# Export local SOTA data to iCloud for syncing to other machines
# Usage: Run this on the Mac Mini (the Indexer)

LOCAL_DATA_DIR="${OBSIDIAN_RAG_DATA_DIR:-/Users/michel/obsidian_rag_local_data}"
ICLOUD_EXPORT_DIR="./data/export_stage"

echo "📦 Exporting SOTA data from $LOCAL_DATA_DIR to iCloud ($ICLOUD_EXPORT_DIR)..."

# Ensure export directory exists
mkdir -p "$ICLOUD_EXPORT_DIR"

# 1. Graph Data (Single file, safe)
echo "  - Copying Knowledge Graph..."
cp "$LOCAL_DATA_DIR/graph_data/knowledge_graph_sota.pkl" "$ICLOUD_EXPORT_DIR/knowledge_graph_sota.pkl" 2>/dev/null || \
cp "$LOCAL_DATA_DIR/graph_data/knowledge_graph_full.pkl" "$ICLOUD_EXPORT_DIR/knowledge_graph_sota.pkl"

# 2. ChromaDB (SQLite - MUST be stopped or carefully copied)
# We use rsync with --delete to create a mirror
echo "  - Syncing ChromaDB (takes time)..."
rsync -av --delete --exclude '*.lock' "$LOCAL_DATA_DIR/chroma_db/" "$ICLOUD_EXPORT_DIR/chroma_db/"

# 3. LightRAG (JSON/KV)
echo "  - Syncing LightRAG DB..."
rsync -av --delete "$LOCAL_DATA_DIR/lightrag_db/" "$ICLOUD_EXPORT_DIR/lightrag_db/"

echo "✅ Export complete! iCloud will now sync these files to your other devices."
echo "   On MacBook, run: ./Scripts/data_sync/import_from_icloud.sh"
