#!/bin/bash
# Index Obsidian vault with GraphRAG

echo "📚 Indexing Obsidian Vault with GraphRAG"
echo "=========================================="
echo ""

# Check if GraphRAG service is running
if ! curl -s http://localhost:8002/health > /dev/null 2>&1; then
    echo "❌ GraphRAG service is not running"
    echo "   Start it with: docker-compose --profile graphrag up -d"
    exit 1
fi

echo "✅ GraphRAG service is ready"
echo ""

# Get vault path from user or use default
VAULT_PATH="${1:-/app/vault}"

echo "📂 Vault path: $VAULT_PATH"
echo ""
echo "🔄 Starting indexing process..."
echo "   (This may take several minutes for large vaults)"
echo "   GraphRAG performs entity extraction and knowledge graph construction"
echo ""

# Send indexing request
RESPONSE=$(curl -s -X POST http://localhost:8002/index-vault \
    -H "Content-Type: application/json" \
    -d "{\"vault_path\": \"$VAULT_PATH\"}")

# Check response
if echo "$RESPONSE" | grep -q '"status":"success"'; then
    FILES=$(echo "$RESPONSE" | grep -o '"files_indexed":[0-9]*' | cut -d':' -f2)
    echo ""
    echo "✅ Indexing complete!"
    echo "   Files indexed: $FILES"
    echo "   Knowledge graph built successfully"
    echo ""
    echo "You can now use GraphRAG queries in the UI:"
    echo "  - graph-global: Comprehensive analysis using community reports"
    echo "  - graph-local:  Entity-focused search with relationships"
    echo ""
    echo "🏥 GraphRAG is optimized for medical content and should provide"
    echo "   better results for your lymphoma treatment timeline queries."

elif echo "$RESPONSE" | grep -q '"status":"partial_success"'; then
    FILES=$(echo "$RESPONSE" | grep -o '"files_prepared":[0-9]*' | cut -d':' -f2)
    echo ""
    echo "⚠️  Partial success - files prepared but indexing incomplete"
    echo "   Files prepared: $FILES"
    echo ""
    echo "🔧 To complete indexing, run:"
    echo "   curl -X POST http://localhost:8002/build-index"
    echo ""
    echo "Or check the GraphRAG service logs:"
    echo "   docker logs obsidian-graphrag"

else
    echo ""
    echo "❌ Indexing failed"
    echo "Response: $RESPONSE"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "   1. Check if Ollama is running: curl http://localhost:11434/api/tags"
    echo "   2. Verify vault mount: docker exec obsidian-graphrag ls /app/vault"
    echo "   3. Check GraphRAG logs: docker logs obsidian-graphrag"
    echo "   4. Ensure models are available: ollama list"
    exit 1
fi

echo ""
echo "🧠 GraphRAG vs Vector Search:"
echo "   - Use vector search for direct fact retrieval"
echo "   - Use graph-global for complex analysis and synthesis"
echo "   - Use graph-local for exploring entity relationships"
echo ""
echo "=========================================="