#!/bin/bash

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEBAPP_DIR="$PROJECT_ROOT/webapp"
LOG_FILE="$SCRIPT_DIR/logs/webapp.log"

# Navigate to webapp directory
cd "$WEBAPP_DIR" || exit 1

# Ensure logs directory exists
mkdir -p "$SCRIPT_DIR/logs"

echo "🚀 Starting Webapp..." | tee -a "$LOG_FILE"
echo "📅 Date: $(date)" | tee -a "$LOG_FILE"

# Load NVM if present to ensure npm is available
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    . "$NVM_DIR/nvm.sh"
fi

# check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..." | tee -a "$LOG_FILE"
    if [ -f "package-lock.json" ]; then
        npm ci >> "$LOG_FILE" 2>&1
    else
        npm install >> "$LOG_FILE" 2>&1
    fi
fi

# Build
echo "🏗️ Building Webapp..." | tee -a "$LOG_FILE"
npm run build >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "❌ Build failed. Check $LOG_FILE for details." | tee -a "$LOG_FILE"
    exit 1
fi

# Start
echo "🌐 Starting Webapp server..." | tee -a "$LOG_FILE"
npm start >> "$LOG_FILE" 2>&1 &
WEBAPP_PID=$!
echo "✅ Webapp started with PID $WEBAPP_PID" | tee -a "$LOG_FILE"
