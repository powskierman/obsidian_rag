#!/bin/bash
# Index Obsidian vault with GraphRAG-Local-Ollama

echo "📚 Indexing Obsidian Vault with GraphRAG-Local-Ollama"
echo "====================================================="
echo ""

# Check if GraphRAG-Local service is running
if ! curl -s http://localhost:8003/health > /dev/null 2>&1; then
    echo "❌ GraphRAG-Local service is not running"
    echo "   Start it with: docker-compose --profile graphrag-local up -d"
    exit 1
fi

echo "✅ GraphRAG-Local service is ready"
echo ""

# Check health status
HEALTH_RESPONSE=$(curl -s http://localhost:8003/health)
if echo "$HEALTH_RESPONSE" | grep -q '"graphrag_available":false'; then
    echo "❌ GraphRAG-Local is not properly initialized"
    echo "   Response: $HEALTH_RESPONSE"
    exit 1
fi

echo "✅ GraphRAG-Local is initialized and available"
echo ""

# Get vault path from user or use default
VAULT_PATH="${1:-/app/vault}"

echo "📂 Vault path: $VAULT_PATH"
echo ""
echo "🔄 Starting indexing process..."
echo "   (This may take several minutes for large vaults)"
echo "   GraphRAG-Local performs entity extraction and knowledge graph construction"
echo "   Optimized for Ollama integration with your qwen2.5-coder:14b model"
echo ""

# Send indexing request
RESPONSE=$(curl -s -X POST http://localhost:8003/index-vault \
    -H "Content-Type: application/json" \
    -d "{\"vault_path\": \"$VAULT_PATH\"}")

# Check response
if echo "$RESPONSE" | grep -q '"status":"success"'; then
    FILES=$(echo "$RESPONSE" | grep -o '"files_indexed":[0-9]*' | cut -d':' -f2)
    echo ""
    echo "✅ Indexing complete!"
    echo "   Files indexed: $FILES"
    echo "   Knowledge graph built successfully with GraphRAG-Local"
    echo ""
    echo "You can now use GraphRAG-Local queries:"
    echo "  - graph-global: Comprehensive analysis using community reports"
    echo "  - graph-local:  Entity-focused search with relationships"
    echo ""
    echo "🏥 GraphRAG-Local is optimized for medical content and should provide"
    echo "   excellent results for your lymphoma treatment timeline queries."

elif echo "$RESPONSE" | grep -q '"status":"partial_success"'; then
    FILES=$(echo "$RESPONSE" | grep -o '"files_prepared":[0-9]*' | cut -d':' -f2)
    echo ""
    echo "⚠️  Partial success - files prepared but indexing incomplete"
    echo "   Files prepared: $FILES"
    echo ""
    echo "🔧 To complete indexing, run:"
    echo "   curl -X POST http://localhost:8003/build-index"
    echo ""
    echo "Or check the GraphRAG-Local service logs:"
    echo "   docker logs obsidian-graphrag-local"

else
    echo ""
    echo "❌ Indexing failed"
    echo "Response: $RESPONSE"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "   1. Check if Ollama is running: curl http://localhost:11434/api/tags"
    echo "   2. Verify vault mount: docker exec obsidian-graphrag-local ls /app/vault"
    echo "   3. Check GraphRAG-Local logs: docker logs obsidian-graphrag-local"
    echo "   4. Ensure models are available: ollama list"
    echo "   5. Check GraphRAG-Local health: curl http://localhost:8003/health"
    exit 1
fi

echo ""
echo "🧠 GraphRAG-Local vs Vector Search:"
echo "   - Use vector search for direct fact retrieval"
echo "   - Use graph-global for complex analysis and synthesis across your entire vault"
echo "   - Use graph-local for exploring specific entity relationships"
echo "   - GraphRAG-Local uses specialized Ollama integration for better performance"
echo ""
echo "📊 Check indexing progress:"
echo "   curl http://localhost:8003/stats"
echo ""
echo "====================================================="