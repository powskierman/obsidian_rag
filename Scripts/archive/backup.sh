#!/bin/bash
echo "💾 Backing up Obsidian RAG System"
echo ""

# Create backup directory
BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup ChromaDB
if [ -d "chroma_db" ]; then
    echo "Backing up ChromaDB..."
    tar -czf $BACKUP_DIR/chroma_${DATE}.tar.gz chroma_db/
    echo "  ✅ chroma_${DATE}.tar.gz"
else
    echo "  ⚠️  ChromaDB not found"
fi

# Backup Mem0 DB
if [ -d "mem0_db" ]; then
    echo "Backing up Mem0 DB..."
    tar -czf $BACKUP_DIR/mem0_${DATE}.tar.gz mem0_db/
    echo "  ✅ mem0_${DATE}.tar.gz"
else
    echo "  ⚠️  Mem0 DB not found"
fi

# Export memories
if [ -f "rag_with_memory.py" ]; then
    echo "Exporting memories..."
    python3 -c "from rag_with_memory import MemoryRAG; MemoryRAG().export_memories('$BACKUP_DIR/memories_${DATE}.json')" 2>/dev/null
    if [ -f "$BACKUP_DIR/memories_${DATE}.json" ]; then
        echo "  ✅ memories_${DATE}.json"
    else
        echo "  ⚠️  Memory export failed"
    fi
fi

# Backup logs
echo "Backing up logs..."
if ls *.log 1> /dev/null 2>&1; then
    tar -czf $BACKUP_DIR/logs_${DATE}.tar.gz *.log
    echo "  ✅ logs_${DATE}.tar.gz"
fi

echo ""
echo "✅ Backup complete!"
echo "Location: $BACKUP_DIR/"
echo ""
ls -lh $BACKUP_DIR/*${DATE}*

# Clean up old backups (keep last 30 days)
echo ""
echo "Cleaning up old backups (>30 days)..."
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.json" -mtime +30 -delete
echo "Done!"
