#!/bin/bash

# Start the Inbox Watcher in the background
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROCESS_SCRIPT="$SCRIPT_DIR/process_inbox.py"
LOG_FILE="$SCRIPT_DIR/logs/inbox_watcher.log"

mkdir -p "$SCRIPT_DIR/logs"

# Check if already running
if pgrep -f "process_inbox.py" > /dev/null; then
    echo "⚠️  Inbox Watcher is already running."
    exit 1
fi

echo "🚀 Starting Inbox Watcher..."
echo "📂 Watching: 00_Inbox"

nohup python3 "$PROCESS_SCRIPT" > "$LOG_FILE" 2>&1 &
PID=$!

echo "✅ Watcher started with PID $PID"
echo "📝 Logs: $LOG_FILE"
