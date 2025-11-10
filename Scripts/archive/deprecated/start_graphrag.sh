#!/bin/bash
# Start GraphRAG Service Script

echo "🚀 Starting GraphRAG Service"
echo ""

cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

# Start GraphRAG service with docker-compose profile
docker-compose --profile graphrag up -d graphrag-service

echo ""
echo "⏳ Waiting for service to start..."
sleep 5

# Check status
echo ""
echo "📊 Service Status:"
docker-compose --profile graphrag ps graphrag-service

echo ""
echo "🔍 Health Check:"
curl -s http://localhost:8002/health | python3 -m json.tool 2>/dev/null || echo "Service not responding yet"

echo ""
echo "✅ GraphRAG service started!"
echo "   - API: http://localhost:8002"
echo "   - Health: http://localhost:8002/health"
echo "   - Stats: http://localhost:8002/stats"
echo ""
echo "To index your vault:"
echo "   curl -X POST http://localhost:8002/index-vault -H 'Content-Type: application/json' -d '{}'"
echo ""
echo "Or use the Streamlit UI sidebar button to index."
