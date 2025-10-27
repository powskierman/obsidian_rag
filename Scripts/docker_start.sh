#!/bin/bash
# Start Obsidian RAG with Docker Compose

set -e

echo "🐳 Starting Obsidian RAG with Docker"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Check if Ollama is accessible
echo "🔍 Checking Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama is running"
else
    echo "⚠️ Ollama not detected on localhost:11434"
    echo "   Make sure Ollama is running: 'ollama serve'"
fi

echo ""
echo "🏗️ Building Docker images..."
docker-compose build

echo ""
echo "🚀 Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service health
echo ""
echo "📊 Service Status:"
echo "-------------------"

# Check embedding service
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Embedding Service: http://localhost:8000"
else
    echo "⚠️ Embedding Service: Starting..."
fi

# Check LightRAG service
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ LightRAG Service:  http://localhost:8001"
else
    echo "⚠️ LightRAG Service:  Starting..."
fi

# Check Streamlit UI
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo "✅ Streamlit UI:      http://localhost:8501"
else
    echo "⚠️ Streamlit UI:      Starting..."
fi

echo ""
echo "=========================================="
echo "✅ Docker services started!"
echo ""
echo "🌐 Access the UI:     http://localhost:8501"
echo "📚 View logs:         docker-compose logs -f"
echo "🛑 Stop services:     docker-compose down"
echo ""
echo "📝 To index your vault with LightRAG:"
echo "   curl -X POST http://localhost:8001/index-vault"
echo ""



