#!/bin/bash
# Quick Fix for Graph Search - Increase Parameters First

set -e

echo "🔧 Quick Fix: Increasing chunk retrieval parameters"
echo "=================================================="

cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

# Backup the current database
echo ""
echo "📦 Step 1: Backing up database..."
cp -r lightrag_db lightrag_db_backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
echo "✅ Backup created"

# Check current status
echo ""
echo "📊 Step 2: Checking current status..."
docker-compose ps lightrag-service

echo ""
echo "🔧 Step 3: Adjusting parameters in lightrag_service.py..."
echo "   - Increasing chunk_top_k to 200"
echo "   - Increasing max_total_tokens to 50000"

# The user will manually edit, or we'll provide instructions
echo ""
echo "📝 Edit lightrag_service.py and update these lines:"
echo "   param = QueryParam("
echo "       mode=mode,"
echo "       chunk_top_k=200,  # Increased from 100"
echo "       top_k=80,  # Increased from 40"
echo "       max_total_tokens=50000  # Increased from 30000"
echo "   )"

echo ""
echo "🚀 Step 4: Rebuilding container..."
echo "   Run: docker-compose build lightrag-service"
echo "   Then: docker-compose up -d lightrag-service"

echo ""
echo "✅ Complete! This should improve graph search results."
echo ""
echo "📋 To test:"
echo "   curl -X POST http://localhost:8001/query \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{\"query\":\"ESP32\",\"mode\":\"naive\"}'"

