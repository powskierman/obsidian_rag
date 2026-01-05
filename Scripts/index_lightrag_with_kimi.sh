#!/bin/bash
# Index Obsidian vault into LightRAG using GPT-4o-mini via OpenRouter
#
# This script indexes your vault into the LightRAG entity-centric knowledge graph.
# NOTE: Keep index_with_kimi.sh separate - that's for NetworkX graph indexing!

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║    Index LightRAG with GPT-4o-mini (via OpenRouter)        ║"
echo "║    Entity-centric knowledge graph (Port 8001)              ║"
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
echo "🤖 LLM Model: openai/gpt-4o-mini"
echo "🔤 Embed Model: nomic-embed-text (via Ollama)"
echo ""

# Check if lightrag service is running
if ! docker ps | grep -q obsidian-lightrag; then
    echo "⚠️  LightRAG service not running. Starting service..."
    cd config/docker && docker compose up -d lightrag-service && cd ../..
    echo "Waiting for service to initialize..."
    sleep 10
fi

# Check service health
echo "🔍 Checking LightRAG service health..."
if ! curl -s http://localhost:8001/health > /dev/null; then
    echo "❌ Error: LightRAG service not responding"
    echo "Check with: docker logs obsidian-lightrag"
    exit 1
fi

echo "✅ LightRAG service is healthy"
echo ""

# Get vault path from environment or use default
VAULT_PATH=${OBSIDIAN_VAULT_PATH:-"./vault"}

if [ ! -d "$VAULT_PATH" ]; then
    echo "❌ Error: Vault path not found: $VAULT_PATH"
    echo ""
    echo "Set your vault path:"
    echo "  export OBSIDIAN_VAULT_PATH='/path/to/your/vault'"
    echo "  or create a symlink: ln -s /path/to/your/vault ./vault"
    exit 1
fi

echo "📂 Vault path: $VAULT_PATH"
echo ""

# Count markdown files
NOTE_COUNT=$(find "$VAULT_PATH" -name "*.md" | wc -l | xargs)
echo "📚 Found $NOTE_COUNT markdown files"
echo ""

# Cost estimates for GPT-4o-mini
echo "💰 Estimated cost with GPT-4o-mini:"
echo "   ~\$0.25-0.50 for $NOTE_COUNT notes (highly optimized!)"
echo "⏱️  Estimated time: 20-40 minutes"
echo ""

read -p "Continue with indexing? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

echo ""
echo "🚀 Starting LightRAG indexing with GPT-4o-mini..."
echo "📊 This will create an entity-centric knowledge graph"
echo "🔗 Nodes: ~20,000+ entities extracted from your notes"
echo "🔗 Edges: ~30,000+ relationships between entities"
echo ""
echo "Progress: Watch container logs with: docker logs -f obsidian-lightrag"
echo ""

# Run indexing via LightRAG service endpoint
python3 - <<'EOF'
import requests
import time
from pathlib import Path

vault_path = "${VAULT_PATH}"
start_time = time.time()

print("📤 Sending indexing request to LightRAG service...")
print("")

try:
    response = requests.post(
        "http://localhost:8001/index-vault",
        json={"vault_path": "/app/vault"},  # Container path
        timeout=7200  # 2 hour timeout for large vaults
    )

    if response.status_code == 200:
        result = response.json()
        elapsed = time.time() - start_time

        print("")
        print("╔════════════════════════════════════════════════════════════╗")
        print("║                  ✅ Indexing Complete!                      ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print("")
        print(f"⏱️  Time: {elapsed/60:.1f} minutes")
        print(f"📊 Files indexed: {result.get('files_indexed', 'N/A')}")
        print(f"📂 Vault path: {result.get('vault_path', 'N/A')}")
        print("")
        print("🔍 Check database stats:")
        print("   curl http://localhost:8001/stats")
        print("")
        print("🧪 Test query:")
        print("   curl -X POST http://localhost:8001/query \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -d '{\"query\":\"your search\",\"mode\":\"hybrid\"}'")
        print("")

    else:
        print(f"❌ Error: HTTP {response.status_code}")
        print(f"Response: {response.text}")
        exit(1)

except requests.exceptions.Timeout:
    print(f"❌ Timeout after 2 hours")
    print("The indexing might still be running. Check logs:")
    print("  docker logs obsidian-lightrag")
    exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    print("")
    print("Troubleshooting:")
    print("  1. Check if service is running: docker ps | grep lightrag")
    print("  2. Check service logs: docker logs obsidian-lightrag")
    print("  3. Check health: curl http://localhost:8001/health")
    exit(1)
EOF

echo ""
echo "Next steps:"
echo "  • Test queries at http://localhost:8501 (Streamlit UI)"
echo "  • Or use API at http://localhost:8001/query"
echo "  • Compare with NetworkX graph (port 8002)"
echo ""
