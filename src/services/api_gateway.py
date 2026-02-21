import os
import httpx
import json
import asyncio
import anthropic
import uvicorn
import math
import re
import time
import sys
from fastapi import FastAPI, WebSocket, Request, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

# Import CascadingRetriever - handle both package and direct execution
try:
    from cascading_retriever import CascadingRetriever
except ImportError:
    from src.services.cascading_retriever import CascadingRetriever


def _load_deep_thinking_rag():
    """Lazy-load DeepThinkingRAG to avoid heavy ML imports during test collection."""
    try:
        from deep_thinking.orchestrator import DeepThinkingRAG

        return DeepThinkingRAG
    except ImportError:
        import sys

        base_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        sys.path.append(base_path)
        sys.path.append(base_path)
        from deep_thinking.orchestrator import DeepThinkingRAG

        return DeepThinkingRAG


def _apply_relevance_filter(sources: Any, threshold: float) -> Any:
    if not isinstance(sources, list):
        return sources
    if not threshold or threshold <= 0:
        return sources
    filtered = []
    for src in sources:
        if not isinstance(src, dict):
            filtered.append(src)
            continue
        try:
            relevance = float(src.get("relevance", 0))
        except (TypeError, ValueError):
            filtered.append(src)
            continue
        if relevance >= threshold:
            filtered.append(src)
    return filtered


def _filter_result_sources(result: Any, threshold: float) -> Any:
    if not isinstance(result, dict):
        return result
    sources = result.get("sources")
    if isinstance(sources, list):
        result["sources"] = _apply_relevance_filter(sources, threshold)
    # LightRAG responses may not have sources field - don't break them
    elif sources is None:
        pass  # Keep result as-is
    return result


