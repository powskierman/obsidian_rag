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
from collections import OrderedDict
from urllib.parse import urlparse, urlunparse
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


def _tag_sources(sources: Any, source_type: str) -> List[Dict[str, Any]]:
    tagged: List[Dict[str, Any]] = []
    if not isinstance(sources, list):
        return tagged
    for source in sources:
        if not isinstance(source, dict):
            continue
        try:
            relevance = float(source.get("relevance", 50.0))
        except (TypeError, ValueError):
            relevance = 50.0
        tagged.append(
            {
                **source,
                "relevance": max(0.0, min(100.0, relevance)),
                "source_type": source.get("source_type") or source_type,
            }
        )
    return tagged


def _normalize_vector_sources(result: Any, source_type: str = "direct-excerpt") -> List[Dict[str, Any]]:
    if not isinstance(result, dict):
        return []

    existing_sources = result.get("sources")
    if isinstance(existing_sources, list) and existing_sources:
        normalized_existing: List[Dict[str, Any]] = []
        for source in existing_sources:
            if not isinstance(source, dict):
                continue
            filepath = str(source.get("filepath") or source.get("file_path") or "").strip()
            filename = str(source.get("filename") or "").strip()
            if not filename and filepath:
                filename = filepath.rsplit("/", 1)[-1]
            snippet = str(source.get("snippet") or source.get("content") or "").strip()
            try:
                relevance = float(source.get("relevance", 50.0))
            except (TypeError, ValueError):
                relevance = 50.0
            normalized_existing.append(
                {
                    "filename": filename or "Unknown",
                    "filepath": filepath,
                    "relevance": relevance,
                    "snippet": snippet[:400] + ("..." if len(snippet) > 400 else ""),
                    "source_type": source.get("source_type") or source_type,
                }
            )
        if normalized_existing:
            return normalized_existing

    documents_blob = result.get("documents")
    metadatas_blob = result.get("metadatas")
    distances_blob = result.get("distances")
    if not isinstance(documents_blob, list) or not documents_blob:
        return []

    documents = documents_blob[0] if isinstance(documents_blob[0], list) else []
    metadatas = (
        metadatas_blob[0]
        if isinstance(metadatas_blob, list) and metadatas_blob and isinstance(metadatas_blob[0], list)
        else []
    )
    distances = (
        distances_blob[0]
        if isinstance(distances_blob, list) and distances_blob and isinstance(distances_blob[0], list)
        else []
    )

    normalized: List[Dict[str, Any]] = []
    for idx, doc in enumerate(documents):
        meta = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
        dist = distances[idx] if idx < len(distances) else None
        try:
            relevance = max(0.0, min(100.0, 100.0 / (1.0 + math.exp(float(dist) / 2.0))))
        except (TypeError, ValueError, OverflowError):
            relevance = 50.0
        filepath = str(meta.get("filepath") or meta.get("file_path") or "").strip()
        filename = str(meta.get("filename") or "").strip()
        if not filename and filepath:
            filename = filepath.rsplit("/", 1)[-1]
        doc_text = doc if isinstance(doc, str) else ""
        normalized.append(
            {
                "filename": filename or "Unknown",
                "filepath": filepath,
                "relevance": relevance,
                "snippet": doc_text[:400] + ("..." if len(doc_text) > 400 else ""),
                "source_type": source_type,
            }
        )

    return normalized


def _is_insufficient_answer(text: Any) -> bool:
    if not isinstance(text, str):
        return True
    cleaned = text.strip().lower()
    if not cleaned:
        return True
    patterns = (
        "cannot provide the analysis",
        "cannot answer",
        "insufficient information",
        "no relevant notes",
        "no relevant relationships",
        "no relevant notes or relationships",
        "provided knowledge graph",
        "would need:",
        "i would need",
        "placeholder",
        "[unknown]",
        "without properly labeled notes",
        "if you can provide a clearer knowledge graph",
    )
    return any(pattern in cleaned for pattern in patterns)


def _build_dual_source_answer(
    primary_answer: Any,
    primary_sources: List[Dict[str, Any]],
    vector_sources: List[Dict[str, Any]],
    *,
    primary_label: str,
) -> str:
    if isinstance(primary_answer, str) and not _is_insufficient_answer(primary_answer):
        return primary_answer

    if primary_sources and vector_sources:
        return (
            f"Showing {len(primary_sources)} {primary_label} items and "
            f"{len(vector_sources)} direct note excerpts below."
        )
    if primary_sources:
        return f"Showing {len(primary_sources)} {primary_label} items below."
    if vector_sources:
        return f"Showing {len(vector_sources)} direct note excerpts below."
    if isinstance(primary_answer, str) and primary_answer.strip():
        return primary_answer
    return "No results found"


def _source_search_text(source: Dict[str, Any]) -> str:
    if not isinstance(source, dict):
        return ""
    parts = [
        str(source.get("filename") or "").strip(),
        str(source.get("filepath") or "").strip(),
        str(source.get("snippet") or "").strip(),
    ]
    return " ".join(part for part in parts if part).lower()


def _source_anchor_text(source: Dict[str, Any]) -> str:
    if not isinstance(source, dict):
        return ""
    filename = str(source.get("filename") or "").strip().lower()
    filepath = str(source.get("filepath") or "").strip().lower()
    basename = filepath.replace("\\", "/").rsplit("/", 1)[-1] if filepath else filename
    snippet = str(source.get("snippet") or "").strip().lower()
    return " ".join(part for part in (basename, filename, snippet) if part)


def _anchor_term_variants(term: str) -> set[str]:
    if not isinstance(term, str):
        return set()
    cleaned = term.strip().lower()
    if not cleaned:
        return set()
    collapsed = re.sub(r"[\s\-_]+", "", cleaned)
    spaced = re.sub(r"[\-_]+", " ", cleaned)
    hyphenated = re.sub(r"[\s_]+", "-", cleaned)
    return {variant for variant in {cleaned, collapsed, spaced, hyphenated} if variant}


def _group_matches_text(text: str, group: set[str]) -> bool:
    if not text:
        return False
    collapsed_text = re.sub(r"[\s\-_]+", "", text.lower())
    lowered_text = text.lower()
    for term in group:
        for variant in _anchor_term_variants(term):
            if variant in lowered_text or variant in collapsed_text:
                return True
    return False


