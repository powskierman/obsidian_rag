"""
Legacy internal graph retrieval service.

This service still backs internal graph-dependent retrieval paths, but it is no longer
the public search-mode surface of the API gateway.
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import os
import re
import requests
import json
try:
    from src.services.networkx_graph_builder import (
        GraphBuilder,
        GraphQuerier,
        graph_storage_stats,
        is_structural_graph,
        select_graph_path,
    )
except ImportError:
    from networkx_graph_builder import (
        GraphBuilder,
        GraphQuerier,
        graph_storage_stats,
        is_structural_graph,
        select_graph_path,
    )
import logging
from openai import OpenAI
import threading
import sys
from pathlib import Path

# Add necessary directories to sys.path for local vs Docker layouts
current_dir = Path(__file__).parent.resolve()
# Docker setup: services are in /app, utils are in /app/utils
# Local setup: services are in src/services, utils are in src/utils
potential_roots = [
    current_dir,           # Docker /app/
    current_dir.parent,    # /app/src/
    current_dir.parent.parent # Project Root
]

for pr in potential_roots:
    if pr.exists() and (pr / "utils").exists():
        if str(pr) not in sys.path:
            sys.path.insert(0, str(pr))
            break
    if pr.exists() and (pr / "src" / "utils").exists():
        src_path = str(pr / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
            break

def _parse_allowed_origins() -> list[str]:
    raw = os.getenv("OBSIDIAN_RAG_ALLOWED_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]


def _get_api_key() -> str | None:
    return os.getenv("OBSIDIAN_RAG_API_KEY")


def _api_key_valid() -> bool:
    expected = _get_api_key()
    if not expected:
        return True
    provided = request.headers.get("X-API-Key")
    return provided == expected


def _service_headers() -> dict:
    api_key = _get_api_key()
    if not api_key:
        return {}
    return {"X-API-Key": api_key}


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": _parse_allowed_origins()}})


@app.before_request
def _require_api_key():
    if not _api_key_valid():
        return jsonify({"error": "Unauthorized"}), 401

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from utils.memory_manager import get_memory_manager
except ImportError as e:
    logger.error(f"Critical Import Error: {e}")
    # Fallback to direct import if possible
    try:
        from src.utils.memory_manager import get_memory_manager
    except ImportError:
        logger.error("All memory_manager import attempts failed.")
        def get_memory_manager(): return None

try:
    from utils.prompt_builder import build_prompt_appendix, build_vault_system_prompt
except ImportError:
    try:
        from src.utils.prompt_builder import build_prompt_appendix, build_vault_system_prompt
    except ImportError:
        def build_prompt_appendix(user_query: str, provider: str) -> str:
            return ""
        def build_vault_system_prompt(context_text: str, user_query: str, provider: str, custom_prompt: str | None = None) -> str:
            return custom_prompt or ""

# Global graph builder and querier
builder = None
querier = None
graph_loaded = False

# Environment variables for vector service
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://embedding-service:8000")


def _default_openrouter_model() -> str:
    return (
        os.getenv("GRAPH_MODEL")
        or os.getenv("OPENROUTER_MODEL")
        or os.getenv("LIGHTRAG_MODEL")
        or os.getenv("KIMI_MODEL")
        or "openrouter/auto"
    )


def _default_model_for_provider(provider: str, streaming: bool = False) -> str:
    if provider == "ollama":
        if streaming:
            return os.getenv("OLLAMA_MODEL", "llama2")
        return os.getenv("OLLAMA_MODEL") or os.getenv("LLM_MODEL") or "llama3.2"
    if provider == "claude":
        return "claude-sonnet-4-5-20250929"
    if provider == "gemini":
        return "gemini-3-pro-preview"
    if provider == "gpt-oss":
        return "gpt-4"
    if provider in {"kimi", "openrouter"}:
        return _default_openrouter_model()
    if provider == "chatgpt":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if provider in {"lmstudio", "mlx"}:
        return (
            os.getenv("LMSTUDIO_MODEL")
            or os.getenv("MLX_MODEL")
            or os.getenv("LLM_MODEL_PATH")
            or os.getenv("LLM_MODEL")
            or "local-model"
        )
    return "llama2" if streaming else "llama3.2"
def extract_entities_from_graph(graph_text: str) -> list:
    """Extract key entities from graph response text."""
    # Extract capitalized phrases (likely entities)
    entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', graph_text)

    # Common words to filter out
    stopwords = {'The', 'This', 'That', 'These', 'Those', 'There', 'Here',
                 'When', 'Where', 'What', 'How', 'Why', 'Based', 'Your'}

    # Filter and deduplicate
    entities = [e for e in entities if e not in stopwords]
    entities = list(set(entities))[:10]  # Top 10 unique entities

    return entities


def relevance_from_distance(dist: float) -> float:
    """Convert distance score to relevance percentage (0-100)."""
    # Map 0->100%, 1->50%, 2->0%
    try:
        relevance = max(0.0, (1.0 - (dist / 2.0)) * 100.0)
        return relevance
    except Exception:
        return 50.0


DEFAULT_INTEGRATION_KEYWORDS = [
    "integrate", "integration", "connect", "connection", "interface", "interfacing",
    "link", "bridge", "combine", "pair",
    "serial", "uart", "i2c", "spi", "gpio", "pinout", "wiring",
    "protocol", "driver", "library", "firmware", "upload", "flash", "hookup"
]


def load_keyword_boosts() -> dict:
    """Load keyword boost config from env or use defaults."""
    raw = os.getenv("GRAPH_KEYWORD_BOOSTS", "").strip()
    if not raw:
        return {"integration": {"weight": 4.0, "keywords": DEFAULT_INTEGRATION_KEYWORDS}}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        logger.warning("Invalid GRAPH_KEYWORD_BOOSTS; using defaults")
    return {"integration": {"weight": 4.0, "keywords": DEFAULT_INTEGRATION_KEYWORDS}}


def is_integration_intent(user_query: str, query_terms: set[str]) -> bool:
    """Heuristic intent detection for integration-style queries."""
    query_lower = user_query.lower()
    cues = {
        "integrate", "integration", "connect", "connection", "interface", "interfacing",
        "link", "bridge", "combine", "pair", "hookup", "wiring", "serial", "uart", "i2c", "spi"
    }
    return any(cue in query_lower for cue in cues)


def count_keyword_hits(text: str, keywords: list[str]) -> int:
    """Count keyword hits with a light boundary check for short terms."""
    import re
    hits = 0
    for kw in keywords:
        kw = kw.lower().strip()
        if not kw:
            continue
        if len(kw) <= 3:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                hits += 1
        else:
            if kw in text:
                hits += 1
    return hits


def normalize_text(text: str) -> str:
    """Normalize text for loose matching (alnum only)."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def term_in_text(term: str, text: str, normalized_text: str) -> bool:
    """Check for whole-word or normalized substring matches."""
    if not term:
        return False
    if re.search(r"\b" + re.escape(term) + r"\b", text):
        return True
    return term in normalized_text


def expand_query_terms(user_query: str, query_terms: set[str]) -> set[str]:
    """Add normalized term variants for letter+number combos (e.g., esp-32 -> esp32)."""
    expanded = set(query_terms)
    for match in re.finditer(r"\b([a-z]+)\s*[-_ ]\s*(\d{1,4})\b", user_query.lower()):
        expanded.add(f"{match.group(1)}{match.group(2)}")
    return expanded


