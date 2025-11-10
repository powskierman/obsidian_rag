#!/bin/bash
# Script to fix ANTHROPIC_API_KEY in Docker containers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔧 Fixing ANTHROPIC_API_KEY for Docker services..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo ""
    echo "Creating .env file template..."
    echo "ANTHROPIC_API_KEY=your-api-key-here" > .env
    echo ""
    echo "✅ Created .env file. Please edit it and add your real API key:"
    echo "   Get your key from: https://console.anthropic.com/"
    echo ""
    exit 1
fi

# Check if API key is set in .env
if grep -q "ANTHROPIC_API_KEY=your-api-key-here" .env || ! grep -q "^ANTHROPIC_API_KEY=" .env; then
    echo "⚠️  .env file has placeholder or missing API key!"
    echo ""
    echo "Please edit .env and set your real ANTHROPIC_API_KEY"
    echo "Get your key from: https://console.anthropic.com/"
    echo ""
    echo "Current .env content (first line):"
    head -1 .env | sed 's/\(ANTHROPIC_API_KEY=\).*/\1***HIDDEN***/'
    echo ""
    read -p "Press Enter after you've updated .env, or Ctrl+C to cancel..."
fi

# Export from .env and restart services
echo ""
echo "🔄 Restarting graph-service with updated API key..."
export $(grep -v '^#' .env | xargs)
docker-compose stop graph-service
docker-compose up -d graph-service

echo ""
echo "⏳ Waiting for service to start..."
sleep 5

# Verify
echo ""
echo "🔍 Verifying API key in container..."
CONTAINER_KEY=$(docker-compose exec -T graph-service printenv ANTHROPIC_API_KEY 2>/dev/null | tr -d '\r' || echo "")

if [ -z "$CONTAINER_KEY" ] || [ "$CONTAINER_KEY" = "your-api-key-here" ]; then
    echo "❌ API key still not set correctly!"
    echo ""
    echo "Try running:"
    echo "  export ANTHROPIC_API_KEY=your-actual-key"
    echo "  docker-compose up -d graph-service"
    exit 1
else
    echo "✅ API key is set (showing first 10 chars): ${CONTAINER_KEY:0:10}..."
    echo ""
    echo "🧪 Testing graph service health..."
    if curl -s http://localhost:8002/health | grep -q "graph_loaded"; then
        echo "✅ Graph service is healthy!"
    else
        echo "⚠️  Service responded but graph may not be loaded"
    fi
fi

echo ""
echo "✅ Done! Try querying the graph in the UI now."


