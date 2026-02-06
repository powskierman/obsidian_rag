#!/usr/bin/env python3
"""
LightRAG Service - Flask API for Graph-based RAG
Provides hybrid search combining knowledge graphs with vector similarity
"""

import os
import json
import asyncio
import re
import time
import threading
from pathlib import Path
from flask import Flask, request, jsonify
from lightrag import LightRAG, QueryParam
from lightrag.llm.ollama import ollama_model_complete, ollama_embed
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status
from openai import AsyncOpenAI
import logging
import datetime
import nest_asyncio
nest_asyncio.apply()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
# Aggressively suppress pypdf warnings
try:
    import pypdf
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    logging.getLogger("pypdf._reader").setLevel(logging.ERROR)
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Configuration
WORKING_DIR = os.getenv("LIGHTRAG_DIR", "./lightrag_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:32b")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshotai/kimi-k2-0905")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "lmstudio")
LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH")
QUERY_TIMEOUT_SECONDS = int(os.getenv("RAG_QUERY_TIMEOUT", "10"))
INIT_WAIT_SECONDS = int(os.getenv("RAG_INIT_WAIT", "15"))
EMBED_ASYNC = int(os.getenv("EMBED_ASYNC", "4"))
LLM_ASYNC = int(os.getenv("LLM_ASYNC", "4"))
LIGHTRAG_BATCH_SIZE = int(os.getenv("LIGHTRAG_BATCH_SIZE", "10"))
LIGHTRAG_BATCH_TIMEOUT = float(os.getenv("LIGHTRAG_BATCH_TIMEOUT", "600"))
LIGHTRAG_CHUNK_TOKENS = int(os.getenv("LIGHTRAG_CHUNK_TOKENS", "128"))
LIGHTRAG_CHUNK_OVERLAP = int(os.getenv("LIGHTRAG_CHUNK_OVERLAP", "32"))
LIGHTRAG_MAX_DOC_CHARS = int(os.getenv("LIGHTRAG_MAX_DOC_CHARS", "0"))
LLM_MAX_TOKENS = os.getenv("LLM_MAX_TOKENS")
LLM_TEMPERATURE = os.getenv("LLM_TEMPERATURE")

# Set Ollama host
os.environ["OLLAMA_HOST"] = OLLAMA_HOST

# Global RAG instance and lock (initialized lazily)
rag_instance = None
rag_lock = threading.Lock()
init_lock = threading.Lock()
init_started = False
init_error = None
storages_ready = False
_chunks_cache = {"mtime": None, "data": None}
index_progress = {
    "status": "idle",
    "total_files": 0,
    "to_index": 0,
    "indexed": 0,
    "batch_size": 0,
    "current_batch": 0,
    "started_at": None,
    "finished_at": None,
    "error": None,
}
index_progress_lock = threading.Lock()

SUPPORTED_EXTENSIONS = {".md", ".pdf"}
INLINE_TAG_PATTERN = re.compile(r"(?<!\\w)#([A-Za-z0-9][A-Za-z0-9/_-]*)")

# LightRAG Constants
COSINE_THRESHOLD = 0.6
COSINE_BETTER_THAN_THRESHOLD = 0.5

# Removed global loop management
# def get_or_create_loop(): ...


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

    text = "\n\n".join(pages_text).strip()
    # Basic cleanup
    text = re.sub(r'\bPage \d+ of \d+\b', '', text)
    return text

from src.indexing.frontmatter import extract_frontmatter, sanitize_content, _dedupe_keep_order


def _truncate_for_extraction(content: str) -> str:
    """Trim oversized documents before LightRAG chunking/extraction to avoid worker timeouts."""
    if LIGHTRAG_MAX_DOC_CHARS <= 0:
        return content
    if len(content) <= LIGHTRAG_MAX_DOC_CHARS:
        return content
    return content[:LIGHTRAG_MAX_DOC_CHARS]

