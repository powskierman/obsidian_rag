#!/bin/bash
# start_obsidian_rag.sh - Start all RAG services

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
echo "📊 Embedding Service: http://localhost:8000"
echo "💬 Chat Interface: http://localhost:8501"
echo ""
echo "Logs:"
echo "  tail -f embedding_service.log"
echo "  tail -f streamlit.log"
echo ""
echo "To stop: ./stop_obsidian_rag.sh"

# ============================================================
# stop_obsidian_rag.sh - Stop all RAG services
# ============================================================

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

echo ""
echo "✅ System stopped"

# ============================================================
# check_status.sh - Check service status
# ============================================================

#!/bin/bash
echo "📊 Obsidian RAG System Status"
echo "=" | tr ' ' '='
echo ""

# Check embedding service
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Embedding Service: RUNNING (port 8000)"
    curl -s http://localhost:8000/stats | python -m json.tool 2>/dev/null || echo "   (stats unavailable)"
else
    echo "❌ Embedding Service: STOPPED"
fi

echo ""

# Check Streamlit
if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Streamlit UI: RUNNING (port 8501)"
    echo "   URL: http://localhost:8501"
else
    echo "❌ Streamlit UI: STOPPED"
fi

echo ""

# Check Ollama
if lsof -Pi :11434 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Ollama: RUNNING (port 11434)"
    ollama list 2>/dev/null | grep -E "qwen2.5|deepseek" || echo "   (no models info)"
else
    echo "❌ Ollama: STOPPED"
    echo "   Start: ollama serve"
fi

echo ""
echo "=" | tr ' ' '='

# ============================================================
# start_with_watcher.sh - Start with file watching
# ============================================================

#!/bin/bash
echo "🚀 Starting Obsidian RAG System with File Watcher"
echo ""

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
source venv/bin/activate

# Start embedding service
echo "Starting embedding service..."
python embedding_service.py > embedding_service.log 2>&1 &
EMBED_PID=$!
sleep 3

# Start file watcher
echo "Starting file watcher..."
python watching_scanner.py > scanner.log 2>&1 &
WATCHER_PID=$!
sleep 2

# Start Streamlit
echo "Starting Streamlit UI..."
streamlit run obsidian_rag_ui.py \
    --server.headless true \
    --browser.gatherUsageStats false \
    --server.port 8501 > streamlit.log 2>&1 &
STREAMLIT_PID=$!

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
