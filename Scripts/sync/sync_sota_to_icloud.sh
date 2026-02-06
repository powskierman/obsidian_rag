#!/bin/bash
# sync_sota_to_icloud.sh
# Run this ON THE MAC MINI to move SOTA results back to iCloud for syncing to MacBook.

set -e

# Paths
PROJECT_DIR="/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"
LOCAL_DATA_DIR="/Users/michel/obsidian_rag_local_data"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║          Syncing SOTA Results back to iCloud             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# 1. Check if we are on the Mini (or at least if paths exist)
if [ ! -d "$LOCAL_DATA_DIR" ]; then
    echo "❌ Error: $LOCAL_DATA_DIR not found."
    echo "This script must be run on the Mac Mini where the local data exists."
    exit 1
fi

cd "$PROJECT_DIR"

# 2. Stop services
echo "🛑 Stopping Docker services..."
docker compose down
echo ""

# 3. Sync ChromaDB
echo "📦 Syncing ChromaDB (Vector) back to iCloud..."
if [ -d "$LOCAL_DATA_DIR/chroma_db" ]; then
    rsync -av --delete "$LOCAL_DATA_DIR/chroma_db/" "./chroma_db/"
    echo "   ✅ ChromaDB synced"
else
    echo "   ⚠️  ChromaDB not found in local data folder"
fi
echo ""

# 4. Sync LightRAG
echo "📦 Syncing LightRAG (Entities) back to iCloud..."
if [ -d "$LOCAL_DATA_DIR/lightrag_db" ]; then
    rsync -av --delete "$LOCAL_DATA_DIR/lightrag_db/" "./lightrag_db/"
    echo "   ✅ LightRAG synced"
else
    echo "   ⚠️  LightRAG not found"
fi
echo ""

# 5. Sync NetworkX Graph
echo "📦 Syncing NetworkX (Structural) back to iCloud..."
if [ -d "$LOCAL_DATA_DIR/graph_data" ]; then
    # Destination is data/graph_data in the project root
    mkdir -p "./data/graph_data"
    rsync -av --delete "$LOCAL_DATA_DIR/graph_data/" "./data/graph_data/"
    echo "   ✅ NetworkX synced"
else
    echo "   ⚠️  NetworkX data not found"
fi
echo ""

# 6. Disable the local override
echo "🔄 Restoring standard iCloud paths..."
if [ -f "docker-compose.override.yml" ]; then
    mv docker-compose.override.yml docker-compose.override.yml.bak
    echo "   ✅ Redirected docker-compose.override.yml to .bak"
else
    echo "   ℹ️  No override file found to disable."
fi
echo ""

# 7. Restart services
echo "🚀 Restarting services in iCloud mode..."
docker compose up -d
echo ""

echo "🎉 SYNC COMPLETE!"
echo "═══════════════════════════════════════════════════════════"
echo "iCloud will now begin syncing these files to your MacBook."
echo "Depending on your upload speed, this may take 15-30 minutes."
echo "Check the Finder Status on both machines."
echo "═══════════════════════════════════════════════════════════"