def _reset_corrupt_lightrag_storage(working_dir: str) -> None:
    """Remove corrupt JSON storage files so LightRAG can reinitialize cleanly."""
    try:
        wd = Path(working_dir)
        if not wd.exists():
            return
        for json_file in wd.glob("*.json"):
            try:
                json_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove {json_file}: {e}")
    except Exception as e:
        logger.warning(f"Failed to reset LightRAG storage: {e}")

def _split_frontmatter(content: str) -> tuple[list[str], list[str], str]:
    """Compatibility wrapper using shared utility"""
    metadata, body = extract_frontmatter(content)
    return metadata.get("tags", []), metadata.get("aliases", []), body

def _extract_headings(content: str, max_headings: int = 12) -> list[str]:
    headings = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(stripped.split()[0])
            heading_text = stripped.lstrip("#").strip()
            if heading_text:
                # Hierarchical format: H1: Title
                headings.append(f"H{level}: {heading_text}")
        if len(headings) >= max_headings:
            break
    return _dedupe_keep_order(headings)

def _extract_inline_tags(content: str) -> list[str]:
    tags = []
    in_code_block = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or stripped.startswith("#"):
            continue
        for match in INLINE_TAG_PATTERN.finditer(line):
            tags.append(match.group(1))
    return _dedupe_keep_order(tags)

def _build_index_text(
    file_path: Path,
    content: str,
    headings: list[str],
    tags: list[str],
    aliases: list[str],
    vault_root: Path = None
) -> str:
    content = content.strip()
    if not content:
        return ""
    
    # Calculate note ID and folder
    if vault_root:
        try:
            rel_path = file_path.relative_to(vault_root)
            note_id = str(rel_path)
            folder = str(rel_path.parent) if rel_path.parent != Path('.') else "/"
        except ValueError:
            note_id = file_path.name
            folder = "unknown"
    else:
        note_id = file_path.name
        folder = "unknown"

    prefix_lines = [
        f"Title: {file_path.stem}",
        f"Filename: {file_path.name}",
        f"NoteID: {note_id}",
        f"Folder: {folder}"
    ]
    if headings:
        prefix_lines.append("Headings: " + " | ".join(headings))
    if tags:
        prefix_lines.append("Tags: " + ", ".join(tags))
    if aliases:
        prefix_lines.append("Aliases: " + ", ".join(aliases))
    prefix = "\n".join(prefix_lines)
    return f"{prefix}\n\n{content}"

def _choose_query_mode(query_text: str, requested_mode: str) -> str:
    # 1. Force naive for extremely short queries
    tokens = re.findall(r"[\w/-]+", query_text)
    if len(tokens) <= 2 and requested_mode in {"local", "global", "hybrid"}:
        logger.info(f"Query '{query_text}' is too short ({len(tokens)} tokens) -> Mode: naive")
        return "naive"

    # 2. Heuristics for Local vs Global
    # If the user explicitly asks for "overview", "compare", "timeline" -> Global
    global_keywords = ["overview", "summary", "compare", "timeline", "history of", "relationship between"]
    lower_query = query_text.lower()
    if any(k in lower_query for k in global_keywords) and requested_mode == "hybrid":
        logger.info(f"Query contains global keywords -> Mode: global")
        return "global"

    # If the query contains specific Capitalized Entities (likely note titles) -> Local
    # We look for Capitalized Words that are not at the start of the sentence
    # (Simplified: just check for capitalized words > 3 chars that aren't typical stopwords)
    # This is rough, but effective for things like "What is Yescarta?"
    if requested_mode == "hybrid":
        # Check for specific capitalized content indicators
        if re.search(r'\b[A-Z][a-zA-Z0-9-]{2,}\b', query_text):
             # If it looks like a specific entity query, lean local
            logger.info("Query contains potential entities -> Mode: local")
            return "local"

    return requested_mode

