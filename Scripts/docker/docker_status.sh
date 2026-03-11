#!/bin/bash
# Check status of Obsidian RAG Docker services

echo "📊 Obsidian RAG Docker Status"
echo "========================================================================"
echo ""

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running"
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Check containers
echo "🐳 Containers:"
docker-compose ps

echo ""
echo "📡 Service Health:"
echo "-------------------"

# Embedding service
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    STATS=$(curl -s http://localhost:8000/stats)
    CHUNKS=$(echo $STATS | grep -o '"total_documents":[0-9]*' | cut -d':' -f2)
    echo "✅ Embedding Service (port 8000)"
    echo "   Chunks: ${CHUNKS:-unknown}"
else
    echo "❌ Embedding Service (port 8000) - Not responding"
fi

# Internal LightRAG service
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    GRAPH_STATS=$(curl -s http://localhost:8001/stats)
    DB_EXISTS=$(echo $GRAPH_STATS | grep -o '"database_exists":[a-z]*' | cut -d':' -f2)
    echo "✅ Internal LightRAG Service (port 8001)"
    echo "   Database: ${DB_EXISTS:-unknown}"
else
    echo "❌ Internal LightRAG Service (port 8001) - Not responding"
fi

# Internal graph service
if curl -s http://localhost:8002/health > /dev/null 2>&1; then
    GRAPH_HEALTH=$(curl -s http://localhost:8002/health)
    GRAPH_LOADED=$(echo $GRAPH_HEALTH | grep -o '"graph_loaded":[a-z]*' | cut -d':' -f2)
    echo "✅ Internal Graph Service (port 8002)"
    echo "   Graph loaded: ${GRAPH_LOADED:-unknown}"
else
    echo "❌ Internal Graph Service (port 8002) - Not responding"
fi

# Streamlit UI
if curl -s http://localhost:8501/_stcore/health > /dev/null 2>&1; then
    echo "✅ Streamlit UI (port 8501)"
    echo "   URL: http://localhost:8501"
else
    echo "❌ Streamlit UI (port 8501) - Not responding"
fi

# Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama (port 11434)"
    ollama list 2>/dev/null | grep -E "qwen|llama|deepseek" | head -3
else
    echo "⚠️ Ollama (port 11434) - Not detected"
fi

echo ""
echo "========================================================================"
echo ""
echo "Note: Graph and LightRAG services are internal retrieval dependencies, not public user modes."
echo ""
echo "Quick Actions:"
echo "  View logs:   docker-compose logs -f [service-name]"
echo "  Restart:     docker-compose restart [service-name]"
echo "  Stop all:    docker-compose down"
echo "  Rebuild:     docker-compose up -d --build"
echo ""


