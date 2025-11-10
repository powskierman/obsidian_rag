#!/bin/bash
echo "🚀 Starting Obsidian RAG System"
echo ""

# Get script directory and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

# Verify we're in the right directory
if [ ! -f "embedding_service.py" ]; then
    echo "❌ Error: embedding_service.py not found. Are you in the right directory?"
    exit 1
fi

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Handle streamlit.log BEFORE venv activation (in case venv script has issues)
STREAMLIT_LOG_FILE="streamlit.log"
if [ -d "$STREAMLIT_LOG_FILE" ]; then
    echo "⚠️ Warning: streamlit.log is a directory, removing it..."
    rm -rf "$STREAMLIT_LOG_FILE" || {
        echo "⚠️ Could not remove directory, using streamlit_ui.log instead"
        STREAMLIT_LOG_FILE="streamlit_ui.log"
    }
fi

# Create empty log file if it doesn't exist (to ensure it's a file, not directory)
touch "$STREAMLIT_LOG_FILE" 2>/dev/null || {
    echo "⚠️ Could not create log file $STREAMLIT_LOG_FILE, using streamlit_ui.log"
    STREAMLIT_LOG_FILE="streamlit_ui.log"
    touch "$STREAMLIT_LOG_FILE" 2>/dev/null || {
        echo "❌ Error: Could not create log file. Check permissions."
        exit 1
    }
}

# Activate virtual environment if it exists (suppress any streamlit.log errors)
if [ -d "venv" ]; then
    source venv/bin/activate 2>&1 | grep -v "streamlit.log" || true
elif [ -d "venv_python313" ]; then
    source venv_python313/bin/activate 2>&1 | grep -v "streamlit.log" || true
else
    echo "⚠️ Warning: No virtual environment found. Using system Python."
fi

# Ensure log file doesn't exist as a directory before redirecting
if [ -d "$STREAMLIT_LOG_FILE" ]; then
    echo "❌ Error: $STREAMLIT_LOG_FILE is still a directory. Please remove it manually:"
    echo "   rm -rf $STREAMLIT_LOG_FILE"
    exit 1
fi

# Start embedding service
echo "Starting embedding service..."
python embedding_service.py > embedding_service.log 2>&1 &
EMBED_PID=$!
echo "  PID: $EMBED_PID"
sleep 5  # Increased wait time for service to start

# Check if embedding service started successfully
if ! kill -0 $EMBED_PID 2>/dev/null; then
    echo "❌ Error: Embedding service failed to start"
    echo "Check embedding_service.log for details"
    echo ""
    echo "Common fixes:"
    echo "  1. Fix dependencies: pip install --upgrade importlib-metadata setuptools"
    echo "  2. Use Docker instead: docker-compose up -d"
    exit 1
fi

# Verify embedding service is responding
sleep 2
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠️ Warning: Embedding service started but not responding yet"
    echo "It may still be initializing. Check logs: tail -f embedding_service.log"
fi

# Determine which Streamlit UI file to use
STREAMLIT_UI=""
if [ -f "streamlit_ui_docker.py" ]; then
    STREAMLIT_UI="streamlit_ui_docker.py"
elif [ -f "streamlit_ui_enhanced.py" ]; then
    STREAMLIT_UI="streamlit_ui_enhanced.py"
elif [ -f "obsidian_rag_ui.py" ]; then
    STREAMLIT_UI="obsidian_rag_ui.py"
else
    echo "❌ Error: No Streamlit UI file found"
    kill $EMBED_PID 2>/dev/null
    exit 1
fi

# Start Streamlit UI - use explicit file path to avoid issues
echo "Starting Streamlit UI ($STREAMLIT_UI)..."
streamlit run "$STREAMLIT_UI" \
    --server.headless true \
    --browser.gatherUsageStats false \
    --server.port 8501 \
    --server.address 0.0.0.0 > "$STREAMLIT_LOG_FILE" 2>&1 &
STREAMLIT_PID=$!
echo "  PID: $STREAMLIT_PID"
sleep 3  # Increased wait time

# Check if Streamlit started successfully
if ! kill -0 $STREAMLIT_PID 2>/dev/null; then
    echo "❌ Error: Streamlit UI failed to start"
    echo "Check $STREAMLIT_LOG_FILE for details"
    kill $EMBED_PID 2>/dev/null
    exit 1
fi

echo ""
echo "✅ System ready!"
echo "📊 Embedding Service: http://localhost:8000 (PID: $EMBED_PID)"
echo "💬 Chat Interface: http://localhost:8501 (PID: $STREAMLIT_PID)"
echo ""
echo "Logs:"
echo "  tail -f embedding_service.log"
echo "  tail -f $STREAMLIT_LOG_FILE"
echo ""
echo "To stop: ./Scripts/stop_obsidian_rag.sh"
echo ""
echo "Note: If services show as offline, they may still be initializing."
echo "      Wait a few seconds and refresh the UI."