def count_term_matches(terms: set[str], text: str) -> int:
    """Count how many query terms appear in text."""
    if not terms:
        return 0
    text_lower = text.lower()
    text_norm = normalize_text(text_lower)
    return sum(1 for term in terms if term_in_text(term, text_lower, text_norm))


def parse_query_tags(query: str) -> tuple[str, dict]:
    """
    Parse 'tag:value' or 'tag:"value"' syntax from query.
    Returns (cleaned_query, filters_dict)
    """
    if not query:
        return "", {}
        
    tag_pattern = re.compile(r'\btag:(?:"([^"]+)"|([a-zA-Z0-9_-]+))', re.IGNORECASE)
    
    tags = []
    def replace_func(match):
        # Group 1 is quoted, Group 2 is simple
        val = match.group(1) or match.group(2)
        tags.append(val.lower())
        return ""
        
    cleaned = tag_pattern.sub(replace_func, query)
    
    # Clean up extra spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    filters = {}
    if tags:
        filters['tags'] = tags
        
    return cleaned, filters


def generate_hyde_text(user_query: str, llm_provider: str, model: str) -> str:
    """Generate a hypothetical answer to improve vector search (HyDE)."""
    hyde_prompt = f"""You are a helpful assistant. Provide a concise, hypothetical but technically accurate answer to the following question. 
This answer will be used to help find relevant documents in a knowledge base.

Question: {user_query}

Hypothetical Answer:"""
    
    try:
        logger.info(f"Generating HyDE hypothetical answer for query: {user_query}")
        hyde_answer = call_llm(llm_provider, model, hyde_prompt, user_query, temperature=0.3)
        return hyde_answer
    except Exception as e:
        logger.error(f"HyDE generation failed: {e}")
        return user_query # Fallback to original query


def call_llm(provider: str, model: str, system_prompt: str, user_query: str, temperature: float = 0.7) -> str:
    """
    Call the specified LLM provider with the given prompt.

    Args:
        provider: 'ollama', 'claude', 'gemini', 'gpt-oss', 'kimi', 'openrouter', or 'chatgpt'
        model: Model name (e.g., 'llama3.2', 'claude-sonnet-4-5-20250929', 'gemini-3-pro-preview')
        system_prompt: System prompt with context
        user_query: User's question
        temperature: Temperature for generation

    Returns:
        LLM response text
    """
    logger.info(f"Calling LLM: provider={provider}, model={model}")

    if provider == "claude":
        # Use Claude API via Anthropic
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_query}]
        )
        return response.content[0].text

    elif provider == "gemini":
        # Use Gemini API via REST
        api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        # Combine system prompt and user query for Gemini
        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"

        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        gemini_response = requests.post(
            gemini_url,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "contents": [{
                    "role": "user",
                    "parts": [{"text": full_prompt}]
                }],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 4000
                }
            },
            timeout=180
        )

        if gemini_response.status_code != 200:
            raise ValueError(f"Gemini API error: {gemini_response.status_code} - {gemini_response.text}")

        result = gemini_response.json()
        candidates = result.get('candidates', [])
        if candidates and len(candidates) > 0:
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if parts and len(parts) > 0:
                return parts[0].get('text', '')

        raise ValueError("Unexpected Gemini response format")

    elif provider == "gpt-oss":
        # Use OpenAI-compatible API (gpt-oss)
        llm_host = os.getenv("GPT_OSS_HOST", "http://host.docker.internal:12434/engines/llama.cpp")

        # Combine system prompt and user query
        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"

        llm_response = requests.post(
            f'{llm_host}/v1/chat/completions',
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': full_prompt}
                ],
                'max_tokens': 4096,
                'temperature': temperature
            },
            timeout=180
        )

        if llm_response.status_code != 200:
            raise ValueError(f"GPT-OSS API error: {llm_response.status_code} - {llm_response.text}")

        result = llm_response.json()
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']

        raise ValueError("Unexpected GPT-OSS response format")

    elif provider == "openrouter":
        # Use OpenRouter for flexible model access
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")

        if not model:
            model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content

    elif provider == "chatgpt":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        if not model:
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        client = OpenAI(api_key=api_key)
        restricted_temp = False
        if model:
            model_lower = model.lower()
            if model_lower.startswith(("gpt-5", "o1", "o3")):
                restricted_temp = True

        request_payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ]
        }
        if not restricted_temp:
            request_payload["temperature"] = temperature

        request_timeout = float(os.getenv("OPENAI_TIMEOUT", "60"))
        response = client.chat.completions.create(timeout=request_timeout, **request_payload)
        return response.choices[0].message.content

    elif provider in {"lmstudio", "mlx"}:
        api_key = (
            os.getenv("QUERY_LMSTUDIO_API_KEY")
            or os.getenv("LMSTUDIO_API_KEY", "lmstudio")
            or os.getenv("QUERY_MLX_API_KEY")
            or os.getenv("MLX_API_KEY", "mlx")
        )
        base_url = (
            os.getenv("QUERY_LMSTUDIO_BASE_URL")
            or os.getenv("LMSTUDIO_BASE_URL")
            or os.getenv("QUERY_MLX_BASE_URL")
            or os.getenv("MLX_BASE_URL", "http://host.docker.internal:1234/v1")
        )

        if not model:
            model = _default_model_for_provider(provider, streaming=False)

        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )

        request_timeout = float(os.getenv("OPENAI_TIMEOUT", "60"))
        response = client.chat.completions.create(
            timeout=request_timeout,
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content

    elif provider == "kimi":
        # Use OpenRouter for Kimi
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content

    else:  # ollama (default)
        ollama_host = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")

        # Combine system prompt and user query for Ollama
        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"

        ollama_response = requests.post(
            f'{ollama_host}/api/generate',
            json={
                'model': model,
                'prompt': full_prompt,
                'stream': False,
                'options': {
                    'temperature': temperature
                }
            },
            timeout=180
        )

        if ollama_response.status_code != 200:
            raise ValueError(f"Ollama API error: {ollama_response.status_code} - {ollama_response.text}")

        result = ollama_response.json()
        return result.get('response', '')


def call_llm_stream(provider: str, model: str, system_prompt: str, user_query: str, temperature: float = 0.7):
    """
    Call the specified LLM provider with streaming enabled.

    Args:
        provider: 'ollama', 'claude', 'gemini', 'gpt-oss', 'kimi', 'openrouter', or 'chatgpt'
        model: Model name
        system_prompt: System prompt with context
        user_query: User's question
        temperature: Temperature for generation

    Yields:
        Chunks of text from the LLM as they're generated
    """
    logger.info(f"Calling LLM with streaming: provider={provider}, model={model}")

    if provider == "claude":
        # Use Claude API with streaming
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        client = Anthropic(api_key=api_key)

        with client.messages.stream(
            model=model,
            max_tokens=4000,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_query}]
        ) as stream:
            for text in stream.text_stream:
                yield text

    elif provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")

        if not model:
            model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=temperature,
            stream=True
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    elif provider == "chatgpt":
        response_text = call_llm(provider, model, system_prompt, user_query, temperature)
        if response_text:
            yield response_text

    elif provider in {"lmstudio", "mlx"}:
        response_text = call_llm(provider, model, system_prompt, user_query, temperature)
        if response_text:
            yield response_text

    elif provider == "ollama":
        # Use Ollama with streaming
        ollama_host = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"

        ollama_response = requests.post(
            f'{ollama_host}/api/generate',
            json={
                'model': model,
                'prompt': full_prompt,
                'stream': True,
                'options': {'temperature': temperature}
            },
            timeout=180,
            stream=True
        )

        if ollama_response.status_code != 200:
            raise ValueError(f"Ollama API error: {ollama_response.status_code}")

        # Stream the response
        for line in ollama_response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    if 'response' in chunk:
                        yield chunk['response']
                except json.JSONDecodeError:
                    continue

    elif provider == "gpt-oss":
        # Use OpenAI-compatible streaming
        llm_host = os.getenv("GPT_OSS_HOST", "http://host.docker.internal:12434/engines/llama.cpp")
        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"

        llm_response = requests.post(
            f'{llm_host}/v1/chat/completions',
            json={
                'model': model,
                'messages': [{'role': 'system', 'content': full_prompt}],
                'max_tokens': 4096,
                'temperature': temperature,
                'stream': True
            },
            timeout=180,
            stream=True
        )

        if llm_response.status_code != 200:
            raise ValueError(f"GPT-OSS API error: {llm_response.status_code}")

        # Stream the response
        for line in llm_response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    line_str = line_str[6:]
                    if line_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(line_str)
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                    except json.JSONDecodeError:
                        continue

    elif provider == "gemini":
        # Gemini doesn't support streaming in the same way, fall back to non-streaming
        # but chunk the response for client-side streaming effect
        api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        gemini_response = requests.post(
            gemini_url,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "contents": [{
                    "role": "user",
                    "parts": [{"text": full_prompt}]
                }],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 4000
                }
            },
            timeout=180
        )

        if gemini_response.status_code != 200:
            raise ValueError(f"Gemini API error: {gemini_response.status_code}")

        result = gemini_response.json()
        candidates = result.get('candidates', [])
        if candidates and len(candidates) > 0:
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if parts and len(parts) > 0:
                text = parts[0].get('text', '')
                # Chunk the response into words for streaming effect
                words = text.split(' ')
                for i, word in enumerate(words):
                    yield word + (' ' if i < len(words) - 1 else '')
        else:
            raise ValueError("Unexpected Gemini response format")


