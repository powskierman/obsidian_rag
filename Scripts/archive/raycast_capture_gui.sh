#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Capture Sticky
# @raycast.mode silent
# @raycast.packageName Obsidian RAG
# @raycast.icon 📝

# Configuration
VAULT_INBOX="/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/00_Inbox"
mkdir -p "$VAULT_INBOX"
GUI_BIN="$(dirname "$0")/capture_gui"

# Run Swift GUI and capture output
CONTENT=$("$GUI_BIN")

if [ ! -z "$CONTENT" ]; then
    TIMESTAMP=$(date +%s)
    FILENAME="capture_${TIMESTAMP}.md"
    FILEPATH="$VAULT_INBOX/$FILENAME"
    
    echo "$CONTENT" > "$FILEPATH"
    echo "Saved to Inbox"
else
    echo "Cancelled"
fi