def _lightrag_result_text(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    text = result.get("result")
    if isinstance(text, str):
        return text
    answer = result.get("answer")
    return answer if isinstance(answer, str) else ""


def _sanitize_lightrag_answer_text(text: str) -> str:
    """Defensive cleanup for stale/older LightRAG synthesis responses."""
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    summary_match = re.search(r"(?im)^\s*summary\s*:?\s*$", cleaned)
    if summary_match and summary_match.start() > 0:
        cleaned = cleaned[summary_match.start():].lstrip()

    filtered: List[str] = []
    for line in cleaned.splitlines():
        low = line.strip().lower()
        if re.match(r"^i(?:'ll| will)\s+(?:search|look|analy[sz]e)\b", low):
            continue
        if "based on limited retrieved context" in low:
            continue
        if "consultation with a healthcare professional" in low:
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


_SYSTEM_PROMPT_PLACEHOLDER_RE = re.compile(r"(?<!{){([A-Za-z_][A-Za-z0-9_]*)}(?!})")
_SYSTEM_PROMPT_ALLOWED_PLACEHOLDERS = {
    "context_data",
    "content_data",
    "query",
    "question",
    "response_type",
    "user_prompt",
    "context",
    "vault_context",
    "memory_context",
    "mem0_context",
}


def _invalid_system_prompt_placeholders(system_prompt: Optional[str]) -> List[str]:
    if not system_prompt:
        return []
    placeholders = {
        match.group(1) for match in _SYSTEM_PROMPT_PLACEHOLDER_RE.finditer(system_prompt)
    }
    return sorted(
        token for token in placeholders if token not in _SYSTEM_PROMPT_ALLOWED_PLACEHOLDERS
    )


def _lightrag_result_empty(result: Any) -> bool:
    if not isinstance(result, dict):
        return True

    raw_result = result.get("result")
    if isinstance(raw_result, list):
        return len(raw_result) == 0
    if isinstance(raw_result, dict):
        return len(raw_result) == 0

    sources = result.get("sources")
    if isinstance(sources, list) and len(sources) > 0:
        return False
    raw_data = result.get("raw_data")
    if isinstance(raw_data, dict):
        chunks = raw_data.get("chunks")
        if isinstance(chunks, list) and len(chunks) > 0:
            return False

    text = _lightrag_result_text(result).strip().lower()
    return not text or text.startswith("not found in notes")


def _extract_lightrag_answer_and_sources(result: Any) -> tuple[str, List[Dict[str, Any]]]:
    if not isinstance(result, dict):
        return "No results found", []

    raw_result = result.get("result")
    answer = _sanitize_lightrag_answer_text(_lightrag_result_text(result))
    if not answer:
        if isinstance(raw_result, list):
            answer = f"Found {len(raw_result)} matching notes in LightRAG."
        elif isinstance(raw_result, dict):
            answer = "LightRAG returned structured results."
        else:
            answer = "No results found"

    sources = result.get("sources")
    if isinstance(sources, list):
        normalized_sources: List[Dict[str, Any]] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            filepath = str(
                source.get("filepath")
                or source.get("file_path")
                or ""
            ).strip()
            filename = str(source.get("filename") or "").strip()
            if not filename and filepath:
                filename = filepath.rsplit("/", 1)[-1]
            if not filename:
                filename = "Unknown"
            try:
                relevance = float(source.get("relevance", 50.0))
            except (TypeError, ValueError):
                relevance = 50.0
            snippet = str(
                source.get("snippet")
                or source.get("content")
                or ""
            ).strip()
            normalized_sources.append(
                {
                    "filename": filename.rsplit(".", 1)[0] if filename else "Unknown",
                    "filepath": filepath,
                    "relevance": relevance,
                    "snippet": snippet[:400] + ("..." if len(snippet) > 400 else ""),
                }
            )
        if normalized_sources:
            return answer, normalized_sources

    raw_data = result.get("raw_data")
    if isinstance(raw_data, dict):
        raw_sources: List[Dict[str, Any]] = []
        for chunk in raw_data.get("chunks", []) if isinstance(raw_data.get("chunks", []), list) else []:
            if not isinstance(chunk, dict):
                continue
            filepath = str(chunk.get("file_path", "")).strip()
            filename = filepath.rsplit("/", 1)[-1] if filepath else "Unknown"
            snippet = str(chunk.get("content", "")).strip()
            raw_sources.append(
                {
                    "filename": filename.rsplit(".", 1)[0] if filename else "Unknown",
                    "filepath": filepath,
                    # Raw LightRAG chunks are already retrieval-selected; keep a neutral
                    # baseline relevance so threshold filtering does not drop all evidence.
                    "relevance": 50.0,
                    "snippet": snippet[:400] + ("..." if len(snippet) > 400 else ""),
                }
            )
        if raw_sources:
            return answer, raw_sources

    # Local-mode LightRAG responses can return a list in `result`; map to source rows.
    normalized_sources: List[Dict[str, Any]] = []
    if isinstance(raw_result, list):
        for item in raw_result:
            if not isinstance(item, dict):
                continue
            try:
                relevance = float(item.get("score", 0))
            except (TypeError, ValueError):
                relevance = 0.0
            normalized_sources.append(
                {
                    "filename": item.get("title", "Unknown"),
                    "filepath": item.get("filepath", ""),
                    "relevance": relevance,
                    "snippet": item.get("excerpt", ""),
                }
            )

    return answer, normalized_sources


def _parse_allowed_origins() -> List[str]:
    raw = os.getenv("OBSIDIAN_RAG_ALLOWED_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]


def _get_api_key() -> Optional[str]:
    return os.getenv("OBSIDIAN_RAG_API_KEY")


def _is_authorized(headers: Any) -> bool:
    expected = _get_api_key()
    if not expected:
        return True
    try:
        provided = headers.get("x-api-key") or headers.get("X-API-Key")
    except AttributeError:
        provided = None
    return provided == expected


def _auth_headers() -> Dict[str, str]:
    api_key = _get_api_key()
    if not api_key:
        return {}
    return {"X-API-Key": api_key}


app = FastAPI(title="Obsidian RAG Unified API", version="1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
GRAPH_SERVICE_URL = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8002")
LIGHTRAG_SERVICE_URL = os.getenv("LIGHTRAG_SERVICE_URL", "http://localhost:8001")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LIGHTRAG_QUERY_TIMEOUT = float(os.getenv("LIGHTRAG_QUERY_TIMEOUT", "60"))

# Reliability controls
REQUEST_RETRIES = int(os.getenv("RAG_REQUEST_RETRIES", "2"))
REQUEST_BACKOFF = float(os.getenv("RAG_REQUEST_BACKOFF", "0.5"))
CIRCUIT_FAILURE_THRESHOLD = int(os.getenv("RAG_CIRCUIT_FAILURES", "3"))
CIRCUIT_RESET_SECONDS = int(os.getenv("RAG_CIRCUIT_RESET_SECONDS", "30"))
ENABLE_FALLBACKS = os.getenv("RAG_ENABLE_FALLBACKS", "true").lower() in (
    "1",
    "true",
    "yes",
)

_circuit_state = {}


@app.middleware("http")
async def _require_api_key(request: Request, call_next):
    if not _is_authorized(request.headers):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


class CircuitOpenError(RuntimeError):
    pass


def _circuit_is_open(service: str) -> bool:
    state = _circuit_state.get(service)
    if not state:
        return False
    opened_at = state.get("opened_at")
    if not opened_at:
        return False
    if time.monotonic() - opened_at < CIRCUIT_RESET_SECONDS:
        return True
    _circuit_state[service] = {"failures": 0, "opened_at": None}
    return False


def _record_success(service: str) -> None:
    _circuit_state[service] = {"failures": 0, "opened_at": None}


def _record_failure(service: str) -> None:
    state = _circuit_state.get(service, {"failures": 0, "opened_at": None})
    failures = state.get("failures", 0) + 1
    opened_at = state.get("opened_at")
    if failures >= CIRCUIT_FAILURE_THRESHOLD:
        opened_at = time.monotonic()
    _circuit_state[service] = {"failures": failures, "opened_at": opened_at}


async def _post_json(
    client: httpx.AsyncClient, url: str, payload: dict, timeout: float, service: str
) -> httpx.Response:
    if _circuit_is_open(service):
        raise CircuitOpenError(f"{service} circuit open")

    last_exception = None
    for attempt in range(REQUEST_RETRIES + 1):
        try:
            response = await client.post(
                url, json=payload, timeout=timeout, headers=_auth_headers()
            )
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"{service} {response.status_code}",
                    request=response.request,
                    response=response,
                )
            _record_success(service)
            return response
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            last_exception = exc
            _record_failure(service)
            if isinstance(exc, httpx.HTTPStatusError):
                status = exc.response.status_code if exc.response is not None else 500
                if status < 500:
                    break
            if attempt >= REQUEST_RETRIES:
                break
            await asyncio.sleep(REQUEST_BACKOFF * (2**attempt))

    raise last_exception or RuntimeError(f"{service} request failed")


# thread pool for running synchronous Deep Thinking agents
executor = ThreadPoolExecutor(max_workers=5)


class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"  # vector, graph, hybrid
    n_results: int = 10
    llm_provider: str = "ollama"
    model: Optional[str] = None
    temperature: float = 0.0
    system_prompt: Optional[str] = None
    web_search: bool = False
    llm_knowledge: bool = False
    reranking: bool = True
    deduplicate: bool = True


class SearchStreamRequest(BaseModel):
    query: str
    mode: str = "hybrid"  # vector, notes, graph, hybrid
    n_results: int = 10
    max_results: Optional[int] = None
    llm_provider: str = "ollama"
    model: Optional[str] = None
    temperature: float = 0.0
    system_prompt: Optional[str] = None
    stream: bool = True


@app.get("/api/v1/health")
async def health_check():
    """Aggregated health check with stats"""
    emb_data = {}
    graph_data = {}
    lightrag_data = {}

    try:
        async with httpx.AsyncClient() as client:
            emb_resp = await client.get(
                f"{EMBEDDING_SERVICE_URL}/health", timeout=2.0, headers=_auth_headers()
            )
            if emb_resp.status_code == 200:
                emb_data = emb_resp.json()
                emb_status = "healthy"
            else:
                emb_status = "unhealthy"
    except:
        emb_status = "unreachable"

    try:
        async with httpx.AsyncClient() as client:
            graph_resp = await client.get(
                f"{GRAPH_SERVICE_URL}/health", timeout=2.0, headers=_auth_headers()
            )
            if graph_resp.status_code == 200:
                graph_data = graph_resp.json()
                graph_status = "healthy"
            else:
                graph_status = "unhealthy"
    except:
        graph_status = "unreachable"

    try:
        async with httpx.AsyncClient() as client:
            lightrag_resp = await client.get(
                f"{LIGHTRAG_SERVICE_URL}/health", timeout=2.0, headers=_auth_headers()
            )
            if lightrag_resp.status_code == 200:
                lightrag_data = lightrag_resp.json()
                lightrag_status = "healthy"
            else:
                lightrag_status = "unhealthy"
    except:
        lightrag_status = "unreachable"

    # Get LightRAG stats
    try:
        async with httpx.AsyncClient() as client:
            stats_resp = await client.get(
                f"{LIGHTRAG_SERVICE_URL}/stats", timeout=2.0, headers=_auth_headers()
            )
            if stats_resp.status_code == 200:
                lightrag_stats = stats_resp.json()
                lightrag_data.update(lightrag_stats)
    except:
        pass

    return {
        "success": True,
        "data": {
            "gateway": "healthy",
            "services": {
                "embedding": {
                    "status": emb_status,
                    "url": EMBEDDING_SERVICE_URL,
                    "count": emb_data.get("documents", 0)
                    or emb_data.get("count", 0),  # Handle various response formats
                },
                "networkx": {
                    "status": graph_status,
                    "url": GRAPH_SERVICE_URL,
                    "nodes": graph_data.get("nodes", 0),
                    "edges": graph_data.get("edges", 0),
                },
                "lightrag": {
                    "status": lightrag_status,
                    "url": LIGHTRAG_SERVICE_URL,
                    "nodes": lightrag_data.get("graph_nodes", 0),
                    "edges": lightrag_data.get("graph_edges", 0),
                    "indexed_notes": lightrag_data.get("indexed_notes", 0),
                },
            },
        },
    }


@app.get("/api/v1/stats")
async def get_stats():
    """Get aggregated stats for UI"""
    health_data = await health_check()
    services = health_data.get("data", {}).get("services", {})

    return {
        "documents": services.get("embedding", {}).get("count", 0),
        "graph": {
            "nodes": services.get("networkx", {}).get("nodes", 0),
            "edges": services.get("networkx", {}).get("edges", 0),
        },
    }


@app.post("/api/v1/search")
async def unified_search(request: SearchRequest):
    """Unified search endpoint acting as a proxy/router"""
    mode = request.mode.lower()

    # 1. Vector Only -> Embedding Service
    if mode == "vector":
        async with httpx.AsyncClient() as client:
            try:
                # Parse tag:value syntax
                query = request.query
                tag_matches = re.findall(r'tag:([a-zA-Z0-9_-]+)', query, re.IGNORECASE)
                print(f"DEBUG: Query='{query}', Matches={tag_matches}, MatchRegex=tag:([a-zA-Z0-9_-]+)")
                filters = {}
                
                if tag_matches:
                    filters['tags'] = tag_matches
                    query = re.sub(r'tag:[a-zA-Z0-9_-]+', '', query, flags=re.IGNORECASE).strip()
                    print(f"🔍 Gateway Parsed tags: {tag_matches}, Cleaned Query: '{query}'")

                # Embedding service expects keys: query, n_results, filters
                payload = {
                    "query": query, 
                    "n_results": request.n_results,
                    "filters": filters
                }
                response = await client.post(
                    f"{EMBEDDING_SERVICE_URL}/query",
                    json=payload,
                    timeout=30.0,
                    headers=_auth_headers(),
                )
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=503, detail=f"Embedding service unreachable: {str(e)}"
                )

    # 2. Graph / Hybrid -> Graph Service
    else:
        extracted_entities, mem0_context = _extract_query_context(
            request.query, 
            include_memory=request.llm_knowledge
        )
        async with httpx.AsyncClient() as client:
            try:
                # Graph service expects robust payload
                payload = request.model_dump()
                payload["entities"] = extracted_entities
                payload["mem0_context"] = mem0_context
                response = await client.post(
                    f"{GRAPH_SERVICE_URL}/query",
                    json=payload,
                    timeout=120.0,
                    headers=_auth_headers(),
                )
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=503, detail=f"Graph service unreachable: {str(e)}"
                )


