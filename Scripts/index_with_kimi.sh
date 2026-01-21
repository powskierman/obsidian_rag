#!/bin/bash
# Index Obsidian vault using GPT-4o-mini via OpenRouter (Graph Service)

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║             Index with GPT-4o-mini (via OpenRouter)        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Source .env file if it exists
if [ -f ".env" ]; then
    echo "📝 Sourcing .env file..."
    set -a
    source .env
    set +a
fi

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ Error: OPENROUTER_API_KEY not set"
    echo ""
    echo "Get your API key at: https://openrouter.ai/keys"
    echo "Then run:"
    echo "  export OPENROUTER_API_KEY='your-key-here'"
    echo ""
    exit 1
fi

echo "✅ OpenRouter API key found"
echo ""

# Check if graph service is running
if ! docker ps | grep -q obsidian-graph-service; then
    echo "⚠️  Graph service not running. Starting services..."
    docker compose up -d graph-service
    echo "Waiting for service to initialize..."
    sleep 5
fi

echo "📂 Copying build script to container..."
# Copy the build script to the container to ensure it's available
docker cp src/services/build_graph.py obsidian-graph-service:/app/build_graph.py

echo "🚀 Starting indexing process inside container..."
echo "Indices will be saved to: /app/graph_data/knowledge_graph_full.pkl"
echo ""
echo "This process may take a while depending on vault size..."
echo ""

# Run the build script with any arguments passed to this shell script
docker exec -it obsidian-graph-service python /app/build_graph.py "$@"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ Indexing Complete!                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
