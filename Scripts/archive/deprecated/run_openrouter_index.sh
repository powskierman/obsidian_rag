#!/bin/bash
# Index Obsidian vault using OpenRouter API (Multi-Model Support)
# Supports Claude, GPT-4, Gemini, Llama, and many other models

set -e

# Default to Claude 3.5 Haiku unless OPENROUTER_MODEL is set
OPENROUTER_MODEL=${OPENROUTER_MODEL:-anthropic/claude-3.5-haiku}

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         Index with OpenRouter (Multi-Model Support)        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ Error: OPENROUTER_API_KEY not set"
    echo ""
    echo "Get your API key at: https://openrouter.ai/keys"
    echo "Then run:"
    echo "  export OPENROUTER_API_KEY='your-key-here'"
    echo ""
    echo "Optional: Choose model (defaults to Claude 3.5 Haiku):"
    echo "  export OPENROUTER_MODEL='anthropic/claude-3.5-haiku'     # ~\$1-2 (fast, cheap)"
    echo "  export OPENROUTER_MODEL='anthropic/claude-3-5-sonnet-20241022'  # ~\$15 (premium)"
    echo "  export OPENROUTER_MODEL='openai/gpt-4o-mini'             # ~\$1 (very fast)"
    echo "  export OPENROUTER_MODEL='google/gemini-flash-1.5'        # ~\$0.50 (fastest)"
    echo "  export OPENROUTER_MODEL='meta-llama/llama-3.1-70b-instruct' # ~\$1 (open source)"
    echo ""
    echo "See all models at: https://openrouter.ai/models"
    echo ""
    exit 1
fi

echo "✅ API key found"
echo "🤖 Model: $OPENROUTER_MODEL"
echo ""

# Check if vault path is provided
if [ -z "$VAULT_PATH" ]; then
    # Try to get vault path from docker-compose.yml
    VAULT_PATH=$(grep "/app/vault" docker-compose.yml | grep -v "VAULT" | sed 's/^[[:space:]]*-[[:space:]]*//' | cut -d: -f1 | tr -d '"')
    
    # If extraction failed or path doesn't exist, try the default
    if [ -z "$VAULT_PATH" ] || [ ! -d "$VAULT_PATH" ]; then
        echo "⚠️  Could not detect vault path from docker-compose.yml"
        # Check if ./vault exists
        if [ -d "./vault" ]; then
            VAULT_PATH="./vault"
            echo "✅ Using mounted path: ./vault"
        else
            echo "❌ Error: No vault directory found"
            echo ""
            echo "Please either:"
            echo "  1. Update docker-compose.yml with your vault path, or"
            echo "  2. Pass vault path: VAULT_PATH=/path/to/vault ./Scripts/run_openrouter_index.sh"
            echo ""
            echo "Example:"
            echo "  VAULT_PATH='/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel' ./Scripts/run_openrouter_index.sh"
            exit 1
        fi
    fi
fi

echo "📂 Vault path: $VAULT_PATH"

# Estimate cost and time based on model
if [[ "$OPENROUTER_MODEL" == *"haiku"* ]]; then
    echo "💰 Estimated cost: \$1-2 for 1600 notes"
    echo "⏱️  Estimated time: 45-75 minutes"
elif [[ "$OPENROUTER_MODEL" == *"gpt-4o-mini"* ]]; then
    echo "💰 Estimated cost: \$1 for 1600 notes"
    echo "⏱️  Estimated time: 30-60 minutes"
elif [[ "$OPENROUTER_MODEL" == *"gemini-flash"* ]]; then
    echo "💰 Estimated cost: \$0.50 for 1600 notes"
    echo "⏱️  Estimated time: 20-40 minutes"
elif [[ "$OPENROUTER_MODEL" == *"sonnet"* ]]; then
    echo "💰 Estimated cost: \$10-20 for 1600 notes"
    echo "⏱️  Estimated time: 1-1.5 hours"
else
    echo "💰 Estimated cost: \$2-5 for 1600 notes (varies by model)"
    echo "⏱️  Estimated time: 45-90 minutes"
fi
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

echo ""
echo "🚀 Starting indexing with OpenRouter..."
echo ""

# Run the OpenRouter indexing script
cd "$(dirname "$0")/.."

# Check if Python script exists
if [ ! -f "index_with_openrouter.py" ]; then
    echo "❌ Error: index_with_openrouter.py not found"
    echo "Please ensure the script is in the project root directory"
    exit 1
fi

# Set environment variables for the Python script
export VAULT_PATH="$VAULT_PATH"

# Run the indexing
python3 index_with_openrouter.py

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ Indexing Complete!                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. View graph: python3 visualize_graph.py"
echo "  2. Start UI: ./Scripts/docker_start.sh"
echo "  3. Open browser: http://localhost:8501"
echo ""