@app.post("/api/v1/search/stream")
async def unified_search_stream(request: SearchStreamRequest):
    """
    Stream search responses over SSE through the API gateway.
    Proxies to graph-service `/query_stream` (internal endpoint).
    """
    mode = request.mode.lower()
    mode_aliases = {"notes": "graph", "graph": "graph", "networkx": "graph"}
    stream_mode = mode_aliases.get(mode, mode)
    if stream_mode not in {"vector", "graph", "hybrid"}:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported stream mode '{request.mode}'. "
                "Use one of: vector, notes, graph, hybrid."
            ),
        )

    n_results = request.max_results if request.max_results is not None else request.n_results
    
    extracted_entities, mem0_context = _extract_query_context(
        request.query, 
        include_memory=request.llm_knowledge
    )

    payload = {
        "query": request.query,
        "mode": stream_mode,
        "llm_provider": request.llm_provider,
        "model": request.model,
        "temperature": request.temperature,
        "system_prompt": request.system_prompt,
        "n_results": n_results,
        "stream": bool(request.stream),
        "entities": extracted_entities,
        "mem0_context": mem0_context,
    }

    async def _proxy_stream():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{GRAPH_SERVICE_URL}/query_stream",
                    json=payload,
                    headers={
                        **_auth_headers(),
                        "Accept": "text/event-stream",
                        "Cache-Control": "no-cache",
                    },
                ) as response:
                    if response.status_code >= 400:
                        raw_body = await response.aread()
                        error_text = raw_body.decode("utf-8", errors="replace")[:500]
                        error_event = {
                            "type": "error",
                            "message": f"Upstream stream failed ({response.status_code}): {error_text}",
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
                        return

                    async for chunk in response.aiter_text():
                        if chunk:
                            yield chunk
        except httpx.RequestError as e:
            error_event = {
                "type": "error",
                "message": f"Graph streaming service unreachable: {str(e)}",
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    return StreamingResponse(
        _proxy_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

def _extract_query_context(query: str, include_memory: bool = False) -> tuple[List[str], str]:
    """Centralized entity extraction and memory synthesis for downstream services."""
    entities = []
    # Fast heuristic entity extraction (avoids slow LLM latency per query)
    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "from", "of", "about", "as", "is", "are", "was", "were", "be", "been", "that", "this", "these", "those", "it", "they", "them", "what", "which", "who", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "can", "will", "just", "should", "now"}
    
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", query)
    seen = set()
    for t in tokens:
        tl = t.lower()
        if tl not in stopwords and not tl.isdigit() and tl not in seen:
            seen.add(tl)
            entities.append(t)
            
    mem0_context = ""
    if include_memory:
        try:
            try:
                from utils.memory_manager import get_memory_manager
            except ImportError:
                try:
                    from src.utils.memory_manager import get_memory_manager
                except ImportError:
                    src_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    if src_root not in sys.path:
                        sys.path.append(src_root)
                    from utils.memory_manager import get_memory_manager
            mm = get_memory_manager()
            mem0_context = mm.search_memory(query, limit=5)
        except Exception as e:
            print(f"Warning: Failed to fetch mem0 context: {e}")
            
    return entities, mem0_context


async def _synthesize_cascading_answer(
    query: str,
    sources: List[Dict[str, Any]],
    llm_provider: str,
    model: str,
    system_prompt: str = None
) -> str:
    """Takes vector snippets and synthesizes an answer using the requested LLM provider."""
    if not sources:
        return "No results found"
    
    # Format context
    context_text = "\n\n".join([
        f"Snippet {i+1} from {s.get('filename', 'Unknown')}:\n{s.get('snippet', '')}"
        for i, s in enumerate(sources[:15])
    ])
    
    sys_prompt = system_prompt or "You are a helpful AI assistant. Synthesize a concise answer to the user's query based ONLY on the provided vault context. If the context does not contain the answer, say so."
    prompt = f"Context:\n{context_text}\n\nQuery: {query}\n\nAnswer:"
    
    ollama_host = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    try:
        if llm_provider == "ollama":
            payload = {
                "model": model or "qwen2.5:7b-instruct",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            async with httpx.AsyncClient() as c:
                resp = await c.post(f"{ollama_host}/api/chat", json=payload, timeout=60.0)
                if resp.status_code == 200:
                    return resp.json().get("message", {}).get("content", "")
        
        else:
            # Default to OpenRouter for any non-ollama provider
            if not openrouter_key:
                return f"Found {len(sources)} matching snippets in your vault. (LLM synthesis skipped: OPENROUTER_API_KEY missing)"
                
            payload = {
                "model": model or "anthropic/claude-3.5-haiku",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}
                ]
            }
            headers = {"Authorization": f"Bearer {openrouter_key}"}
            async with httpx.AsyncClient() as c:
                resp = await c.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"]
                    
    except Exception as e:
        print(f"Error in cascading fallback synthesis: {e}")
        
    return f"Found {len(sources)} matching snippets in your vault."

class UnifiedQueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"  # networkx, lightrag, hybrid
    max_results: int = 10
    llm_provider: str = "ollama"
    model: Optional[str] = None
    temperature: float = 0.7
    relevance_threshold: float = 0  # 0-100%, 0 = show all results
    distance_threshold: Optional[float] = None  # Legacy support (deprecated)
    system_prompt: Optional[str] = None
    web_search: bool = False
    llm_knowledge: bool = False
    entities_mode: Optional[str] = None  # naive, local, global, hybrid
    force_mode: bool = False
    require_llm: bool = False


@app.post("/api/v1/query")
async def unified_query(request: UnifiedQueryRequest):
    """
    Enhanced unified query endpoint with multiple knowledge source modes

    Single-source modes:
    - vector: Pure vector similarity (ChromaDB, 7k chunks)
    - notes (or networkx): Note-centric graph with wiki-links (16k nodes)
    - entities (or lightrag): Entity-centric semantic graph (2k notes)

    Dual-source modes:
    - notes+vector: NetworkX graph + ChromaDB vectors
    - entities+vector: LightRAG graph + ChromaDB vectors
    - dual-graph: Both graphs (NetworkX + LightRAG)

    Ultimate mode:
    - hybrid: All three sources (Vector + Notes + Entities) - RECOMMENDED
    """
    mode = request.mode.lower()

    # Normalize mode aliases (keep backward compatibility)
    mode_aliases = {"graph": "notes", "networkx": "notes", "lightrag": "entities"}
    mode = mode_aliases.get(mode, mode)
    supported_modes = {
        "vector",
        "notes",
        "entities",
        "notes+vector",
        "entities+vector",
        "dual-graph",
        "hybrid",
        "cascading",
    }
    if mode not in supported_modes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported mode '{request.mode}'. "
                "Use one of: vector, notes, entities, notes+vector, "
                "entities+vector, dual-graph, hybrid, cascading. "
                "For deep research, use WebSocket /api/v1/deep-research."
            ),
        )

    if request.system_prompt and mode in {
        "entities",
        "entities+vector",
        "dual-graph",
        "hybrid",
        "cascading",
    }:
        invalid_placeholders = _invalid_system_prompt_placeholders(request.system_prompt)
        if invalid_placeholders:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid system_prompt placeholders",
                    "invalid_placeholders": invalid_placeholders,
                    "allowed_placeholders": sorted(_SYSTEM_PROMPT_ALLOWED_PLACEHOLDERS),
                },
            )
    print(f"DEBUG: Unified query incoming mode: {mode}")
    effective_relevance_threshold = request.relevance_threshold
    if effective_relevance_threshold == 0 and request.distance_threshold is not None:
        import math

        effective_relevance_threshold = max(0.0, (1.0 - (request.distance_threshold / 2.0)) * 100.0)
        effective_relevance_threshold = max(
            0.0, min(100.0, effective_relevance_threshold)
        )
    print(
        f"🎯 API Gateway received relevance_threshold: {effective_relevance_threshold}%"
    )

    print(f"DEBUG: Raw Query Input: '{request.query}'") # NEW DEBUG
    # Parse tag:value syntax
    tag_matches = re.findall(r'tag:([a-zA-Z0-9_\-]+)', request.query, re.IGNORECASE)
    filters = {}
    if tag_matches:
        filters['tags'] = tag_matches
        request.query = re.sub(r'tag:[a-zA-Z0-9_\-]+', '', request.query, flags=re.IGNORECASE).strip()
        print(f"DEBUG: Parsed tags (UnifiedQuery): {tag_matches}, Cleaned Query: '{request.query}'")

    entities_mode = (request.entities_mode or "hybrid").strip().lower()
    if entities_mode not in {"naive", "local", "global", "hybrid"}:
        entities_mode = "hybrid"

    # Gateway centralized Context & Entity Extraction
    extracted_entities, mem0_context = _extract_query_context(
        request.query, 
        include_memory=request.llm_knowledge
    )
    if mem0_context:
        print(f"🧠 Mem0 context loaded: {len(mem0_context)} chars")

    # ===== CASCADING RETRIEVAL MODE =====
    if mode == "cascading":
        try:
            api_key = None
            if request.llm_provider == "anthropic":
                api_key = ANTHROPIC_API_KEY

            retriever = CascadingRetriever(
                embed_url=EMBEDDING_SERVICE_URL,
                graph_url=GRAPH_SERVICE_URL,
                lightrag_url=LIGHTRAG_SERVICE_URL,
                llm_provider=request.llm_provider,
                api_key=api_key,
            )

            result = await retriever.retrieve(
                request.query, 
                max_results=request.max_results,
                entities=extracted_entities,
                mem0_context=mem0_context
            )

            answer = ""
            sources = []
            anchor_sources = []
            vector_sources = []
            stages = result.get("stages", {}) if isinstance(result, dict) else {}

            # Prefer graph answer if present from the anchor stage
            anchors = stages.get("anchors", {})
            if isinstance(anchors, dict):
                answer = anchors.get("answer", "") or anchors.get("result", "")
                anchor_sources = anchors.get("sources", []) or []

            # Build sources from vector stage if available
            vector_snippets_by_path = {}
            vector_snippets_by_name = {}
            vector_data = stages.get("vectors", {})
            if isinstance(vector_data, dict) and vector_data.get("documents"):
                docs = vector_data.get("documents", [[]])[0]
                metas = vector_data.get("metadatas", [[]])[0]
                dists = vector_data.get("distances", [[]])[0]
                for doc, meta, dist in zip(docs, metas, dists):
                    try:
                        # Map 0->100%, 1->50%, 2->0%
                        relevance = max(0.0, (1.0 - (dist / 2.0)) * 100.0)
                    except Exception:
                        relevance = 50.0
                    doc_text = doc if isinstance(doc, str) else ""
                    snippet = (
                        (doc_text[:300] + "...") if len(doc_text) > 300 else doc_text
                    )
                    filename = meta.get("filename", "unknown")
                    filepath = meta.get("filepath", "unknown")
                    vector_sources.append(
                        {
                            "filename": filename,
                            "filepath": filepath,
                            "relevance": relevance,
                            "snippet": snippet,
                        }
                    )
                    if filepath and (
                        filepath not in vector_snippets_by_path
                        or relevance > vector_snippets_by_path[filepath]["relevance"]
                    ):
                        vector_snippets_by_path[filepath] = {
                            "snippet": snippet,
                            "relevance": relevance,
                        }
                    if filename and (
                        filename not in vector_snippets_by_name
                        or relevance > vector_snippets_by_name[filename]["relevance"]
                    ):
                        vector_snippets_by_name[filename] = {
                            "snippet": snippet,
                            "relevance": relevance,
                        }

            def _is_boilerplate_snippet(text: str) -> bool:
                if not text:
                    return True
                return bool(re.match(r"^\s*context\s*:", text, re.IGNORECASE))

            if anchor_sources and (vector_snippets_by_path or vector_snippets_by_name):
                for src in anchor_sources:
                    snippet = src.get("snippet", "")
                    if not _is_boilerplate_snippet(snippet):
                        continue
                    filepath = src.get("filepath", "")
                    filename = src.get("filename", "")
                    replacement = None
                    if filepath in vector_snippets_by_path:
                        replacement = vector_snippets_by_path[filepath]["snippet"]
                    elif filename in vector_snippets_by_name:
                        replacement = vector_snippets_by_name[filename]["snippet"]
                    if replacement:
                        src["snippet"] = replacement

            sources = anchor_sources + vector_sources

            # Deduplicate sources by filename, keep highest relevance
            deduped = {}
            for src in sources:
                fname = src.get("filename", "unknown")
                rel = src.get("relevance", 0) or 0
                if fname not in deduped or rel > deduped[fname].get("relevance", 0):
                    deduped[fname] = src
            sources = sorted(
                deduped.values(), key=lambda s: s.get("relevance", 0), reverse=True
            )
            sources = _apply_relevance_filter(sources, effective_relevance_threshold)

            query_terms = set(
                re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{1,}", request.query.lower())
            )
            filename_stopwords = {
                "a",
                "an",
                "and",
                "or",
                "the",
                "to",
                "of",
                "in",
                "on",
                "for",
                "with",
                "from",
                "by",
                "doc",
                "docs",
                "documentation",
                "guide",
                "readme",
                "overview",
                "index",
                "notes",
                "note",
                "setup",
                "quickstart",
                "reference",
                "example",
                "examples",
                "workflow",
                "implementation",
                "instructions",
                "tutorial",
                "how",
                "template",
            }

            def _diversity_key(src: Dict[str, Any]) -> str:
                name = src.get("filename") or src.get("filepath") or ""
                base = os.path.splitext(os.path.basename(name))[0]
                tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{1,}", base.lower())
                for token in tokens:
                    if token in query_terms or token in filename_stopwords:
                        continue
                    return token
                return base.lower() if base else "unknown"

            diversity_cap = 3
            diversity_counts = {}
            diversified = []
            for src in sources:
                key = _diversity_key(src)
                count = diversity_counts.get(key, 0)
                if count >= diversity_cap:
                    continue
                diversity_counts[key] = count + 1
                diversified.append(src)
            sources = diversified[: request.max_results]

            if not answer and isinstance(result, dict):
                answer = result.get("answer", "") or ""

            if not answer:
                answer = await _synthesize_cascading_answer(
                    request.query,
                    sources,
                    request.llm_provider,
                    request.model,
                    request.system_prompt
                )

            if isinstance(result, dict):
                result["answer"] = answer
                result["sources"] = sources

            return {
                "query": request.query,
                "mode": "cascading",
                "answer": answer,
                "sources": sources,
                "results": result,
                "metadata": {
                    "description": "5-Stage Cascading Retrieval (Anchor -> Entity -> Expand -> Vector -> Synthesis)",
                    "stages": [
                        "Note Discovery",
                        "Entity Extraction",
                        "Semantic Expansion",
                        "Vector Search",
                    ],
                },
            }
        except Exception as e:
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=500, detail=f"Cascading retrieval error: {str(e)}"
            )

    async with httpx.AsyncClient() as client:
        # ===== SINGLE-SOURCE MODES =====

        # Pure vector search
        if mode == "vector":
            try:
                payload = {
                    "query": request.query,
                    "n_results": request.max_results,
                    "relevance_threshold": effective_relevance_threshold,
                    "filters": filters
                }
                response = await _post_json(
                    client,
                    f"{EMBEDDING_SERVICE_URL}/query",
                    payload,
                    timeout=30.0,
                    service="vector",
                )
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code, detail=response.text
                    )
                result = response.json()

                return {
                    "query": request.query,
                    "mode": "vector",
                    "results": result,
                    "metadata": {
                        "source": "ChromaDB Vectors",
                        "description": "Pure vector similarity search across 7,102 document chunks",
                    },
                }
            except Exception as e:
                raise HTTPException(
                    status_code=503, detail=f"Vector service error: {str(e)}"
                )

        # NetworkX notes graph
        elif mode == "notes":
            try:
                payload = {
                    "query": request.query,
                    "mode": "graph",
                    "n_results": request.max_results,
                    "use_vector": True,
                    "llm_provider": request.llm_provider,
                    "model": request.model,
                    "temperature": request.temperature,
                    "web_search": request.web_search,
                    "llm_knowledge": request.llm_knowledge,
                    "system_prompt": request.system_prompt,
                    "entities": extracted_entities,
                    "mem0_context": mem0_context,
                }
                response = await _post_json(
                    client,
                    f"{GRAPH_SERVICE_URL}/query",
                    payload,
                    timeout=120.0,
                    service="graph",
                )
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code, detail=response.text
                    )
                result = response.json()
                result = _filter_result_sources(result, effective_relevance_threshold)

                return {
                    "query": request.query,
                    "mode": "notes",
                    "results": result,
                    "metadata": {
                        "source": "NetworkX Graph",
                        "description": "Note-centric graph with wiki-link relationships (16,212 nodes, 16,268 edges)",
                    },
                }
            except Exception as e:
                if isinstance(e, httpx.HTTPStatusError):
                    status = e.response.status_code if e.response is not None else 500
                    if status == 400 and request.system_prompt:
                        try:
                            detail_payload = e.response.json() if e.response is not None else {}
                        except Exception:
                            detail_payload = {"error": e.response.text if e.response is not None else str(e)}
                        if isinstance(detail_payload, dict) and (
                            detail_payload.get("error") == "Invalid system_prompt placeholders"
                            or "invalid_placeholders" in detail_payload
                        ):
                            raise HTTPException(status_code=400, detail=detail_payload)
                if ENABLE_FALLBACKS:
                    try:
                        fallback_payload = {
                            "query": request.query,
                            "n_results": request.max_results,
                            "relevance_threshold": effective_relevance_threshold,
                        }
                        fallback_response = await _post_json(
                            client,
                            f"{EMBEDDING_SERVICE_URL}/query",
                            fallback_payload,
                            timeout=30.0,
                            service="vector",
                        )
                        if fallback_response.status_code == 200:
                            fallback_result = fallback_response.json()
                            return {
                                "query": request.query,
                                "mode": "notes",
                                "results": fallback_result,
                                "metadata": {
                                    "source": "Fallback Vector",
                                    "description": "NetworkX unavailable; returned vector results",
                                },
                            }
                    except Exception:
                        pass
                raise HTTPException(
                    status_code=503, detail=f"Notes graph error: {str(e)}"
                )

        # LightRAG entities graph
        elif mode == "entities":
            try:
                payload = {
                    "query": request.query,
                    "mode": entities_mode,
                    "force_mode": request.force_mode,
                    "require_llm": request.require_llm,
                    "max_results": request.max_results,
                    "llm_provider": request.llm_provider,
                    "model": request.model,
                    "temperature": request.temperature,
                    "web_search": request.web_search,
                    "llm_knowledge": request.llm_knowledge,
                    "system_prompt": request.system_prompt,
                    "filters": filters,
                    "entities": extracted_entities,
                    "mem0_context": mem0_context,
                }
                response = await _post_json(
                    client,
                    f"{LIGHTRAG_SERVICE_URL}/query",
                    payload,
                    timeout=LIGHTRAG_QUERY_TIMEOUT,
                    service="lightrag",
                )
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code, detail=response.text
                    )
                result = response.json()
                result = _filter_result_sources(result, effective_relevance_threshold)

                if ENABLE_FALLBACKS and _lightrag_result_empty(result):
                    fallback_payload = {
                        "query": request.query,
                        "n_results": request.max_results,
                        "relevance_threshold": effective_relevance_threshold,
                    }
                    fallback_response = await _post_json(
                        client,
                        f"{EMBEDDING_SERVICE_URL}/query",
                        fallback_payload,
                        timeout=30.0,
                        service="vector",
                    )
                    if fallback_response.status_code == 200:
                        fallback_result = fallback_response.json()
                        return {
                            "query": request.query,
                            "mode": "entities",
                            "results": fallback_result,
                            "metadata": {
                                "source": "Fallback Vector",
                                "description": "LightRAG returned no matches; returned vector results",
                            },
                        }

                # Normalize answer/sources while preserving the raw LightRAG payload.
                answer, sources = _extract_lightrag_answer_and_sources(result)
                sources = _apply_relevance_filter(
                    sources, effective_relevance_threshold
                )

                return {
                    "query": request.query,
                    "mode": "entities",
                    "results": result,
                    "answer": answer,
                    "sources": sources,
                    "metadata": {
                        "source": "LightRAG Graph",
                        "description": "Entity-centric semantic graph (2,000 indexed notes)",
                    },
                }
            except Exception as e:
                if ENABLE_FALLBACKS:
                    try:
                        fallback_payload = {
                            "query": request.query,
                            "n_results": request.max_results,
                            "relevance_threshold": effective_relevance_threshold,
                        }
                        fallback_response = await _post_json(
                            client,
                            f"{EMBEDDING_SERVICE_URL}/query",
                            fallback_payload,
                            timeout=30.0,
                            service="vector",
                        )
                        if fallback_response.status_code == 200:
                            fallback_result = fallback_response.json()
                            return {
                                "query": request.query,
                                "mode": "entities",
                                "results": fallback_result,
                                "metadata": {
                                    "source": "Fallback Vector",
                                    "description": "LightRAG unavailable; returned vector results",
                                },
                            }
                    except Exception:
                        pass
                raise HTTPException(
                    status_code=503, detail=f"Entities graph error: {str(e)}"
                )

        # ===== DUAL-SOURCE MODES =====

        # Notes + Vector
        elif mode == "notes+vector":
            try:
                tasks = [
                    _post_json(
                        client,
                        f"{GRAPH_SERVICE_URL}/query",
                        {
                            "query": request.query,
                            "mode": "hybrid",
                            "n_results": request.max_results,
                            "use_vector": False,
                            "llm_provider": request.llm_provider,
                            "model": request.model,
                            "temperature": request.temperature,
                            "web_search": request.web_search,
                            "llm_knowledge": request.llm_knowledge,
                            "system_prompt": request.system_prompt,
                            "entities": extracted_entities,
                            "mem0_context": mem0_context,
                        },
                        timeout=120.0,
                        service="graph",
                    ),
                    _post_json(
                        client,
                        f"{EMBEDDING_SERVICE_URL}/query",
                        {
                            "query": request.query,
                            "n_results": request.max_results,
                            "relevance_threshold": effective_relevance_threshold,
                        },
                        timeout=30.0,
                        service="vector",
                    ),
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                notes_result = (
                    None if isinstance(responses[0], Exception) else responses[0].json()
                )
                notes_result = _filter_result_sources(
                    notes_result, effective_relevance_threshold
                )
                vector_result = (
                    None if isinstance(responses[1], Exception) else responses[1].json()
                )

                return {
                    "query": request.query,
                    "mode": "notes+vector",
                    "notes": {
                        "available": notes_result is not None,
                        "data": notes_result,
                    },
                    "vector": {
                        "available": vector_result is not None,
                        "data": vector_result,
                    },
                    "metadata": {
                        "description": "Combined NetworkX graph + ChromaDB vectors"
                    },
                }
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Notes+Vector error: {str(e)}"
                )

        # Entities + Vector
        elif mode == "entities+vector":
            try:
                tasks = [
                    _post_json(
                        client,
                        f"{LIGHTRAG_SERVICE_URL}/query",
                        {
                            "query": request.query,
                            "mode": entities_mode,
                            "force_mode": request.force_mode,
                            "require_llm": request.require_llm,
                            "max_results": request.max_results,
                            "llm_provider": request.llm_provider,
                            "model": request.model,
                            "temperature": request.temperature,
                            "web_search": request.web_search,
                            "llm_knowledge": request.llm_knowledge,
                            "system_prompt": request.system_prompt,
                            "filters": filters,
                            "entities": extracted_entities,
                            "mem0_context": mem0_context,
                        },
                        timeout=LIGHTRAG_QUERY_TIMEOUT,
                        service="lightrag",
                    ),
                    _post_json(
                        client,
                        f"{EMBEDDING_SERVICE_URL}/query",
                        {
                            "query": request.query,
                            "n_results": request.max_results,
                            "relevance_threshold": effective_relevance_threshold,
                        },
                        timeout=30.0,
                        service="vector",
                    ),
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                entities_result = (
                    None if isinstance(responses[0], Exception) else responses[0].json()
                )
                entities_result = _filter_result_sources(
                    entities_result, effective_relevance_threshold
                )
                vector_result = (
                    None if isinstance(responses[1], Exception) else responses[1].json()
                )

                return {
                    "query": request.query,
                    "mode": "entities+vector",
                    "entities": {
                        "available": entities_result is not None,
                        "data": entities_result,
                    },
                    "vector": {
                        "available": vector_result is not None,
                        "data": vector_result,
                    },
                    "metadata": {
                        "description": "Combined LightRAG graph + ChromaDB vectors"
                    },
                }
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Entities+Vector error: {str(e)}"
                )

        # Dual-Graph (both graphs, no vectors)
        elif mode == "dual-graph":
            try:
                tasks = [
                    _post_json(
                        client,
                        f"{GRAPH_SERVICE_URL}/query",
                        {
                            "query": request.query,
                            "mode": "hybrid",
                            "n_results": request.max_results,
                            "use_vector": False,
                            "llm_provider": request.llm_provider,
                            "model": request.model,
                            "temperature": request.temperature,
                            "web_search": request.web_search,
                            "llm_knowledge": request.llm_knowledge,
                            "system_prompt": request.system_prompt,
                            "entities": extracted_entities,
                            "mem0_context": mem0_context,
                        },
                        timeout=120.0,
                        service="graph",
                    ),
                    _post_json(
                        client,
                        f"{LIGHTRAG_SERVICE_URL}/query",
                        {
                            "query": request.query,
                            "mode": entities_mode,
                            "force_mode": request.force_mode,
                            "require_llm": request.require_llm,
                            "max_results": request.max_results,
                            "llm_provider": request.llm_provider,
                            "model": request.model,
                            "temperature": request.temperature,
                            "web_search": request.web_search,
                            "llm_knowledge": request.llm_knowledge,
                            "system_prompt": request.system_prompt,
                            "filters": filters,
                            "entities": extracted_entities,
                            "mem0_context": mem0_context,
                        },
                        timeout=LIGHTRAG_QUERY_TIMEOUT,
                        service="lightrag",
                    ),
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                notes_result = (
                    None if isinstance(responses[0], Exception) else responses[0].json()
                )
                entities_result = (
                    None if isinstance(responses[1], Exception) else responses[1].json()
                )
                notes_result = _filter_result_sources(
                    notes_result, effective_relevance_threshold
                )
                entities_result = _filter_result_sources(
                    entities_result, effective_relevance_threshold
                )

                return {
                    "query": request.query,
                    "mode": "dual-graph",
                    "notes": {
                        "available": notes_result is not None,
                        "data": notes_result,
                    },
                    "entities": {
                        "available": entities_result is not None,
                        "data": entities_result,
                    },
                    "metadata": {"description": "Combined NetworkX + LightRAG graphs"},
                }
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Dual-graph error: {str(e)}"
                )

        # ===== ULTIMATE HYBRID MODE =====

        # Hybrid: All three sources
        # Hybrid: All three sources
        elif mode == "hybrid":
            try:
                tasks = [
                    _post_json(
                        client,
                        f"{GRAPH_SERVICE_URL}/query",
                        {
                            "query": request.query,
                            "mode": "hybrid",
                            "n_results": request.max_results,
                            "use_vector": False,
                            "llm_provider": request.llm_provider,
                            "model": request.model,
                            "temperature": request.temperature,
                            "web_search": request.web_search,
                            "llm_knowledge": request.llm_knowledge,
                            "system_prompt": request.system_prompt,
                            "entities": extracted_entities,
                            "mem0_context": mem0_context,
                        },
                        timeout=90.0,
                        service="graph",
                    ),
                    _post_json(
                        client,
                        f"{LIGHTRAG_SERVICE_URL}/query",
                        {
                            "query": request.query,
                            "mode": entities_mode,
                            "force_mode": request.force_mode,
                            "require_llm": request.require_llm,
                            "max_results": request.max_results,
                            "llm_provider": request.llm_provider,
                            "model": request.model,
                            "temperature": request.temperature,
                            "web_search": request.web_search,
                            "llm_knowledge": request.llm_knowledge,
                            "system_prompt": request.system_prompt,
                            "filters": filters,
                            "entities": extracted_entities,
                            "mem0_context": mem0_context,
                        },
                        timeout=LIGHTRAG_QUERY_TIMEOUT,
                        service="lightrag",
                    ),
                    _post_json(
                        client,
                        f"{EMBEDDING_SERVICE_URL}/query",
                        {
                            "query": request.query,
                            "n_results": request.max_results,
                            "relevance_threshold": effective_relevance_threshold,
                        },
                        timeout=30.0,
                        service="vector",
                    ),
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                notes_result = (
                    None if isinstance(responses[0], Exception) else responses[0].json()
                )
                entities_result = (
                    None if isinstance(responses[1], Exception) else responses[1].json()
                )
                notes_result = _filter_result_sources(
                    notes_result, effective_relevance_threshold
                )
                entities_result = _filter_result_sources(
                    entities_result, effective_relevance_threshold
                )
                vector_result = (
                    None if isinstance(responses[2], Exception) else responses[2].json()
                )

                return {
                    "query": request.query,
                    "mode": "hybrid",
                    "notes": {
                        "available": notes_result is not None,
                        "data": notes_result,
                    },
                    "entities": {
                        "available": entities_result is not None,
                        "data": entities_result,
                    },
                    "vector": {
                        "available": vector_result is not None,
                        "data": vector_result,
                    },
                    "metadata": {
                        "description": "Ultimate hybrid: All 3 sources (Vector + Notes + Entities)",
                        "sources": {
                            "vector": "ChromaDB (7,102 chunks)",
                            "notes": "NetworkX Graph (16,212 nodes)",
                            "entities": "LightRAG Graph (2,000 notes)",
                        },
                    },
                }
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Hybrid query error: {str(e)}"
                )


