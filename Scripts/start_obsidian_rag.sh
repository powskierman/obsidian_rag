#!/bin/bash
echo "🚀 Starting Obsidian RAG System"
echo ""

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
source venv/bin/activate

# Start embedding service
echo "Starting embedding service..."
python embedding_service.py > embedding_service.log 2>&1 &
EMBED_PID=$!
echo "  PID: $EMBED_PID"
sleep 3

# Start Streamlit UI
echo "Starting Streamlit UI..."
streamlit run obsidian_rag_ui.py \
    --server.headless true \
    --browser.gatherUsageStats false \
    --server.port 8501 > streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo "  PID: $STREAMLIT_PID"

echo ""
echo "✅ System ready!"
echo "📊 Embedding Service: http://localhost:8000 (PID: $EMBED_PID)"
echo "💬 Chat Interface: http://localhost:8501 (PID: $STREAMLIT_PID)"
echo ""
echo "Logs:"
echo "  tail -f embedding_service.log"
echo "  tail -f streamlit.log"
echo ""
echo "To stop: ./stop_obsidian_rag.sh"