def _text_matches_anchor_groups(text: str, anchor_groups: List[List[str]]) -> bool:
    if not text:
        return False
    return all(_group_matches_text(text, set(group)) for group in anchor_groups)


def _is_home_assistant_dashboard_query(query: str) -> bool:
    if not isinstance(query, str):
        return False
    text = query.lower()
    has_home_assistant = "home assistant" in text or re.search(r"\bhass\b", text)
    has_dashboard = any(
        token in text for token in ("dashboard", "lovelace", "card", "widget")
    )
    return bool(has_home_assistant and has_dashboard)


def _truncate_source_snippet(text: Any, limit: int = 240) -> str:
    if not isinstance(text, str):
        return ""
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def _source_display_name(source: Dict[str, Any]) -> str:
    if not isinstance(source, dict):
        return "Unknown"
    filename = str(source.get("filename") or "").strip()
    filepath = str(source.get("filepath") or "").strip()
    target = filepath or filename
    if not target:
        return "Unknown"
    return target.replace("\\", "/").rsplit("/", 1)[-1]


def _query_terms(query: str) -> List[str]:
    if not isinstance(query, str):
        return []
    stopwords = {
        "a", "an", "and", "are", "did", "do", "does", "for", "from", "how",
        "i", "in", "is", "it", "my", "of", "on", "or", "the", "to", "using",
        "with", "what", "when", "where", "why", "your",
        "both", "context", "direct", "excerpt", "excerpts", "linked", "show",
    }
    return [
        term for term in re.findall(r"[a-z0-9][a-z0-9\-]+", query.lower())
        if len(term) > 2 and term not in stopwords
    ]


_QUERY_NORMALIZER_CACHE: "OrderedDict[str, str]" = OrderedDict()
_QUERY_NORMALIZER_CACHE_SIZE = max(32, int(os.getenv("QUERY_NORMALIZER_CACHE_SIZE", "256")))
_QUERY_NORMALIZER_TIMEOUT = max(1.0, float(os.getenv("QUERY_NORMALIZER_TIMEOUT_SECONDS", "4.0")))


def _query_anchor_terms(query: str) -> set[str]:
    generic_terms = {
        "associated",
        "association",
        "compare",
        "connections",
        "connected",
        "contrast",
        "context",
        "direct",
        "excerpt",
        "excerpts",
        "linked",
        "mentions",
        "mentioned",
        "note",
        "notes",
        "related",
        "relationship",
        "relationships",
        "show",
        "treatment",
        "treatments",
    }
    return {term for term in _query_terms(query) if term not in generic_terms}


def _short_anchor_groups(query: str) -> List[set[str]]:
    if not isinstance(query, str):
        return []
    text = query.strip().lower()
    if not text:
        return []
    if len(_query_terms(text)) > 8:
        return []

    cleaned = re.sub(r"\b(compare|contrast)\b", " ", text)
    parts = [
        part.strip()
        for part in re.split(r"\s+(?:vs\.?|versus|and)\s+|,\s*", cleaned)
        if part.strip()
    ]
    groups: List[set[str]] = []
    seen: set[frozenset[str]] = set()
    for part in parts:
        terms = _query_anchor_terms(part)
        if not terms:
            continue
        frozen = frozenset(terms)
        if frozen in seen:
            continue
        seen.add(frozen)
        groups.append(set(terms))
    return groups if len(groups) >= 2 else []


def _is_short_multi_anchor_query(query: str) -> bool:
    if not isinstance(query, str):
        return False
    anchor_groups = _short_anchor_groups(query)
    term_count = len(_query_terms(query))
    text = query.lower()
    return len(anchor_groups) >= 2 and term_count <= 4 and any(token in text for token in (" and ", ",", " vs", " versus "))


def _is_short_compare_query(query: str) -> bool:
    if not isinstance(query, str):
        return False
    text = query.lower()
    return len(_short_anchor_groups(query)) >= 2 and any(
        token in text for token in (" vs", " versus ", "compare", "contrast")
    )


def _source_group_hit_count(source: Dict[str, Any], anchor_groups: List[set[str]]) -> int:
    text = _source_anchor_text(source)
    return sum(1 for group in anchor_groups if _group_matches_text(text, group))


def _source_group_match_indexes(source: Dict[str, Any], anchor_groups: List[set[str]]) -> set[int]:
    text = _source_anchor_text(source)
    return {
        idx
        for idx, group in enumerate(anchor_groups)
        if _group_matches_text(text, group)
    }


def _source_basename_group_hit_count(source: Dict[str, Any], anchor_groups: List[set[str]]) -> int:
    basename_text = _source_basename(source)
    return sum(1 for group in anchor_groups if _group_matches_text(basename_text, group))


def _narrative_source_list(sources: List[Dict[str, Any]], limit: int = 3) -> str:
    names: List[str] = []
    seen: set[str] = set()
    for source in sources:
        name = _source_display_name(source)
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
        if len(names) >= limit:
            break
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _prioritize_short_anchor_sources(
    sources: List[Dict[str, Any]],
    anchor_groups: List[set[str]],
    *,
    max_total: int,
    compare_mode: bool = False,
) -> List[Dict[str, Any]]:
    if not sources or not anchor_groups:
        return sources[:max_total]

    ranked_sources = sorted(
        sources,
        key=lambda src: (
            _source_group_hit_count(src, anchor_groups),
            _source_basename_group_hit_count(src, anchor_groups),
            float(src.get("_rank_score", 0.0)),
            float(src.get("relevance", 0.0)),
        ),
        reverse=True,
    )
    selected: List[Dict[str, Any]] = []
    selected_keys: set[str] = set()

    def add_source(source: Dict[str, Any]) -> None:
        key = _source_path_key(source)
        if not key or key in selected_keys or len(selected) >= max_total:
            return
        selected.append(source)
        selected_keys.add(key)

    group_count = len(anchor_groups)
    fully_covering = [
        source
        for source in ranked_sources
        if _source_group_hit_count(source, anchor_groups) >= group_count
    ]
    if fully_covering and not compare_mode:
        return fully_covering[:max_total]

    if compare_mode:
        for group_index in range(group_count):
            for source in ranked_sources:
                if (
                    group_index in _source_group_match_indexes(source, anchor_groups)
                    and _source_basename_group_hit_count(source, anchor_groups) > 0
                ):
                    add_source(source)
                    break
            else:
                for source in ranked_sources:
                    if group_index in _source_group_match_indexes(source, anchor_groups):
                        add_source(source)
                        break
        return selected[:max_total]

    uncovered = set(range(group_count))
    while uncovered and len(selected) < max_total:
        best_source: Optional[Dict[str, Any]] = None
        best_key: tuple[int, int, float, float] | None = None
        for source in ranked_sources:
            if _source_path_key(source) in selected_keys:
                continue
            matches = _source_group_match_indexes(source, anchor_groups)
            new_coverage = len(matches & uncovered)
            if new_coverage <= 0:
                continue
            candidate_key = (
                new_coverage,
                _source_basename_group_hit_count(source, anchor_groups),
                len(matches),
                float(source.get("_rank_score", 0.0)),
                float(source.get("relevance", 0.0)),
            )
            if best_key is None or candidate_key > best_key:
                best_source = source
                best_key = candidate_key
        if best_source is None:
            break
        add_source(best_source)
        uncovered -= _source_group_match_indexes(best_source, anchor_groups)

    for source in ranked_sources:
        if _source_group_hit_count(source, anchor_groups) > 0:
            add_source(source)

    return selected[:max_total]


