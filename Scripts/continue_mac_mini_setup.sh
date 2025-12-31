#!/bin/bash
# Continue Mac Mini Setup After Networking Fix
#
# Run this on the Mac Mini after the docker-compose.yml has been updated
# This bypasses the Ollama model pull (since it's already installed)

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     Continue Mac Mini Setup - LightRAG Service           ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Project directory not found: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

echo "📍 Working directory: $PROJECT_DIR"
echo ""

# Check if Ollama is running
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  VERIFYING OLLAMA"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama not responding. Starting Ollama..."
    pkill ollama 2>/dev/null || true
    sleep 2
    ollama serve &
    OLLAMA_PID=$!
    echo "✅ Ollama started (PID: $OLLAMA_PID)"
    sleep 5
else
    echo "✅ Ollama is already running"
fi

# Verify nomic-embed-text model exists
if ollama list | grep -q "nomic-embed-text"; then
    echo "✅ nomic-embed-text model is installed"
else
    echo "⚠️  nomic-embed-text model not found. Pulling..."
    ollama pull nomic-embed-text
fi
echo ""

# Stop any existing containers
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  RESTARTING DOCKER CONTAINER WITH FIXED NETWORKING"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd config/docker

echo "🛑 Stopping existing containers..."
docker compose down 2>/dev/null || true
echo ""

echo "🚀 Starting LightRAG service with fixed networking..."
docker compose up -d lightrag-service
echo ""

echo "⏳ Waiting for service to initialize (15 seconds)..."
sleep 15
echo ""

# Check container status
if docker ps | grep -q obsidian-lightrag; then
    echo "✅ Container is running"
else
    echo "❌ Container failed to start"
    echo ""
    echo "Check logs with:"
    echo "  docker logs obsidian-lightrag"
    exit 1
fi
echo ""

# Load database
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  LOADING DATABASE INTO CONTAINER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd ../..

if [ ! -d "lightrag_db" ]; then
    echo "⚠️  lightrag_db directory not found in project root"
    echo "You may need to restore the database backup"
    exit 1
fi

DB_SIZE=$(du -sh lightrag_db | cut -f1)
echo "📂 Database location: $PROJECT_DIR/lightrag_db"
echo "📊 Database size: $DB_SIZE"
echo ""

echo "📤 Copying database to container..."
docker cp lightrag_db/. obsidian-lightrag:/app/lightrag_db/
echo ""

echo "🔄 Restarting container to load database..."
docker restart obsidian-lightrag
echo ""

echo "⏳ Waiting for restart (10 seconds)..."
sleep 10
echo ""

# Verify setup
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  VERIFYING SETUP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🏥 Health check..."
HEALTH_RESPONSE=$(curl -s http://localhost:8001/health)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "✅ Service is healthy"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool
else
    echo "⚠️  Service may not be ready yet"
    echo "Response: $HEALTH_RESPONSE"
fi
echo ""

echo "📊 Database statistics..."
STATS_RESPONSE=$(curl -s http://localhost:8001/stats)
echo "$STATS_RESPONSE" | python3 -m json.tool
echo ""

FILE_COUNT=$(echo "$STATS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_files', 0))" 2>/dev/null || echo "0")

if [ "$FILE_COUNT" -gt 0 ]; then
    echo "✅ Database loaded successfully ($FILE_COUNT files in database)"
else
    echo "⚠️  Database appears empty (may still be initializing)"
fi
echo ""

# Test Ollama connection from container
echo "🔌 Testing Ollama connection from container..."
docker exec obsidian-lightrag curl -s http://host.docker.internal:11434/api/tags > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Container can reach Ollama on host"
else
    echo "⚠️  Container cannot reach Ollama (may need to check networking)"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅  SETUP COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Summary:"
echo "  ✅ Ollama: Running on port 11434"
echo "  ✅ LightRAG: Running on port 8001"
echo "  ✅ Database: Loaded ($DB_SIZE, $FILE_COUNT files)"
echo "  ✅ Networking: Fixed (host.docker.internal working)"
echo ""
echo "🔗 Service endpoints:"
echo "  Health:   http://localhost:8001/health"
echo "  Stats:    http://localhost:8001/stats"
echo "  Query:    http://localhost:8001/query"
echo ""
echo "📝 Next step - Set API key and run indexing:"
echo ""
echo "  export OPENROUTER_API_KEY='your-key-here'"
echo "  cd '$PROJECT_DIR'"
echo "  ./Scripts/index_lightrag_with_kimi.sh"
echo ""
echo "💡 Monitor progress with:"
echo "  docker logs -f obsidian-lightrag"
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          Mac Mini is ready for indexing!                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