def _is_not_found_result(result_text: str) -> bool:
    if not result_text:
        return True
    text = result_text.strip().lower()
    
    # Reject standard failure patterns
    rejection_phrases = [
        "not found in notes",
        "i am sorry", 
        "i'm sorry",
        "does not contain information",
        "no information found",
        "no relevant information",
        "no entities found"
    ]
    
    if any(phrase in text for phrase in rejection_phrases):
        logger.info(f"Refusing result because it matches rejection phrase: {text[:100]}...")
        return True

    # Reject placeholders/speculation to prevent hallucinations
    speculation_markers = [
        "likely",
        "probably",
        "maybe",
        "might",
        "unknown",
        "institution name",
        "or specific regimen",
    ]
    if any(marker in text for marker in speculation_markers):
        logger.info(f"Refusing result because it contains speculation: {text[:100]}...")
        return True
    if re.search(r"\[[^\]]+\]", text):
        logger.info(f"Refusing result because it contains placeholders: {text[:100]}...")
        return True
        
    return False


def _extract_note_title_and_excerpt(content: str, max_chars: int = 400) -> tuple[str, str]:
    title = ""
    filename = ""
    note_id = ""
    for line in content.splitlines():
        if line.startswith("Title:"):
            title = line.split(":", 1)[1].strip()
        elif line.startswith("Filename:"):
            filename = line.split(":", 1)[1].strip()
        elif line.startswith("NoteID:"):
            note_id = line.split(":", 1)[1].strip()
        if title:
            break
    if not title:
        if filename:
            title = filename.rsplit(".", 1)[0]
        elif note_id:
            title = note_id.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    excerpt = content.strip().replace("\n", " ")
    if len(excerpt) > max_chars:
        excerpt = excerpt[:max_chars] + "..."
    return title, excerpt


def _load_chunks_cache():
    chunks_path = Path(WORKING_DIR) / "kv_store_text_chunks.json"
    if not chunks_path.exists():
        return None
    try:
        mtime = chunks_path.stat().st_mtime
    except Exception:
        return None
    if _chunks_cache["data"] is not None and _chunks_cache["mtime"] == mtime:
        return _chunks_cache["data"]
    try:
        with open(chunks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _chunks_cache["data"] = data
        _chunks_cache["mtime"] = mtime
        return data
    except Exception as e:
        logger.warning(f"Failed to load text chunks: {e}")
        return None


def _local_extractive_search(query_text: str, max_hits: int = 3) -> list[dict]:
    """Return top matching chunks without LLM generation."""
    terms = [t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9/._-]{1,}", query_text) if len(t) > 2]
    if not terms:
        return []

    data = _load_chunks_cache()
    if not data:
        return []

    scored = []
    for _, entry in data.items():
        if not isinstance(entry, dict):
            continue
        content = entry.get("content", "")
        if not content:
            continue
        hay = content.lower()
        title, excerpt = _extract_note_title_and_excerpt(content)
        title_lower = (title or "").lower()
        title_score = sum(1 for t in terms if t in title_lower)
        body_score = sum(1 for t in terms if t in hay)
        score = body_score + (title_score * 3)
        if score:
            scored.append((score, title, excerpt))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, title, excerpt in scored[:max_hits]:
        results.append({
            "title": title or "Unknown",
            "score": score,
            "excerpt": excerpt
        })
    return results


# Default system prompt for Michel's Obsidian Knowledge Base
DEFAULT_SYSTEM_PROMPT = """You are an assistant integrated with Michel's Obsidian Knowledge Base.

Your job is to answer ONLY from the retrieved context. Do not use outside knowledge.

STRICT REQUIREMENTS:
1) If the retrieved context does NOT explicitly contain the answer, respond exactly: "Not found in notes."
2) Do not guess, infer dates, or add background details not present in the retrieved context.
3) Quote or paraphrase ONLY what is in the retrieved context and name the note(s) you used.
4) If multiple notes conflict, state the conflict and cite each note.

When generating your answer:
- Use the provided chunks/entities/relations as the sole source of truth.
- Keep the response concise and factual.
- For medical topics, keep a neutral, supportive tone without adding new medical claims.

Return a structured answer (bullet points preferred)."""


def get_effective_llm_model():
    if LLM_PROVIDER == "openrouter":
        return KIMI_MODEL or "openrouter"
    if LLM_PROVIDER == "lmstudio":
        return LLM_MODEL_PATH or LLM_MODEL
    return LLM_MODEL


def get_effective_llm_provider():
    if LLM_PROVIDER == "openrouter":
        return "openrouter"
    if LLM_PROVIDER == "lmstudio":
        return "lmstudio"
    return "ollama"


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
        # Add timeout to OpenRouter calls to prevent hanging
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=KIMI_MODEL,
                messages=messages,
                **filtered_kwargs
            ),
            timeout=120.0 # 2 minute timeout for generation
        )
        return response.choices[0].message.content
    except asyncio.TimeoutError:
        logger.error("OpenRouter API timed out")
        return "Error: Timeout waiting for LLM response"
    except Exception as e:
        logger.error(f"OpenRouter API error: {e}")
        return f"Error: {str(e)}"


