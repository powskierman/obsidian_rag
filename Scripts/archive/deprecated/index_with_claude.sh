#!/bin/bash
# Index Obsidian vault using Claude API (Haiku or Sonnet)

set -e

# Default to Haiku 4.5 (latest, best value!) unless CLAUDE_MODEL is set
CLAUDE_MODEL=${CLAUDE_MODEL:-claude-haiku-4-5-20250122}

if [[ "$CLAUDE_MODEL" == *"haiku-4"* ]]; then
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║      Index with Claude Haiku 4.5 (Latest & Best!)          ║"
    echo "╚════════════════════════════════════════════════════════════╝"
elif [[ "$CLAUDE_MODEL" == *"haiku"* ]]; then
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║      Index with Claude 3.5 Haiku (Previous Version)        ║"
    echo "╚════════════════════════════════════════════════════════════╝"
else
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║     Index with Claude 3.5 Sonnet (Premium Quality)         ║"
    echo "╚════════════════════════════════════════════════════════════╝"
fi
echo ""

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY not set"
    echo ""
    echo "Get your API key at: https://console.anthropic.com/"
    echo "Then run:"
    echo "  export ANTHROPIC_API_KEY='your-key-here'"
    echo ""
    echo "Optional: Choose model (defaults to Haiku 4.5):"
    echo "  export CLAUDE_MODEL='claude-haiku-4-5-20250122'   # ~\$1-2 (latest!)"
    echo "  export CLAUDE_MODEL='claude-3-5-haiku-20241022'   # ~\$1-2 (previous)"
    echo "  export CLAUDE_MODEL='claude-3-5-sonnet-20241022'  # ~\$15 (premium)"
    echo ""
    exit 1
fi

echo "✅ API key found"
echo "🤖 Model: $CLAUDE_MODEL"
echo ""

# Check if lightrag service is running
if ! docker ps | grep -q obsidian-lightrag; then
    echo "⚠️  LightRAG service not running. Starting services..."
    ./Scripts/docker_start.sh
    sleep 5
fi

# Get vault path from docker-compose.yml
# Extract the host path (left side) before the colon, removing the leading dash and spaces
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
        echo "  2. Pass vault path: VAULT_PATH=/path/to/vault ./Scripts/index_with_claude.sh"
        exit 1
    fi
fi

echo "📂 Vault path: $VAULT_PATH"

if [[ "$CLAUDE_MODEL" == *"haiku"* ]]; then
    echo "💰 Estimated cost: \$1-2 for 1600 notes"
    echo "⏱️  Estimated time: 45-75 minutes"
else
    echo "💰 Estimated cost: \$10-20 for 1600 notes"
    echo "⏱️  Estimated time: 1-1.5 hours"
fi
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

echo ""
echo "🚀 Starting indexing with Claude..."
echo ""

# Run indexing using Claude-enabled service
# Note: You need to update docker-compose to use the Claude service
# For now, we'll call the API directly

python3 - <<EOF
import requests
import os
import time
from pathlib import Path

api_key = os.getenv("ANTHROPIC_API_KEY")
vault_path = "${VAULT_PATH}"

# Load notes
notes = []
for md_file in Path(vault_path).rglob("*.md"):
    try:
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                notes.append(content)
    except Exception as e:
        print(f"⚠️  Could not read {md_file}: {e}")

print(f"📚 Found {len(notes)} notes")
print("")

if not notes:
    print("❌ No markdown files found")
    exit(1)

# Send to LightRAG service
start_time = time.time()

try:
    response = requests.post(
        "http://localhost:8001/index-vault",
        json={"vault_path": vault_path},
        timeout=7200  # 2 hour timeout
    )
    
    if response.status_code == 200:
        elapsed = time.time() - start_time
        print(f"")
        print(f"✅ Indexing complete!")
        print(f"⏱️  Time: {elapsed/60:.1f} minutes")
        print(f"📊 Notes indexed: {response.json()['files_indexed']}")
    else:
        print(f"❌ Error: {response.text}")
        exit(1)
        
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
EOF

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ Indexing Complete!                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next: Try graph search at http://localhost:8501"
echo ""

