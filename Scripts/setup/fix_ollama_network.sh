#!/bin/bash
# Fix Ollama binding to allow Docker access
# This is required for Obsidian RAG (running in Docker) to access the host's Ollama.

echo "🔧 Configuring Ollama to listen on all interfaces (0.0.0.0)..."

# 1. Set global env for the .app (persistent across launches)
launchctl setenv OLLAMA_HOST "0.0.0.0"

# 2. Stop running instance
echo "🛑 Stopping running Ollama..."
pkill -TERM Ollama
pkill -TERM ollama
sleep 2

# 3. Start it back up (CLI mode or App mode)
# If the App exists, open it (it will pick up the launchctl env)
if [ -d "/Applications/Ollama.app" ]; then
    echo "🚀 Restarting Ollama.app..."
    open -a Ollama
else
    # Fallback to CLI
    echo "🚀 Starting 'ollama serve' in background..."
    export OLLAMA_HOST=0.0.0.0
    nohup ollama serve > Scripts/logs/ollama.log 2>&1 &
fi

echo "⏳ Waiting for Ollama (10s)..."
sleep 10

# 4. Verify
if netstat -an | grep 11434 | grep "\*\.\*"; then
    echo "✅ Success: Ollama is listening on all interfaces!"
else
    echo "⚠️ Warning: Ollama might still be bound to localhost only."
    echo "   Please quit Ollama manually and restart it."
fi