async def lmstudio_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """LM Studio OpenAI-compatible API wrapper for LightRAG"""
    client = AsyncOpenAI(
        base_url=LMSTUDIO_BASE_URL,
        api_key=LMSTUDIO_API_KEY,
    )

    effective_system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    messages = []
    if effective_system_prompt:
        messages.append({"role": "system", "content": effective_system_prompt})

    if history_messages:
        messages.extend(history_messages)

    messages.append({"role": "user", "content": prompt})

    allowed_kwargs = ['temperature', 'max_tokens', 'top_p', 'response_format']
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_kwargs}

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=LLM_MODEL_PATH or LLM_MODEL,
                messages=messages,
                **filtered_kwargs
            ),
            timeout=120.0
        )
        return response.choices[0].message.content
    except asyncio.TimeoutError:
        logger.error("LM Studio API timed out")
        return "Error: Timeout waiting for LLM response"
    except Exception as e:
        logger.error(f"LM Studio API error: {e}")
        return f"Error: {str(e)}"


async def initialize_rag():
    """Initialize LightRAG instance at startup"""
    global rag_instance
    
    if rag_instance is None:
        logger.info(f"Initializing LightRAG at startup (Working Dir: {WORKING_DIR})...")
        try:
            logger.info("Step 1: Constructing LightRAG instance...")
            def wrapped_embed(texts):
                # Pre-truncate to avoid Ollama context-length errors.
                safe_texts = [t[:8000] if isinstance(t, str) else t for t in texts]
                try:
                    return ollama_embed.func(
                        safe_texts,
                        embed_model=EMBED_MODEL,
                        host=OLLAMA_HOST,
                        options={"num_ctx": 8192} 
                    )
                except Exception as e:
                    # Fallback for "context length exceeded" or other errors
                    logger.warning(f"Embedding failed (likely context length): {e}. Retrying with truncation...")
                    truncated_texts = [t[:8000] for t in texts] # Truncate more aggressively for safety
                    try:
                         return ollama_embed.func(
                            truncated_texts,
                            embed_model=EMBED_MODEL,
                            host=OLLAMA_HOST,
                            options={"num_ctx": 8192}
                        )
                    except Exception as e2:
                        logger.error(f"Embedding failed even after truncation: {e2}")
                        # Return zero vectors or raise? 
                        # LightRAG expects a list of numpy arrays. We'll let it raise to avoid silent data corruption.
                        raise e2

            ef = EmbeddingFunc(
                embedding_dim=768,
                func=wrapped_embed
            )
            
            if LLM_PROVIDER == "openrouter":
                rag_llm_func = openrouter_model_complete
                rag_llm_model = KIMI_MODEL
            elif LLM_PROVIDER == "lmstudio":
                rag_llm_func = lmstudio_model_complete
                rag_llm_model = LLM_MODEL_PATH or LLM_MODEL
            else:
                rag_llm_func = ollama_model_complete
                rag_llm_model = LLM_MODEL
            llm_kwargs = {}
            if LLM_MAX_TOKENS:
                try:
                    llm_kwargs["max_tokens"] = int(LLM_MAX_TOKENS)
                except ValueError:
                    pass
            if LLM_TEMPERATURE:
                try:
                    llm_kwargs["temperature"] = float(LLM_TEMPERATURE)
                except ValueError:
                    pass



            # Define initialization logic as a function to support retry
            async def _init_rag_and_storages():
                 # 1. Create instance (this loads NanoVectorDB which might fail if corrupt)
                 rag = LightRAG(
                    working_dir=WORKING_DIR,
                    llm_model_func=rag_llm_func,
                    llm_model_name=rag_llm_model,
                    llm_model_kwargs=llm_kwargs,
                    embedding_func=ef,
                    cosine_threshold=COSINE_THRESHOLD,
                    cosine_better_than_threshold=COSINE_BETTER_THAN_THRESHOLD,
                    top_k=100,
                    chunk_top_k=50,
                    max_total_tokens=60000,
                    embedding_func_max_async=EMBED_ASYNC,
                    llm_model_max_async=LLM_ASYNC,
                    chunk_token_size=LIGHTRAG_CHUNK_TOKENS,
                    chunk_overlap_token_size=LIGHTRAG_CHUNK_OVERLAP,
                )
                 # 2. Add extra storages if needed
                 logger.info("Step 2: Initializing storages...")
                 await rag.initialize_storages()
                 return rag

            try:
                rag = await _init_rag_and_storages()
            except Exception as e:
                err_str = str(e)
                if "Extra data" in err_str or "Expecting value" in err_str or "JSON" in type(e).__name__:
                     logger.error(f"Corrupt LightRAG storage detected during init: {e}. Resetting JSON stores.")
                     _reset_corrupt_lightrag_storage(WORKING_DIR)
                     # Retry once
                     rag = await _init_rag_and_storages()
                else:
                    raise e
            logger.info("Step 3: Initializing pipeline status...")
            await initialize_pipeline_status()
            
            logger.info("✅ LightRAG initialized successfully")
            
            logger.info("✅ LightRAG initialized successfully")
            
            # Only assign to global once fully initialized
            rag_instance = rag
            global storages_ready
            storages_ready = True
        except Exception as e:
            logger.error(f"❌ Failed to initialize LightRAG at step: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise e

def _start_background_init():
    """Kick off LightRAG initialization in a background thread once per process."""
    global init_started, init_error
    with init_lock:
        if init_started:
            return
        init_started = True
        def _runner():
            global init_error
            try:
                asyncio.run(initialize_rag())
            except Exception as e:
                init_error = e
        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()


def get_rag():
    """Get the initialized LightRAG instance or wait briefly for init."""
    global rag_instance
    if rag_instance is None:
        _start_background_init()
        waited = 0.0
        while rag_instance is None and waited < INIT_WAIT_SECONDS:
            time.sleep(0.1)
            waited += 0.1
        if rag_instance is None:
            raise RuntimeError("LightRAG initializing")
    return rag_instance


async def _ensure_storages_ready(rag: LightRAG):
    global storages_ready
    if not storages_ready:
        await rag.initialize_storages()
        storages_ready = True


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "lightrag",
        "llm_model": get_effective_llm_model(),
        "llm_provider": get_effective_llm_provider(),
        "ollama_host": OLLAMA_HOST,
        "embed_model": EMBED_MODEL,
        "ready": rag_instance is not None
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
            "llm_model": get_effective_llm_model(),  # Show the actual model being used
            "llm_provider": get_effective_llm_provider(),
            "embed_model": EMBED_MODEL
        }

        if exists:
            # Count indexed notes from indexed_files.txt
            indexed_files_path = db_path / "indexed_files.txt"
            if indexed_files_path.exists():
                with open(indexed_files_path, 'r', encoding='utf-8') as f:
                    indexed_count = sum(1 for line in f if line.strip())
                stats_data["indexed_notes"] = indexed_count
                stats_data["last_index_time"] = datetime.datetime.fromtimestamp(indexed_files_path.stat().st_mtime).isoformat()
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
                    # Quick size check only to avoid parsing huge XML on every stat call
                    stats_data["graph_size_mb"] = round(graph_file.stat().st_size / (1024*1024), 2)
                    
                    # Only parse if file is smallish (< 50MB) to avoid blocking
                    if stats_data["graph_size_mb"] < 50: 
                        tree = ET.parse(graph_file)
                        root = tree.getroot()
                        ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}
                        nodes = root.findall('.//g:node', ns)
                        edges = root.findall('.//g:edge', ns)
                        stats_data["graph_nodes"] = len(nodes)
                        stats_data["graph_edges"] = len(edges)
                    else:
                        stats_data["graph_nodes"] = "Too large to count live"
                        stats_data["graph_edges"] = "Too large to count live"
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
            await _ensure_storages_ready(rag)
            await initialize_pipeline_status()
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
    rag = get_rag()
    await _ensure_storages_ready(rag)
    
    if mode in ['global', 'hybrid']:
        param = QueryParam(
            mode=mode,
            chunk_top_k=10,
            top_k=15,
            max_total_tokens=6000,
            enable_rerank=False
        )
    elif mode == 'naive':
         param = QueryParam(
            mode=mode,
            chunk_top_k=20,
            top_k=20,
            max_total_tokens=16000, # Limit naive cost
            enable_rerank=False
        )
    else:
        # Local: use vector chunks for better note-text grounding
        param = QueryParam(
            mode="naive",
            chunk_top_k=30,
            top_k=40,
            max_total_tokens=16000,
            enable_rerank=False
        )

    # Use LightRAG's in-library response path with a stronger system prompt
    result = await rag.aquery(query_text, param=param, system_prompt=DEFAULT_SYSTEM_PROMPT)
    return result

