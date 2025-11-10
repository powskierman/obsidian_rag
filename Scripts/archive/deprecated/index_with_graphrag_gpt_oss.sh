#!/bin/bash
# Index Obsidian vault with LightRAG (graph-based RAG) using GPT-OSS and Nomic-embed-text

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   LightRAG (Graph-based RAG) Indexing                      ║"
echo "║   Using GPT-OSS & Nomic-embed-text                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Change to project directory
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

# Check if Python script exists
if [ ! -f "Scripts/index_with_graphrag_gpt_oss.py" ]; then
    echo "❌ Error: Scripts/index_with_graphrag_gpt_oss.py not found"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "venv_python313" ]; then
    source venv_python313/bin/activate
fi

# Run the Python script with all arguments passed through
python Scripts/index_with_graphrag_gpt_oss.py "$@"

