#!/bin/bash
# Import SOTA data from iCloud to local SSD
# Usage: Run this on the MacBook (the Consumer)

# Default to creating a local data folder if env var not set
DEST_DIR="${OBSIDIAN_RAG_DATA_DIR:-/Users/michel/obsidian_rag_local_data}"
ICLOUD_SOURCE_DIR="./data/export_stage"

echo "📥 Importing SOTA data from iCloud ($ICLOUD_SOURCE_DIR) to $DEST_DIR..."

if [ ! -d "$ICLOUD_SOURCE_DIR/chroma_db" ]; then
    echo "❌ Error: Source data not found in $ICLOUD_SOURCE_DIR."
    echo "   Did you run export_to_icloud.sh on the Mini yet?"
    exit 1
fi

# Ensure destination exists
mkdir -p "$DEST_DIR/chroma_db"
mkdir -p "$DEST_DIR/lightrag_db"
mkdir -p "$DEST_DIR/graph_data"

echo "🛑 Stopping services to ensure safe overwrite..."
docker-compose down

# 1. Graph Data
echo "  - Importing Knowledge Graph..."
cp "$ICLOUD_SOURCE_DIR/knowledge_graph_sota.pkl" "$DEST_DIR/graph_data/knowledge_graph_sota.pkl"

# 2. ChromaDB
echo "  - Importing ChromaDB..."
rsync -av --delete "$ICLOUD_SOURCE_DIR/chroma_db/" "$DEST_DIR/chroma_db/"

# 3. LightRAG
echo "  - Importing LightRAG DB..."
rsync -av --delete "$ICLOUD_SOURCE_DIR/lightrag_db/" "$DEST_DIR/lightrag_db/"

echo "🚀 Restarting services..."
docker-compose up -d

echo "✅ Import complete! You are now running with the latest SOTA data."
