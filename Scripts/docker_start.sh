#!/bin/bash
# Start Docker Services for Obsidian RAG

echo "🐳 Starting Obsidian RAG with Docker"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "⚠️ Docker is not running!"
    echo ""
    echo "Please start Docker Desktop first:"
    echo "  1. Open Docker Desktop application"
    echo "  2. Wait for it to fully start (whale icon in menu bar)"
    echo "  3. Run this script again"
    echo ""
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Navigate to project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

# Stop any existing containers
echo "🛑 Stopping any existing containers..."
docker-compose down 2>/dev/null

# Start services
echo ""
echo "🚀 Starting Docker services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Check service status
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "🔍 Health Checks:"
echo "-------------------"

# Check embedding service
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    STATS=$(curl -s http://localhost:8000/stats 2>/dev/null)
    CHUNKS=$(echo $STATS | grep -o '"total_documents":[0-9]*' | cut -d':' -f2 || echo "unknown")
    echo "✅ Embedding Service (port 8000) - $CHUNKS chunks"
else
    echo "⏳ Embedding Service (port 8000) - Starting..."
fi

# Check Claude Graph service
if curl -s http://localhost:8002/health > /dev/null 2>&1; then
    GRAPH_STATS=$(curl -s http://localhost:8002/health 2>/dev/null)
    if echo "$GRAPH_STATS" | grep -q '"graph_loaded":true'; then
        echo "✅ Claude Graph Service (port 8002) - Graph loaded"
    else
        echo "⏳ Claude Graph Service (port 8002) - Starting (graph not loaded yet)"
    fi
else
    echo "⏳ Claude Graph Service (port 8002) - Starting..."
fi

# Check Streamlit UI
if curl -s http://localhost:8501/_stcore/health > /dev/null 2>&1; then
    echo "✅ Streamlit UI (port 8501)"
else
    echo "⏳ Streamlit UI (port 8501) - Starting..."
fi

# Check Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama (port 11434)"
else
    echo "⚠️ Ollama (port 11434) - Not detected (run separately if needed)"
fi

echo ""
echo "✅ Docker services started!"
echo ""
echo "📝 Access points:"
echo "  • Streamlit UI: http://localhost:8501"
echo "  • Embedding API: http://localhost:8000"
echo "  • Claude Graph API: http://localhost:8002"
echo ""
echo "📋 Useful commands:"
echo "  • View logs:    docker-compose logs -f [service-name]"
echo "  • Stop all:     docker-compose down"
echo "  • Restart:      docker-compose restart"
echo "  • Status:       docker-compose ps"
echo ""
echo "💡 Note: Services may take 30-60 seconds to fully initialize."
echo "   Refresh the UI if services show as offline initially."