def initialize_graph(graph_path: str = None):
    """Initialize the knowledge graph"""
    global builder, querier, graph_loaded
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set")
        return False
    
    try:
        builder = GraphBuilder(api_key=api_key)
        
        # If no explicit path provided, resolve from env with centralized data-dir fallback.
        if graph_path is None:
            graph_path = os.environ.get('GRAPH_PATH')

        # Honor an explicit graph path before falling back to best-effort discovery.
        if graph_path:
            explicit_path = Path(graph_path).expanduser()
            if explicit_path.is_file():
                graph_file = explicit_path
            elif explicit_path.is_dir():
                graph_file = select_graph_path([explicit_path])
            else:
                graph_file = None
        else:
            graph_file = None

        if graph_file is None:
            possible_paths = []

            data_dir = os.environ.get('OBSIDIAN_RAG_DATA_DIR', '').strip()
            if data_dir:
                possible_paths.extend([
                    str(Path(data_dir) / 'graph_data'),
                    str(Path(data_dir) / 'graph_data' / 'knowledge_graph_full.pkl'),
                    str(Path(data_dir) / 'graph_data' / 'knowledge_graph.pkl'),
                    str(Path(data_dir) / 'graph_data' / 'knowledge_graph_test.pkl'),
                    str(Path(data_dir) / 'knowledge_graph_full.pkl'),
                    str(Path(data_dir) / 'knowledge_graph.pkl'),
                ])

            possible_paths.extend([
                '/app/graph_data',
                '/app/graph_data/knowledge_graph_full.pkl',
                '/app/graph_data/knowledge_graph.pkl',
                '/app/graph_data/knowledge_graph_test.pkl',
                '/app/knowledge_graph_full.pkl',
                '/app/knowledge_graph.pkl',
                '/app/knowledge_graph_test.pkl',
            ])

            graph_file = select_graph_path(possible_paths)

        if graph_file:
            builder.load_graph(str(graph_file))
            stats = graph_storage_stats(builder.graph)
            structural = is_structural_graph(builder.graph)
            if not structural:
                logger.warning(
                    "Loaded legacy/non-structural graph from %s (tuple_nodes=%s, string_nodes=%s). "
                    "Notes mode may be noisy until the graph is rebuilt.",
                    graph_file,
                    stats.get("tuple_nodes", 0),
                    stats.get("string_nodes", 0),
                )
            querier = GraphQuerier(builder, api_key=api_key)
            graph_loaded = True
            logger.info(
                "Graph loaded from %s: %s nodes, %s edges (structural=%s)",
                graph_file,
                builder.graph.number_of_nodes(),
                builder.graph.number_of_edges(),
                structural,
            )
            return True
        else:
            logger.warning(f"Graph file not found. Tried: {possible_paths}")
            return False
    except Exception as e:
        logger.error(f"Error loading graph: {e}")
        return False


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'graph_loaded': graph_loaded,
        'nodes': builder.graph.number_of_nodes() if graph_loaded else 0,
        'edges': builder.graph.number_of_edges() if graph_loaded else 0
    })


