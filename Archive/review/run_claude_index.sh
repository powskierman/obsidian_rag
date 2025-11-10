#!/bin/bash
# Activate venv and run Claude indexing

cd "$(dirname "$0")"
source venv/bin/activate

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY not set"
    echo ""
    echo "Please run:"
    echo "  export ANTHROPIC_API_KEY='your-key-here'"
    echo "  ./run_claude_index.sh"
    exit 1
fi

python3 index_with_claude_direct.py
