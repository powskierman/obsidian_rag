#!/bin/bash
# sync_local_to_icloud.sh
# Check if running on Mac Mini (Volume existence check or Hostname check)
# Default Source: /Users/michel/obsidian_rag_local_data
# Default Target: ~/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag

set -e

SOURCE_DIR="/Users/michel/obsidian_rag_local_data"
TARGET_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║      Syncing Local Databases to iCloud                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo "Source: $SOURCE_DIR"
echo "Target: $TARGET_DIR"
echo ""

if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Error: Source directory not found at $SOURCE_DIR"
    echo "   (Are you running this on the Mac Mini?)"
    exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "❌ Error: Target directory not found at $TARGET_DIR"
    exit 1
fi

# Function to sync a directory
sync_dir() {
    local subdir=$1
    echo "🔄 Syncing $subdir..."
    if [ -d "$SOURCE_DIR/$subdir" ]; then
        # Use rsync with checksums (-c) to only copy changed files
        # --delete ensures the target mirrors source (removes deleted files)
        rsync -avc --delete "$SOURCE_DIR/$subdir/" "$TARGET_DIR/$subdir/"
        echo "   ✅ $subdir Synced"
    else
        echo "   ⚠️  Source $subdir not found, skipping"
    fi
}

# 1. Sync ChromaDB
sync_dir "chroma_db"

# 2. Sync LightRAG
sync_dir "lightrag_db"

# 3. Sync Graph Data
sync_dir "graph_data"

echo ""
echo "🎉 SYNC COMPLETE! MacBook should now see updated databases."
