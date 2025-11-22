#!/usr/bin/env python3
"""
LightRAG Service - Flask API for Graph-based RAG
Provides hybrid search combining knowledge graphs with vector similarity
"""

import os
import asyncio
from pathlib import Path
from flask import Flask, request, jsonify
from lightrag import LightRAG, QueryParam
from lightrag.llm.ollama import ollama_model_complete, ollama_embed
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WORKING_DIR = os.getenv("LIGHTRAG_DIR", "./lightrag_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:32b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# Set Ollama host
os.environ["OLLAMA_HOST"] = OLLAMA_HOST

# Global RAG instance and event loop
rag_instance = None
rag_lock = asyncio.Lock()
_loop = None


def get_or_create_loop():
    """Get or create a global event loop"""
    global _loop
    try:
        _loop = asyncio.get_event_loop()
    except RuntimeError:
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


async def get_rag():
    """Get or create LightRAG instance"""
    global rag_instance
    
    async with rag_lock:
        if rag_instance is None:
            logger.info("Initializing LightRAG...")
            rag_instance = LightRAG(
                working_dir=WORKING_DIR,
                llm_model_func=ollama_model_complete,
                llm_model_name=LLM_MODEL,
                llm_model_kwargs={"options": {"num_ctx": 32768}},
                embedding_func=EmbeddingFunc(
                    embedding_dim=768,
                    func=lambda texts: ollama_embed(
                        texts,
                        embed_model=EMBED_MODEL,
                        host=OLLAMA_HOST
                    )
                ),
                # Fix the cosine thresholds for better matching
                cosine_threshold=0.05,  # Lower threshold for initial filtering
                cosine_better_than_threshold=0.05,  # Lower threshold for result ranking
                # Increase retrieval limits
                top_k=100,  # More entities per query
                chunk_top_k=50,  # More chunks per query
                max_total_tokens=60000,  # More context
                # Reduce async concurrency to avoid event loop conflicts
                embedding_func_max_async=2,  # Reduce from default 8
                llm_model_max_async=2,  # Reduce from default 4
                # Improve chunking
                chunk_token_size=800,  # Smaller chunks for better matching
                chunk_overlap_token_size=200,  # More overlap
            )
            await rag_instance.initialize_storages()
            await initialize_pipeline_status()
            logger.info("✅ LightRAG initialized with pipeline status")
        
        return rag_instance


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "lightrag",
        "ollama_host": OLLAMA_HOST,
        "llm_model": LLM_MODEL
    }), 200


@app.route('/stats', methods=['GET'])
def stats():
    """Get statistics about the knowledge graph"""
    try:
        # Check if database exists
        db_path = Path(WORKING_DIR)
        exists = db_path.exists()
        
        stats_data = {
            "working_dir": WORKING_DIR,
            "database_exists": exists,
            "llm_model": LLM_MODEL,
            "embed_model": EMBED_MODEL
        }
        
        if exists:
            # Count files in the directory
            files = list(db_path.rglob("*"))
            stats_data["total_files"] = len(files)
        
        return jsonify(stats_data), 200
    
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/insert', methods=['POST'])
def insert_documents():
    """Insert documents into LightRAG knowledge graph"""
    try:
        data = request.json
        texts = data.get('texts', [])
        
        if not texts:
            return jsonify({"error": "No texts provided"}), 400
        
        # Run async insert
        async def do_insert():
            rag = await get_rag()
            await rag.ainsert(texts)
        
        asyncio.run(do_insert())
        
        return jsonify({
            "status": "success",
            "documents_inserted": len(texts)
        }), 200
    
    except Exception as e:
        logger.error(f"Insert error: {e}")
        return jsonify({"error": str(e)}), 500


async def _do_query_async(query_text, mode):
    """Helper async method for querying"""
    rag = await get_rag()
    
    # Optimized query parameters for faster processing while maintaining quality
    if mode in ['global', 'hybrid']:
        # For computationally expensive modes, reduce parameters
        param = QueryParam(
            mode=mode,
            chunk_top_k=50,  # Reduced for faster processing
            top_k=75,  # Reduced entities for speed
            max_total_tokens=32000,  # Reduced token limit
            only_need_context=False
        )
    else:
        # For local/naive modes, can use higher values
        param = QueryParam(
            mode=mode,
            chunk_top_k=100,
            top_k=150,
            max_total_tokens=60000,
            only_need_context=False
        )
    result = await rag.aquery(query_text, param=param)
    return result


@app.route('/query', methods=['POST'])
def query_graph():
    """Query the knowledge graph using LightRAG"""
    try:
        data = request.json
        query_text = data.get('query')
        mode = data.get('mode', 'hybrid')  # naive, local, global, or hybrid
        
        if not query_text:
            return jsonify({"error": "No query provided"}), 400
        
        # Validate mode
        valid_modes = ['naive', 'local', 'global', 'hybrid']
        if mode not in valid_modes:
            return jsonify({"error": f"Invalid mode. Use: {valid_modes}"}), 400
        
        # Run async query using asyncio.run (creates a fresh event loop each time)
        # This avoids the "different event loop" error
        result = asyncio.run(_do_query_async(query_text, mode))
        
        return jsonify({
            "query": query_text,
            "mode": mode,
            "result": result
        }), 200
    
    except Exception as e:
        logger.error(f"Query error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/index-vault', methods=['POST'])
def index_vault():
    """Index all markdown files from a vault directory"""
    try:
        data = request.json or {}
        vault_path = data.get('vault_path', './vault')
        
        # Load markdown files
        notes = []
        vault_dir = Path(vault_path)
        
        if not vault_dir.exists():
            return jsonify({"error": f"Vault path not found: {vault_path}"}), 400
        
        for md_file in vault_dir.rglob("*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        notes.append(content)
            except Exception as e:
                logger.warning(f"Could not read {md_file}: {e}")
        
        if not notes:
            return jsonify({"error": "No markdown files found"}), 400
        
        # Insert into LightRAG
        async def do_index():
            rag = await get_rag()
            await rag.ainsert(notes)
        
        asyncio.run(do_index())
        
        return jsonify({
            "status": "success",
            "files_indexed": len(notes),
            "vault_path": vault_path
        }), 200
    
    except Exception as e:
        logger.error(f"Index vault error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info(f"""
╔══════════════════════════════════════════════════════════╗
║          LightRAG Service - Knowledge Graph RAG          ║
╚══════════════════════════════════════════════════════════╝

📂 Working Dir: {WORKING_DIR}
🤖 LLM Model:   {LLM_MODEL}
🔤 Embed Model: {EMBED_MODEL}
🌐 Ollama Host: {OLLAMA_HOST}

Endpoints:
  GET  /health        - Health check
  GET  /stats         - Database statistics
  POST /insert        - Insert documents
  POST /query         - Query knowledge graph
  POST /index-vault   - Index Obsidian vault

Starting server...
""")
    
    app.run(host='0.0.0.0', port=8001, debug=False)

