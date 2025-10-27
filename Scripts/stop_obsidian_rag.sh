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