def _should_normalize_query(query: str) -> bool:
    if not isinstance(query, str):
        return False
    text = query.strip().lower()
    if not text:
        return False
    terms = _query_terms(text)
    if len(terms) <= 2:
        return False
    instruction_phrases = (
        "show both linked-note context",
        "direct note excerpts",
        "linked-note context",
        "in my notes",
        "from my notes",
        "in the graph",
        "based on my notes",
        "associated with",
        "connected to",
    )
    if any(phrase in text for phrase in instruction_phrases):
        return True
    return len(terms) >= 7


def _deterministic_normalize_query(query: str) -> str:
    if not isinstance(query, str):
        return ""
    normalized = query.strip()
    if not normalized:
        return ""

    direct_excerpt_patterns = (
        r"^\s*show both linked-note context and direct note excerpts for\s+",
        r"^\s*show linked-note context and direct note excerpts for\s+",
        r"^\s*show direct note excerpts and linked-note context for\s+",
        r"^\s*show both direct note excerpts and linked-note context for\s+",
    )
    for pattern in direct_excerpt_patterns:
        normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE).strip()

    relationships_match = re.match(
        r"^\s*what relationships and treatments are associated with\s+(.+?)\s+in my notes\??\s*$",
        normalized,
        flags=re.IGNORECASE,
    )
    if relationships_match:
        topic = relationships_match.group(1).strip()
        return f"{topic} relationships treatments".strip()

    normalized = re.sub(r"\bin my notes\b", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bfrom my notes\b", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bin the graph\b", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ?")
    return normalized or query.strip()


def _normalizer_cache_key(query: str, provider: str, model: Optional[str]) -> str:
    return f"{provider or ''}::{model or ''}::{query.strip().lower()}"


def _get_cached_normalized_query(query: str, provider: str, model: Optional[str]) -> Optional[str]:
    key = _normalizer_cache_key(query, provider, model)
    cached = _QUERY_NORMALIZER_CACHE.get(key)
    if cached is None:
        return None
    _QUERY_NORMALIZER_CACHE.move_to_end(key)
    return cached


def _set_cached_normalized_query(query: str, provider: str, model: Optional[str], normalized: str) -> None:
    key = _normalizer_cache_key(query, provider, model)
    _QUERY_NORMALIZER_CACHE[key] = normalized
    _QUERY_NORMALIZER_CACHE.move_to_end(key)
    while len(_QUERY_NORMALIZER_CACHE) > _QUERY_NORMALIZER_CACHE_SIZE:
        _QUERY_NORMALIZER_CACHE.popitem(last=False)


def _extract_json_object(text: str) -> Dict[str, Any]:
    if not isinstance(text, str):
        return {}
    text = text.strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _resolve_query_normalizer_provider(provider: str, model: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    override_provider = os.getenv("QUERY_NORMALIZER_PROVIDER", "").strip().lower()
    override_model = os.getenv("QUERY_NORMALIZER_MODEL", "").strip()
    candidate_provider = override_provider or (provider or "").strip().lower()
    candidate_model = override_model or model

    supported = {"ollama", "openrouter", "chatgpt", "mlx"}
    if candidate_provider in supported:
        return candidate_provider, candidate_model

    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter", os.getenv("QUERY_NORMALIZER_MODEL", "").strip() or os.getenv("OPENROUTER_MODEL", "openrouter/auto")
    if os.getenv("OPENAI_API_KEY"):
        return "chatgpt", os.getenv("QUERY_NORMALIZER_MODEL", "").strip() or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if os.getenv("MLX_BASE_URL") or os.getenv("MLX_MODEL"):
        return "mlx", os.getenv("QUERY_NORMALIZER_MODEL", "").strip() or os.getenv("MLX_MODEL")
    if os.getenv("OLLAMA_HOST"):
        return "ollama", os.getenv("QUERY_NORMALIZER_MODEL", "").strip() or os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
    return None, None


async def _call_query_normalizer_llm(query: str, provider: str, model: Optional[str]) -> Optional[str]:
    if not query.strip():
        return None

    system_prompt = (
        "You normalize retrieval queries for a personal knowledge base. "
        "Return JSON only with keys: query, must_terms. "
        "Rules: remove instructional boilerplate, retrieval wording, pronouns, and filler. "
        "Keep exact topic names, drug names, product names, diseases, and file-like terms. "
        "Return a short retrieval query of 1 to 6 essential terms."
    )
    user_prompt = (
        f'Original query: "{query}"\n'
        'Return JSON only, for example: {"query":"yescarta","must_terms":["yescarta"]}'
    )

    try:
        if provider == "ollama":
            payload = {
                "model": model or os.getenv("LLM_MODEL", "qwen2.5:7b-instruct"),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": 0},
            }
            async with httpx.AsyncClient(timeout=_QUERY_NORMALIZER_TIMEOUT) as client:
                resp = await client.post(
                    f'{os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434").rstrip("/")}/api/chat',
                    json=payload,
                )
            if resp.status_code != 200:
                return None
            content = resp.json().get("message", {}).get("content", "")
        else:
            if provider == "openrouter":
                api_key = os.getenv("OPENROUTER_API_KEY")
                if not api_key:
                    return None
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Obsidian RAG",
                }
                resolved_model = model or os.getenv("OPENROUTER_MODEL", "openrouter/auto")
            elif provider == "chatgpt":
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return None
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                resolved_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            elif provider == "mlx":
                api_key = os.getenv("QUERY_MLX_API_KEY") or os.getenv("MLX_API_KEY", "mlx")
                url = f'{(os.getenv("QUERY_MLX_BASE_URL") or os.getenv("MLX_BASE_URL", "http://host.docker.internal:8090/v1")).rstrip("/")}/chat/completions'
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                resolved_model = model or os.getenv("MLX_MODEL")
            else:
                return None

            payload = {
                "model": resolved_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "max_tokens": 120,
                "response_format": {"type": "json_object"},
            }
            async with httpx.AsyncClient(timeout=_QUERY_NORMALIZER_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                return None
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return None
            content = choices[0].get("message", {}).get("content", "")

        parsed = _extract_json_object(content)
        candidate = str(parsed.get("query") or "").strip()
        if not candidate:
            return None
        return candidate
    except Exception:
        return None


async def _normalize_query_for_retrieval(
    query: str,
    llm_provider: str,
    model: Optional[str],
) -> str:
    if not isinstance(query, str):
        return ""
    query = query.strip()
    if not query:
        return ""

    deterministic = _deterministic_normalize_query(query)
    if not _should_normalize_query(query):
        return deterministic

    if len(_query_terms(deterministic)) <= 4:
        return deterministic

    provider, resolved_model = _resolve_query_normalizer_provider(llm_provider, model)
    if not provider:
        return deterministic

    cached = _get_cached_normalized_query(query, provider, resolved_model)
    if cached:
        return cached

    candidate = await _call_query_normalizer_llm(deterministic, provider, resolved_model)
    normalized = candidate.strip() if isinstance(candidate, str) and candidate.strip() else deterministic
    _set_cached_normalized_query(query, provider, resolved_model, normalized)
    return normalized


def _is_procedural_config_query(query: str) -> bool:
    if not isinstance(query, str):
        return False
    text = query.lower()
    cues = {
        "how", "configure", "configured", "setup", "set up", "yaml",
        "code", "esphome", "sensor", "garage", "automation",
    }
    return any(cue in text for cue in cues)


def _source_path_key(source: Dict[str, Any]) -> str:
    filepath = str(source.get("filepath") or "").strip()
    filename = str(source.get("filename") or "").strip()
    return (filepath or filename).lower()


def _source_basename(source: Dict[str, Any]) -> str:
    filepath = str(source.get("filepath") or "").strip()
    filename = str(source.get("filename") or "").strip()
    target = filepath or filename
    if not target:
        return ""
    return target.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _source_domain_tokens(source: Dict[str, Any]) -> set[str]:
    if not isinstance(source, dict):
        return set()
    raw = " ".join(
        str(source.get(key) or "").lower()
        for key in ("filename", "filepath")
    )
    generic_tokens = {
        "associated",
        "circle",
        "composition",
        "file",
        "files",
        "math",
        "medical",
        "media",
        "note",
        "notes",
        "path",
        "paths",
        "pdf",
        "png",
        "relationship",
        "relationships",
        "tech",
        "treatment",
        "treatments",
        "types",
        "uml",
        "unit",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9\-]+", raw)
        if len(token) > 2 and token not in generic_tokens
    }


def _score_notes_vector_source(query: str, source: Dict[str, Any]) -> float:
    text = _source_search_text(source)
    snippet = str(source.get("snippet") or "").lower()
    filename = str(source.get("filename") or "").lower()
    filepath = str(source.get("filepath") or "").lower()
    try:
        base_relevance = float(source.get("relevance", 50.0))
    except (TypeError, ValueError):
        base_relevance = 50.0
    score = max(0.0, min(100.0, base_relevance))
    terms = _query_terms(query)
    anchor_terms = _query_anchor_terms(query)
    short_anchor_groups = _short_anchor_groups(query)
    short_compare_query = _is_short_compare_query(query)
    procedural = _is_procedural_config_query(query)
    dashboard_query = _is_home_assistant_dashboard_query(query)
    source_type = str(source.get("source_type") or "")

    term_hits = sum(1 for term in terms if term in text)
    score += term_hits * 6.0
    if anchor_terms and source_type == "linked-note" and not any(term in text for term in anchor_terms):
        score -= 28.0
    if short_anchor_groups:
        anchor_hit_count = sum(1 for group in short_anchor_groups if any(term in text for term in group))
        basename_anchor_hit_count = _source_basename_group_hit_count(source, short_anchor_groups)
        if anchor_hit_count >= len(short_anchor_groups):
            score += 28.0
        elif anchor_hit_count == len(short_anchor_groups) - 1:
            score -= 18.0
        else:
            score -= 40.0
        score += basename_anchor_hit_count * 12.0
        if short_compare_query and anchor_hit_count > 0 and basename_anchor_hit_count == 0:
            score -= 18.0

    if dashboard_query:
        dashboard_feature_match = any(
            token in text
            for token in (
                "lovelace",
                "card",
                "widget",
                "panel",
                "layout",
                "view",
                "setup",
                "configure",
                "configured",
                "configuration",
            )
        )
        if "home assistant" in text or re.search(r"\bhass\b", text):
            score += 12.0
        if "dashboard" in text:
            score += 18.0
        if "lovelace" in text:
            score += 22.0
        if any(token in text for token in ("card", "widget", "panel", "layout", "view")):
            score += 14.0
        if any(token in text for token in ("setup", "configure", "configured", "configuration")):
            score += 10.0
        if source_type == "direct-excerpt":
            score += 12.0
        elif source_type == "linked-note":
            score += 4.0
        if "dashboard" in text and not dashboard_feature_match:
            score -= 28.0
        if (
            not dashboard_feature_match
            and any(
                token in text
                for token in (
                    "https",
                    "duckdns",
                    "swiftui",
                    "websocket",
                    "subscribe",
                    "event",
                    "events",
                    "message",
                    "messages",
                    "esphome",
                )
            )
        ):
            score -= 72.0

        off_topic_penalties = {
            "https": 30.0,
            "duckdns": 24.0,
            "swiftui": 30.0,
            "websocket": 24.0,
            "subscribe": 18.0,
            "event": 14.0,
            "events": 14.0,
            "message": 16.0,
            "messages": 16.0,
        }
        for token, penalty in off_topic_penalties.items():
            if token in text and token not in query.lower():
                score -= penalty

        if "esphome" in text and not any(token in text for token in ("dashboard", "lovelace")):
            score -= 22.0

    if procedural:
        if source_type == "direct-excerpt":
            score += 30.0
        elif source_type == "linked-note":
            score += 8.0

        if "```yaml" in snippet or "yaml" in snippet:
            score += 20.0
        if any(token in snippet for token in ("esphome:", "binary_sensor:", "sensor:", "switch:", "cover:")):
            score += 22.0
        if "garage" in filename or "garage" in filepath:
            score += 14.0
        if "esphome" in filename or "esphome" in filepath:
            score += 10.0
        if "sensor" in filename or "sensor" in filepath or "sensor" in snippet:
            score += 10.0
        if "code" in filename or "yaml" in filename:
            score += 10.0

        generic_penalties = {
            "constitution": 45.0,
            "specification": 40.0,
            "plan": 35.0,
            "troubleshooting": 20.0,
            "device not shown": 24.0,
            "cli": 18.0,
            "update from": 18.0,
            "platformio": 14.0,
        }
        for token, penalty in generic_penalties.items():
            if token in filename and token not in query.lower():
                score -= penalty

    return score


def _dedupe_ranked_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[str, Dict[str, Any]] = {}
    basename_winners: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        key = _source_path_key(source)
        if not key:
            continue
        current = deduped.get(key)
        if current is None or float(source.get("_rank_score", 0.0)) > float(current.get("_rank_score", 0.0)):
            deduped[key] = source

    for source in deduped.values():
        basename = _source_basename(source)
        if not basename:
            continue
        current = basename_winners.get(basename)
        current_path = str(current.get("filepath") or "") if current else ""
        source_path = str(source.get("filepath") or "")
        current_score = float(current.get("_rank_score", 0.0)) if current else float("-inf")
        source_score = float(source.get("_rank_score", 0.0))
        if (
            current is None
            or source_score > current_score
            or (source_score == current_score and len(source_path) > len(current_path))
        ):
            basename_winners[basename] = source

    ranked = sorted(
        basename_winners.values(),
        key=lambda src: (float(src.get("_rank_score", 0.0)), float(src.get("relevance", 0.0))),
        reverse=True,
    )
    return ranked


def _finalize_ranked_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not sources:
        return []

    rank_scores: List[float] = []
    for source in sources:
        try:
            rank_scores.append(float(source.get("_rank_score", source.get("relevance", 0.0)) or 0.0))
        except (TypeError, ValueError):
            rank_scores.append(0.0)

    max_rank = max(rank_scores) if rank_scores else 0.0
    finalized: List[Dict[str, Any]] = []
    for source, rank_score in zip(sources, rank_scores):
        finalized_source = dict(source)
        if max_rank > 0.0:
            finalized_source["relevance"] = round(
                max(0.0, min(100.0, (rank_score / max_rank) * 100.0)),
                1,
            )
        else:
            finalized_source["relevance"] = max(
                0.0,
                min(100.0, float(source.get("relevance", 0.0) or 0.0)),
            )
        finalized_source.pop("_rank_score", None)
        finalized.append(finalized_source)
    return finalized


def _filter_notes_vector_sources_for_query(
    query: str,
    note_sources: List[Dict[str, Any]],
    vector_sources: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    filtered_notes = [src for src in note_sources if isinstance(src, dict)]
    filtered_vectors = [src for src in vector_sources if isinstance(src, dict)]

    # Combined search should not present very weak direct excerpts as evidence.
    filtered_vectors = [
        src for src in filtered_vectors if float(src.get("relevance", 0) or 0) >= 20.0
    ]

    if _is_home_assistant_dashboard_query(query):
        filtered_notes = [
            src for src in filtered_notes
            if _score_notes_vector_source(
                query,
                {**src, "source_type": src.get("source_type") or "linked-note"},
            ) >= 48.0
        ]
        filtered_vectors = [
            src for src in filtered_vectors
            if _score_notes_vector_source(
                query,
                {**src, "source_type": src.get("source_type") or "direct-excerpt"},
            ) >= 52.0
        ]

        # Graph context is weaker evidence than direct excerpts for this query type.
        filtered_notes = [
            src for src in filtered_notes if float(src.get("relevance", 0) or 0) >= 60.0
        ]
    procedural = _is_procedural_config_query(query)

    scored_notes = []
    for source in filtered_notes:
        scored = dict(source)
        scored["relevance"] = max(0.0, min(100.0, float(source.get("relevance", 0) or 0)))
        scored["_rank_score"] = _score_notes_vector_source(query, scored)
        scored_notes.append(scored)

    scored_vectors = []
    for source in filtered_vectors:
        scored = dict(source)
        scored["relevance"] = max(0.0, min(100.0, float(source.get("relevance", 0) or 0)))
        scored["_rank_score"] = _score_notes_vector_source(query, scored)
        scored_vectors.append(scored)

    ranked_vectors = _dedupe_ranked_sources(scored_vectors)
    strong_vector_threshold = 70.0 if procedural else 55.0
    strong_vector_paths = {
        _source_path_key(source)
        for source in ranked_vectors[:3]
        if float(source.get("_rank_score", 0.0)) >= strong_vector_threshold
    }
    strong_vector_domain_tokens: set[str] = set(_query_anchor_terms(query))
    short_anchor_groups = _short_anchor_groups(query)
    short_compare_query = _is_short_compare_query(query)
    for source in ranked_vectors[:3]:
        strong_vector_domain_tokens.update(_source_domain_tokens(source))
    ranked_notes = _dedupe_ranked_sources(scored_notes)

    if procedural and strong_vector_paths:
        ranked_notes = [
            source for source in ranked_notes
            if _source_path_key(source) in strong_vector_paths
            or float(source.get("_rank_score", 0.0)) >= 95.0
        ]
        ranked_vectors = [
            source for source in ranked_vectors
            if not any(
                token in str(source.get("filename") or "").lower()
                for token in ("constitution", "specification", "plan", "device not shown", "troubleshooting")
            )
            or float(source.get("_rank_score", 0.0)) >= 95.0
        ]
    elif strong_vector_paths and strong_vector_domain_tokens:
        ranked_notes = [
            source for source in ranked_notes
            if (
                _source_path_key(source) in strong_vector_paths
                or bool(_source_domain_tokens(source) & strong_vector_domain_tokens)
            )
        ]
    if short_anchor_groups:
        group_count = len(short_anchor_groups)
        combined_sources = ranked_notes + ranked_vectors
        has_joint_coverage = any(
            _source_group_hit_count(source, short_anchor_groups) >= group_count
            for source in combined_sources
        )
        if has_joint_coverage and not short_compare_query:
            ranked_notes = [
                source
                for source in ranked_notes
                if _source_group_hit_count(source, short_anchor_groups) >= group_count
            ]
            ranked_vectors = [
                source
                for source in ranked_vectors
                if _source_group_hit_count(source, short_anchor_groups) >= group_count
            ]
        ranked_notes = _prioritize_short_anchor_sources(
            ranked_notes,
            short_anchor_groups,
            max_total=4,
            compare_mode=short_compare_query,
        )
        ranked_vectors = _prioritize_short_anchor_sources(
            ranked_vectors,
            short_anchor_groups,
            max_total=5,
            compare_mode=short_compare_query,
        )

    ranked_notes = ranked_notes[:4]
    ranked_vectors = ranked_vectors[:5]

    return _finalize_ranked_sources(ranked_notes), _finalize_ranked_sources(ranked_vectors)


def _build_grounded_notes_vector_answer(
    query: str,
    note_sources: List[Dict[str, Any]],
    vector_sources: List[Dict[str, Any]],
) -> str:
    filtered_notes, filtered_vectors = _filter_notes_vector_sources_for_query(
        query, note_sources, vector_sources
    )

    if not filtered_notes and not filtered_vectors:
        return "No grounded Home Assistant dashboard notes were found."

    sections: List[str] = []
    procedural = _is_procedural_config_query(query)
    short_anchor_groups = _short_anchor_groups(query)
    short_compare_query = _is_short_compare_query(query)

    narrative_lines: List[str] = []
    if short_compare_query and len(short_anchor_groups) >= 2:
        side_summaries: List[str] = []
        for group in short_anchor_groups[:2]:
            anchor_label = " / ".join(sorted(group))
            matching_vectors = [
                source for source in vector_sources
                if _group_matches_text(_source_anchor_text(source), group)
            ]
            matching_notes = [
                source for source in note_sources
                if _group_matches_text(_source_anchor_text(source), group)
            ]
            pieces: List[str] = []
            vector_list = _narrative_source_list(matching_vectors, limit=2)
            note_list = _narrative_source_list(matching_notes, limit=2)
            if vector_list:
                pieces.append(f"direct evidence comes from {vector_list}")
            if note_list:
                pieces.append(f"linked-note context points to {note_list}")
            if pieces:
                side_summaries.append(f"For {anchor_label}, " + "; ".join(pieces) + ".")
        if side_summaries:
            narrative_lines.append(
                "The results split into two comparison sides rather than one merged cluster."
            )
            narrative_lines.extend(side_summaries)
    else:
        if vector_sources:
            narrative_lines.append(
                f"The strongest direct evidence comes from {_narrative_source_list(vector_sources, limit=3)}."
            )
        if note_sources:
            narrative_lines.append(
                f"Linked-note context reinforces this with {_narrative_source_list(note_sources, limit=3)}."
            )
        if short_anchor_groups and len(short_anchor_groups) >= 2:
            anchor_labels = [" / ".join(sorted(group)) for group in short_anchor_groups[:3]]
            narrative_lines.append(
                f"These results are grounded around the combined anchors {', '.join(anchor_labels)} rather than a loose topic match."
            )

    if narrative_lines:
        sections.append("\n".join(narrative_lines))

    if filtered_vectors:
        vector_lines = ["## Direct Note Excerpts"]
        for idx, source in enumerate(filtered_vectors, start=1):
            title = _source_display_name(source)
            snippet = _truncate_source_snippet(source.get("snippet"))
            vector_lines.append(f"{idx}. **{title}**")
            if snippet:
                vector_lines.append(f'   "{snippet}"')
        sections.append("\n".join(vector_lines))

    if filtered_notes:
        note_lines = ["## Linked-Note Context"]
        for idx, source in enumerate(filtered_notes, start=1):
            title = _source_display_name(source)
            snippet = _truncate_source_snippet(source.get("snippet"))
            note_lines.append(f"{idx}. **{title}**")
            if snippet:
                note_lines.append(f'   "{snippet}"')
        sections.append("\n".join(note_lines))

    return "\n\n".join(sections)


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
        "http://localhost:3030",
        "http://127.0.0.1:3030",
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
    allow_origins=["*"],
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
_SERVICE_HOST_FALLBACKS = {
    "embedding-service": ("localhost", "127.0.0.1", "host.docker.internal"),
    "graph-service": ("localhost", "127.0.0.1", "host.docker.internal"),
    "lightrag-service": ("localhost", "127.0.0.1", "host.docker.internal"),
}


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


def _candidate_service_urls(url: str) -> List[str]:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    fallbacks = _SERVICE_HOST_FALLBACKS.get(hostname)
    if not fallbacks:
        return [url]

    candidates = [url]
    netloc_suffix = ""
    if parsed.port:
        netloc_suffix = f":{parsed.port}"

    for fallback_host in fallbacks:
        if fallback_host == hostname:
            continue
        fallback_netloc = f"{fallback_host}{netloc_suffix}"
        candidates.append(urlunparse(parsed._replace(netloc=fallback_netloc)))

    return candidates


async def _request_with_fallback(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    timeout: float,
    service: str,
    json_payload: Optional[dict] = None,
) -> httpx.Response:
    last_exception: Optional[Exception] = None
    candidates = _candidate_service_urls(url)

    for candidate_url in candidates:
        try:
            request_kwargs: Dict[str, Any] = {
                "timeout": timeout,
                "headers": _auth_headers(),
            }
            if json_payload is not None:
                request_kwargs["json"] = json_payload
            response = await client.request(method, candidate_url, **request_kwargs)
            return response
        except httpx.RequestError as exc:
            last_exception = exc
            continue

    raise last_exception or RuntimeError(f"{service} request failed")


async def _post_json(
    client: httpx.AsyncClient, url: str, payload: dict, timeout: float, service: str
) -> httpx.Response:
    if _circuit_is_open(service):
        raise CircuitOpenError(f"{service} circuit open")

    last_exception = None
    for attempt in range(REQUEST_RETRIES + 1):
        try:
            response = await _request_with_fallback(
                client,
                "POST",
                url,
                json_payload=payload,
                timeout=timeout,
                service=service,
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


async def _get_json(
    client: httpx.AsyncClient, url: str, timeout: float, service: str
) -> Optional[httpx.Response]:
    try:
        return await _request_with_fallback(
            client,
            "GET",
            url,
            timeout=timeout,
            service=service,
        )
    except httpx.RequestError:
        return None


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
    llm_knowledge: bool = False


@app.get("/api/v1/health")
async def health_check():
    """Aggregated health check with stats"""
    emb_data = {}
    graph_data = {}
    lightrag_data = {}

    try:
        async with httpx.AsyncClient() as client:
            emb_resp = await _get_json(
                client, f"{EMBEDDING_SERVICE_URL}/health", timeout=2.0, service="vector"
            )
            if emb_resp and emb_resp.status_code == 200:
                emb_data = emb_resp.json()
                emb_status = "healthy"
            else:
                emb_status = "unhealthy"
    except:
        emb_status = "unreachable"

    try:
        async with httpx.AsyncClient() as client:
            graph_resp = await _get_json(
                client, f"{GRAPH_SERVICE_URL}/health", timeout=2.0, service="graph"
            )
            if graph_resp and graph_resp.status_code == 200:
                graph_data = graph_resp.json()
                graph_status = "healthy"
            else:
                graph_status = "unhealthy"
    except:
        graph_status = "unreachable"

    try:
        async with httpx.AsyncClient() as client:
            lightrag_resp = await _get_json(
                client, f"{LIGHTRAG_SERVICE_URL}/health", timeout=2.0, service="lightrag"
            )
            if lightrag_resp and lightrag_resp.status_code == 200:
                lightrag_data = lightrag_resp.json()
                lightrag_status = "healthy"
            else:
                lightrag_status = "unhealthy"
    except:
        lightrag_status = "unreachable"

    # Get LightRAG stats
    try:
        async with httpx.AsyncClient() as client:
            stats_resp = await _get_json(
                client, f"{LIGHTRAG_SERVICE_URL}/stats", timeout=2.0, service="lightrag"
            )
            if stats_resp and stats_resp.status_code == 200:
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
        "lightrag": {
            "nodes": services.get("lightrag", {}).get("nodes", 0),
            "edges": services.get("lightrag", {}).get("edges", 0),
            "indexed_notes": services.get("lightrag", {}).get("indexed_notes", 0),
        },
    }


@app.post("/api/v1/search")
async def unified_search(request: SearchRequest):
    """Unified search endpoint acting as a proxy/router"""
    mode = request.mode.lower()
    retrieval_query = request.query

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
                retrieval_query = await _normalize_query_for_retrieval(
                    query,
                    getattr(request, "llm_provider", "ollama"),
                    getattr(request, "model", None),
                )

                # Embedding service expects keys: query, n_results, filters
                payload = {
                    "query": retrieval_query,
                    "n_results": request.n_results
                }
                
                # Only include filters if there are any, some Chroma instances reject empty filter dicts
                if filters:
                    payload["filters"] = filters

                response = await client.post(
                    f"{EMBEDDING_SERVICE_URL}/query",
                    json=payload,
                    timeout=30.0,
                    headers=_auth_headers(),
                )
                
                if response.status_code != 200:
                    print(f"Vector search failed with {response.status_code}: {response.text}")
                    return {"results": {"documents": [], "distances": [], "metadatas": []}, "answer": "Vector search failed.", "error": response.text}
                
                return {"results": response.json()}
            except httpx.RequestError as e:
                print(f"Embedding service proxy error: {str(e)}")
                return {"results": {"documents": [], "distances": [], "metadatas": []}, "answer": "Vector service unreachable.", "error": str(e)}

    # 2. Graph / Hybrid -> Graph Service
    else:
        retrieval_query = await _normalize_query_for_retrieval(
            request.query,
            getattr(request, "llm_provider", "ollama"),
            getattr(request, "model", None),
        )
        extracted_entities, mem0_context = _extract_query_context(
            retrieval_query,
            include_memory=request.llm_knowledge
        )
        async with httpx.AsyncClient() as client:
            try:
                # Graph service expects robust payload
                payload = request.model_dump()
                payload["query"] = retrieval_query
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
    retrieval_query = await _normalize_query_for_retrieval(
        request.query,
        request.llm_provider,
        request.model,
    )
    
    extracted_entities, mem0_context = _extract_query_context(
        retrieval_query,
        include_memory=request.llm_knowledge
    )

    payload = {
        "query": retrieval_query,
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

    # Re-use resolution logic from normalizer
    resolved_provider = llm_provider.lower()
    
    try:
        if resolved_provider == "ollama":
            payload = {
                "model": model or os.getenv("LLM_MODEL", "qwen2.5:7b-instruct"),
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"temperature": 0.3}
            }
            async with httpx.AsyncClient() as c:
                resp = await c.post(f"{ollama_host.rstrip('/')}/api/chat", json=payload, timeout=60.0)
                if resp.status_code == 200:
                    return resp.json().get("message", {}).get("content", "")
        
        else:
            if resolved_provider == "openrouter":
                api_key = os.getenv("OPENROUTER_API_KEY")
                if not api_key:
                    return f"Found {len(sources)} matching snippets in your vault. (LLM synthesis skipped: OPENROUTER_API_KEY missing)"
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Obsidian RAG",
                }
                resolved_model = model or os.getenv("OPENROUTER_MODEL", "openrouter/auto")
            elif resolved_provider == "chatgpt":
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return f"Found {len(sources)} matching snippets in your vault. (LLM synthesis skipped: OPENAI_API_KEY missing)"
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                resolved_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            elif resolved_provider == "mlx":
                api_key = os.getenv("QUERY_MLX_API_KEY") or os.getenv("MLX_API_KEY", "mlx")
                url = f'{(os.getenv("QUERY_MLX_BASE_URL") or os.getenv("MLX_BASE_URL", "http://host.docker.internal:8090/v1")).rstrip("/")}/chat/completions'
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                resolved_model = model or os.getenv("MLX_MODEL")
            elif resolved_provider in ["gemini", "google"]:
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    return f"Found {len(sources)} matching snippets in your vault. (LLM synthesis skipped: GEMINI_API_KEY missing)"
                resolved_model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
                # Ensure model name matches Gemini's expected format if needed
                if not resolved_model.startswith("models/") and not resolved_model.startswith("gemini-"):
                     resolved_model = "gemini-1.5-flash"
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{resolved_model}:generateContent"
                
                # Gemini has a different payload structure
                payload = {
                     "contents": [
                          {"role": "user", "parts": [{"text": f"System:\n{sys_prompt}\n\nUser:\n{prompt}"}]}
                     ],
                     "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024}
                }
                
                async with httpx.AsyncClient() as c:
                    resp = await c.post(url, headers={"x-goog-api-key": api_key, "Content-Type": "application/json"}, json=payload, timeout=60.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                             parts = candidates[0].get("content", {}).get("parts", [])
                             if parts:
                                  return parts[0].get("text", "")
                    else:
                        print(f"Gemini API error: {resp.status_code} {resp.text}")
                return f"Found {len(sources)} matching snippets in your vault."
            else:
                 # Fallback behavior if unknown provider
                 return f"Found {len(sources)} matching snippets in your vault. (LLM synthesis skipped: unknown provider '{llm_provider}')"

            # Common OpenAI-compatible payload format (OpenRouter, ChatGPT, MLX)
            payload = {
                "model": resolved_model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3
            }
            
            async with httpx.AsyncClient() as c:
                resp = await c.post(url, headers=headers, json=payload, timeout=60.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0].get("message", {}).get("content", "")
                        return content
                else:
                    print(f"{resolved_provider.capitalize()} API Error: {resp.status_code} - {resp.text}")
                    
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

    retrieval_query = await _normalize_query_for_retrieval(
        request.query,
        request.llm_provider,
        request.model,
    )
    if retrieval_query != request.query:
        print(f"DEBUG: Normalized Retrieval Query: '{retrieval_query}'")

    entities_mode = (request.entities_mode or "hybrid").strip().lower()
    if entities_mode not in {"naive", "local", "global", "hybrid"}:
        entities_mode = "hybrid"

    # Gateway centralized Context & Entity Extraction
    extracted_entities, mem0_context = _extract_query_context(
        retrieval_query,
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
                retrieval_query,
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
                re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{1,}", retrieval_query.lower())
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

            # Always synthesize if we have sources, but pass the existing graph answer in as context
            if sources:
                system_with_graph = request.system_prompt
                if answer:
                    graph_context = f"The following is a partial analytical answer derived from the knowledge graph. Incorporate it into your final response:\n{answer}\n\n"
                    # If there's an existing answer, we use the vector synthesis to augment it.
                    sys_prompt = request.system_prompt or "You are a helpful AI assistant. Synthesize a concise answer to the user's query based ONLY on the provided vault context."
                    system_with_graph = f"{sys_prompt}\n\n{graph_context}"

                answer = await _synthesize_cascading_answer(
                    request.query,
                    sources,
                    request.llm_provider,
                    request.model,
                    system_with_graph
                )
            
            if not answer:
                 answer = "No results found."

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
                    "query": retrieval_query,
                    "n_results": request.max_results,
                    "relevance_threshold": effective_relevance_threshold
                }
                if filters:
                    payload["filters"] = filters
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
                    "query": retrieval_query,
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
                            "query": retrieval_query,
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
                    "query": retrieval_query,
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
                        "query": retrieval_query,
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
                            "query": retrieval_query,
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
                            "query": retrieval_query,
                            "mode": "graph",
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
                            "query": retrieval_query,
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
                if isinstance(notes_result, dict):
                    notes_sources = _tag_sources(notes_result.get("sources"), "linked-note")
                    if notes_sources:
                        notes_result["sources"] = notes_sources
                else:
                    notes_sources = []

                vector_result = (
                    None if isinstance(responses[1], Exception) else responses[1].json()
                )
                vector_sources = _normalize_vector_sources(vector_result)
                vector_sources = _apply_relevance_filter(
                    vector_sources, effective_relevance_threshold
                )
                notes_sources, vector_sources = _filter_notes_vector_sources_for_query(
                    retrieval_query,
                    notes_sources,
                    vector_sources,
                )
                if isinstance(vector_result, dict) and vector_sources:
                    vector_result["sources"] = vector_sources

                answer = _build_grounded_notes_vector_answer(
                    retrieval_query,
                    notes_sources,
                    vector_sources,
                )
                combined_sources = _dedupe_ranked_sources(
                    [
                        {
                            **source,
                            "_rank_score": _score_notes_vector_source(retrieval_query, source),
                            "relevance": max(0.0, min(100.0, float(source.get("relevance", 0) or 0))),
                        }
                        for source in (notes_sources + vector_sources)
                    ]
                )
                combined_sources = _finalize_ranked_sources(combined_sources)

                return {
                    "query": request.query,
                    "mode": "notes+vector",
                    "answer": answer,
                    "sources": combined_sources,
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
                            "query": retrieval_query,
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
                            "query": retrieval_query,
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
                if isinstance(entities_result, dict):
                    entity_sources = _tag_sources(
                        entities_result.get("sources"), "entity-context"
                    )
                    if entity_sources:
                        entities_result["sources"] = entity_sources
                else:
                    entity_sources = []
                vector_result = (
                    None if isinstance(responses[1], Exception) else responses[1].json()
                )
                vector_sources = _normalize_vector_sources(vector_result)
                vector_sources = _apply_relevance_filter(
                    vector_sources, effective_relevance_threshold
                )
                if isinstance(vector_result, dict) and vector_sources:
                    vector_result["sources"] = vector_sources

                answer = _build_dual_source_answer(
                    _lightrag_result_text(entities_result),
                    entity_sources,
                    vector_sources,
                    primary_label="entity context",
                )

                return {
                    "query": request.query,
                    "mode": "entities+vector",
                    "answer": answer,
                    "sources": entity_sources + vector_sources,
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
                            "query": retrieval_query,
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
                            "query": retrieval_query,
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
                            "query": retrieval_query,
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
                            "query": retrieval_query,
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
                            "query": retrieval_query,
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
            "mlx",
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
            if os.getenv("MLX_BASE_URL") or os.getenv("MLX_MODEL"):
                return "mlx"
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
                        "content": "Deep Thinking supports MLX, Perplexity, Claude, Gemini, OpenRouter, ChatGPT, or Ollama. No compatible configuration found.",
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
        elif provider == "mlx":
            api_key = os.getenv("QUERY_MLX_API_KEY") or os.getenv("MLX_API_KEY", "mlx")
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
