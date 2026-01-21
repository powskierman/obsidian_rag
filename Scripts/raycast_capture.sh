#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Capture to Second Brain
# @raycast.mode silent
# @raycast.packageName Obsidian RAG
# @raycast.icon 🧠

# Optional parameters:
# @raycast.argument1 { "type": "text", "placeholder": "Thought...", "optional": true }

# Configuration
VAULT_INBOX="/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/00_Inbox"
mkdir -p "$VAULT_INBOX"

CONTENT="$1"

# If no argument provided, open input dialog
if [ -z "$CONTENT" ]; then
    TEXT=$(osascript -e 'Tell application "System Events" to display dialog "Enter your note:" default answer "" with title "Second Brain Capture" with icon note buttons {"Cancel", "Save"} default button "Save"')
    
    BUTTON=$(echo "$TEXT" | awk -F "button returned:" '{print $2}' | awk -F ", " '{print $1}')
    CONTENT=$(echo "$TEXT" | awk -F "text returned:" '{print $2}')
    
    if [ "$BUTTON" != "Save" ] || [ -z "$CONTENT" ]; then
        echo "Cancelled"
        exit 0
    fi
fi

# Save content
TIMESTAMP=$(date +%s)
FILENAME="capture_${TIMESTAMP}.md"
FILEPATH="$VAULT_INBOX/$FILENAME"

echo "$CONTENT" > "$FILEPATH"
echo "Captured to Inbox"