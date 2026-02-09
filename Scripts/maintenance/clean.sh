#!/bin/bash
echo "🧹 Cleaning Obsidian RAG System"
echo ""

# Remove logs
if ls *.log 1> /dev/null 2>&1; then
    echo "Removing log files..."
    rm -f *.log
    echo "  ✅ Logs removed"
fi

# Remove Python cache
if [ -d "__pycache__" ]; then
    echo "Removing Python cache..."
    rm -rf __pycache__
    echo "  ✅ Python cache removed"
fi

# Remove temporary files
echo "Removing temporary files..."
find . -name "*.pyc" -delete
find . -name ".DS_Store" -delete
echo "  ✅ Temporary files removed"
echo ""
echo "✅ Cleanup complete!"
