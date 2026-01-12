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
from openai import AsyncOpenAI
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WORKING_DIR = os.getenv("LIGHTRAG_DIR", "./lightrag_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:32b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshotai/kimi-k2-0905")

# Set Ollama host
os.environ["OLLAMA_HOST"] = OLLAMA_HOST

# Global RAG instance and lock (initialized lazily)
rag_instance = None
rag_lock = None
_loop = None
SUPPORTED_EXTENSIONS = {".md", ".pdf"}


def get_or_create_loop():
    """Get or create a global event loop"""
    global _loop
    if _loop is None:
        try:
            _loop = asyncio.get_event_loop()
        except RuntimeError:
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
    return _loop


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning(f"pypdf not installed; skipping PDF: {pdf_path}")
        return ""

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        logger.warning(f"Failed to read PDF {pdf_path}: {e}")
        return ""

    pages_text = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            pages_text.append(f"[Page {page_index}]\n{page_text}")

    return "\n\n".join(pages_text).strip()


# Default system prompt for Michel's Obsidian Knowledge Base
DEFAULT_SYSTEM_PROMPT = """You are a **Deep Thinking AI assistant** integrated with Michel's Obsidian Knowledge Base.

Your task is to answer questions by analyzing the retrieved materials and Michel's personal context.

**CRITICAL INSTRUCTION**: You will be provided with relevant context from Michel's notes. Your job is to SYNTHESIZE and SUMMARIZE this information to answer the question. DO NOT claim "insufficient information" unless the retrieved context is genuinely empty or completely unrelated to the query.

When generating your answer:
1. **USE THE PROVIDED CONTEXT**: Synthesize information from the retrieved documents, chunks, and entities.
2. Reference Michel's specific **medical timeline** (DLBCL, Yescarta, scans) when relevant.
3. Incorporate insights from his **Obsidian notes**, citing which notes or sources you use.
4. Maintain a **compassionate and supportive** tone for medical topics.
5. Provide **technical depth** and precision for engineering and coding topics.
6. Adapt to his **expert-level understanding** — avoid overexplaining known concepts.
7. Be **concise but thorough**, focusing on clarity and reasoning.
8. Avoid redundant or generic phrasing.
9. **Ground answers in the notes**; avoid generic background not present in sources.
10. If the retrieved context is unrelated or missing, say "Not found in notes."

Finally, provide your answer in a structured, easy-to-read format."""

