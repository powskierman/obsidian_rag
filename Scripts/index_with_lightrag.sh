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

FORCE_REINDEX=false
VAULT_PATH="./vault"

for arg in "$@"; do
    case "$arg" in
        --force)
            FORCE_REINDEX=true
            ;;
        -*)
            echo "Unknown option: $arg"
            exit 1
            ;;
        *)
            VAULT_PATH="$arg"
            ;;
    esac
done

echo "📂 Vault path: $VAULT_PATH"
echo ""
echo "🔄 Starting indexing process..."
echo "   (This may take several minutes for large vaults)"
echo ""

# Send indexing request
FORCE_FLAG=""
if [ "$FORCE_REINDEX" = true ]; then
    FORCE_FLAG=", \"force\": true"
    echo "⚠️  Force reindex enabled"
    echo ""
fi

RESPONSE=$(curl -s -X POST http://localhost:8001/index-vault \
    -H "Content-Type: application/json" \
    -d "{\"vault_path\": \"$VAULT_PATH\"$FORCE_FLAG}")

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

