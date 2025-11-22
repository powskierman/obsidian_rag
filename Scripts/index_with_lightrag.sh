#!/bin/bash
# Index Obsidian vault with LightRAG

echo "📚 Indexing Obsidian Vault with LightRAG"
echo "=========================================="
echo ""

# Check if LightRAG service is running
if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "❌ LightRAG service is not running"
    echo "   Start it with: ./Scripts/docker_start.sh"
    exit 1
fi

echo "✅ LightRAG service is ready"
echo ""

# Get vault path from user or use default
VAULT_PATH="${1:-./vault}"

echo "📂 Vault path: $VAULT_PATH"
echo ""
echo "🔄 Starting indexing process..."
echo "   (This may take several minutes for large vaults)"
echo ""

# Send indexing request
RESPONSE=$(curl -s -X POST http://localhost:8001/index-vault \
    -H "Content-Type: application/json" \
    -d "{\"vault_path\": \"$VAULT_PATH\"}")

# Check response
if echo "$RESPONSE" | grep -q '"status":"success"'; then
    FILES=$(echo "$RESPONSE" | grep -o '"files_indexed":[0-9]*' | cut -d':' -f2)
    echo ""
    echo "✅ Indexing complete!"
    echo "   Files indexed: $FILES"
    echo ""
    echo "You can now use graph-based queries in the UI:"
    echo "  - graph-local:  Local entity relationships"
    echo "  - graph-global: Global knowledge synthesis"
    echo "  - graph-hybrid: Combined approach"
else
    echo ""
    echo "❌ Indexing failed"
    echo "Response: $RESPONSE"
    exit 1
fi

echo ""
echo "=========================================="