async def openrouter_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """OpenRouter API wrapper for LightRAG"""
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not set")
        return "Error: OPENROUTER_API_KEY not set"

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

    # Use provided system prompt or fall back to Michel's default prompt
    effective_system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    # DEBUG LOGGING
    debug_log_path = "/app/lightrag_db/prompt_debug.log"
    with open(debug_log_path, "a") as f:
        import datetime
        timestamp = datetime.datetime.now().isoformat()
        f.write(f"\n{'='*80}\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"System prompt provided: {system_prompt is not None}\n")
        f.write(f"Using DEFAULT_SYSTEM_PROMPT: {effective_system_prompt == DEFAULT_SYSTEM_PROMPT}\n")
        f.write(f"Effective system prompt:\n{effective_system_prompt}\n")
        f.write(f"User prompt (first 200 chars): {prompt[:200]}\n")
        f.write(f"Model: {KIMI_MODEL}\n")
        f.write(f"{'='*80}\n")

    messages = []
    if effective_system_prompt:
        messages.append({"role": "system", "content": effective_system_prompt})

    if history_messages:
        messages.extend(history_messages)

    messages.append({"role": "user", "content": prompt})
    
    # Filter kwargs to only include supported ones
    allowed_kwargs = ['temperature', 'max_tokens', 'top_p', 'response_format']
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_kwargs}
    
    try:
        response = await client.chat.completions.create(
            model=KIMI_MODEL,
            messages=messages,
            **filtered_kwargs
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenRouter API error: {e}")
        return f"Error: {str(e)}"


async def initialize_rag():
    """Initialize LightRAG instance at startup"""
    global rag_instance
    
    if rag_instance is None:
        logger.info(f"Initializing LightRAG at startup (Working Dir: {WORKING_DIR})...")
        try:
            logger.info("Step 1: Constructing LightRAG instance...")
            def wrapped_embed(texts):
                return ollama_embed.func(
                    texts,
                    embed_model=EMBED_MODEL,
                    host=OLLAMA_HOST,
                    options={"num_ctx": 16384}
                )

            ef = EmbeddingFunc(
                embedding_dim=768,
                func=wrapped_embed
            )
            
            rag_instance = LightRAG(
                working_dir=WORKING_DIR,
                llm_model_func=openrouter_model_complete,
                llm_model_name=KIMI_MODEL,
                llm_model_kwargs={"temperature": 0.1},
                embedding_func=ef,
                cosine_threshold=0.05,
                cosine_better_than_threshold=0.05,
                top_k=100,
                chunk_top_k=50,
                max_total_tokens=60000,
                embedding_func_max_async=2,
                llm_model_max_async=2,
                chunk_token_size=800,
                chunk_overlap_token_size=200,
            )
            logger.info("Step 2: Initializing storages...")
            await rag_instance.initialize_storages()
            logger.info("Step 3: Initializing pipeline status...")
            await initialize_pipeline_status()
            logger.info("✅ LightRAG initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize LightRAG at step: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise e

def get_rag():
    """Get the initialized LightRAG instance"""
    if rag_instance is None:
        raise RuntimeError("LightRAG not initialized. Check logs for startup errors.")
    return rag_instance


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "lightrag",
        "llm_model": KIMI_MODEL,
        "ollama_host": OLLAMA_HOST,
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
            "llm_model": KIMI_MODEL,  # Show the actual model being used
            "embed_model": EMBED_MODEL
        }

        if exists:
            # Count indexed notes from indexed_files.txt
            indexed_files_path = db_path / "indexed_files.txt"
            if indexed_files_path.exists():
                with open(indexed_files_path, 'r', encoding='utf-8') as f:
                    indexed_count = sum(1 for line in f if line.strip())
                stats_data["indexed_notes"] = indexed_count
            else:
                stats_data["indexed_notes"] = 0

            # Count database files
            db_files = [f for f in db_path.iterdir() if f.is_file()]
            stats_data["database_files"] = len(db_files)

            # Check for graph file
            graph_file = db_path / "graph_chunk_entity_relation.graphml"
            if graph_file.exists():
                import xml.etree.ElementTree as ET
                try:
                    tree = ET.parse(graph_file)
                    root = tree.getroot()
                    # Count nodes and edges in GraphML
                    ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}
                    nodes = root.findall('.//g:node', ns)
                    edges = root.findall('.//g:edge', ns)
                    stats_data["graph_nodes"] = len(nodes)
                    stats_data["graph_edges"] = len(edges)
                    stats_data["graph_size_mb"] = round(graph_file.stat().st_size / (1024*1024), 2)
                except Exception as e:
                    logger.warning(f"Could not parse graph file: {e}")

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
        
        # Run async insert using the initialized RAG
        async def do_insert():
            rag = get_rag()
            await rag.ainsert(texts)
        
        loop = get_or_create_loop()
        loop.run_until_complete(do_insert())
        
        return jsonify({
            "status": "success",
            "documents_inserted": len(texts)
        }), 200
    
    except Exception as e:
        logger.error(f"Insert error: {e}")
        return jsonify({"error": str(e)}), 500