@app.route('/query', methods=['POST'])
def query_graph():
    """
    Unified query endpoint supporting vector, graph, and hybrid modes with LLM synthesis

    POST body:
    {
        "query": "What treatments are mentioned?",
        "mode": "vector" | "graph" | "hybrid",  // optional, default: "graph"
        "llm_provider": "ollama" | "claude" | "gemini" | "gpt-oss",  // optional, default: "ollama"
        "model": "llama3.2",  // optional, defaults based on provider
        "temperature": 0.7,  // optional
        "system_prompt": "Custom system instructions...",  // optional
        "max_entities": 20,  // optional, for graph mode
        "n_results": 10,  // optional, for vector/hybrid modes
        "web_search": false,  // optional, enables web search with Tavily
        "llm_knowledge": false,  // optional, adds complementary LLM insights
        "conversation_history": []  // optional, list of {role, content} messages
    }
    """
    try:
        data = request.json
        user_query = data.get('query', '')
        mode = data.get('mode', 'graph')
        llm_provider = data.get('llm_provider', 'ollama')
        model = data.get('model', '')
        temperature = data.get('temperature', 0.7)
        custom_system_prompt = data.get('system_prompt', '')
        max_entities = data.get('max_entities', 20)
        n_results = data.get('n_results', 10)
        web_search_enabled = data.get('web_search', False)
        llm_knowledge_enabled = data.get('llm_knowledge', False)
        conversation_history = data.get('conversation_history', [])
        provided_entities = data.get('entities', None)
        provided_mem0_context = data.get('mem0_context', None)

        # Parse tags from query
        clean_query, tag_filters = parse_query_tags(user_query)
        logger.info(f"Parsed query: '{clean_query}', filters: {tag_filters}")
        
        # Use cleaning query for vector search, but pass filters
        current_query_text = clean_query if clean_query.strip() else user_query

        logger.info(
            "Query request: mode=%s provider=%s model=%s n_results=%s web_search=%s llm_knowledge=%s",
            mode,
            llm_provider,
            model or "default",
            n_results,
            web_search_enabled,
            llm_knowledge_enabled,
        )

        if not current_query_text:
             # If query was ONLY tags, we still might want to search but the embedding service handles empty string poorly usually
             # But here we fallback to user_query if clean_query is empty, which is fine (means no tags or only tags)
             if not user_query:
                return jsonify({'error': 'Query is required'}), 400
             current_query_text = user_query

        # Set default models based on provider
        if not model:
            model = _default_model_for_provider(llm_provider, streaming=False)

        # Handle vector mode: Vector search + LLM synthesis
        if mode == 'vector':
            try:
                # Get vector search results with threshold to filter noise
                # Pass relevance_threshold to filter out low quality matches (e.g. 73% iOS nonsense)
                vector_response = requests.post(
                    f'{EMBEDDING_SERVICE_URL}/query',
                    json={
                        'query': current_query_text,
                        'n_results': n_results,
                        'reranking': True,
                        'deduplicate': True,
                        'relevance_threshold': 40,  # Filter out noise < 40%
                        'filters': tag_filters if tag_filters else None
                    },
                    timeout=60,
                    headers=_service_headers()
                )

                if vector_response.status_code != 200:
                    return jsonify({'error': 'Vector search failed', 'mode': mode}), 503

                vector_data = vector_response.json()
                documents = vector_data.get('documents', [[]])[0]
                metadatas = vector_data.get('metadatas', [[]])[0]
                distances = vector_data.get('distances', [[]])[0]

                # Build context from vector results
                context_parts = []
                vector_sources = []
                
                # Combine into list for proper sorting locally
                combined_results = []

                for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
                    # Calculate relevance compatible with embedding service logic
                    relevance = relevance_from_distance(dist)

                    if relevance < 75:  # Double check filtering
                        continue
                        
                    combined_results.append({
                        'doc': doc,
                        'meta': meta,
                        'relevance': relevance
                    })

                # Sort by relevance descending
                combined_results.sort(key=lambda x: x['relevance'], reverse=True)

                for i, res in enumerate(combined_results, 1):
                    doc = res['doc']
                    meta = res['meta']
                    relevance = res['relevance']
                    
                    filename = meta.get('filename', 'unknown')
                    filepath = meta.get('filepath', 'unknown')
                    snippet = doc[:200] + "..." if len(doc) > 200 else doc

                    context_parts.append(f"Source {i} ({filename}):\n{doc}\n")
                    vector_sources.append({
                        'filename': filename,
                        'filepath': filepath,
                        'relevance': relevance,
                        'snippet': snippet
                    })


                context_text = "\n".join(context_parts)

                # Build system prompt
                system_prompt = build_vault_system_prompt(
                    context_text=context_text,
                    user_query=user_query,
                    provider=llm_provider,
                    custom_prompt=custom_system_prompt
                )

                # Call LLM
                answer = call_llm(llm_provider, model, system_prompt, user_query, temperature)

                return jsonify({
                    'answer': answer,
                    'query': user_query,
                    'mode': mode,
                    'sources': vector_sources,
                    'llm_provider': llm_provider,
                    'model': model
                })

            except Exception as e:
                logger.error(f"Vector mode error: {e}")
                return jsonify({'error': str(e), 'mode': mode}), 500

        # Handle graph and hybrid modes
        else:
            if not graph_loaded:
                return jsonify({'error': 'Graph not loaded'}), 503

            # Step 1: Query the knowledge graph with custom system prompt
            logger.info(f"=== GRAPH QUERY DEBUG ===")
            logger.info(f"Query: {user_query}")
            logger.info(f"Mode: {mode}")
            logger.info(f"LLM Provider: {llm_provider}")
            logger.info(f"Model: {model}")
            logger.info(f"Max Entities: {max_entities}")
            logger.info(f"Custom System Prompt Present: {bool(custom_system_prompt)}")
            logger.info(f"Custom System Prompt (first 200 chars): {custom_system_prompt[:200] if custom_system_prompt else 'None'}")

            # Pass custom_system_prompt to graph query for personalized responses
            graph_answer, context_nodes = querier.query_with_llm(
                user_query,
                max_entities=max_entities,
                custom_system_prompt=custom_system_prompt,
                llm_provider=llm_provider,
                llm_model=model,
                temperature=temperature,
                llm_caller=call_llm,
            )
            logger.info(f"Graph Answer (first 500 chars): {graph_answer[:500]}")

            # Extract entities directly from the context nodes used
            raw_entities = [node['entity'] for node in context_nodes if 'entity' in node]
            
            # Filter out dates (YYYY-MM-DD) and specific noise words
            import re
            date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
            # Add specific terms user found irrelevant
            stopwords = {'Readwise', 'Source', 'Context', 'Key', 'Attached', 'Static', 'Unknown'}
            
            verified_entities = []
            for e in raw_entities:
                # Skip dates
                if date_pattern.match(e.strip()):
                    continue
                # Skip stopwords (case-insensitive check)
                if e.strip().title() in stopwords or e.strip() in stopwords:
                    continue
                # Skip short numeric artifacts
                if e.strip().isdigit() and len(e.strip()) < 4:
                    continue
                    
                verified_entities.append(e)
                
            # Deduplicate with case normalization preference
            # Prefer "ESP32" over "esp32", "IoT" over "iot" (heuristic: prefer more uppercase)
            normalized_map = {}
            for e in verified_entities:
                norm = e.lower()
                if norm not in normalized_map:
                    normalized_map[norm] = e
                else:
                    # If current entity has more uppercase letters than stored one, replace it
                    # e.g. "ESP32" (3 filtered upper) > "esp32" (0)
                    current_upper = sum(1 for c in e if c.isupper())
                    stored_upper = sum(1 for c in normalized_map[norm] if c.isupper())
                    if current_upper > stored_upper:
                        normalized_map[norm] = e
            
            entities = list(normalized_map.values())
            logger.info(f"Extracted {len(entities)} verified graph entities for visualization (filtered from {len(raw_entities)})")
            retrieval_debug = getattr(querier, "last_retrieval_debug", {}) or {}
            path_source_files = {
                str(node.get("path", "") or "")
                for path in retrieval_debug.get("paths", [])
                for node in path.get("nodes", [])
                if str(node.get("kind", "") or "").lower() in {"note", "pdf"}
                and str(node.get("path", "") or "").strip()
            }

            # Build base response
            base_response = {
                'answer': graph_answer,
                'query': user_query,
                'mode': mode,
                'extracted_entities': entities
            }
            if retrieval_debug.get("intent") == "connection" and retrieval_debug.get("paths"):
                base_response["paths"] = retrieval_debug.get("paths", [])
                base_response["retrieval_intent"] = "connection"
            elif retrieval_debug.get("intent"):
                base_response["retrieval_intent"] = retrieval_debug.get("intent")

            # Pre-populate sources from graph context nodes as initial fallback
            query_terms = {t for t in re.split(r"\W+", user_query.lower()) if len(t) > 2}
            stopwords = {
                "and", "or", "the", "a", "an", "in", "on", "with", "for", "to", "of",
                "from", "by", "is", "are", "was", "were", "be", "been", "it", "this",
                "that", "these", "those", "as", "at", "via", "etc"
            }
            query_terms = {t for t in query_terms if t not in stopwords}
            query_terms = expand_query_terms(user_query, query_terms)
            is_summary_query = user_query.strip().lower() in ["summary", "overview", "graph", "nodes", "concepts"]
            keyword_boosts = load_keyword_boosts()
            integration_cfg = keyword_boosts.get("integration", {})
            integration_keywords = integration_cfg.get("keywords", DEFAULT_INTEGRATION_KEYWORDS)
            integration_weight = float(integration_cfg.get("weight", 4.0))
            integration_intent = is_integration_intent(user_query, query_terms)
            term_count = len(query_terms)
            hardware_terms = {
                "nextion", "esp32", "esp8266", "esp", "uart", "gpio", "i2c", "spi",
                "pinout", "wiring", "display", "screen", "hmi", "sensor", "board", "pcb"
            }
            hardware_query = any(term in query_terms for term in hardware_terms)
            query_has_integration = any(t.startswith("integrat") for t in query_terms)
            query_has_agent = any(t.startswith("agent") for t in query_terms)
            query_has_supervisor = "supervisor" in query_terms
            query_has_moc = "moc" in query_terms

            graph_sources = []
            seen_source_files = set()
            total_source_count = 0
            MAX_GRAPH_SOURCES = 40  # Cap total sources from graph
            ai_folder_markers = [
                "tech/ai/", "/ai/", "rag/", "obsidian_rag"
            ]
            
            for node in context_nodes:
                if total_source_count >= MAX_GRAPH_SOURCES:
                    break
                    
                node_props = node.get('properties', {})
                entity_name = node.get('entity', '')
                retrieval_score = float(node_props.get('retrieval_score', 0.0) or 0.0)
                retrieval_depth = int(node_props.get('retrieval_depth', 9) or 9)
                retrieval_path_hit = bool(node_props.get('retrieval_path_hit', False))
                retrieval_seed_hits = int(node_props.get('retrieval_seed_hits', 0) or 0)
                retrieval_intent = str(node_props.get('retrieval_intent', '') or '').strip().lower()
                retrieval_node_kind = str(node_props.get('retrieval_node_kind', '') or '').strip().lower()
                timeline_date = str(node_props.get('timeline_date', '') or '').strip()
                node_path = str(node_props.get('path', '') or '').strip()
                entity_text = f"{entity_name} {node_props.get('description', '')}".lower()
                entity_text_norm = normalize_text(entity_text)
                match_terms = [
                    term for term in query_terms
                    if term_in_text(term, entity_text, entity_text_norm)
                ]
                match_strength = len(match_terms)
                # Only surface sources for entities that match query terms
                if not is_summary_query and query_terms:
                    if match_strength == 0:
                        filename_match = False
                        for src in node_props.get('sources', []):
                            fname = src.get('filename', '').lower()
                            if not fname:
                                continue
                            if count_term_matches(query_terms, fname) > 0:
                                filename_match = True
                                break
                        if not filename_match and not retrieval_path_hit and not (retrieval_intent == "timeline" and timeline_date):
                            continue
                        match_strength = 1 if (filename_match or retrieval_path_hit or timeline_date) else 0
                # Our GraphBuilder adds 'sources' list to properties
                node_sources = node_props.get('sources', [])
                
                # Limit sources per node to prevent one central node from pulling in hundreds of files
                node_source_limit = 8
                current_node_sources = 0
                
                for src in node_sources:
                    if total_source_count >= MAX_GRAPH_SOURCES or current_node_sources >= node_source_limit:
                        break
                        
                    fname = src.get('filename', 'Unknown')
                    fname_lower = fname.lower()
                    fname_norm = normalize_text(fname_lower)
                    # Basic validation of filename
                    if not fname or fname == 'Unknown' or '.' not in fname:
                        continue
                        
                    if fname not in seen_source_files:
                        seen_source_files.add(fname)
                        filename_match_count = count_term_matches(query_terms, fname_lower)
                        direct_path_source = bool(
                            retrieval_path_hit
                            and retrieval_node_kind in {"note", "pdf"}
                            and (
                                (node_path and node_path == fname)
                                or fname in path_source_files
                            )
                        )
                        if not is_summary_query and term_count >= 2:
                            if match_strength < 2 and filename_match_count < 2:
                                allow_path_exception = retrieval_path_hit and retrieval_seed_hits >= 2
                                allow_timeline_exception = (
                                    retrieval_intent == "timeline"
                                    and bool(timeline_date)
                                    and filename_match_count >= 1
                                )
                                if not (
                                    allow_path_exception
                                    or allow_timeline_exception
                                    or (match_strength == 1 and filename_match_count >= 1 and term_count <= 3)
                                ):
                                    continue
                        
                        # Calculate dynamic relevance
                        # Range will be roughly 70% to 95%
                        importance = node_props.get('importance', 5)
                        try:
                            importance_val = float(importance)
                        except:
                            importance_val = 5.0
                            
                        # Boost relevance if the entity name is actually in the query
                        entity_name = node.get('entity', '').lower()
                        query_lower = user_query.lower()
                        entity_match = entity_name in query_lower or query_lower in entity_name
                        
                        keyword_hits = 0
                        if integration_intent and match_strength > 0:
                            keyword_hits = count_keyword_hits(
                                f"{entity_text} {fname_lower}",
                                integration_keywords
                            )
                        keyword_boost = min(keyword_hits * integration_weight, 8.0)
                        effective_match_strength = max(match_strength, min(filename_match_count, 2))
                        term_count_safe = max(1, term_count)
                        coverage = effective_match_strength / term_count_safe
                        base_rel = 55.0 + (coverage * 25.0)
                        entity_match_bonus = 5.0 if entity_match else 0.0
                        graph_rank_bonus = min(retrieval_score * 0.45, 16.0)
                        path_bonus = 8.0 if retrieval_path_hit else 0.0
                        direct_path_bonus = 6.0 if direct_path_source else 0.0
                        seed_bonus = min(max(retrieval_seed_hits - 1, 0) * 1.5, 4.5)
                        depth_bonus = max(0.0, 4.0 - float(retrieval_depth))
                        timeline_bonus = 4.0 if retrieval_intent == "timeline" and timeline_date else 0.0
                        relevance = min(
                            95.0,
                            base_rel
                            + (importance_val * 1.5)
                            + keyword_boost
                            + entity_match_bonus
                            + graph_rank_bonus
                            + path_bonus
                            + direct_path_bonus
                            + seed_bonus
                            + depth_bonus
                            + timeline_bonus
                        )
                        if coverage < 0.5:
                            if retrieval_intent == "connection" and retrieval_path_hit:
                                relevance = max(relevance, 84.0 if direct_path_source else 80.0)
                            elif retrieval_intent == "connection":
                                relevance = min(relevance, 72.0)
                            else:
                                relevance = min(relevance, 78.0)
                        if hardware_query and any(marker in fname_lower for marker in ai_folder_markers):
                            relevance -= 12.0
                        if not query_has_moc and term_in_text("moc", fname_lower, fname_norm):
                            relevance -= 6.0
                        if not query_has_agent and term_in_text("agent", fname_lower, fname_norm):
                            relevance -= 10.0
                        if not query_has_supervisor and term_in_text("supervisor", fname_lower, fname_norm):
                            relevance -= 10.0
                        if not query_has_integration and term_in_text("integration", fname_lower, fname_norm):
                            relevance -= 4.0
                        relevance = max(0.0, relevance)

                        snippet_parts = []
                        if retrieval_intent == "connection" and retrieval_path_hit:
                            if direct_path_source:
                                snippet_parts.append(
                                    f"On explicit graph path. depth={retrieval_depth}, seed_hits={retrieval_seed_hits}."
                                )
                            else:
                                snippet_parts.append(
                                    f"Connected via explicit graph path through {node.get('entity', 'graph context')}."
                                )
                        elif retrieval_intent == "timeline" and timeline_date:
                            snippet_parts.append(f"Timeline note dated {timeline_date}.")
                        else:
                            snippet_parts.append(f"Context: {node['entity']} mentioned.")

                        description = str(node_props.get('description', '') or '').strip()
                        if description:
                            snippet_parts.append(description)
                        
                        graph_sources.append({
                            'filename': fname,
                            'filepath': fname,
                            'relevance': relevance,
                            'snippet': " ".join(part for part in snippet_parts if part).strip(),
                            'match_strength': effective_match_strength,
                            'path_source': direct_path_source,
                            'path_hit': retrieval_path_hit,
                        })
                        total_source_count += 1
                        current_node_sources += 1
            
            if graph_sources and not is_summary_query:
                graph_sources.sort(
                    key=lambda x: (
                        x.get('path_source', False),
                        x.get('path_hit', False),
                        x.get('match_strength', 0),
                        x['relevance'],
                    ),
                    reverse=True
                )
                if retrieval_debug.get("intent") == "connection":
                    explicit_connection_sources = [
                        source for source in graph_sources
                        if source.get('path_hit', False)
                    ]
                    if explicit_connection_sources:
                        graph_sources = explicit_connection_sources
                graph_sources = graph_sources[:MAX_GRAPH_SOURCES]

            for source in graph_sources:
                source.pop('match_strength', None)
                source.pop('path_source', None)
                source.pop('path_hit', None)

            base_response['sources'] = graph_sources


            # Step 2: If mode is 'hybrid', enhance with vector search
            if mode == 'hybrid':
                try:
                    # === STEP 2a: HyDE Enhancement ===
                    # Generate hypothetical answer for better vector retrieval
                    hyde_text = generate_hyde_text(user_query, llm_provider, model)
                    
                    # Search using both original query and hypothetical answer
                    enhanced_query = f"{user_query} {hyde_text} {' '.join(entities)}"

                    vector_response = requests.post(
                        f'{EMBEDDING_SERVICE_URL}/query',
                        json={
                            'query': enhanced_query,
                            'n_results': n_results,
                            'reranking': True,
                            'deduplicate': True,
                            'relevance_threshold': 40,  # Filter out noise < 40%
                            'expand_query': False,
                        },
                        timeout=60,
                        headers=_service_headers()
                    )

                    if vector_response.status_code == 200:
                        vector_data = vector_response.json()
                        documents = vector_data.get('documents', [[]])[0]
                        metadatas = vector_data.get('metadatas', [[]])[0]
                        distances = vector_data.get('distances', [[]])[0]

                        # Build vector context
                        vector_sources = []
                        context_parts = []
                        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                            # Calculate relevance matching embedding service logic
                            relevance = relevance_from_distance(dist)

                            if relevance < 75: continue


                            filename = meta.get('filename', 'unknown')
                            filepath = meta.get('filepath', 'unknown')
                            snippet = doc[:300] + "..." if len(doc) > 300 else doc
                            
                            doc_context = f"Source {i} ({filename}):\n{doc}\n"
                            context_parts.append(doc_context)

                            vector_sources.append({
                                'filename': filename,
                                'filepath': filepath,
                                'relevance': relevance,
                                'snippet': snippet
                            })

                        # CRITICAL FIX: If we found good vector sources, REPLACE the potential fallback graph sources
                        # This prevents showing "Hacking with iOS" (from central nodes) when we actually found "Nextion MoC" via vector
                        if vector_sources:
                            # Only keep graph sources if they are highly relevant (>80%) - i.e. actual entity matches
                            # "Hacking with iOS" usually comes in at ~73% from the graph fallback logic
                            high_quality_graph_sources = [s for s in graph_sources if s['relevance'] > 80]
                            
                            # Combine: Strong Vector matches + Strong Graph matches
                            final_sources = vector_sources + high_quality_graph_sources
                            logger.info(f"Hybrid Merge: {len(vector_sources)} vector sources + {len(high_quality_graph_sources)} graph sources")
                        else:
                             # No vector sources found? Keep the graph ones (better than nothing)
                             final_sources = graph_sources

                        base_response['sources'] = final_sources
                        base_response['extracted_entities'] = entities

                        
                        # SYNTHESIS STEP: Re-generate answer using both Graph and Vector context
                        logger.info("Synthesizing Hybrid Answer with Vector Context...")
                        vector_context_text = "\n".join(context_parts)
                        
                        # Prepare context strings
                        vault_context = f"=== GRAPH ANALYSIS ===\n{graph_answer}\n\n=== DOCUMENTS ===\n{vector_context_text}"
                        
                        # === STEP 2b: Personal Memory Integration ===
                        logger.info("Fetching Personal Memories from mem0...")
                        memory_manager = get_memory_manager()
                        memory_context = ""
                        if memory_manager:
                            memory_context = memory_manager.search_memory(user_query)
                        else:
                            logger.warning("Memory manager not available (mem0 import likely failed)")
                        if not memory_context:
                            memory_context = "(No specific personal history found for this query)"
                        
                        synthesis_system_prompt = f"""Your task is to answer questions by analyzing the retrieved materials and Michel's personal context.

**CRITICAL INSTRUCTION**: You have been provided with extensive context from Michel's notes, memory, and knowledge graphs. Your job is to SYNTHESIZE and SUMMARIZE this information to answer the question. DO NOT claim "insufficient information" unless the retrieved context is genuinely empty or completely unrelated to the query.

### CONTEXT FROM MEMORY
{memory_context}

### RELEVANT NOTES FROM VAULT
{vault_context}

### USER QUESTION
{user_query}

When generating your answer:
1. **USE THE PROVIDED CONTEXT**: Synthesize information from the retrieved documents, graph analysis, and memory.
2. Reference Michel's specific **medical timeline** (DLBCL, Yescarta, scans) when relevant.
3. Incorporate insights from his **Obsidian notes**, citing which notes or sources you use.
4. Maintain a **compassionate and supportive** tone for medical topics.
5. Provide **technical depth** and precision for engineering and coding topics.
6. Adapt to his **expert-level understanding** — avoid overexplaining known concepts.
7. Be **concise but thorough**, focusing on clarity and reasoning.
8. Avoid redundant or generic phrasing.
9. **Ground the answer in the notes**; avoid generic background not present in sources.
10. If a specific detail is missing, say "Not found in notes" and suggest what to search for next.

Finally, provide your answer in a structured, easy-to-read format.

**Answer:**
"""
                        synthesis_appendix = build_prompt_appendix(user_query, llm_provider)
                        if synthesis_appendix:
                            synthesis_system_prompt = f"{synthesis_system_prompt}\n\n{synthesis_appendix}"
                        # Call LLM for final synthesis
                        final_answer = call_llm(llm_provider, model, synthesis_system_prompt, user_query, temperature)
                        base_response['answer'] = final_answer
                        
                        # === STEP 2c: Async Memory Update ===
                        def update_mem0():
                            try:
                                interaction = f"User asked: {user_query}\nAssistant answered: {final_answer}"
                                memory_manager.add_memory(interaction)
                                logger.info("mem0 personal memory updated successfully")
                            except Exception as ex:
                                logger.error(f"Failed to update mem0: {ex}")
                        
                        threading.Thread(target=update_mem0, daemon=True).start()
                        
                    else:
                        logger.warning(f"Vector search failed with status {vector_response.status_code}")
                        base_response['mode'] = 'graph'
                        base_response['warning'] = 'Vector search unavailable, returned graph-only result'

                except Exception as e:
                    logger.error(f"Hybrid search error: {e}")
                    base_response['mode'] = 'graph'
                    base_response['warning'] = f'Hybrid search failed: {str(e)}'

            # Step 3: If web search is requested, extract terms from combined context
            if web_search_enabled:
                try:
                    from tavily import TavilyClient

                    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
                    if TAVILY_API_KEY:
                        # Combine graph answer and vector sources for richer context
                        combined_context = graph_answer
                        if base_response.get('sources'):
                            # Add top 3 vector source snippets to context
                            top_sources = base_response['sources'][:3]
                            source_text = "\n\n".join([f"Source: {s['snippet']}" for s in top_sources])
                            combined_context = f"Graph Analysis:\n{graph_answer}\n\nVault Context:\n{source_text}"

                        # Extract specific medical/technical terms from combined context
                        search_terms_prompt = f"""Based on this combined knowledge, extract 4-6 specific medical terms, medications, procedures, measurements, or technical concepts that would find the most relevant and detailed clinical information on the web. Focus on:
- Specific medical conditions, diseases, or syndromes mentioned
- Medications, treatments, or procedures
- Technical measurements, biomarkers, or test results
- Specific medical entities (not general terms)

Context:
{combined_context[:1500]}

Provide only the search terms separated by spaces, no explanation or formatting."""

                        # Call OpenRouter with Kimi to extract search terms
                        from openai import OpenAI
                        client = OpenAI(
                            base_url="https://openrouter.ai/api/v1",
                            api_key=os.environ.get("OPENROUTER_API_KEY")
                        )
                        web_search_model = os.getenv(
                            "GRAPH_WEB_SEARCH_MODEL", _default_openrouter_model()
                        )

                        terms_response = client.chat.completions.create(
                            model=web_search_model,
                            messages=[{"role": "user", "content": search_terms_prompt}],
                            max_tokens=100
                        )
                        search_terms = terms_response.choices[0].message.content.strip()

                        logger.info(f"Web search terms extracted: {search_terms}")

                        # Perform web search with extracted terms
                        tavily = TavilyClient(api_key=TAVILY_API_KEY)
                        search_response = tavily.search(query=search_terms, search_depth="advanced", max_results=5)

                        if 'results' in search_response and search_response['results']:
                            web_results = []
                            for res in search_response['results'][:3]:
                                web_results.append({
                                    'title': res['title'],
                                    'url': res['url'],
                                    'content': res['content']
                                })

                            base_response['web_search'] = {
                                'search_terms': search_terms,
                                'results': web_results
                            }
                            logger.info(f"Web search returned {len(web_results)} results")
                        else:
                            base_response['web_search'] = {
                                'search_terms': search_terms,
                                'results': [],
                                'message': 'No web results found'
                            }
                            logger.warning("Web search returned no results")
                    else:
                        base_response['web_search'] = {
                            'error': 'TAVILY_API_KEY not configured'
                        }
                        logger.error("TAVILY_API_KEY not set")
                except ImportError:
                    base_response['web_search'] = {
                        'error': 'tavily-python not installed'
                    }
                    logger.error("tavily-python package not installed")
                except Exception as e:
                    logger.error(f"Web search error: {e}")
                    base_response['web_search'] = {
                        'error': str(e)
                    }

            # Step 4: If LLM knowledge is requested, get additional insights
            if llm_knowledge_enabled:
                try:
                    # Build knowledge prompt that complements the main answer
                    # Use custom system prompt if provided, otherwise use default
                    if custom_system_prompt:
                        knowledge_prompt = f"""{custom_system_prompt}

Based on the following information found in the user's vault:

{graph_answer[:2000]}

User's question: {user_query}

Provide ADDITIONAL insights, clinical context, or alternative perspectives that COMPLEMENT (not repeat) the vault information."""
                    else:
                        knowledge_prompt = f"""Based on the following information found in the user's vault:

{graph_answer[:2000]}

User's question: {user_query}

Provide ADDITIONAL insights, clinical context, or alternative perspectives that COMPLEMENT (not repeat) the vault information. Focus on:
1. Clinical implications of the findings
2. Treatment considerations mentioned
3. Additional context that would be helpful
4. Answering aspects of the question not covered by vault notes"""

                    # Call LLM for additional knowledge
                    llm_knowledge = call_llm(llm_provider, model, knowledge_prompt, user_query, temperature)
                    base_response['llm_knowledge'] = llm_knowledge
                    logger.info("LLM knowledge section generated")

                except Exception as e:
                    logger.error(f"LLM knowledge error: {e}")
                    base_response['llm_knowledge'] = {
                        'error': str(e)
                    }

            # Add response alias for researcher compatibility
            base_response['response'] = base_response.get('answer', '')
            return jsonify(base_response)

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/query_stream', methods=['POST'])
def query_stream():
    """
    Streaming version of /query endpoint for real-time LLM responses.

    Accepts same parameters as /query but returns Server-Sent Events (SSE) stream.

    Request body:
    {
        "query": "What treatments are mentioned?",
        "mode": "vector" | "graph" | "hybrid",
        "llm_provider": "ollama" | "claude" | "gemini" | "gpt-oss" | "kimi" | "openrouter",
        "model": "llama2",
        "temperature": 0.7,
        "system_prompt": "Custom instructions...",
        "n_results": 10,
        "stream": true  // Must be true for streaming
    }

    Returns: Server-Sent Events stream with JSON chunks
    """
    try:
        data = request.json
        user_query = data.get('query', '')
        mode = data.get('mode', 'vector')  # Default to vector for streaming
        llm_provider = data.get('llm_provider', 'ollama')
        model = data.get('model', '')
        temperature = data.get('temperature', 0.7)
        custom_system_prompt = data.get('system_prompt', '')
        n_results = data.get('n_results', 10)

        if not user_query:
            return jsonify({'error': 'Query is required'}), 400

        # Set default models
        if not model:
            model = _default_model_for_provider(llm_provider, streaming=True)

        def generate_stream():
            """Generator function for streaming response"""
            try:
                # Send metadata first
                yield f"data: {json.dumps({'type': 'metadata', 'mode': mode, 'provider': llm_provider, 'model': model})}\n\n"

                # Handle vector mode with streaming
                if mode == 'vector':
                    # Get vector search results
                    vector_response = requests.post(
                        f'{EMBEDDING_SERVICE_URL}/query',
                        json={
                            'query': user_query,
                            'n_results': n_results,
                            'reranking': True,
                            'deduplicate': True
                        },
                        timeout=30,
                        headers=_service_headers()
                    )

                    if vector_response.status_code != 200:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Vector search failed'})}\n\n"
                        return

                    vector_data = vector_response.json()
                    documents = vector_data.get('documents', [[]])[0]
                    metadatas = vector_data.get('metadatas', [[]])[0]
                    distances = vector_data.get('distances', [[]])[0]

                    # Build context and sources
                    context_parts = []
                    vector_sources = []

                    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                        relevance = (1 / (1 + abs(dist))) * 100 if dist < 0 else (1 / (1 + dist)) * 100
                        relevance = min(100, max(0, relevance))

                        filename = meta.get('filename', 'unknown')
                        filepath = meta.get('filepath', 'unknown')
                        snippet = doc[:200] + "..." if len(doc) > 200 else doc

                        context_parts.append(f"Source {i} ({filename}):\n{doc}\n")
                        vector_sources.append({
                            'filename': filename,
                            'filepath': filepath,
                            'relevance': relevance,
                            'snippet': snippet
                        })

                    # Send sources
                    yield f"data: {json.dumps({'type': 'sources', 'sources': vector_sources})}\n\n"

                    context_text = "\n".join(context_parts)

                    # Build system prompt
                    system_prompt = build_vault_system_prompt(
                        context_text=context_text,
                        user_query=user_query,
                        provider=llm_provider,
                        custom_prompt=custom_system_prompt
                    )

                    # Stream LLM response
                    yield f"data: {json.dumps({'type': 'start'})}\n\n"

                    for chunk in call_llm_stream(llm_provider, model, system_prompt, user_query, temperature):
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

                elif mode == 'graph':
                    # Graph mode with streaming
                    if not graph_loaded:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Graph not loaded'})}\n\n"
                        return

                    # For graph mode, we can't stream the initial query result
                    # but we can send it in chunks
                    graph_answer, _ = querier.query_with_llm(
                        user_query,
                        max_entities=20,
                        llm_provider=llm_provider,
                        llm_model=model,
                        temperature=temperature,
                        llm_caller=call_llm,
                    )

                    yield f"data: {json.dumps({'type': 'start'})}\n\n"

                    # Chunk the response for streaming effect
                    words = graph_answer.split(' ')
                    for i, word in enumerate(words):
                        chunk = word + (' ' if i < len(words) - 1 else '')
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

                elif mode == 'hybrid':
                    # Hybrid mode - similar to graph but with vector enhancement
                    if not graph_loaded:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Graph not loaded'})}\n\n"
                        return

                    # Get graph answer
                    graph_answer, _ = querier.query_with_llm(
                        user_query,
                        max_entities=20,
                        llm_provider=llm_provider,
                        llm_model=model,
                        temperature=temperature,
                        llm_caller=call_llm,
                    )

                    # Use provided entities or fallback to extracting from graph
                    entities = provided_entities if provided_entities is not None else extract_entities_from_graph(graph_answer)
                    enhanced_query = f"{user_query} {' '.join(entities)}"

                    vector_response = requests.post(
                        f'{EMBEDDING_SERVICE_URL}/query',
                        json={
                            'query': enhanced_query,
                            'n_results': n_results,
                            'reranking': True,
                            'deduplicate': True,
                            'expand_query': False
                        },
                        timeout=60,
                        headers=_service_headers()
                    )

                    vector_sources = []
                    if vector_response.status_code == 200:
                        vector_data = vector_response.json()
                        documents = vector_data.get('documents', [[]])[0]
                        metadatas = vector_data.get('metadatas', [[]])[0]
                        distances = vector_data.get('distances', [[]])[0]

                        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                            relevance = (1 / (1 + abs(dist))) * 100 if dist < 0 else (1 / (1 + dist)) * 100
                            vector_sources.append({
                                'filename': meta.get('filename', 'unknown'),
                                'filepath': meta.get('filepath', 'unknown'),
                                'relevance': min(100, max(0, relevance)),
                                'snippet': doc[:200] + "..." if len(doc) > 200 else doc
                            })

                    # Send sources and entities
                    yield f"data: {json.dumps({'type': 'sources', 'sources': vector_sources})}\n\n"
                    yield f"data: {json.dumps({'type': 'entities', 'entities': entities})}\n\n"

                    # Stream the answer
                    yield f"data: {json.dumps({'type': 'start'})}\n\n"

                    words = graph_answer.split(' ')
                    for i, word in enumerate(words):
                        chunk = word + (' ' if i < len(words) - 1 else '')
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return Response(
            stream_with_context(generate_stream()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        logger.error(f"Error setting up stream: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/entity/<path:entity_name>', methods=['GET'])
def get_entity(entity_name: str):
    """Get information about a specific entity"""
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        neighborhood = querier.get_entity_neighborhood(entity_name)
        return jsonify(neighborhood)
    except Exception as e:
        logger.error(f"Error getting entity: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/path', methods=['POST'])
def find_path():
    """
    Find paths between two entities
    
    POST body:
    {
        "source": "Entity 1",
        "target": "Entity 2",
        "max_depth": 3  // optional
    }
    """
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        data = request.json
        source = data.get('source', '')
        target = data.get('target', '')
        max_depth = data.get('max_depth', 3)
        
        if not source or not target:
            return jsonify({'error': 'Both source and target are required'}), 400
        
        paths = querier.find_paths(source, target, max_depth)
        
        return jsonify({
            'source': source,
            'target': target,
            'paths': paths,
            'count': len(paths)
        })
    
    except Exception as e:
        logger.error(f"Error finding path: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get graph statistics"""
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        stats = querier.get_graph_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/search_entities', methods=['POST'])
def search_entities():
    """
    Search for entities by name
    
    POST body:
    {
        "query": "search term",
        "limit": 10  // optional
    }
    """
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        data = request.json
        search_query = data.get('query', '').lower()
        limit = data.get('limit', 10)
        
        if not search_query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Search entities
        matching_entities = []
        for node in builder.graph.nodes():
            if search_query in node.lower():
                node_data = dict(builder.graph.nodes[node])
                matching_entities.append({
                    'name': node,
                    'type': node_data.get('entity_type', 'Unknown'),
                    'connections': builder.graph.degree(node)
                })
        
        # Sort by number of connections
        matching_entities.sort(key=lambda x: x['connections'], reverse=True)
        
        return jsonify({
            'query': search_query,
            'results': matching_entities[:limit],
            'total': len(matching_entities)
        })
    
    except Exception as e:
        logger.error(f"Error searching entities: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Initialize graph on startup
    graph_path = os.environ.get('GRAPH_PATH')
    initialize_graph(graph_path)
    
    # Run Flask app
    port = int(os.environ.get('PORT', 8002))
    app.run(host='0.0.0.0', port=port, debug=False)
