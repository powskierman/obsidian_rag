#!/bin/bash
# Mac Mini Setup Script for Obsidian RAG
#
# This script sets up the LightRAG indexing environment on your Mac Mini.
# Run this AFTER iCloud has synced the project files to the Mac Mini.

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║      Mac Mini Setup for Obsidian RAG - LightRAG          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "This script will:"
echo "  1. Check prerequisites (Docker, Ollama)"
echo "  2. Pull Ollama embedding model"
echo "  3. Build Docker images"
echo "  4. Start LightRAG service"
echo "  5. Load your existing database"
echo "  6. Verify everything is working"
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Setup cancelled"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  CHECKING PREREQUISITES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Docker
echo "🐳 Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    echo ""
    echo "Install Docker Desktop from: https://www.docker.com/products/docker-desktop/"
    echo "Then run this script again."
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "⚠️  Docker is installed but not running"
    echo ""
    echo "Please start Docker Desktop, then run this script again."
    exit 1
fi

echo "✅ Docker is installed and running"
docker --version
echo ""

# Check Ollama
echo "🦙 Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama not installed"
    echo ""
    echo "Installing Ollama via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install ollama
    else
        echo "❌ Homebrew not found"
        echo ""
        echo "Install Ollama manually from: https://ollama.ai/download"
        echo "Or install Homebrew first: https://brew.sh/"
        exit 1
    fi
fi

echo "✅ Ollama is installed"
ollama --version
echo ""

# Navigate to project directory
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  NAVIGATING TO PROJECT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PROJECT_DIR="/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Project directory not found: $PROJECT_DIR"
    echo ""
    echo "Possible reasons:"
    echo "  1. iCloud sync not complete yet (check iCloud status in System Settings)"
    echo "  2. Different username on Mac Mini"
    echo "  3. iCloud Drive not enabled"
    echo ""
    echo "Wait for iCloud sync to complete, then run this script again."
    exit 1
fi

cd "$PROJECT_DIR"
echo "✅ Found project directory"
echo "📂 Location: $PROJECT_DIR"
echo ""

# Check key files
echo "🔍 Checking for key files..."
MISSING_FILES=()

if [ ! -f "Dockerfile.lightrag" ]; then
    MISSING_FILES+=("Dockerfile.lightrag")
fi

if [ ! -f "src/integrations/lightrag_service.py" ]; then
    MISSING_FILES+=("src/integrations/lightrag_service.py")
fi

if [ ! -f "config/docker/docker-compose.yml" ]; then
    MISSING_FILES+=("config/docker/docker-compose.yml")
fi

if [ ! -d "lightrag_db" ]; then
    MISSING_FILES+=("lightrag_db/")
fi

if [ ${#MISSING_FILES[@]} -ne 0 ]; then
    echo "⚠️  Some files are missing (iCloud still syncing?):"
    for file in "${MISSING_FILES[@]}"; do
        echo "   ❌ $file"
    done
    echo ""
    echo "Wait for iCloud sync to complete, then run this script again."
    exit 1
fi

echo "✅ All required files present"
echo ""

# Check environment variables
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  CHECKING ENVIRONMENT VARIABLES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Source .env if exists
if [ -f ".env" ]; then
    echo "📝 Found .env file"
    export $(grep -v '^#' .env | xargs)
else
    echo "⚠️  No .env file found"
fi

# Check for OpenRouter API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "⚠️  OPENROUTER_API_KEY not set"
    echo ""
    echo "You'll need to set this before indexing:"
    echo "  export OPENROUTER_API_KEY='your-key-here'"
    echo ""
    echo "Get your key at: https://openrouter.ai/keys"
    echo ""
    echo "Continuing setup anyway..."
else
    echo "✅ OPENROUTER_API_KEY is set"
fi
echo ""

# Start Ollama
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  STARTING OLLAMA"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🦙 Starting Ollama service..."
# Kill existing ollama processes
pkill ollama 2>/dev/null || true
sleep 2

# Start Ollama in background
ollama serve &
OLLAMA_PID=$!
echo "✅ Ollama started (PID: $OLLAMA_PID)"

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to initialize..."
for i in {1..10}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama is ready"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Ollama failed to start"
        exit 1
    fi
    sleep 2
done
echo ""

# Pull embedding model
echo "📥 Pulling embedding model (nomic-embed-text)..."
echo "⏳ This may take a few minutes on first run..."
ollama pull nomic-embed-text
echo "✅ Embedding model ready"
echo ""

# Build Docker images
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  BUILDING DOCKER IMAGES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd config/docker

echo "🏗️  Building LightRAG service image..."
echo "⏳ This may take 5-10 minutes (downloading packages, cloning LightRAG)..."
echo ""

docker compose build lightrag-service

echo ""
echo "✅ Docker image built successfully"
echo ""

# Start services
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6️⃣  STARTING SERVICES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🚀 Starting LightRAG service..."
docker compose up -d lightrag-service

echo "⏳ Waiting for service to initialize (15 seconds)..."
sleep 15

echo "✅ Service started"
echo ""

# Check service status
echo "🔍 Checking service status..."
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

# Copy database to container
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7️⃣  LOADING DATABASE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd ../..

echo "📂 Database location: $PROJECT_DIR/lightrag_db"
DB_SIZE=$(du -sh lightrag_db | cut -f1)
echo "📊 Database size: $DB_SIZE"
echo ""

echo "📤 Copying database to container..."
docker cp lightrag_db/. obsidian-lightrag:/app/lightrag_db/

echo "🔄 Restarting container to load database..."
docker restart obsidian-lightrag

echo "⏳ Waiting for restart (10 seconds)..."
sleep 10

echo "✅ Database loaded"
echo ""

# Verify setup
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "8️⃣  VERIFYING SETUP"
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

# Extract file count from stats
FILE_COUNT=$(echo "$STATS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_files', 0))")

if [ "$FILE_COUNT" -gt 0 ]; then
    echo "✅ Database loaded successfully ($FILE_COUNT files in database)"
else
    echo "⚠️  Database appears empty (may still be initializing)"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅  SETUP COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Summary:"
echo "  ✅ Docker: Running"
echo "  ✅ Ollama: Running (PID: $OLLAMA_PID)"
echo "  ✅ LightRAG: Running on port 8001"
echo "  ✅ Database: Loaded ($DB_SIZE)"
echo ""
echo "🔗 Service endpoints:"
echo "  Health:   http://localhost:8001/health"
echo "  Stats:    http://localhost:8001/stats"
echo "  Query:    http://localhost:8001/query"
echo ""
echo "📝 Next steps:"
echo ""
echo "  1. Set API key (if not already set):"
echo "     export OPENROUTER_API_KEY='your-key-here'"
echo ""
echo "  2. Run incremental indexing:"
echo "     cd '$PROJECT_DIR'"
echo "     ./Scripts/index_lightrag_with_kimi.sh"
echo ""
echo "  3. Monitor indexing progress:"
echo "     docker logs -f obsidian-lightrag"
echo ""
echo "💡 Tip: Keep this terminal open to keep Ollama running,"
echo "    or start it manually with: ollama serve &"
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              Mac Mini is ready for indexing!             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
