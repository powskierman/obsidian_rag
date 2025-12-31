#!/bin/bash
# Restore November backup from /Volumes/max to Mac Mini
set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     Restore November LightRAG Backup to Mac Mini         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

BACKUP_SOURCE="/Volumes/max/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag_backup_20241222/lightrag_db"
MINI_DEST="/Volumes/Michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/lightrag_db"

# Check backup exists
if [ ! -d "$BACKUP_SOURCE" ]; then
    echo "❌ Backup not found at: $BACKUP_SOURCE"
    echo "Please ensure /Volumes/max is mounted"
    exit 1
fi

echo "📂 Backup source: $BACKUP_SOURCE"
echo "📂 Mac Mini destination: $MINI_DEST"
echo ""

# Show backup size
BACKUP_SIZE=$(du -sh "$BACKUP_SOURCE" | cut -f1)
echo "📊 Backup size: $BACKUP_SIZE"
echo ""

# Count files in backup
FILE_COUNT=$(find "$BACKUP_SOURCE" -type f | wc -l | xargs)
echo "📁 Files in backup: $FILE_COUNT"
echo ""

read -p "Continue with restore? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Restore cancelled"
    exit 1
fi

echo ""
echo "🗑️  Removing current lightrag_db on Mac Mini..."
rm -rf "$MINI_DEST"

echo "📦 Copying backup to Mac Mini via SMB..."
rsync -avh --progress "$BACKUP_SOURCE" "$MINI_DEST"

echo ""
echo "✅ Backup restored to Mac Mini"
echo ""
echo "📊 Verifying restore..."
RESTORED_SIZE=$(du -sh "$MINI_DEST" | cut -f1)
echo "   Size: $RESTORED_SIZE"

RESTORED_FILES=$(find "$MINI_DEST" -type f | wc -l | xargs)
echo "   Files: $RESTORED_FILES"
echo ""

# Check indexed_files.txt
if [ -f "$MINI_DEST/indexed_files.txt" ]; then
    INDEXED_COUNT=$(wc -l < "$MINI_DEST/indexed_files.txt")
    echo "   Indexed files: $INDEXED_COUNT"
else
    echo "   ⚠️  indexed_files.txt not found"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                ✅ Restore Complete!                       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps on Mac Mini:"
echo ""
echo "1. Restart the Docker container:"
echo "   cd config/docker"
echo "   docker compose down"
echo "   docker compose up -d lightrag-service"
echo "   sleep 15"
echo ""
echo "2. Copy database to container:"
echo "   cd ../.."
echo "   docker cp lightrag_db/. obsidian-lightrag:/app/lightrag_db/"
echo "   docker restart obsidian-lightrag"
echo "   sleep 15"
echo ""
echo "3. Verify:"
echo "   curl http://localhost:8001/stats"
echo ""
