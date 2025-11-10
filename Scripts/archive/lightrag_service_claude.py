#!/usr/bin/env python3
"""
LightRAG Service with Claude API support
Best quality for knowledge graph generation
"""

import os
import asyncio
from pathlib import Path
from flask import Flask, request, jsonify
from lightrag import LightRAG, QueryParam
from lightrag.llm import openai_complete_if_cache, openai_embedding
from lightrag.utils import EmbeddingFunc
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WORKING_DIR = os.getenv("LIGHTRAG_DIR", "./lightrag_db")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")  # Set this in environment
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")  # OpenAI for embeddings

if not ANTHROPIC_API_KEY:
    raise ValueError("❌ ANTHROPIC_API_KEY environment variable required!")

# Global RAG instance
rag_instance = None
rag_lock = asyncio.Lock()


async def claude_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """Claude API wrapper for LightRAG"""
    import anthropic
    
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    # Get model from environment or default to Haiku 4.5 (best value!)
    model = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20250122")
    # Options: 
    # - "claude-haiku-4-5-20250122" (latest, cheap, fast) - RECOMMENDED!
    # - "claude-3-5-haiku-20241022" (previous version)
    # - "claude-3-5-sonnet-20241022" (premium, expensive)
    
    messages = []
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})
    
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt or "You are a helpful assistant.",
        messages=messages
    )
    
    return response.content[0].text


async def get_rag():
    """Get or create LightRAG instance with Claude"""
    global rag_instance
    
    async with rag_lock:
        if rag_instance is None:
            logger.info("Initializing LightRAG with Claude 3.5 Sonnet...")
            
            # Use OpenAI embeddings (faster and cheaper than Claude)
            os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", ANTHROPIC_API_KEY)
            
            rag_instance = LightRAG(
                working_dir=WORKING_DIR,
                llm_model_func=claude_model_complete,
                llm_model_name="claude-3-5-sonnet-20241022",
                embedding_func=EmbeddingFunc(
                    embedding_dim=1536,
                    max_token_size=8192,
                    func=lambda texts: openai_embedding(
                        texts,
                        model=EMBED_MODEL
                    )
                ),
            )
            await rag_instance.initialize_storages()
            logger.info("✅ LightRAG initialized with Claude API")
        
        return rag_instance


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "lightrag-claude",
        "llm_model": "claude-3.5-sonnet-20241022"
    }), 200


@app.route('/insert', methods=['POST'])
def insert_documents():
    """Insert documents into LightRAG knowledge graph"""
    try:
        data = request.json
        texts = data.get('texts', [])
        
        if not texts:
            return jsonify({"error": "No texts provided"}), 400
        
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


@app.route('/query', methods=['POST'])
def query_graph():
    """Query the knowledge graph"""
    try:
        data = request.json
        query_text = data.get('query')
        mode = data.get('mode', 'hybrid')
        
        if not query_text:
            return jsonify({"error": "No query provided"}), 400
        
        async def do_query():
            rag = await get_rag()
            param = QueryParam(mode=mode)
            result = await rag.aquery(query_text, param=param)
            return result
        
        result = asyncio.run(do_query())
        
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
    """Index all markdown files from vault"""
    try:
        data = request.json or {}
        vault_path = data.get('vault_path', './vault')
        
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
        
        logger.info(f"📚 Indexing {len(notes)} notes with Claude 3.5 Sonnet...")
        
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
    claude_model = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20250122")
    logger.info(f"""
╔══════════════════════════════════════════════════════════╗
║         LightRAG Service - Claude API Edition            ║
╚══════════════════════════════════════════════════════════╝

📂 Working Dir: {WORKING_DIR}
🤖 LLM Model:   {claude_model}
🔤 Embed Model: {EMBED_MODEL}
🔑 API Key:     {'✅ Set' if ANTHROPIC_API_KEY else '❌ Missing'}

💡 Using Haiku 4.5? ~$1-2 for 1600 notes (LATEST & RECOMMENDED!)
💎 Using Sonnet 3.5? ~$15 for 1600 notes (premium quality)

⚡ High-quality entity extraction
⚡ Fast cloud processing
⚡ Zero local RAM usage

Endpoints:
  GET  /health        - Health check
  POST /insert        - Insert documents  
  POST /query         - Query knowledge graph
  POST /index-vault   - Index Obsidian vault

Starting server...
""")
    
    app.run(host='0.0.0.0', port=8001, debug=False)

