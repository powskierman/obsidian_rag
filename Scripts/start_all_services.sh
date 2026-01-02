#!/bin/bash

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Starting All Services..."

# Start Backend and Streamlit
echo "💎 Starting Backend & Streamlit..."
"$SCRIPT_DIR/start_obsidian_rag.sh" &
BACKEND_PID=$!

# Start Webapp
echo "🌐 Starting Webapp..."
"$SCRIPT_DIR/start_webapp.sh" &
WEBAPP_PID=$!

echo "✅ All services initiated."
echo "Backend/Streamlit PID: $BACKEND_PID"
echo "Webapp PID: $WEBAPP_PID"

# Wait for processes
wait $BACKEND_PID $WEBAPP_PID
