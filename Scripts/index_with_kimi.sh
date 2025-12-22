#!/bin/bash
# Index Obsidian vault using Kimi K2 via OpenRouter

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║             Index with Kimi K2 (via OpenRouter)            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Source .env file if it exists
if [ -f ".env" ]; then
    echo "📝 Sourcing .env file..."
    export $(grep -v '^#' .env | xargs)
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

# Check if lightrag service is running
if ! docker ps | grep -q obsidian-lightrag; then
    echo "⚠️  LightRAG service not running. Starting services..."
    docker compose up -d lightrag-service
    sleep 5
fi

# Get vault path
if [ ! -z "$OBSIDIAN_VAULT_PATH" ]; then
    VAULT_PATH="$OBSIDIAN_VAULT_PATH"
else
    # Fallback to parsing docker-compose.yml
    VAULT_PATH=$(grep "/app/vault" docker-compose.yml | head -n 1 | sed 's/^[[:space:]]*-[[:space:]]*//' | cut -d: -f1 | tr -d '"' | sed 's/\${OBSIDIAN_VAULT_PATH}//')
fi

if [ -z "$VAULT_PATH" ] || [ ! -d "$VAULT_PATH" ]; then
    if [ -d "./vault" ]; then
        VAULT_PATH="./vault"
    else
        echo "❌ Error: Could not detect vault path"
        exit 1
    fi
fi

echo "📂 Vault path: $VAULT_PATH"
echo "💰 Estimated cost: ~$0.10 per 1M tokens"
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

echo ""
echo "🚀 Starting indexing with Kimi..."
echo ""

# Call the LightRAG service indexing endpoint
# Using /app/vault because that's what's mounted inside the container
curl -X POST http://localhost:8001/index-vault \
     -H "Content-Type: application/json" \
     -d '{"vault_path": "/app/vault"}'

echo ""
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ Indexing Triggered!                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Monitor progress with: docker logs -f obsidian-lightrag"
echo ""
