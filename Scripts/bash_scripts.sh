#!/bin/bash
# =============================================================================
# start_obsidian_rag.sh - Start basic RAG services
# =============================================================================
#!/bin/bash

echo "🚀 Starting Obsidian RAG System"
echo ""

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
source venv/bin/activate

# Start embedding service
echo "Starting embedding service..."
python embedding_service.py > embedding_service.log 2>&1 &
EMBED_PID=$!
echo "  PID: $EMBED_PID"
sleep 3

# Start Streamlit UI
echo "Starting Streamlit UI..."
streamlit run obsidian_rag_ui.py \
    --server.headless true \
    --browser.gatherUsageStats false \
    --server.port 8501 > streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo "  PID: $STREAMLIT_PID"

echo ""
echo "✅ System ready!"
echo "📊 Embedding Service: http://localhost:8000 (PID: $EMBED_PID)"
echo "💬 Chat Interface: http://localhost:8501 (PID: $STREAMLIT_PID)"
echo ""
echo "Logs:"
echo "  tail -f embedding_service.log"
echo "  tail -f streamlit.log"
echo ""
echo "To stop: ./stop_obsidian_rag.sh"


# =============================================================================
# stop_obsidian_rag.sh - Stop all RAG services
# =============================================================================
#!/bin/bash

echo "🛑 Stopping Obsidian RAG System"
echo ""

# Stop embedding service
EMBED_PID=$(lsof -ti:8000)
if [ ! -z "$EMBED_PID" ]; then
    echo "Stopping embedding service (PID: $EMBED_PID)..."
    kill $EMBED_PID
    sleep 1
else
    echo "Embedding service not running"
fi

# Stop Streamlit
STREAMLIT_PID=$(lsof -ti:8501)
if [ ! -z "$STREAMLIT_PID" ]; then
    echo "Stopping Streamlit (PID: $STREAMLIT_PID)..."
    kill $STREAMLIT_PID
    sleep 1
else
    echo "Streamlit not running"
fi

# Stop file watcher if running
WATCHER_PID=$(pgrep -f watching_scanner.py)
if [ ! -z "$WATCHER_PID" ]; then
    echo "Stopping file watcher (PID: $WATCHER_PID)..."
    kill $WATCHER_PID
    sleep 1
else
    echo "File watcher not running"
fi

echo ""
echo "✅ System stopped"


# =============================================================================
# check_status.sh - Check service status
# =============================================================================
#!/bin/bash

echo "📊 Obsidian RAG System Status"
echo "======================================================================"
echo ""

# Check embedding service
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Embedding Service: RUNNING (port 8000)"
    echo -n "   Stats: "
    curl -s http://localhost:8000/stats 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"{data['total_documents']} chunks, ~{data.get('estimated_notes', int(data['total_documents']/4.4))} notes\")" 2>/dev/null || echo "unavailable"
else
    echo "❌ Embedding Service: STOPPED"
    echo "   Start: python embedding_service.py"
fi

echo ""

# Check Streamlit
if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Streamlit UI: RUNNING (port 8501)"
    echo "   URL: http://localhost:8501"
else
    echo "❌ Streamlit UI: STOPPED"
    echo "   Start: streamlit run obsidian_rag_ui.py"
fi

echo ""

# Check Ollama
if lsof -Pi :11434 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Ollama: RUNNING (port 11434)"
    echo "   Models:"
    ollama list 2>/dev/null | grep -E "qwen2.5|deepseek|llama" | head -5 || echo "   (no models info)"
else
    echo "❌ Ollama: STOPPED"
    echo "   Start: ollama serve"
fi

echo ""

# Check file watcher
if pgrep -f watching_scanner.py >/dev/null ; then
    WATCHER_PID=$(pgrep -f watching_scanner.py)
    echo "✅ File Watcher: RUNNING (PID: $WATCHER_PID)"
    echo "   Monitoring vault for changes"
else
    echo "⚪ File Watcher: STOPPED (optional)"
    echo "   Start: ./start_with_watcher.sh"
fi

echo ""

# Check memory system
if [ -d "mem0_db" ]; then
    MEMORY_SIZE=$(du -sh mem0_db 2>/dev/null | cut -f1)
    echo "✅ Memory System: INITIALIZED"
    echo "   Database: mem0_db ($MEMORY_SIZE)"
else
    echo "⚠️  Memory System: NOT INITIALIZED"
    echo "   Run: python rag_with_memory.py init"
fi

echo ""
echo "======================================================================"
echo ""
echo "Quick Actions:"
echo "  Start:  ./start_obsidian_rag.sh"
echo "  Stop:   ./stop_obsidian_rag.sh"
echo "  Watch:  ./start_with_watcher.sh"
echo "  Logs:   tail -f *.log"


# =============================================================================
# start_with_watcher.sh - Start with file watching
# =============================================================================
#!/bin/bash

echo "🚀 Starting Obsidian RAG System with File Watcher"
echo ""

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
source venv/bin/activate

# Start embedding service
echo "Starting embedding service..."
python embedding_service.py > embedding_service.log 2>&1 &
EMBED_PID=$!
echo "  PID: $EMBED_PID"
sleep 3

# Start file watcher
echo "Starting file watcher..."
python watching_scanner.py > scanner.log 2>&1 &
WATCHER_PID=$!
echo "  PID: $WATCHER_PID"
sleep 2

# Start Streamlit
echo "Starting Streamlit UI..."
streamlit run obsidian_rag_ui.py \
    --server.headless true \
    --browser.gatherUsageStats false \
    --server.port 8501 > streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo "  PID: $STREAMLIT_PID"

