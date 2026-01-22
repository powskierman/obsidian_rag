#!/bin/bash
# deploy_from_local_volume.sh
# Deploys fresh databases from the mounted /Volumes/michel/obsidian_rag_local_data
# to the current active project.
# Automatically rebuilds graph pickle to ensure NetworkX version compatibility.

set -e

SOURCE_DIR="/Volumes/michel/obsidian_rag_local_data"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║      Deploying Databases from Local Volume               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo "Source: $SOURCE_DIR"
echo "Target: $PROJECT_DIR"
echo ""

if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Error: Source directory not found at $SOURCE_DIR"
    exit 1
fi

# 1. Stop Docker Services
echo "🛑 Stopping Docker services to unlock databases..."
cd "$PROJECT_DIR"
docker compose down
echo ""

# 2. Deploy ChromaDB
echo "📦 Deploying ChromaDB..."
if [ -d "$SOURCE_DIR/chroma_db" ]; then
    # Backup existing
    if [ -d "chroma_db" ]; then
        mv chroma_db "chroma_db_backup_$(date +%s)"
    fi
    mkdir -p chroma_db
    cp -R "$SOURCE_DIR/chroma_db/"* chroma_db/
    echo "   ✅ ChromaDB Deployed"
else
    echo "   ⚠️  Source ChromaDB not found"
fi

# 3. Deploy LightRAG
echo "📦 Deploying LightRAG..."
if [ -d "$SOURCE_DIR/lightrag_db" ]; then
    # Backup existing
    if [ -d "lightrag_db" ]; then
        mv lightrag_db "lightrag_db_backup_$(date +%s)"
    fi
    mkdir -p lightrag_db
    cp -R "$SOURCE_DIR/lightrag_db/"* lightrag_db/
    echo "   ✅ LightRAG Deployed"
else
    echo "   ⚠️  Source LightRAG not found"
fi

# 4. Deploy Knowledge Graph
echo "📦 Deploying Knowledge Graph..."
if [ -d "$SOURCE_DIR/graph_data" ]; then
    # Target is data/graph_data
    mkdir -p data/graph_data
    
    # Backup existing pkl if exists
    if [ -f "data/graph_data/knowledge_graph_full.pkl" ]; then
        mv data/graph_data/knowledge_graph_full.pkl "data/graph_data/knowledge_graph_full_backup_$(date +%s).pkl"
    fi
    
    # Copy JSON (Source of Truth)
    if [ -f "$SOURCE_DIR/graph_data/knowledge_graph_full.json" ]; then
        cp "$SOURCE_DIR/graph_data/knowledge_graph_full.json" "data/graph_data/"
        echo "   ✅ Graph JSON Deployed"
        
        # 4b. Rebuild Pickle from JSON (Compatibility Fix)
        echo "🔄 Rebuilding Graph Pickle from JSON (to match local NetworkX version)..."
        if [ -f "Scripts/rebuild_graph_from_json.py" ] && [ -x "$PYTHON_BIN" ]; then
            "$PYTHON_BIN" Scripts/rebuild_graph_from_json.py \
                "data/graph_data/knowledge_graph_full.json" \
                "data/graph_data/knowledge_graph_full.pkl"
            
            # Copy new pickle to root graph_data if it exists (legacy support)
            if [ -d "graph_data" ]; then
                cp "data/graph_data/knowledge_graph_full.pkl" "graph_data/"
                echo "   ✅ Updated legacy root graph_data"
            fi
        else
            echo "   ⚠️  Skipping rebuild: rebuild script or venv python not found."
            # Fallback: Copy the pickle from source (risky if versions differ)
            cp "$SOURCE_DIR/graph_data/knowledge_graph_full.pkl" "data/graph_data/"
            echo "   ⚠️  Copied source pickle as fallback."
        fi
    else
        echo "   ⚠️  JSON source not found. Copying pickle directly (version mismatch risk)."
        cp "$SOURCE_DIR/graph_data/knowledge_graph_full.pkl" "data/graph_data/"
    fi
    
    echo "   ✅ Knowledge Graph Deployed"
else
    echo "   ⚠️  Source graph_data not found"
fi

# 5. Restart Services
echo ""
echo "🚀 Restarting Docker Services..."
docker compose up -d

echo ""
echo "🎉 DEPLOYMENT COMPLETE!"