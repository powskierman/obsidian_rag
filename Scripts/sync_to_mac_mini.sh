#!/bin/bash
# Quick sync of updated files to Mac Mini
# Use this when you've made changes and need to update the Mac Mini

set -e

echo "📡 Syncing updated files to Mac Mini..."
echo ""

# Sync just the docker config
rsync -avh --progress \
  "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/config/docker/docker-compose.yml" \
  "/Volumes/Michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/config/docker/"

echo ""
echo "✅ docker-compose.yml synced to Mac Mini"
echo ""
echo "Next: On Mac Mini, restart the container:"
echo "  cd '/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/config/docker'"
echo "  docker compose down"
echo "  docker compose up -d lightrag-service"
echo ""
