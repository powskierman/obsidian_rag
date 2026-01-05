#!/bin/bash
# start_webapp.sh
# Optimized startup for the Next.js Webapp

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEBAPP_DIR="$PROJECT_ROOT/webapp"
LOG_FILE="$SCRIPT_DIR/logs/webapp.log"

# Navigate to webapp directory
cd "$WEBAPP_DIR" || exit 1

# Ensure logs directory exists
mkdir -p "$SCRIPT_DIR/logs"

echo "🚀 Starting Webapp (Dev Mode)..." | tee -a "$LOG_FILE"
echo "📅 Date: $(date)" | tee -a "$LOG_FILE"

# Load NVM if present to ensure npm is available
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    . "$NVM_DIR/nvm.sh"
fi

# 1. Install dependencies if node_modules missing
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..." | tee -a "$LOG_FILE"
    npm install >> "$LOG_FILE" 2>&1
fi

# 2. Clear any existing Next process on port 3000
PORT_PID=$(lsof -t -i:3000)
if [ ! -z "$PORT_PID" ]; then
    echo "🧹 Killing existing process on port 3000 (PID: $PORT_PID)..." | tee -a "$LOG_FILE"
    kill -9 "$PORT_PID" >> "$LOG_FILE" 2>&1
fi

# 3. Start in Dev Mode (fastest startup)
echo "🌐 Launching Next.js on http://localhost:3000..." | tee -a "$LOG_FILE"
# Use -p 3000 explicitly and binding to 0.0.0.0 for accessibility
npm run dev -- -p 3000 >> "$LOG_FILE" 2>&1 &
WEBAPP_PID=$!

echo "✅ Webapp started with PID $WEBAPP_PID" | tee -a "$LOG_FILE"