async def _do_query_async(query_text, mode):
    """Helper async method for querying"""
    rag = get_rag()
    
    if mode in ['global', 'hybrid']:
        param = QueryParam(
            mode=mode,
            chunk_top_k=50,
            top_k=75,
            max_total_tokens=32000
        )
    else:
        param = QueryParam(
            mode=mode,
            chunk_top_k=100,
            top_k=150,
            max_total_tokens=60000
        )

    # Use LightRAG's in-library response path with a stronger system prompt
    result = await rag.aquery(query_text, param=param, system_prompt=DEFAULT_SYSTEM_PROMPT)
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
        
        # Run async query using run_until_complete on the shared loop
        loop = get_or_create_loop()
        result = loop.run_until_complete(_do_query_async(query_text, mode))
        
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
    """Index all markdown and PDF files from a vault directory (INCREMENTAL)"""
    try:
        data = request.json or {}
        vault_path = data.get('vault_path', './vault')
        force_reindex = data.get('force', False)  # Force full reindex if True

        vault_dir = Path(vault_path)
        if not vault_dir.exists():
            return jsonify({"error": f"Vault path not found: {vault_path}"}), 400

        # Load indexed files tracking
        indexed_files_path = Path(WORKING_DIR) / "indexed_files.txt"
        indexed_files = set()

        if indexed_files_path.exists() and not force_reindex:
            with open(indexed_files_path, 'r', encoding='utf-8') as f:
                indexed_files = set(line.strip() for line in f if line.strip())
            logger.info(f"Found {len(indexed_files)} already-indexed files")

        # Find all markdown and PDF files
        all_files = [
            path for path in vault_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        logger.info(f"Found {len(all_files)} total markdown/PDF files in vault")

        # Filter to only NEW files (not yet indexed)
        new_files = []
        for vault_file in all_files:
            # Try both absolute and relative paths for compatibility
            abs_path = str(vault_file)
            rel_path = str(vault_file.relative_to(vault_dir.parent))

            # Check if file is already indexed (check both path formats)
            already_indexed = abs_path in indexed_files or rel_path in indexed_files

            if force_reindex or not already_indexed:
                new_files.append((vault_file, abs_path))

        logger.info(f"Found {len(new_files)} NEW files to index")

        if not new_files:
            return jsonify({
                "status": "success",
                "message": "No new files to index",
                "total_files": len(all_files),
                "already_indexed": len(indexed_files),
                "newly_indexed": 0
            }), 200

        # Load content of new files only
        notes_to_index = []
        successfully_read = []

        for vault_file, file_path in new_files:
            try:
                if vault_file.suffix.lower() == ".pdf":
                    content = extract_pdf_text(vault_file)
                else:
                    with open(vault_file, "r", encoding="utf-8") as f:
                        content = f.read()

                content = content.strip()
                if content:
                    notes_to_index.append(content)
                    successfully_read.append(file_path)
            except Exception as e:
                logger.warning(f"Could not read {vault_file}: {e}")

        if not notes_to_index:
            return jsonify({"error": "No readable markdown/PDF files found"}), 400

        logger.info(f"Indexing {len(notes_to_index)} new files...")

        # Insert into LightRAG
        async def do_index():
            rag = get_rag()
            await rag.ainsert(notes_to_index)

        loop = get_or_create_loop()
        loop.run_until_complete(do_index())

        # Update indexed files tracking
        with open(indexed_files_path, 'a', encoding='utf-8') as f:
            for file_path in successfully_read:
                f.write(f"{file_path}\n")

        logger.info(f"✅ Successfully indexed {len(notes_to_index)} new files")
        logger.info(f"📊 Total indexed files now: {len(indexed_files) + len(successfully_read)}")

        return jsonify({
            "status": "success",
            "total_files": len(all_files),
            "already_indexed": len(indexed_files),
            "newly_indexed": len(notes_to_index),
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
🤖 LLM Model:   {KIMI_MODEL}
🔤 Embed Model: {EMBED_MODEL}
🌐 Ollama Host: {OLLAMA_HOST}

Endpoints:
  GET  /health        - Health check
  GET  /stats         - Database statistics
  POST /insert        - Insert documents
  POST /query         - Query knowledge graph
  POST /index-vault   - Index Obsidian vault
""")
    # Initialize RAG before starting the server
    try:
        loop = get_or_create_loop()
        loop.run_until_complete(initialize_rag())
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}")
        # Continue to start server so health checks can report error
        
    app.run(host='0.0.0.0', port=8001, debug=False)
