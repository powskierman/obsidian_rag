#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."

echo "🛑 Stopping Obsidian RAG Docker stack"
echo ""

cd "$PROJECT_ROOT"

if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Cannot stop the Docker-managed services cleanly."
    exit 1
fi

echo "Stopping containers, including internal graph dependencies..."
docker-compose down

echo ""
echo "✅ Docker stack stopped"
