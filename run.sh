#!/bin/bash
# Obsidian RAG - Simple startup script
# Runs embedding service and Streamlit UI locally (no Docker)

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║          🧠 Obsidian RAG - Starting Services                 ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Load environment from .env.local
if [ -f .env.local ]; then
    echo -e "${GREEN}✅ Loading environment from .env.local${NC}"
    export $(cat .env.local | grep -v '#' | xargs)
else
    echo -e "${YELLOW}⚠️  .env.local not found. Using system environment.${NC}"
    echo "    Run: ./setup.sh"
fi

# Check if Ollama is running
echo ""
echo "Checking Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama is running${NC}"
else
    echo -e "${RED}❌ Ollama is not running${NC}"
    echo "    Start Ollama in another terminal:"
    echo "    ${BLUE}ollama serve${NC}"
    exit 1
fi

# Start embedding service in background
echo ""
echo "Starting Embedding Service..."
python3 embedding_service.py > /tmp/embedding_service.log 2>&1 &
EMBEDDING_PID=$!
echo -e "${GREEN}✅ Embedding Service started (PID: $EMBEDDING_PID)${NC}"
echo "    Logs: /tmp/embedding_service.log"

# Wait for embedding service to be ready
echo ""
echo "Waiting for services to be ready..."
sleep 3

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Embedding Service is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Embedding Service is starting...${NC}"
    sleep 2
fi

# Start Streamlit UI
echo ""
echo "Starting Streamlit UI..."
echo "   Access at: ${BLUE}http://localhost:8501${NC}"
echo ""
echo -e "${GREEN}All services running!${NC}"
echo ""
echo "Press Ctrl+C to stop."
echo ""

# Start Streamlit (this runs in foreground)
streamlit run streamlit_ui_enhanced.py --server.port 8501

# Cleanup on exit
trap "kill $EMBEDDING_PID 2>/dev/null; exit" EXIT INT TERM
