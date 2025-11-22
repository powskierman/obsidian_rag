#!/bin/bash
echo "🧪 Testing Obsidian RAG System"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if services are running
"$SCRIPT_DIR/check_status.sh"

echo ""
echo "Running quick tests..."
echo ""

# Test embedding service
echo "1. Testing embedding service..."
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$STATUS_CODE" = "200" ]; then
    echo "   ✅ Embedding service healthy"
else
    echo "   ❌ Embedding service not responding (code: $STATUS_CODE)"
fi

# Test stats endpoint
echo "2. Testing stats endpoint..."
STATS=$(curl -s http://localhost:8000/stats)
if [ ! -z "$STATS" ]; then
    echo "   ✅ Stats: $STATS"
else
    echo "   ❌ Stats endpoint failed"
fi

# Test Ollama
echo "3. Testing Ollama..."
if ollama list >/dev/null 2>&1; then
    echo "   ✅ Ollama responding"
    MODELS=$(ollama list | grep -c qwen)
    echo "   Found $MODELS Qwen model(s)"
else
    echo "   ❌ Ollama not responding"
fi

# Test memory system
echo "4. Testing memory system..."
if [ -d "mem0_db" ]; then
    echo "   ✅ Memory database exists"
    MEMORY_COUNT=$(python3 -c "from rag_with_memory import MemoryRAG; print(len(MemoryRAG().get_all_memories()))" 2>/dev/null)
    if [ ! -z "$MEMORY_COUNT" ]; then
        echo "   ✅ Memories stored: $MEMORY_COUNT"
    else
        echo "   ⚠️  Could not count memories"
    fi
else
    echo "   ⚠️  Memory system not initialized"
fi

echo ""
echo "Test complete!"
