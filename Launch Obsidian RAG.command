#!/bin/bash

# Get the directory where this script is located
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$PROJECT_ROOT"

echo "💎 Launching Obsidian RAG..."

# Check if Streamlit is already running
if curl -s --head --fail http://localhost:8501 > /dev/null; then
    echo "✅ Obsidian RAG is already running. Skipping startup."
else
    echo "🚀 Services are offline. Starting Obsidian RAG..."
    # Run the existing start script in the background
    ./Scripts/start_obsidian_rag.sh
fi

echo "⏳ Waiting for UI to be ready..."

# 2. Wait for Streamlit to respond (port 8501)
MAX_WAIT=20
WAIT_COUNT=0
while ! curl -s http://localhost:8501 > /dev/null; do
    sleep 1
    ((WAIT_COUNT++))
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo "⚠️  Streamlit is taking a while to start. Opening browser anyway..."
        break
    fi
done

# 3. Open the browser
open http://localhost:8501

echo "🚀 Search interface opened!"
echo "Keep this window open while using the search, or close it if you want to run in the background."

# Prevent terminal from closing immediately if there's an error
sleep 2
