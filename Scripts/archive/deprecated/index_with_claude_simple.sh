#!/bin/bash
# Index Obsidian vault using Claude API (simplified - uses Docker endpoint)

set -e

# Default to Haiku 4.5 (latest, best value!) unless CLAUDE_MODEL is set
CLAUDE_MODEL=${CLAUDE_MODEL:-claude-haiku-4-5-20250122}

if [[ "$CLAUDE_MODEL" == *"haiku-4"* ]]; then
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║      Index with Claude Haiku 4.5 (Latest & Best!)          ║"
    echo "╚════════════════════════════════════════════════════════════╝"
elif [[ "$CLAUDE_MODEL" == *"haiku"* ]]; then
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║      Index with Claude 3.5 Haiku (Previous Version)        ║"
    echo "╚════════════════════════════════════════════════════════════╝"
else
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║     Index with Claude 3.5 Sonnet (Premium Quality)         ║"
    echo "╚════════════════════════════════════════════════════════════╝"
fi
echo ""

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY not set"
    echo ""
    echo "Get your API key at: https://console.anthropic.com/"
    echo "Then run:"
    echo "  export ANTHROPIC_API_KEY='your-key-here'"
    echo ""
    echo "Optional: Choose model (defaults to Haiku 4.5):"
    echo "  export CLAUDE_MODEL='claude-haiku-4-5-20250122'   # ~\$1-2 (latest!)"
    echo "  export CLAUDE_MODEL='claude-3-5-haiku-20241022'   # ~\$1-2 (previous)"
    echo "  export CLAUDE_MODEL='claude-3-5-sonnet-20241022'  # ~\$15 (premium)"
    echo ""
    exit 1
fi

echo "✅ API key found"
echo "🤖 Model: $CLAUDE_MODEL"
echo ""

# Check if lightrag service is running
if ! docker ps | grep -q obsidian-lightrag; then
    echo "⚠️  LightRAG service not running. Starting services..."
    ./Scripts/docker_start.sh
    sleep 5
fi

# Count markdown files in your vault (from host)
VAULT_HOST_PATH="/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
NOTE_COUNT=$(find "$VAULT_HOST_PATH" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')

echo "📂 Vault: $VAULT_HOST_PATH"
echo "📚 Found: $NOTE_COUNT markdown files"
echo ""

if [[ "$CLAUDE_MODEL" == *"haiku"* ]]; then
    echo "💰 Estimated cost: \$1-2 for $NOTE_COUNT notes"
    echo "⏱️  Estimated time: 45-75 minutes"
else
    echo "💰 Estimated cost: \$10-20 for $NOTE_COUNT notes"
    echo "⏱️  Estimated time: 1-1.5 hours"
fi
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

echo ""
echo "🚀 Starting indexing with Claude..."
echo "📊 Progress will be shown in the LightRAG service logs"
echo ""
echo "💡 Tip: Watch progress in another terminal:"
echo "   docker logs -f obsidian-lightrag"
echo ""

# Call the LightRAG service API to index the vault
# The vault is mounted at /app/vault inside the container
curl -X POST http://localhost:8001/index-vault \
  -H "Content-Type: application/json" \
  -d '{"vault_path": "/app/vault"}' \
  --max-time 7200

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ Indexing Complete!                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next: Try graph search at http://localhost:8501"
echo ""

