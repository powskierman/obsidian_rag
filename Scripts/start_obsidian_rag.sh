#!/bin/bash
echo "🚀 Starting Obsidian RAG System"
echo ""

# Get script directory and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

# Verify we're in the right directory
if [ ! -f "src/services/embedding_service.py" ]; then
    echo "❌ Error: src/services/embedding_service.py not found. Are you in the right directory?"
    exit 1
fi

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Ensure log directory exists
mkdir -p Scripts/logs

# Handle streamlit.log BEFORE venv activation
STREAMLIT_LOG_FILE="Scripts/logs/streamlit.log"
if [ -d "$STREAMLIT_LOG_FILE" ]; then
    echo "⚠️ Warning: streamlit.log is a directory, removing it..."
    rm -rf "$STREAMLIT_LOG_FILE" || {
        echo "⚠️ Could not remove directory, using streamlit_ui.log instead"
        STREAMLIT_LOG_FILE="Scripts/logs/streamlit_ui.log"
    }
fi

# Create empty log file
touch "$STREAMLIT_LOG_FILE" 2>/dev/null || {
    echo "⚠️ Could not create log file $STREAMLIT_LOG_FILE, using streamlit_ui.log"
    STREAMLIT_LOG_FILE="Scripts/logs/streamlit_ui.log"
    touch "$STREAMLIT_LOG_FILE" 2>/dev/null || {
        echo "❌ Error: Could not create log file. Check permissions."
        exit 1
    }
}

# Determine Python and Streamlit executables
PYTHON_EXEC="python3"
STREAMLIT_EXEC="streamlit"

if [ -d "venv" ]; then
    # Activate venv for good measure, though we use explicit paths
    source venv/bin/activate
    PYTHON_EXEC="venv/bin/python3"
    STREAMLIT_EXEC="venv/bin/streamlit"
elif [ -d "venv_python313" ]; then
    source venv_python313/bin/activate
    PYTHON_EXEC="venv_python313/bin/python3"
    STREAMLIT_EXEC="venv_python313/bin/streamlit"
else
    echo "⚠️ Warning: No virtual environment found. Using system Python."
fi

echo "Using Python: $PYTHON_EXEC"
echo "Using Streamlit: $STREAMLIT_EXEC"

# Load variables from .env if it exists
if [ -f ".env" ]; then
    echo "📝 Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# FORCE LOCALHOST for all services
export OLLAMA_HOST="http://localhost:11434"
export EMBEDDING_SERVICE_URL="http://localhost:8000"
export CLAUDE_GRAPH_SERVICE_URL="http://localhost:8002"
export LLM_HOST="http://localhost:11434"
export KIMI_MODEL="anthropic/claude-haiku-4.5" # Use Haiku 4.5 via OpenRouter for backend services

# Ensure log file doesn't exist as a directory
if [ -d "$STREAMLIT_LOG_FILE" ]; then
    echo "❌ Error: $STREAMLIT_LOG_FILE is still a directory."
    exit 1
fi

# Start embedding service
echo "Starting embedding service..."
$PYTHON_EXEC src/services/embedding_service.py > Scripts/logs/embedding_service.log 2>&1 &
EMBED_PID=$!
echo "  PID: $EMBED_PID"
sleep 5

# Check embedding service
if ! kill -0 $EMBED_PID 2>/dev/null; then
    echo "❌ Error: Embedding service failed to start"
    echo "Check Scripts/logs/embedding_service.log for details"
    exit 1
fi

sleep 2
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠️ Warning: Embedding service started but not responding yet"
fi

# Start Knowledge Graph service
echo "Starting Knowledge Graph service..."
export GRAPH_PATH="graph_data/knowledge_graph_full.pkl"
$PYTHON_EXEC src/services/graph_query_service.py > Scripts/logs/graph_service.log 2>&1 &
GRAPH_PID=$!
echo "  PID: $GRAPH_PID"
sleep 3

# Verify graph service
if ! kill -0 $GRAPH_PID 2>/dev/null; then
    echo "❌ Error: Knowledge Graph service failed to start"
    echo "Check Scripts/logs/graph_service.log for details"
else
    if ! curl -s http://localhost:8002/health > /dev/null 2>&1; then
        echo "⚠️ Warning: Knowledge Graph service started but not responding yet"
    fi
fi

# Start File Watcher
echo "Starting File Watcher..."
$PYTHON_EXEC Scripts/vault_management/watching_scanner.py --non-interactive > Scripts/logs/watcher.log 2>&1 &
WATCHER_PID=$!
echo "  PID: $WATCHER_PID"
sleep 1

# Determine which Streamlit UI file to use
STREAMLIT_UI=""
if [ -f "src/ui/streamlit_ui_docker.py" ]; then
    STREAMLIT_UI="src/ui/streamlit_ui_docker.py"
elif [ -f "src/ui/streamlit_ui_enhanced.py" ]; then
    STREAMLIT_UI="src/ui/streamlit_ui_enhanced.py"
else
    echo "❌ Error: No Streamlit UI file found in src/ui/"
    kill $EMBED_PID 2>/dev/null
    exit 1
fi

# Start Streamlit UI
echo "Starting Streamlit UI ($STREAMLIT_UI)..."
$STREAMLIT_EXEC run "$STREAMLIT_UI" \
    --server.headless true \
    --browser.gatherUsageStats false \
    --server.port 8501 \
    --server.address 0.0.0.0 > "$STREAMLIT_LOG_FILE" 2>&1 &
STREAMLIT_PID=$!
echo "  PID: $STREAMLIT_PID"
sleep 3

# Check if Streamlit started successfully
if ! kill -0 $STREAMLIT_PID 2>/dev/null; then
    echo "❌ Error: Streamlit UI failed to start"
    echo "Check $STREAMLIT_LOG_FILE for details"
    kill $EMBED_PID 2>/dev/null
    kill $GRAPH_PID 2>/dev/null
    kill $WATCHER_PID 2>/dev/null
    exit 1
fi

echo ""
echo "✅ System ready!"
echo "📊 Embedding Service: http://localhost:8000"
echo "📊 Knowledge Graph:  http://localhost:8002"
echo "👁️  File Watcher:      Active"
echo "💬 Chat Interface:   http://localhost:8501"
echo ""
echo "To stop: Scripts/stop_obsidian_rag.sh"
echo ""
