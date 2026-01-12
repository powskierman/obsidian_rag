#!/bin/bash
# start_watcher.sh
# Start the Obsidian vault watcher for incremental indexing

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
WATCHER_LOG="$LOG_DIR/watcher.log"
WATCHER_ERR="$LOG_DIR/watcher.error.log"

WATCHER_CHOICE="${WATCHER_CHOICE:-3}"
EMBEDDING_URL="${EMBEDDING_URL:-http://localhost:8000}"

if pgrep -f "scripts/vault_management/watching_scanner.py" > /dev/null 2>&1; then
    echo "Watcher already running."
    exit 0
fi

cd "$PROJECT_ROOT" || exit 1

# Wait for embedding service (port 8000)
MAX_RETRIES=30
RETRY_COUNT=0
until curl -s "$EMBEDDING_URL/health" > /dev/null 2>&1 || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Embedding service not ready after $((MAX_RETRIES*2)) seconds." | tee -a "$WATCHER_LOG"
    exit 1
fi

echo "Embedding service ready. Starting watcher (choice: $WATCHER_CHOICE)" | tee -a "$WATCHER_LOG"
python scripts/vault_management/watching_scanner.py --non-interactive --choice "$WATCHER_CHOICE" >> "$WATCHER_LOG" 2>> "$WATCHER_ERR"
