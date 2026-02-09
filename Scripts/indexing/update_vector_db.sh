#!/bin/bash
# Update Vector Database (ChromaDB) Only
# Usage: ./update_vector_db.sh [--refresh]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source .env
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

# Determine python interpreter
if [ -f "$REPO_ROOT/venv/bin/python" ]; then
    PYTHON_CMD="$REPO_ROOT/venv/bin/python"
elif [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$REPO_ROOT/.venv/bin/python"
else
    PYTHON_CMD="python"
fi

echo "🔹 Updating Vector Database (Chroma)..."
# Passes all arguments (like --refresh) through to the python script
PYTHONPATH="$REPO_ROOT" "$PYTHON_CMD" "$REPO_ROOT/src/indexing/index_vault.py" "$@"
