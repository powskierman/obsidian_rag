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
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status
import logging

# Import GPT-OSS integration
try:
    from gpt_oss_integration import (
        get_model_func, get_embed_func, is_gpt_oss_endpoint
    )
    GPT_OSS_AVAILABLE = True
except ImportError:
    # Fallback to Ollama if GPT-OSS integration not available
    from lightrag.llm.ollama import ollama_model_complete, ollama_embed
    GPT_OSS_AVAILABLE = False

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WORKING_DIR = os.getenv("LIGHTRAG_DIR", "./lightrag_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:32b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()  # ollama, gpt-oss, or claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Detect GPT-OSS endpoint
USE_GPT_OSS = is_gpt_oss_endpoint(OLLAMA_HOST) if GPT_OSS_AVAILABLE else False

# Claude API client (lazy load)
_claude_client = None

def get_claude_client():
    """Get or create Claude API client"""
    global _claude_client
    if _claude_client is None and ANTHROPIC_API_KEY:
        try:
            from anthropic import Anthropic
            _claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)
            logger.info("✅ Claude API client initialized")
        except ImportError:
            logger.error("❌ anthropic package not installed. Run: pip install anthropic")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to initialize Claude client: {e}")
            raise
    return _claude_client

async def claude_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """Claude API completion function compatible with LightRAG"""
    try:
        client = get_claude_client()
        
        # Build messages
        messages = []
        if history_messages:
            messages.extend(history_messages[-3:])  # Keep last 3 for context
        messages.append({"role": "user", "content": prompt})
        
        # Call Claude API
        response = client.messages.create(
            model=kwargs.get("model", "claude-3-5-sonnet-20241022"),
            max_tokens=kwargs.get("max_tokens", 4000),
            system=system_prompt if system_prompt else "You are a helpful assistant.",
            messages=messages,
            temperature=kwargs.get("temperature", 0.0)
        )
        
        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        raise

# Set Ollama host (for backward compatibility)
os.environ["OLLAMA_HOST"] = OLLAMA_HOST

if USE_GPT_OSS:
    logger.info(f"🎯 GPT-OSS detected: Using {OLLAMA_HOST}")
else:
    logger.info(f"🎯 Using Ollama: {OLLAMA_HOST}")

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
            
            # Select LLM provider based on configuration
            if LLM_PROVIDER == "claude":
                model_func = claude_model_complete
                model_kwargs = {"model": "claude-3-5-sonnet-20241022", "max_tokens": 4000}
                logger.info(f"✅ Using Claude API: claude-3-5-sonnet-20241022")
            elif GPT_OSS_AVAILABLE and (USE_GPT_OSS or LLM_PROVIDER == "gpt-oss"):
                model_func = get_model_func(OLLAMA_HOST)
                model_kwargs = {"options": {"num_ctx": 32768}, "host": OLLAMA_HOST}
                logger.info(f"✅ Using GPT-OSS: {OLLAMA_HOST}")
            else:
                from lightrag.llm.ollama import ollama_model_complete
                model_func = ollama_model_complete
                model_kwargs = {"options": {"num_ctx": 32768}, "host": OLLAMA_HOST}
                logger.info(f"✅ Using Ollama: {OLLAMA_HOST}")
            
            # Embeddings always use Ollama (free & fast)
            from lightrag.llm.ollama import ollama_embed
            def embedding_wrapper(texts):
                return ollama_embed(texts, embed_model=EMBED_MODEL, host=OLLAMA_HOST)
            
            rag_instance = LightRAG(
                working_dir=WORKING_DIR,
                llm_model_func=model_func,
                llm_model_name=LLM_MODEL,
                llm_model_kwargs=model_kwargs,
                embedding_func=EmbeddingFunc(
                    embedding_dim=768,
                    func=embedding_wrapper
                ),
            )
            await rag_instance.initialize_storages()
            await initialize_pipeline_status()
            
            provider = "GPT-OSS" if USE_GPT_OSS else "Ollama"
            logger.info(f"✅ LightRAG initialized with {provider} ({LLM_MODEL})")
        
        return rag_instance


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "lightrag",
        "host": OLLAMA_HOST,
        "llm_model": LLM_MODEL,
        "provider": "GPT-OSS" if USE_GPT_OSS else "Ollama",
        "embed_model": EMBED_MODEL
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
    
    # Increase chunk retrieval to work around strict similarity threshold
    # More chunks = better chance of passing the 0.2 filter
    param = QueryParam(
        mode=mode,
        chunk_top_k=200,  # Drastically increase to compensate for strict threshold
        top_k=80,  # Get more entities
        max_total_tokens=50000  # Allow more context
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