@app.websocket("/api/v1/deep-research")
async def deep_research_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for Deep Thinking Agent.
    Client sends JSON: {"query": "..."}
    Server streams messages:
      {"type": "log", "content": "..."}
      {"type": "status", "content": "🤔 Planning..."}
      {"type": "answer", "data": {...}}
    """
    if not _is_authorized(websocket.headers):
        await websocket.close(code=4401)
        return

    await websocket.accept()

    try:
        data = await websocket.receive_json()
        query = data.get("query")
        provider = data.get("provider", "claude").lower()
        model = data.get("model")
        supported_providers = {
            "claude",
            "gemini",
            "openrouter",
            "chatgpt",
            "ollama",
            "perplexity",
        }

        def _select_fallback_provider():
            if os.getenv("PERPLEXITY_API_KEY"):
                return "perplexity"
            if os.getenv("OPENROUTER_API_KEY"):
                return "openrouter"
            if ANTHROPIC_API_KEY:
                return "claude"
            if os.getenv("GEMINI_API_KEY"):
                return "gemini"
            if os.getenv("OPENAI_API_KEY"):
                return "chatgpt"
            if os.getenv("OLLAMA_HOST"):  # Basic check for Ollama
                return "ollama"
            return None

        if not query:
            await websocket.send_json({"type": "error", "content": "No query provided"})
            return

        # Normalize provider for Deep Thinking
        if provider not in supported_providers:
            fallback_provider = _select_fallback_provider()
            if not fallback_provider:
                await websocket.send_json(
                    {
                        "type": "error",
                        "content": "Deep Thinking supports Perplexity, Claude, Gemini, OpenRouter, ChatGPT, or Ollama. No compatible configuration found.",
                    }
                )
                await websocket.close()
                return
            await websocket.send_json(
                {
                    "type": "log",
                    "message": f"Deep Thinking does not support '{provider}'. Using '{fallback_provider}'.",
                }
            )
            provider = fallback_provider
            model = None

        # Determine API Key based on provider
        api_key = None
        if provider == "claude":
            api_key = ANTHROPIC_API_KEY
            if not api_key:
                await websocket.send_json(
                    {"type": "error", "content": "ANTHROPIC_API_KEY not configured"}
                )
                await websocket.close()
                return
        elif provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                await websocket.send_json(
                    {"type": "error", "content": "GEMINI_API_KEY not configured"}
                )
                await websocket.close()
                return
        elif provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                await websocket.send_json(
                    {"type": "error", "content": "OPENROUTER_API_KEY not configured"}
                )
                await websocket.close()
                return
        elif provider == "chatgpt":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                await websocket.send_json(
                    {"type": "error", "content": "OPENAI_API_KEY not configured"}
                )
                await websocket.close()
                return
        elif provider == "perplexity":
            api_key = os.getenv("PERPLEXITY_API_KEY")
            if not api_key:
                await websocket.send_json(
                    {"type": "error", "content": "PERPLEXITY_API_KEY not configured"}
                )
                await websocket.close()
                return
        elif provider == "ollama":
            api_key = "ollama"  # No key needed, but passing string to avoid validation errors downstream

        # Initialize Agent with Universal Client
        # Note: We must use the INTERNAL Docker URLs here
        DeepThinkingRAG = _load_deep_thinking_rag()
        rag = DeepThinkingRAG(
            provider=provider,
            api_key=api_key,
            model=model,
            vector_service_url=EMBEDDING_SERVICE_URL,
            graph_service_url=GRAPH_SERVICE_URL,
            enable_reranking=True,
        )

        # Define synchronous callback to run in thread
        def status_callback(msg, details=None):
            # We can't await here, so we run a coroutine in the main event loop
            # But making it thread-safe is tricky.
            # Simplified: formatting the message and putting it in a queue, or just printing?
            # Ideally we want to send to websocket.

            # Since this runs in a thread, we need to schedule the send on the loop
            loop = asyncio.new_event_loop()
            # Wait, creating a new loop is risky.
            # Better approach: The callback is run in the thread.
            # We can use asyncio.run_coroutine_threadsafe if we have reference to the loop.
            pass

        # Actually, let's redefine this to run nicely with FastAPI's event loop
        loop = asyncio.get_running_loop()

        def sync_callback(msg, details=None):
            payload = {"type": "log", "message": msg, "details": details}
            # Schedule sending the message on the main loop
            asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)

        # Run the heavy blocking function in a thread pool
        def run_agent():
            return rag.query(query, status_callback=sync_callback)

        await websocket.send_json({"type": "status", "content": "Agent started"})

        # Execute in thread
        result = await asyncio.get_running_loop().run_in_executor(executor, run_agent)

        # Send final result
        await websocket.send_json({"type": "result", "data": result})

        await websocket.close()

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {e}")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
            await websocket.close(code=1011)
        except:
            pass


if __name__ == "__main__":
    uvicorn.run("api_gateway:app", host="0.0.0.0", port=3000, reload=True)