def _run_query_with_timeout(query_text: str, mode: str):
    """Run async query with a hard timeout to avoid blocking the server."""
    async def _runner():
        return await asyncio.wait_for(_do_query_async(query_text, mode), timeout=QUERY_TIMEOUT_SECONDS)
    return asyncio.run(_runner())




@app.route('/query', methods=['POST'])
def query_graph():
    """Query the knowledge graph using LightRAG"""
    try:
        data = request.json
        query_text = data.get('query')
        mode = data.get('mode', 'hybrid')  # naive, local, global, or hybrid
        force_mode = bool(data.get('force_mode', False))
        require_llm = bool(data.get('require_llm', False))
        
        if not query_text:
            return jsonify({"error": "No query provided"}), 400
        
        # Validate mode
        valid_modes = ['naive', 'local', 'global', 'hybrid']
        if mode not in valid_modes:
            return jsonify({"error": f"Invalid mode. Use: {valid_modes}"}), 400
        
        logging.info(f"Incoming query: '{query_text}' | Requested mode: '{mode}'")
        if not force_mode:
            mode = _choose_query_mode(query_text, mode)
        logging.info(f"Effective mode after heuristic: '{mode}'")
        
        start_time = time.time()
        llm_used = False
        fallback_used = False

        # Local mode: return extractive chunks without LLM
        if mode == "local":
            fallback_used = True
            if require_llm:
                return jsonify({"error": "require_llm=true is incompatible with mode=local", "llm_used": False, "fallback_used": True}), 400
            hits = _local_extractive_search(query_text, max_hits=3)
            result = hits if hits else "Not found in notes."
        else:
            # Run async query with timeout; fall back to extractive sources on timeout/failure unless require_llm is set
            try:
                result = _run_query_with_timeout(query_text, mode)
                llm_used = True
            except asyncio.TimeoutError:
                if require_llm:
                    return jsonify({"error": f"LLM timeout after {QUERY_TIMEOUT_SECONDS}s", "llm_used": False, "fallback_used": True}), 504
                logger.warning(f"Query timed out after {QUERY_TIMEOUT_SECONDS}s; returning sources-only fallback.")
                fallback_used = True
                hits = _local_extractive_search(query_text, max_hits=3)
                result = hits if hits else "Not found in notes."
            except Exception as e:
                if require_llm:
                    status = 503 if "initializing" in str(e).lower() else 502
                    return jsonify({"error": f"LLM error: {e}", "llm_used": False, "fallback_used": True}), status
                logger.error(f"Async query failed: {e}")
                fallback_used = True
                hits = _local_extractive_search(query_text, max_hits=3)
                result = hits if hits else "Not found in notes."

        if isinstance(result, str) and _is_not_found_result(result):
            result = "Not found in notes."
            
        # Log query performance
        elapsed = time.time() - start_time
        logger.info(f"QUERY_STATS: Mode={mode} | Latency={elapsed:.2f}s | ResultLen={len(str(result))}")
        
        return jsonify({
            "query": query_text,
            "mode": mode,
            "result": result,
            "latency": elapsed,
            "llm_used": llm_used,
            "fallback_used": fallback_used
        }), 200
    
    except Exception as e:
        logger.error(f"Query error: {e}")
        return jsonify({"error": str(e)}), 500


    except Exception as e:
        logger.error(f"Query error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/index-vault', methods=['POST'])
def index_vault():
    """Index all markdown and PDF files from a vault directory (INCREMENTAL with mtime)"""
    try:
        with index_progress_lock:
            index_progress.update({
                "status": "starting",
                "total_files": 0,
                "to_index": 0,
                "indexed": 0,
                "batch_size": 0,
                "current_batch": 0,
                "started_at": datetime.datetime.now().isoformat(),
                "finished_at": None,
                "error": None,
            })

        data = request.json or {}
        vault_path = data.get('vault_path', './vault')
        force_reindex = data.get('force', False)
        max_files = data.get('max_files', 0) # 0 means unlimited

        Path(WORKING_DIR).mkdir(parents=True, exist_ok=True)
        
        vault_dir = Path(vault_path)
        if not vault_dir.exists():
            return jsonify({"error": f"Vault path not found: {vault_path}"}), 400

        # Load indexed files tracking: path|mtime
        indexed_files_path = Path(WORKING_DIR) / "indexed_files.txt"
        
        # Map: file_path -> last_mtime
        indexed_files_state = {}

        if indexed_files_path.exists() and not force_reindex:
            try:
                with open(indexed_files_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        if "|" in line:
                            parts = line.split("|")
                            if len(parts) >= 2:
                                indexed_files_state[parts[0]] = float(parts[1])
                        else:
                            # Backward compatibility: treat as old entry with mtime=0 to force reindex if real file is newer
                            indexed_files_state[line] = 0.0
                logger.info(f"Found {len(indexed_files_state)} tracked files in index history")
            except Exception as e:
                logger.warning(f"Error reading indexed_files.txt: {e}. Starting fresh.")
                indexed_files_state = {}

        # Scan for files
        all_files = [
            path for path in vault_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        logger.info(f"Found {len(all_files)} total markdown/PDF files in vault")
        with index_progress_lock:
            index_progress["total_files"] = len(all_files)

        # Determine what needs indexing
        notes_to_index = []
        new_state_entries = []

        count = 0
        for vault_file in all_files:
            if max_files > 0 and count >= max_files:
                break
                
            abs_path = str(vault_file)
            try:
                current_mtime = vault_file.stat().st_mtime
            except FileNotFoundError:
                continue

            # Check if needs update
            # Reindex if: force=True, or not in state, or current_mtime > stored_mtime
            stored_mtime = indexed_files_state.get(abs_path)
            
            if force_reindex or stored_mtime is None or current_mtime > stored_mtime:
                try:
                    # Process Content
                    if vault_file.suffix.lower() == ".pdf":
                        raw_text = extract_pdf_text(vault_file)
                        # PDFs don't have frontmatter, so we construct synthetic structure
                        # Use file path for folder structure
                        tags = ["#pdf"]
                        # Build index text
                        content = _build_index_text(
                            vault_file, raw_text, [], tags, [], vault_root=vault_dir
                        )
                    else:
                        try:
                            with open(vault_file, "r", encoding="utf-8") as f:
                                raw_content = f.read()
                        except UnicodeDecodeError:
                            logger.warning(f"UTF-8 decode failed for {vault_file}, trying latin-1")
                            with open(vault_file, "r", encoding="latin-1") as f:
                                raw_content = f.read()
                        tags, aliases, body = _split_frontmatter(raw_content)
                        body = sanitize_content(body) # Clean Obsidian artifacts
                        inline_tags = _extract_inline_tags(body)
                        tags = _dedupe_keep_order(tags + inline_tags)
                        headings = _extract_headings(body)
                        content = _build_index_text(
                            vault_file, body, headings, tags, aliases, vault_root=vault_dir
                        )

                    content = content.strip()
                    if content:
                        content = _truncate_for_extraction(content)
                        notes_to_index.append(content)
                        new_state_entries.append((abs_path, current_mtime))
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to process {vault_file}: {e}")
            else:
                # Up to date, keep existing state
                pass

        logger.info(f"determined {len(notes_to_index)} files need indexing/re-indexing")
        with index_progress_lock:
            index_progress["to_index"] = len(notes_to_index)

        if not notes_to_index:
            with index_progress_lock:
                index_progress.update({
                    "status": "completed",
                    "finished_at": datetime.datetime.now().isoformat(),
                })
            return jsonify({
                "status": "success",
                "message": "Index is up to date",
                "total_files": len(all_files),
                "newly_indexed": 0
            }), 200

        # Insert into LightRAG in batches to prevent stalling and improve progress visibility
        async def do_index():
            rag = get_rag()
            # Ensure initialization in the current loop
            await rag.initialize_storages()
            await initialize_pipeline_status()
            
            BATCH_SIZE = max(1, LIGHTRAG_BATCH_SIZE)
            total = len(notes_to_index)
            with index_progress_lock:
                index_progress["batch_size"] = BATCH_SIZE
            
            for i in range(0, total, BATCH_SIZE):
                batch = notes_to_index[i : i + BATCH_SIZE]
                with index_progress_lock:
                    index_progress["status"] = "running"
                    index_progress["current_batch"] = (i // BATCH_SIZE) + 1
                logger.info(f"STARTING BATCH {i+1} to {min(i+BATCH_SIZE, total)} of {total} documents")
                try:
                     # Use wait_for to enforce a hard timeout per batch (e.g. 5 minutes)
                    await asyncio.wait_for(rag.ainsert(batch), timeout=LIGHTRAG_BATCH_TIMEOUT)
                    with index_progress_lock:
                        index_progress["indexed"] += len(batch)
                    logger.info(f"COMPLETED BATCH {i+1} to {min(i+BATCH_SIZE, total)}")
                except asyncio.TimeoutError:
                    logger.error(f"BATCH {i+1} TIMED OUT! Skipping this batch of {len(batch)} documents.")
                except Exception as e:
                    logger.error(f"BATCH {i+1} FAILED: {e}")
        
        asyncio.run(do_index())

        # Update persistent state
        # We merge new state entries with existing state (overwriting updated ones)
        for path, mtime in new_state_entries:
            indexed_files_state[path] = mtime
            
        # Write back full state
        with open(indexed_files_path, 'w', encoding='utf-8') as f:
            for path, mtime in indexed_files_state.items():
                f.write(f"{path}|{mtime}\n")

        with index_progress_lock:
            index_progress.update({
                "status": "completed",
                "finished_at": datetime.datetime.now().isoformat(),
            })

        return jsonify({
            "status": "success",
            "total_files": len(all_files),
            "newly_indexed": len(notes_to_index),
            "vault_path": vault_path
        }), 200

    except Exception as e:
        logger.error(f"Index vault error: {e}")
        with index_progress_lock:
            index_progress.update({
                "status": "error",
                "error": str(e),
                "finished_at": datetime.datetime.now().isoformat(),
            })
        return jsonify({"error": str(e)}), 500


@app.route('/index-progress', methods=['GET'])
def index_progress_status():
    """Get current indexing progress (best-effort, per-process)."""
    with index_progress_lock:
        snapshot = dict(index_progress)
    return jsonify(snapshot), 200


if __name__ == '__main__':
    logger.info(f"""
╔══════════════════════════════════════════════════════════╗
║          LightRAG Service - Knowledge Graph RAG          ║
╚══════════════════════════════════════════════════════════╝

📂 Working Dir: {WORKING_DIR}
🤖 LLM Model:   {get_effective_llm_model()} ({get_effective_llm_provider()})
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
        # Initialize global RAG instance
        asyncio.run(initialize_rag())
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}")
        # Continue to start server so health checks can report error
        
    app.run(host='0.0.0.0', port=8001, debug=False, threaded=True)