echo ""
echo "✅ System ready!"
echo "📊 Embedding Service: http://localhost:8000 (PID: $EMBED_PID)"
echo "👁️  File Watcher: Active (PID: $WATCHER_PID)"
echo "💬 Chat Interface: http://localhost:8501 (PID: $STREAMLIT_PID)"
echo ""
echo "Logs:"
echo "  tail -f embedding_service.log"
echo "  tail -f scanner.log"
echo "  tail -f streamlit.log"
echo ""
echo "The file watcher will automatically index new/modified notes."
echo "To stop: ./stop_obsidian_rag.sh"


# =============================================================================
# backup.sh - Backup databases and memories
# =============================================================================
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


# =============================================================================
# restore.sh - Restore from backup
# =============================================================================
#!/bin/bash

echo "🔄 Restore Obsidian RAG System from Backup"
echo ""

if [ -z "$1" ]; then
    echo "Usage: ./restore.sh <backup_date>"
    echo ""
    echo "Available backups:"
    ls -1 backups/ | grep -E "[0-9]{8}_[0-9]{6}" | cut -d_ -f2-3 | sort -u
    exit 1
fi

BACKUP_DATE=$1
BACKUP_DIR="backups"

# Stop services first
echo "Stopping services..."
./stop_obsidian_rag.sh

echo ""
echo "Restoring from backup: $BACKUP_DATE"
echo ""

# Restore ChromaDB
if [ -f "$BACKUP_DIR/chroma_${BACKUP_DATE}.tar.gz" ]; then
    echo "Restoring ChromaDB..."
    rm -rf chroma_db/
    tar -xzf $BACKUP_DIR/chroma_${BACKUP_DATE}.tar.gz
    echo "  ✅ ChromaDB restored"
else
    echo "  ⚠️  ChromaDB backup not found"
fi

# Restore Mem0 DB
if [ -f "$BACKUP_DIR/mem0_${BACKUP_DATE}.tar.gz" ]; then
    echo "Restoring Mem0 DB..."
    rm -rf mem0_db/
    tar -xzf $BACKUP_DIR/mem0_${BACKUP_DATE}.tar.gz
    echo "  ✅ Mem0 DB restored"
else
    echo "  ⚠️  Mem0 DB backup not found"
fi

echo ""
echo "✅ Restore complete!"
echo "Restart services: ./start_obsidian_rag.sh"


# =============================================================================
# test.sh - Quick system test
# =============================================================================
#!/bin/bash

echo "🧪 Testing Obsidian RAG System"
echo ""

# Check if services are running
./check_status.sh

echo ""
echo "Running quick tests..."
echo ""

# Test embedding service
echo "1. Testing embedding service..."
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$STATUS_CODE" = "200" ]; then
    echo "   ✅ Embedding service healthy"
else
    echo "   ❌ Embedding service not responding (code: $STATUS_CODE)"
fi

# Test stats endpoint
echo "2. Testing stats endpoint..."
STATS=$(curl -s http://localhost:8000/stats)
if [ ! -z "$STATS" ]; then
    echo "   ✅ Stats: $STATS"
else
    echo "   ❌ Stats endpoint failed"
fi

# Test Ollama
echo "3. Testing Ollama..."
if ollama list >/dev/null 2>&1; then
    echo "   ✅ Ollama responding"
    MODELS=$(ollama list | grep -c qwen)
    echo "   Found $MODELS Qwen model(s)"
else
    echo "   ❌ Ollama not responding"
fi

# Test memory system
echo "4. Testing memory system..."
if [ -d "mem0_db" ]; then
    echo "   ✅ Memory database exists"
    MEMORY_COUNT=$(python3 -c "from rag_with_memory import MemoryRAG; print(len(MemoryRAG().get_all_memories()))" 2>/dev/null)
    if [ ! -z "$MEMORY_COUNT" ]; then
        echo "   ✅ Memories stored: $MEMORY_COUNT"
    else
        echo "   ⚠️  Could not count memories"
    fi
else
    echo "   ⚠️  Memory system not initialized"
fi

echo ""
echo "Test complete!"


# =============================================================================
# clean.sh - Clean logs and temporary files
# =============================================================================
#!/bin/bash

echo "🧹 Cleaning Obsidian RAG System"
echo ""

# Remove logs
if ls *.log 1> /dev/null 2>&1; then
    echo "Removing log files..."
    rm -f *.log
    echo "  ✅ Logs removed"
fi

# Remove Python cache
if [ -d "__pycache__" ]; then
    echo "Removing Python cache..."
    rm -rf __pycache__
    echo "  ✅ Python cache removed"
fi

# Remove temporary files
echo "Removing temporary files..."
find . -name "*.pyc" -delete
find . -name ".DS_Store" -delete
echo "  ✅ Temporary files removed"

echo ""
echo "✅ Cleanup complete!"


# =============================================================================
# Usage Instructions
# =============================================================================

# To use these scripts:
# 1. Save this file as 'scripts.sh' in your project directory
# 2. Extract individual scripts:
#    ./extract_scripts.sh
# 3. Or manually create each script file and make executable:
#    chmod +x start_obsidian_rag.sh
#    chmod +x stop_obsidian_rag.sh
#    chmod +x check_status.sh
#    chmod +x start_with_watcher.sh
#    chmod +x backup.sh
#    chmod +x restore.sh
#    chmod +x test.sh
#    chmod +x clean.sh
