#!/bin/bash
echo "📊 Obsidian RAG System Status"
echo "======================================================================"
echo ""

# Check embedding service
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Embedding Service: RUNNING (port 8000)"
    echo -n "   Stats: "
    curl -s http://localhost:8000/stats 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"{data['total_documents']} chunks, ~{data.get('estimated_notes', int(data['total_documents']/4.4))} notes\")" 2>/dev/null || echo "unavailable"
else
    echo "❌ Embedding Service: STOPPED"
    echo "   Start: python src/services/embedding_service.py"
fi

echo ""

# Check Streamlit
if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Streamlit UI: RUNNING (port 8501)"
    echo "   URL: http://localhost:8501"
else
    echo "❌ Streamlit UI: STOPPED"
    echo "   Start: streamlit run src/ui/streamlit_ui_docker.py"
fi

echo ""

# Check Ollama
if lsof -Pi :11434 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Ollama: RUNNING (port 11434)"
    echo "   Models:"
    ollama list 2>/dev/null | grep -E "qwen2.5|deepseek|llama" | head -5 || echo "   (no models info)"
else
    echo "❌ Ollama: STOPPED"
    echo "   Start: ollama serve"
fi

echo ""

# Check file watcher
if pgrep -f watching_scanner.py >/dev/null ; then
    WATCHER_PID=$(pgrep -f watching_scanner.py)
    echo "✅ File Watcher: RUNNING (PID: $WATCHER_PID)"
    echo "   Monitoring vault for changes"
else
    echo "⚪ File Watcher: STOPPED (optional)"
    echo "   Start: ./start_with_watcher.sh"
fi

echo ""

# Check memory system
if [ -d "mem0_db" ]; then
    MEMORY_SIZE=$(du -sh mem0_db 2>/dev/null | cut -f1)
    echo "✅ Memory System: INITIALIZED"
    echo "   Database: mem0_db ($MEMORY_SIZE)"
else
    echo "⚠️  Memory System: NOT INITIALIZED"
    echo "   Run: python rag_with_memory.py init"
fi

echo ""
echo "======================================================================"
echo ""
echo "Quick Actions:"
echo "  Start:  Scripts/start_obsidian_rag.sh"
echo "  Stop:   Scripts/stop_obsidian_rag.sh"
echo "  Watch:  Scripts/start_with_watcher.sh"
echo "  Logs:   tail -f Scripts/logs/*.log"
