#!/bin/bash
# Clean git history to remove large files
# WARNING: This rewrites history - backup first!

set -e

REPO_DIR="/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"
cd "$REPO_DIR"

echo "📦 Creating backup branch..."
git branch backup-before-cleanup-$(date +%Y%m%d-%H%M%S) || true

echo "🧹 Removing large files from git history..."
echo "This may take several minutes..."

# Remove large files from all history
git filter-branch --force --index-filter '
  git rm --cached --ignore-unmatch \
    "chroma_db_backup_*" \
    "lightrag_db_backup_*" \
    "graph_data/*.pkl" \
    "graph_data/*.json" \
    "graphrag_claude_db" \
    "graphrag_db" \
    "Archive/old_databases" \
    2>/dev/null || true
' --prune-empty --tag-name-filter cat -- --all

echo "🧼 Cleaning up refs..."
git for-each-ref --format="%(refname)" refs/original/ | xargs -n 1 git update-ref -d 2>/dev/null || true

echo "🗑️  Expiring reflog..."
git reflog expire --expire=now --all

echo "📦 Aggressive garbage collection..."
git gc --prune=now --aggressive

echo ""
echo "✅ Cleanup complete!"
echo "📊 New repository size:"
du -sh .git

echo ""
echo "⚠️  Next steps:"
echo "1. Verify with: git log --oneline"
echo "2. Force push: git push --force origin master"
echo "3. If issues, restore: git checkout backup-before-cleanup-*"
