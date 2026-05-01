import os
import httpx
import json
import asyncio
import subprocess
import logging
import anthropic
import uvicorn
import math
import re
import time
import sys
import inspect
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from fastapi import FastAPI, WebSocket, Request, Response, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

try:
    from utils.ollama_runtime import iter_ollama_routes
except ImportError:
    try:
        from src.utils.ollama_runtime import iter_ollama_routes
    except ImportError:
        base_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        if base_path not in sys.path:
            sys.path.append(base_path)
        from src.utils.ollama_runtime import iter_ollama_routes

# Import CascadingRetriever - handle both package and direct execution
try:
    from cascading_retriever import CascadingRetriever
except ImportError:
    from src.services.cascading_retriever import CascadingRetriever
try:
    from cascading_pipeline import (
        build_cascading_degraded_answer as _build_cascading_degraded_answer_impl,
        build_comparison_insufficient_answer as _build_comparison_insufficient_answer_impl,
        build_relationship_insufficient_answer as _build_relationship_insufficient_answer_impl,
        distance_to_relevance as _distance_to_relevance_impl,
        extract_query_facets as _extract_cascading_query_facets_impl,
        has_multi_facet_query as _has_multi_facet_query_impl,
        hydrate_cascading_sources as _hydrate_cascading_sources_impl,
        is_generic_cascading_fallback_answer as _is_generic_cascading_fallback_answer_impl,
        is_comparison_style_query as _is_comparison_style_query_impl,
        is_personal_scope_query as _is_personal_scope_query_impl,
        is_relation_style_query as _is_relation_style_query_impl,
        looks_like_structural_graph_path_answer as _looks_like_structural_graph_path_answer_impl,
        normalize_cascading_source as _normalize_cascading_source_impl,
        relevance_threshold_from_distance_threshold as _relevance_threshold_from_distance_threshold_impl,
        select_cascading_evidence_set as _select_cascading_evidence_set_impl,
        should_require_vault_comparison_guardrail as _should_require_vault_comparison_guardrail_impl,
        should_require_vault_relationship_guardrail as _should_require_vault_relationship_guardrail_impl,
        source_set_covers_query_facets as _source_set_covers_query_facets_impl,
        synthesize_cascading_answer as _synthesize_cascading_answer_impl,
        synthesize_vault_review_answer as _synthesize_vault_review_answer_impl,
    )
except ImportError:
    from src.services.cascading_pipeline import (
        build_cascading_degraded_answer as _build_cascading_degraded_answer_impl,
        build_comparison_insufficient_answer as _build_comparison_insufficient_answer_impl,
        build_relationship_insufficient_answer as _build_relationship_insufficient_answer_impl,
        distance_to_relevance as _distance_to_relevance_impl,
        extract_query_facets as _extract_cascading_query_facets_impl,
        has_multi_facet_query as _has_multi_facet_query_impl,
        hydrate_cascading_sources as _hydrate_cascading_sources_impl,
        is_generic_cascading_fallback_answer as _is_generic_cascading_fallback_answer_impl,
        is_comparison_style_query as _is_comparison_style_query_impl,
        is_personal_scope_query as _is_personal_scope_query_impl,
        is_relation_style_query as _is_relation_style_query_impl,
        looks_like_structural_graph_path_answer as _looks_like_structural_graph_path_answer_impl,
        normalize_cascading_source as _normalize_cascading_source_impl,
        relevance_threshold_from_distance_threshold as _relevance_threshold_from_distance_threshold_impl,
        select_cascading_evidence_set as _select_cascading_evidence_set_impl,
        should_require_vault_comparison_guardrail as _should_require_vault_comparison_guardrail_impl,
        should_require_vault_relationship_guardrail as _should_require_vault_relationship_guardrail_impl,
        source_set_covers_query_facets as _source_set_covers_query_facets_impl,
        synthesize_cascading_answer as _synthesize_cascading_answer_impl,
        synthesize_vault_review_answer as _synthesize_vault_review_answer_impl,
    )

try:
    from deep_thinking.source_utils import (
        canonical_source_identity,
        normalize_source_record,
        normalize_vault_path,
    )
except ImportError:
    base_path = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    sys.path.append(base_path)
    from deep_thinking.source_utils import (
        canonical_source_identity,
        normalize_source_record,
        normalize_vault_path,
    )

try:
    from query_normalizer import (
        deterministic_clean_query as _deterministic_clean_query_impl,
        normalize_query_structure as _normalize_query_structure_impl,
        query_terms as _query_normalizer_terms_impl,
    )
except ImportError:
    try:
        from src.services.query_normalizer import (
            deterministic_clean_query as _deterministic_clean_query_impl,
            normalize_query_structure as _normalize_query_structure_impl,
            query_terms as _query_normalizer_terms_impl,
        )
    except ImportError:
        base_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        sys.path.append(base_path)
        from src.services.query_normalizer import (
            deterministic_clean_query as _deterministic_clean_query_impl,
            normalize_query_structure as _normalize_query_structure_impl,
            query_terms as _query_normalizer_terms_impl,
        )

try:
    from utils.prompt_builder import prefers_full_vault_answer as _prefers_full_vault_answer_impl
except ImportError:
    try:
        from src.utils.prompt_builder import prefers_full_vault_answer as _prefers_full_vault_answer_impl
    except ImportError:
        def _prefers_full_vault_answer_impl(query: str) -> bool:
            return False


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


def _get_env_value(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if not isinstance(value, str):
        return default
    return value.strip()


def _sanitize_base_url(value: str, default: str) -> str:
    cleaned = str(value or default).strip()
    while cleaned and cleaned[-1] in {"`", ";", "'", '"'}:
        cleaned = cleaned[:-1].rstrip()
    if cleaned and not cleaned.startswith(("http://", "https://")):
        cleaned = f"http://{cleaned}"
    return cleaned.rstrip("/") or default.rstrip("/")


def _safe_url_port(parsed) -> int | None:
    try:
        return parsed.port
    except ValueError:
        return None


_LAST_MLX_RECOVERY_TS = 0.0


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _vault_root() -> Path:
    return Path(os.getenv("OBSIDIAN_VAULT_PATH", "/app/vault")).expanduser().resolve()


def _normalize_summary_focus_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = os.path.splitext(os.path.basename(text.replace("\\", "/")))[0]
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _summary_query_targets_source(query: str, source: Dict[str, Any]) -> bool:
    normalized_query = _normalize_summary_focus_text(query)
    if not normalized_query:
        return False

    candidates = [
        source.get("filename"),
        source.get("filepath"),
        source.get("canonical_id"),
    ]
    for candidate in candidates:
        normalized_candidate = _normalize_summary_focus_text(candidate)
        if normalized_candidate and normalized_candidate in normalized_query:
            return True
    return False


def _format_web_search_context_for_synthesis(web_search_result: Optional[Dict[str, Any]]) -> str:
    if not isinstance(web_search_result, dict):
        return ""

    results = web_search_result.get("results") or []
    if not isinstance(results, list) or not results:
        return ""

    lines = ["Supplemental web evidence:"]
    for index, result in enumerate(results[:3], start=1):
        if not isinstance(result, dict):
            continue
        title = str(result.get("title") or "").strip()
        url = str(result.get("url") or "").strip()
        content = _truncate_source_snippet(
            result.get("content") or result.get("snippet") or "",
            limit=500,
        )
        entry = [f"{index}. {title or url or 'Web result'}"]
        if url:
            entry.append(f"URL: {url}")
        if content:
            entry.append(f"Snippet: {content}")
        lines.append("\n".join(entry))

    return "\n\n".join(lines) if len(lines) > 1 else ""


def _cascading_source_rank_score(query: str, source: Dict[str, Any]) -> float:
    base_relevance = float(source.get("relevance", 0.0) or 0.0)
    normalized_query = _normalize_summary_focus_text(query)
    if not normalized_query:
        return base_relevance

    query_terms = [
        term for term in normalized_query.split()
        if len(term) > 2 and term not in {
            "what", "when", "where", "which", "with", "from", "into", "about",
            "study", "studies", "results", "result", "note", "notes",
        }
    ]
    candidates = [
        _normalize_summary_focus_text(source.get("filename")),
        _normalize_summary_focus_text(source.get("filepath")),
        _normalize_summary_focus_text(source.get("canonical_id")),
    ]

    bonus = 0.0
    for candidate in candidates:
        if not candidate:
            continue
        if candidate in normalized_query:
            bonus = max(bonus, 30.0)
        overlap = sum(1 for term in query_terms if term in candidate)
        if overlap:
            bonus = max(bonus, min(24.0, overlap * 8.0))

    return base_relevance + bonus


def _resolve_vault_source_path(source: Dict[str, Any]) -> Optional[Path]:
    raw_path = normalize_vault_path(source.get("filepath") or source.get("source") or "")
    if not raw_path:
        return None

    vault_root = _vault_root()
    try:
        resolved = (vault_root / raw_path).resolve()
        resolved.relative_to(vault_root)
    except Exception:
        return None

    return resolved if resolved.is_file() else None


def _expand_summary_sources_for_synthesis(
    query: str,
    sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    try:
        expansion_limit = max(
            1000,
            int(os.getenv("VECTOR_SUMMARY_SOURCE_EXPANSION_CHARS", "12000")),
        )
    except (TypeError, ValueError):
        expansion_limit = 12000

    expanded_sources: List[Dict[str, Any]] = []
    for source in sources or []:
        prepared = dict(source)
        if not _summary_query_targets_source(query, prepared):
            expanded_sources.append(prepared)
            continue

        resolved = _resolve_vault_source_path(prepared)
        if not resolved or resolved.suffix.lower() not in {".md", ".txt"}:
            expanded_sources.append(prepared)
            continue

        try:
            with resolved.open("r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read(expansion_limit).strip()
        except OSError:
            expanded_sources.append(prepared)
            continue

        if content and len(content) > len(str(prepared.get("snippet") or "")):
            prepared["snippet"] = content
            prepared["content"] = content
            prepared["is_full_content"] = True

        expanded_sources.append(prepared)

    return expanded_sources


def _should_expand_named_sources_for_synthesis(query: str, sources: List[Dict[str, Any]]) -> bool:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{1,}", str(query or ""))
    if not tokens or len(tokens) > 4:
        return False
    return any(_summary_query_targets_source(query, source) for source in (sources or []) if isinstance(source, dict))


def _prepare_vector_sources_for_synthesis(
    query: str,
    sources: List[Dict[str, Any]],
    *,
    expand_named_sources: bool = False,
) -> List[Dict[str, Any]]:
    prepared_sources = list(sources or [])
    if expand_named_sources:
        prepared_sources = _expand_summary_sources_for_synthesis(query, prepared_sources)

    try:
        snippet_limit = max(
            400,
            int(os.getenv("VECTOR_SYNTHESIS_SNIPPET_CHARS", "1800")),
        )
    except (TypeError, ValueError):
        snippet_limit = 1800

    cleaned_sources: List[Dict[str, Any]] = []
    for source in prepared_sources:
        prepared = dict(source)
        raw_text = str(prepared.get("content") or prepared.get("snippet") or "")
        cleaned = _clean_extractive_fallback_text(raw_text)
        if cleaned:
            prepared["snippet"] = cleaned[:snippet_limit].rstrip() + ("..." if len(cleaned) > snippet_limit else "")
            prepared["content"] = cleaned
        cleaned_sources.append(prepared)
    return cleaned_sources


def _summary_display_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    preview_limit = 1200
    display_sources: List[Dict[str, Any]] = []
    for source in sources or []:
        prepared = dict(source)
        snippet = str(prepared.get("snippet") or "").strip()
        if len(snippet) > preview_limit:
            prepared["snippet"] = snippet[:preview_limit].rstrip() + "..."
        display_sources.append(prepared)
    return display_sources


def _clean_extractive_fallback_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    text = re.sub(r"^---\s*.*?\s*---\s*", "", text, flags=re.DOTALL)
    notes_match = re.search(
        r"(?ims)^#{1,6}\s+notes\s*$([\s\S]*?)(?=^#{1,6}\s+(related notes|questions|to-do|smart connections insights)\s*$|\Z)",
        text,
    )
    if notes_match:
        text = notes_match.group(1).strip()
    text = re.sub(r"(?:\[[^\]]+:\s[^\]]+\]\s*)+", "", text)
    text = re.sub(r"<mark[^>]*>", "", text, flags=re.IGNORECASE)
    text = text.replace("</mark>", "")
    text = text.replace("==", "")
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extractive_fallback_candidates(text: str) -> List[str]:
    cleaned = _clean_extractive_fallback_text(text)
    if not cleaned:
        return []

    fragments = re.split(r"(?<=[.!?])\s+", cleaned)
    candidates: List[str] = []
    for fragment in fragments:
        candidate = fragment.strip(" -\n\t")
        if len(candidate) < 35:
            continue
        if len(candidate) > 320:
            continue
        lowered = candidate.lower()
        if lowered.startswith(("source:", "date:", "canonical id:", "entity type:", "timeline date:", "tags:")):
            continue
        if lowered.startswith(("main idea", "references", "related notes", "questions / ideas for further exploration", "to-do", "smart connections insights")):
            continue
        if "mermaid" in lowered or "xychart-beta" in lowered:
            continue
        if candidate.count(":") >= 2 and len(candidate.split()) < 18:
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _load_vector_fallback_source_text(query: str, source: Dict[str, Any]) -> str:
    base_text = str(source.get("content") or source.get("snippet") or "")
    resolved = _resolve_vault_source_path(source)
    if not resolved or resolved.suffix.lower() not in {".md", ".txt"}:
        return base_text

    try:
        expansion_limit = max(
            500,
            int(os.getenv("VECTOR_FALLBACK_SOURCE_EXPANSION_CHARS", "4000")),
        )
    except (TypeError, ValueError):
        expansion_limit = 4000

    try:
        with resolved.open("r", encoding="utf-8", errors="ignore") as handle:
            content = handle.read(expansion_limit).strip()
    except OSError:
        return base_text

    if not content:
        return base_text

    normalized_query = _normalize_summary_focus_text(query)
    normalized_source = _normalize_summary_focus_text(
        source.get("filename") or source.get("filepath") or source.get("canonical_id")
    )
    if normalized_query and normalized_source and any(
        token in normalized_source for token in normalized_query.split()
    ):
        return content

    if len(content) > len(base_text):
        return content
    return base_text


def _build_extractive_vector_fallback_answer(
    query: str,
    sources: List[Dict[str, Any]],
    *,
    max_bullets: int = 4,
) -> str:
    if not sources:
        return "No results found."

    query_terms = {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", str(query or ""))
        if token
    }
    ranked: List[tuple[float, str]] = []
    seen: set[str] = set()

    for source_index, source in enumerate(sources[:5]):
        snippet = _load_vector_fallback_source_text(query, source)
        relevance = float(source.get("relevance", 0.0) or 0.0)
        for candidate_index, candidate in enumerate(_extractive_fallback_candidates(snippet)[:4]):
            candidate = re.sub(r"^[^A-Za-z0-9]+", "", candidate).strip()
            if candidate and candidate[0].islower():
                candidate = candidate[0].upper() + candidate[1:]
            normalized = re.sub(r"[^a-z0-9]+", " ", candidate.lower()).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            term_hits = sum(1 for term in query_terms if term and term in normalized)
            score = (term_hits * 1000) + (relevance * 10) - (source_index * 10) - candidate_index
            ranked.append((score, candidate))

    if not ranked:
        return "I found relevant vault evidence. Review the attached sources for the most reliable details."

    ranked.sort(key=lambda item: item[0], reverse=True)
    bullets = [candidate.rstrip(". ") + "." for _, candidate in ranked[:max_bullets]]
    return "\n".join(f"- {bullet}" for bullet in bullets)


async def _perform_tavily_web_search(
    client: httpx.AsyncClient,
    query: str,
    *,
    max_results: int = 3,
) -> Dict[str, Any]:
    search_terms = str(query or "").strip()
    if not search_terms:
        return {
            "search_terms": "",
            "results": [],
            "message": "No web search terms available.",
        }

    api_key = _get_env_value("TAVILY_API_KEY")
    if not api_key:
        return {
            "search_terms": search_terms,
            "results": [],
            "message": "TAVILY_API_KEY not configured.",
        }

    payload = {
        "api_key": api_key,
        "query": search_terms,
        "search_depth": "advanced",
        "max_results": max(max_results, 5),
        "include_answer": False,
        "include_raw_content": False,
    }

    try:
        response = await _post_json(
            client,
            "https://api.tavily.com/search",
            payload,
            timeout=20.0,
            service="web_search",
        )
        data = response.json() if hasattr(response, "json") else {}
    except Exception as exc:
        return {
            "search_terms": search_terms,
            "results": [],
            "message": f"Web search failed: {exc}",
        }

    normalized_results: List[Dict[str, str]] = []
    for item in (data.get("results") or [])[:max_results]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        content = _truncate_source_snippet(
            item.get("content") or item.get("snippet") or "",
            limit=280,
        )
        if not (title or url or content):
            continue
        normalized_results.append(
            {
                "title": title or url or "Untitled result",
                "url": url,
                "content": content,
            }
        )

    result = {
        "search_terms": search_terms,
        "results": normalized_results,
    }
    if not normalized_results:
        result["message"] = "No web results found."
    return result


def _recovery_script_path() -> str:
    return os.path.join(_project_root(), "Scripts", "setup", "recover_api_gateway_and_mlx.sh")


def _is_mlx_runtime_failure(
    provider: Optional[str],
    exc: Exception,
    model: Optional[str] = None,
) -> bool:
    provider_normalized = (provider or "").strip().lower()
    model_normalized = (model or "").strip().lower()

    mlx_route_markers = [
        "mlx",
        "lfm2",
        "qwen2.5-7b-instruct-4bit",
    ]
    points_to_local_mlx = "host.docker.internal:8090" in _get_env_value("OPENAI_BASE_URL").lower()
    likely_mlx_route = (
        provider_normalized == "mlx"
        or any(marker in model_normalized for marker in mlx_route_markers)
        or (provider_normalized == "chatgpt" and points_to_local_mlx)
    )
    if not likely_mlx_route:
        return False

    message = str(exc or "")
    lowered = message.lower()
    failure_markers = [
        "host.docker.internal",
        "port=8090",
        "/v1/chat/completions",
        "connection refused",
        "max retries exceeded",
        "newconnectionerror",
        "httppool",
        "remote end closed connection",
        "remotedisconnected",
        "insufficient memory",
        "outofmemory",
        "[metal]",
        "kiogpucommandbuffercallbackerroroutofmemory",
        "failed to establish a new connection",
        "connection aborted",
    ]
    return any(marker in lowered for marker in failure_markers)


def _looks_like_mlx_transport_failure_text(message: Optional[str]) -> bool:
    lowered = (message or "").strip().lower()
    if not lowered:
        return False
    failure_markers = [
        "host.docker.internal",
        "port=8090",
        "/v1/chat/completions",
        "connection refused",
        "max retries exceeded",
        "newconnectionerror",
        "httppool",
        "httpconnectionpool",
        "remote end closed connection",
        "remotedisconnected",
        "connection aborted",
        "failed to establish a new connection",
        "insufficient memory",
        "outofmemory",
        "[metal]",
        "kiogpucommandbuffercallbackerroroutofmemory",
    ]
    return any(marker in lowered for marker in failure_markers)


def _start_mlx_recovery() -> bool:
    global _LAST_MLX_RECOVERY_TS

    now = time.time()
    if now - _LAST_MLX_RECOVERY_TS < 20:
        return False

    script_path = _recovery_script_path()
    if not os.path.exists(script_path):
        return False

    log_dir = os.path.join(_project_root(), "Scripts", "setup", "logs")
    os.makedirs(log_dir, exist_ok=True)
    recovery_trigger_log = os.path.join(log_dir, "recovery-trigger.log")

    with open(recovery_trigger_log, "ab") as handle:
        subprocess.Popen(
            ["/bin/bash", script_path, "--force"],
            cwd=_project_root(),
            stdout=handle,
            stderr=handle,
            start_new_session=True,
        )

    _LAST_MLX_RECOVERY_TS = now
    return True


def _mlx_recovery_error_payload(exc: Exception) -> Dict[str, Any]:
    recovery_started = _start_mlx_recovery()
    message = "Local MLX crashed or ran out of GPU memory"
    if recovery_started:
        message += "; recovery running. Retry in 15-30 seconds."
    else:
        message += "; recovery may already be running. Retry in 15-30 seconds."

    return {
        "type": "error",
        "content": message,
        "code": "MLX_RECOVERING",
        "details": {
            "provider": "mlx",
            "recovery_started": recovery_started,
            "raw_error": str(exc),
        },
    }


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
        relevance = _distance_to_relevance_impl(dist, default=50.0)
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


def _normalize_cascading_source(
    source: Dict[str, Any],
    *,
    source_type: str,
    default_relevance: float = 50.0,
) -> Dict[str, Any]:
    return _normalize_cascading_source_impl(
        source,
        source_type=source_type,
        default_relevance=default_relevance,
    )


def _hydrate_cascading_sources(
    base_sources: List[Dict[str, Any]],
    hydrated_sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return _hydrate_cascading_sources_impl(base_sources, hydrated_sources)


def _normalize_summary_focus_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = os.path.splitext(os.path.basename(text.replace("\\", "/")))[0]
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _is_summary_style_query(query: str) -> bool:
    lowered = str(query or "").strip().lower()
    if not lowered:
        return False
    return (
        "summary of " in lowered
        or lowered.startswith("summarize ")
        or "point form summary" in lowered
        or "bullet summary" in lowered
    )


def _select_cascading_evidence_set(
    query: str,
    sources: List[Dict[str, Any]],
    *,
    max_results: int,
) -> List[Dict[str, Any]]:
    return _select_cascading_evidence_set_impl(
        query,
        sources,
        max_results=max_results,
    )


def _is_relation_style_query(query: str) -> bool:
    return _is_relation_style_query_impl(query)


def _extract_cascading_query_facets(query: str) -> List[set[str]]:
    return _extract_cascading_query_facets_impl(query)


def _has_multi_facet_query(query: str) -> bool:
    return _has_multi_facet_query_impl(query)


def _source_set_covers_query_facets(query: str, sources: List[Dict[str, Any]]) -> bool:
    return _source_set_covers_query_facets_impl(query, sources)


def _should_require_vault_relationship_guardrail(query: str, sources: List[Dict[str, Any]]) -> bool:
    return _should_require_vault_relationship_guardrail_impl(query, sources)


def _should_require_vault_comparison_guardrail(query: str, sources: List[Dict[str, Any]]) -> bool:
    return _should_require_vault_comparison_guardrail_impl(query, sources)


def _canonical_cascading_provider_name(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    aliases = {
        "anthropic": "claude",
        "claude": "claude",
        "google": "gemini",
        "gemini": "gemini",
        "openai": "chatgpt",
        "chatgpt": "chatgpt",
        "openrouter": "openrouter",
        "ollama": "ollama",
        "lmstudio": "lmstudio",
        "mlx": "lmstudio",
        "perplexity": "perplexity",
    }
    return aliases.get(normalized, normalized)


def _default_cascading_model(provider: str) -> Optional[str]:
    provider = _canonical_cascading_provider_name(provider)
    defaults = {
        "claude": _get_env_value("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"),
        "gemini": _get_env_value("GEMINI_MODEL", "gemini-3-flash-preview"),
        "chatgpt": _get_env_value("OPENAI_MODEL", "gpt-4o-mini"),
        "openrouter": _get_env_value("OPENROUTER_MODEL", "openrouter/auto"),
        "ollama": _get_env_value("OLLAMA_MODEL", _get_env_value("LLM_MODEL", "qwen2.5:7b-instruct")),
        "lmstudio": _get_env_value("LMSTUDIO_MODEL", _get_env_value("MLX_MODEL", _get_env_value("LLM_MODEL_PATH", "local-model"))),
        "perplexity": _get_env_value("PERPLEXITY_MODEL", "llama-3.1-sonar-large-128k-online"),
    }
    return defaults.get(provider)


def _cascading_provider_api_key(provider: str) -> Optional[str]:
    provider = _canonical_cascading_provider_name(provider)
    if provider == "claude":
        return _get_env_value("ANTHROPIC_API_KEY") or None
    if provider == "gemini":
        return _get_env_value("GEMINI_API_KEY") or None
    if provider == "chatgpt":
        return _get_env_value("OPENAI_API_KEY") or None
    if provider == "openrouter":
        return _get_env_value("OPENROUTER_API_KEY") or None
    if provider == "ollama":
        return None
    if provider == "lmstudio":
        return (
            _get_env_value("QUERY_LMSTUDIO_API_KEY")
            or _get_env_value("LMSTUDIO_API_KEY", "lmstudio")
            or _get_env_value("QUERY_MLX_API_KEY")
            or _get_env_value("MLX_API_KEY", "mlx")
            or "lmstudio"
        )
    if provider == "perplexity":
        return _get_env_value("PERPLEXITY_API_KEY") or None
    return None


def _deep_research_configured_provider() -> str:
    for env_name in ("DEEP_THINKING_PROVIDER", "QUERY_LLM_PROVIDER", "LLM_PROVIDER"):
        configured = _get_env_value(env_name)
        if configured:
            return _canonical_cascading_provider_name(configured)
    return ""


def _deep_research_auto_provider() -> Optional[str]:
    candidates = [
        _deep_research_configured_provider(),
        "perplexity",
        "openrouter",
        "chatgpt",
        "gemini",
        "claude",
        "lmstudio",
        "ollama",
    ]
    seen = set()
    for candidate in candidates:
        provider = _canonical_cascading_provider_name(candidate)
        if not provider or provider in seen:
            continue
        seen.add(provider)
        if provider in {"ollama", "lmstudio"}:
            if provider == "ollama" and os.getenv("OLLAMA_HOST"):
                return provider
            if provider == "lmstudio" and (
                os.getenv("LMSTUDIO_BASE_URL")
                or os.getenv("LMSTUDIO_MODEL")
                or os.getenv("MLX_BASE_URL")
                or os.getenv("MLX_MODEL")
            ):
                return provider
            continue
        if _cascading_provider_api_key(provider):
            return provider
    return None


def _deep_research_default_model(provider: str) -> Optional[str]:
    configured = _get_env_value("DEEP_THINKING_MODEL")
    if configured:
        return configured
    return _default_cascading_model(provider)


def _is_insufficient_answer(text: Any) -> bool:
    if not isinstance(text, str):
        return True
    cleaned = text.strip().lower()
    if not cleaned:
        return True
    patterns = (
        "i cannot provide",
        "i can't provide",
        "i can’t provide",
        "i am unable to provide",
        "i'm unable to provide",
        "i’m unable to provide",
        "unable to provide",
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


def _is_generic_cascading_fallback_answer(text: Any) -> bool:
    return _is_generic_cascading_fallback_answer_impl(text)


def _looks_like_structural_graph_path_answer(text: Any) -> bool:
    return _looks_like_structural_graph_path_answer_impl(text)


def _build_cascading_degraded_answer(
    anchor_answer: str,
    sources: List[Dict[str, Any]],
    diagnostics: Dict[str, Any],
    reason: str,
) -> str:
    return _build_cascading_degraded_answer_impl(
        anchor_answer,
        sources,
        diagnostics,
        reason,
        _is_insufficient_answer,
    )


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


_QUERY_TAG_PATTERN = re.compile(r'\btag:(?:"(#?[^"]+)"|(#?[A-Za-z0-9_/-]+))', re.IGNORECASE)


def _parse_query_tag_filters(query: str) -> tuple[str, dict]:
    if not isinstance(query, str) or not query.strip():
        return "", {}

    tags: List[str] = []
    tag_mode = "all"
    matches = list(_QUERY_TAG_PATTERN.finditer(query))
    for match in matches:
        value = (match.group(1) or match.group(2) or "").strip().lower()
        value = value.lstrip("#").strip()
        if value and value not in tags:
            tags.append(value)

    for left, right in zip(matches, matches[1:]):
        between = query[left.end():right.start()]
        if re.search(r"\bor\b", between, re.IGNORECASE):
            tag_mode = "any"
            break

    cleaned = _QUERY_TAG_PATTERN.sub("", query)
    cleaned = re.sub(r"^(?:\s*(?:or|and)\b)+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:\b(?:or|and)\s*)+$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    filters: Dict[str, Any] = {}
    if tags:
        filters["tags"] = tags
        if tag_mode != "all":
            filters["tag_mode"] = tag_mode
    return cleaned, filters


def _deterministic_normalize_query(query: str) -> str:
    return _deterministic_clean_query_impl(query)


def _normalize_query_object(query: str) -> Dict[str, Any]:
    payload = _normalize_query_structure_impl(query)
    if not isinstance(payload, dict):
        return {
            "original_query": str(query or "").strip(),
            "clean_query": _deterministic_normalize_query(query),
            "intent": "lookup",
            "entities": [],
            "relations": [],
            "facets": [],
            "must_terms": [],
        }
    return payload


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

    supported = {"ollama", "openrouter", "chatgpt", "lmstudio", "mlx"}
    if candidate_provider in supported:
        return candidate_provider, candidate_model

    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter", os.getenv("QUERY_NORMALIZER_MODEL", "").strip() or os.getenv("OPENROUTER_MODEL", "openrouter/auto")
    if os.getenv("OPENAI_API_KEY"):
        return "chatgpt", os.getenv("QUERY_NORMALIZER_MODEL", "").strip() or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if os.getenv("LMSTUDIO_BASE_URL") or os.getenv("LMSTUDIO_MODEL") or os.getenv("MLX_BASE_URL") or os.getenv("MLX_MODEL"):
        return (
            "lmstudio",
            os.getenv("QUERY_NORMALIZER_MODEL", "").strip()
            or os.getenv("LMSTUDIO_MODEL")
            or os.getenv("MLX_MODEL"),
        )
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
            async with httpx.AsyncClient(timeout=_QUERY_NORMALIZER_TIMEOUT) as client:
                resp = None
                for ollama_host, candidate_model in iter_ollama_routes(
                    model or os.getenv("LLM_MODEL", "qwen2.5:7b-instruct"),
                    default_host="http://host.docker.internal:11434",
                    fallback_default_model="qwen2.5:7b-instruct",
                ):
                    payload = {
                        "model": candidate_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": False,
                        "options": {"temperature": 0},
                    }
                    try:
                        resp = await client.post(
                            f"{ollama_host}/api/chat",
                            json=payload,
                        )
                    except httpx.HTTPError:
                        continue
                    if resp.status_code == 200:
                        break
            if resp is None or resp.status_code != 200:
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
            elif provider in {"lmstudio", "mlx"}:
                api_key = (
                    os.getenv("QUERY_LMSTUDIO_API_KEY")
                    or os.getenv("LMSTUDIO_API_KEY", "lmstudio")
                    or os.getenv("QUERY_MLX_API_KEY")
                    or os.getenv("MLX_API_KEY", "mlx")
                )
                base_url = _sanitize_base_url(
                    os.getenv("QUERY_LMSTUDIO_BASE_URL")
                    or os.getenv("LMSTUDIO_BASE_URL")
                    or os.getenv("QUERY_MLX_BASE_URL")
                    or os.getenv("MLX_BASE_URL", "http://host.docker.internal:1234/v1"),
                    "http://host.docker.internal:1234/v1",
                )
                url = f"{base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                resolved_model = model or os.getenv("LMSTUDIO_MODEL") or os.getenv("MLX_MODEL")
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
                "response_format": {
                    "type": "text" if provider in {"lmstudio", "mlx"} else "json_object"
                },
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


_SUMMARY_INSTRUCTION_SIGNALS = (
    re.compile(r"\bsummariz(?:e|ing)\b", re.IGNORECASE),
    re.compile(r"\bin\s+\d+\s+(?:short\s+)?(?:sections?|parts?|bullets?|paragraphs?)\b", re.IGNORECASE),
    re.compile(r"\bcite\s+(?:note\s+)?titles?\b", re.IGNORECASE),
    re.compile(r"\busing only (?:evidence from )?(?:my )?(?:vault|notes?)\b", re.IGNORECASE),
    re.compile(r"\bsay when (?:a claim|it) is not supported\b", re.IGNORECASE),
)


def _is_instructional_summary_query(query: str) -> bool:
    """Return True if query is a complex instructional query with formatting requirements.

    These queries mix a core retrieval topic ("lymphoma treatment history") with
    structural instructions ("in 3 sections", "cite note titles") that confuse
    graph entity extraction and vector search.
    """
    if not isinstance(query, str) or len(query.strip()) < 60:
        return False
    matches = sum(1 for p in _SUMMARY_INSTRUCTION_SIGNALS if p.search(query))
    return matches >= 2


_LEADING_VAULT_INSTRUCTION_RE = re.compile(
    r"^(?:using only (?:evidence from )?(?:my )?(?:vault|notes?)|"
    r"based on (?:my )?(?:notes?|vault|evidence)|"
    r"from (?:my )?(?:notes?|vault)|"
    r"only using (?:my )?(?:notes?|vault))"
    r"[,;.\s]+",
    re.IGNORECASE,
)

_SUMMARIZE_SUBJECT_RE = re.compile(
    r"^summarize\s+(?:my\s+|the\s+)?(.+?)"
    r"(?:\s+in\s+\d+\s|\s*[;:]\s|\s*\.\s+|\s+and\s+cite\b|\s+with\s+(?:citations?|sources?)|\s*$)",
    re.IGNORECASE,
)


def _extract_core_retrieval_topic(query: str) -> str:
    """Extract the core retrieval topic from an instructional summary query.

    Example:
        "Using only evidence from my vault, summarize my lymphoma treatment history
         in 3 short sections: confirmed treatments, complications or side effects..."
        → "lymphoma treatment history"

    Returns the original query unchanged if no instructional pattern is found.
    """
    text = query.strip()

    # Strip leading vault/note context instructions
    text = _LEADING_VAULT_INSTRUCTION_RE.sub("", text).strip()

    # Extract subject from "summarize [my/the] TOPIC in N sections: ..."
    m = _SUMMARIZE_SUBJECT_RE.match(text)
    if m:
        topic = m.group(1).strip().rstrip(".,;:")
        if topic and 3 <= len(topic) <= 100:
            return topic

    # Fallback: strip trailing formatting instructions if present
    text = re.sub(
        r"\s+in\s+\d+\s+(?:short\s+)?(?:sections?|parts?|bullets?)[;:,\s].*$",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()
    text = re.sub(r"\s*\.\s*(?:Cite|Include|Say|Use)\s+.*$", "", text, flags=re.IGNORECASE).strip()

    result = text.strip(".,;:")
    # Only return the stripped version if it's meaningfully shorter than the original
    if result and len(result) < len(query) * 0.7:
        return result
    return query.strip()


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

    normalized_payload = _normalize_query_object(query)
    deterministic = str(normalized_payload.get("clean_query") or _deterministic_normalize_query(query)).strip()
    if _has_multi_facet_query(query):
        # For instructional summary queries (e.g. "summarize my lymphoma treatment history
        # in 3 sections: confirmed treatments, complications..."), the multi-facet signal
        # fires on the *enumerated sections*, not the core topic.  Extract just the topic
        # so that graph entity extraction and vector search target the right documents.
        if _is_instructional_summary_query(query):
            topic = _extract_core_retrieval_topic(deterministic)
            if topic and topic != deterministic:
                logger.info(
                    "normalize_query.instructional_summary_simplification "
                    "original=%r simplified=%r",
                    query[:120],
                    topic,
                )
                return topic
        return deterministic
    if not _should_normalize_query(query):
        return deterministic

    if len(_query_normalizer_terms_impl(deterministic)) <= 4:
        return deterministic

    provider, resolved_model = _resolve_query_normalizer_provider(llm_provider, model)
    if not provider:
        return deterministic

    cached = _get_cached_normalized_query(query, provider, resolved_model)
    if cached:
        return cached

    candidate = await _call_query_normalizer_llm(deterministic, provider, resolved_model)
    normalized = candidate.strip() if isinstance(candidate, str) and candidate.strip() else deterministic
    if _has_multi_facet_query(query) and not _source_set_covers_query_facets(query, [
        {"filename": normalized, "filepath": normalized, "snippet": normalized, "content": normalized}
    ]):
        return deterministic
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
    _category, locator = canonical_source_identity(source, default_category="vault")
    return locator


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


@app.middleware("http")
async def _tag_deprecated_mode(request: Request, call_next):
    # Stamp X-Deprecated-Mode on every /api/v1/query response whose body carries
    # a legacy mode name. Runs as the outermost middleware so the header
    # survives HTTPException paths (Starlette discards pre-set headers when a
    # handler raises). Body is consumed here once and cached on
    # request._body so the downstream handler re-reads from cache.
    deprecated: Optional[str] = None
    if request.method == "POST" and request.url.path == "/api/v1/query":
        try:
            from src.services.query_dispatch import LEGACY_MODE_MAP
            body_bytes = await request.body()
            if body_bytes:
                raw_mode = str(json.loads(body_bytes).get("mode") or "").strip().lower()
                if raw_mode in LEGACY_MODE_MAP:
                    deprecated = raw_mode
        except Exception:
            # Malformed body / non-JSON / missing field — fall through; the
            # handler will produce its own 4xx and no header is needed.
            pass

    response = await call_next(request)
    if deprecated:
        response.headers["X-Deprecated-Mode"] = deprecated
    return response


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
    parsed_port = _safe_url_port(parsed)
    if parsed_port:
        netloc_suffix = f":{parsed_port}"

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


_MCP_VAULT_TOOL_IMPLS: Optional[tuple[Any, Any, Any]] = None
_REVIEW_QUERY_LEADING_RE = re.compile(
    r"^\s*(?:please\s+)?(?:(?:deep|comprehensive)\s+)?"
    r"(?:review|analy[sz]e|assess|evaluate|summari[sz]e)\s+",
    re.IGNORECASE,
)
_REVIEW_QUERY_TRAILING_RE = re.compile(
    r"\s+(?:using|with|from)\s+(?:only\s+)?(?:evidence|information|context)\s+from\s+(?:my\s+)?vault\b.*$",
    re.IGNORECASE,
)
_REVIEW_COMPOUND_PATTERNS = (
    (re.compile(r"\bpet\s*(?:/|\band\b)?\s*ct\b", re.IGNORECASE), "pet_ct"),
    (re.compile(r"\bblood\s+work\b", re.IGNORECASE), "bloodwork"),
)


def _load_mcp_vault_tool_impls() -> tuple[Any, Any, Any]:
    global _MCP_VAULT_TOOL_IMPLS
    if _MCP_VAULT_TOOL_IMPLS is not None:
        return _MCP_VAULT_TOOL_IMPLS

    try:
        from src.mcp.obsidian_rag_unified_mcp import (
            batch_read_vault_notes as _mcp_batch_read_vault_notes_impl,
            read_attachment_text as _mcp_read_attachment_text_impl,
            search_vault as _mcp_search_vault_impl,
        )
    except Exception:
        base_path = _project_root()
        if base_path not in sys.path:
            sys.path.append(base_path)
        from src.mcp.obsidian_rag_unified_mcp import (
            batch_read_vault_notes as _mcp_batch_read_vault_notes_impl,
            read_attachment_text as _mcp_read_attachment_text_impl,
            search_vault as _mcp_search_vault_impl,
        )

    _MCP_VAULT_TOOL_IMPLS = (
        _mcp_search_vault_impl,
        _mcp_batch_read_vault_notes_impl,
        _mcp_read_attachment_text_impl,
    )
    return _MCP_VAULT_TOOL_IMPLS


def _extract_mcp_text_payload(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    parts: List[str] = []
    for item in items:
        text = getattr(item, "text", None)
        if text is None and isinstance(item, dict):
            text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text)
    return "\n".join(parts).strip()


def _clean_review_fragment(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip(" \t\r\n,;:.!?"))
    cleaned = re.sub(r"^(?:my|the|all\s+my)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:from|in)\s+(?:my\s+)?vault$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:documents?|docs?|files?)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _extract_review_facets(query: str) -> List[str]:
    normalized = re.sub(r"\s+", " ", str(query or "").strip())
    if not normalized:
        return []

    working = _REVIEW_QUERY_LEADING_RE.sub("", normalized)
    working = _REVIEW_QUERY_TRAILING_RE.sub("", working)
    working = re.sub(r"\b(?:from|in)\s+(?:my\s+)?vault\b", "", working, flags=re.IGNORECASE)
    working = re.sub(r"\b(?:notes?|documents?|docs?|files?)\s+about\b", "", working, flags=re.IGNORECASE)
    working = working.strip(" ?!.,;:")
    if not working:
        return []

    protected = working
    for pattern, replacement in _REVIEW_COMPOUND_PATTERNS:
        protected = pattern.sub(replacement, protected)

    primary_fragments = [
        fragment.strip()
        for fragment in re.split(r"\s*(?:,|;|\n)\s*", protected)
        if fragment.strip()
    ] or [protected]

    fragments: List[str] = []
    for fragment in primary_fragments:
        parts = [
            part.strip()
            for part in re.split(r"\s+\band\b\s+", fragment, flags=re.IGNORECASE)
            if part.strip()
        ]
        fragments.extend(parts or [fragment])

    restored: List[str] = []
    seen: set[str] = set()
    for fragment in fragments:
        restored_fragment = fragment.replace("pet_ct", "pet ct")
        cleaned = _clean_review_fragment(restored_fragment)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        restored.append(cleaned)

    return restored


def _is_comprehensive_vault_review_query(query: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(query or "").strip()).lower()
    if not normalized:
        return False

    has_review_signal = any(
        signal in normalized
        for signal in (
            "review ",
            "review my",
            "deep review",
            "comprehensive review",
            "assess ",
            "analyze ",
            "analyse ",
            "evaluate ",
        )
    )
    if not has_review_signal:
        return False

    facets = _extract_review_facets(query)
    has_personal_scope = any(
        marker in normalized
        for marker in (
            " my ",
            "my vault",
            "my notes",
            "from my vault",
            "using only evidence from my vault",
            "all my",
            "entire vault",
        )
    )
    has_comprehensive_scope = any(
        marker in normalized
        for marker in (
            "all my",
            "entire vault",
            "full vault",
            "comprehensive",
            "deep review",
        )
    )
    return bool((has_personal_scope and len(facets) >= 1) or len(facets) >= 2 or has_comprehensive_scope)


def _parse_mcp_semantic_search_results(payload_text: str) -> List[Dict[str, Any]]:
    if not payload_text or "❌" in payload_text:
        return []

    entry_pattern = re.compile(
        r"\*\*(?P<index>\d+)\.\s+(?P<filename>.*?)\*\*\s+\((?P<relevance>\d+)% relevant\)\s*\n"
        r"\s*📁\s+(?P<filepath>[^\n]+)"
        r"(?:\n\s*📄\s+(?P<snippet>.*?))?"
        r"(?=\n\*\*\d+\.|\Z)",
        re.DOTALL,
    )
    results: List[Dict[str, Any]] = []
    for match in entry_pattern.finditer(payload_text):
        filepath = normalize_vault_path(match.group("filepath").strip())
        filename = match.group("filename").strip() or os.path.basename(filepath)
        snippet = str(match.group("snippet") or "").strip()
        try:
            relevance = float(match.group("relevance"))
        except (TypeError, ValueError):
            relevance = 50.0
        results.append(
            {
                "filename": filename,
                "filepath": filepath,
                "relevance": relevance,
                "snippet": snippet,
                "source_type": "direct-excerpt",
                "source_category": "vault",
            }
        )
    return results


async def _multi_facet_vault_search(
    facets: List[str],
    *,
    n_per_facet: int,
) -> tuple[List[Dict[str, Any]], List[str]]:
    search_vault_impl, _batch_read_impl, _read_attachment_impl = _load_mcp_vault_tool_impls()
    warnings: List[str] = []
    if not facets:
        return [], warnings

    responses = await asyncio.gather(
        *[
            search_vault_impl(
                {
                    "query": facet,
                    "n_results": max(1, min(10, n_per_facet)),
                    "include_content": True,
                }
            )
            for facet in facets
        ],
        return_exceptions=True,
    )

    deduped: Dict[tuple[str, str], Dict[str, Any]] = {}
    for facet, response in zip(facets, responses):
        if isinstance(response, Exception):
            warnings.append(f"Semantic search failed for '{facet}': {response}")
            continue

        payload_text = _extract_mcp_text_payload(response)
        facet_results = _parse_mcp_semantic_search_results(payload_text)
        for result in facet_results:
            identity = canonical_source_identity(result, default_category="vault")
            current = deduped.get(identity)
            facet_hits = set(current.get("matched_facets", [])) if current else set()
            facet_hits.add(facet)
            candidate = {
                **result,
                "matched_facets": sorted(facet_hits),
            }
            candidate_score = float(candidate.get("relevance", 0.0) or 0.0) + (len(facet_hits) * 8.0)
            existing_score = -1.0
            if current:
                existing_score = float(current.get("relevance", 0.0) or 0.0) + (len(current.get("matched_facets", [])) * 8.0)
            if current is None or candidate_score >= existing_score:
                deduped[identity] = candidate

    ranked = sorted(
        deduped.values(),
        key=lambda item: (
            len(item.get("matched_facets", [])),
            float(item.get("relevance", 0.0) or 0.0),
        ),
        reverse=True,
    )
    return ranked, warnings


def _parse_mcp_batch_read_results(payload_text: str) -> tuple[OrderedDict[str, str], List[str]]:
    notes: OrderedDict[str, str] = OrderedDict()
    warnings: List[str] = []
    if not payload_text:
        return notes, warnings

    section_pattern = re.compile(r"^--- (?P<path>.+)$", re.MULTILINE)
    matches = list(section_pattern.finditer(payload_text))
    if not matches:
        return notes, warnings

    for index, match in enumerate(matches):
        raw_path = match.group("path").strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(payload_text)
        content = payload_text[start:end].strip()
        normalized_path = normalize_vault_path(raw_path)
        if not content:
            warnings.append(f"No content returned for {normalized_path}.")
            continue
        if content.startswith("❌"):
            warnings.append(f"{normalized_path}: {content}")
            continue
        notes[normalized_path] = content

    return notes, warnings


def _read_note_from_vault(path: str) -> Optional[str]:
    normalized_path = normalize_vault_path(path)
    try:
        resolved = (_vault_root() / normalized_path).resolve()
        resolved.relative_to(_vault_root())
    except Exception:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None

    max_chars = 200000
    raw_limit = _get_env_value("MCP_MAX_NOTE_CHARS", "200000")
    try:
        max_chars = max(1000, int(raw_limit))
    except (TypeError, ValueError):
        pass

    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    return text[:max_chars]


async def _read_vault_notes(paths: List[str]) -> tuple[OrderedDict[str, str], List[str]]:
    _search_vault_impl, batch_read_impl, read_attachment_impl = _load_mcp_vault_tool_impls()
    requested_paths = [normalize_vault_path(path) for path in paths if str(path or "").strip()]
    if not requested_paths:
        return OrderedDict(), []

    batch_result = await batch_read_impl({"paths": requested_paths})
    payload_text = _extract_mcp_text_payload(batch_result)
    notes, warnings = _parse_mcp_batch_read_results(payload_text)

    for path in requested_paths:
        if path in notes:
            continue
        if path.lower().endswith(".pdf"):
            attachment_result = await read_attachment_impl({"path": path})
            attachment_text = _extract_mcp_text_payload(attachment_result)
            if attachment_text and not attachment_text.startswith("❌"):
                notes[path] = attachment_text
                warnings = [
                    warning for warning in warnings
                    if not str(warning).startswith(f"{path}:")
                ]
                continue
        fallback_content = _read_note_from_vault(path)
        if fallback_content is not None:
            notes[path] = fallback_content
        else:
            warnings.append(f"Unable to read note content for {path}.")

    ordered_notes: OrderedDict[str, str] = OrderedDict()
    for path in requested_paths:
        if path in notes:
            ordered_notes[path] = notes[path]
    return ordered_notes, warnings


async def _vault_review_query(
    request: "UnifiedQueryRequest",
    retrieval_query: str,
    effective_relevance_threshold: float,
    client: httpx.AsyncClient,
    *,
    requested_mode: str,
    auto_routed: bool,
) -> Dict[str, Any]:
    review_query = retrieval_query or request.query
    facets = _extract_review_facets(review_query)
    if not facets:
        facets = [review_query]

    n_per_facet = min(6, max(3, math.ceil(request.max_results / max(1, len(facets)))))
    retrieval_sources, warnings = await _multi_facet_vault_search(facets, n_per_facet=n_per_facet)
    retrieval_sources = _apply_relevance_filter(retrieval_sources, effective_relevance_threshold)

    max_note_count = min(18, max(request.max_results, len(facets) * n_per_facet))
    selected_retrieval_sources = retrieval_sources[:max_note_count]
    if not selected_retrieval_sources and review_query != request.query:
        selected_retrieval_sources, extra_warnings = await _multi_facet_vault_search(
            [request.query],
            n_per_facet=min(8, max(4, request.max_results)),
        )
        warnings.extend(extra_warnings)
        selected_retrieval_sources = _apply_relevance_filter(
            selected_retrieval_sources,
            effective_relevance_threshold,
        )[:max_note_count]

    if not selected_retrieval_sources:
        answer = "No vault notes were found for this review query."
        if request.web_search:
            web_search_result = await _perform_tavily_web_search(client, review_query or request.query)
        else:
            web_search_result = None
        return {
            "query": request.query,
            "mode": "vault_review",
            "answer": answer,
            "citations": [],
            "sources": [],
            "web_search": web_search_result,
            "results": {
                "facets": facets,
                "used_documents": [],
                "warnings": warnings,
            },
            "metadata": {
                "description": "Deep Review full-note pipeline (MCP semantic search + batch note reads).",
                "facets": facets,
                "requested_mode": requested_mode,
                "auto_routed": auto_routed,
                "web_search_enabled": bool(request.web_search),
                "warnings": warnings,
            },
        }

    note_paths = [str(source.get("filepath") or "") for source in selected_retrieval_sources if source.get("filepath")]
    notes, read_warnings = await _read_vault_notes(note_paths)
    warnings.extend(read_warnings)

    web_search_result = None
    if request.web_search:
        web_search_result = await _perform_tavily_web_search(
            client,
            review_query or request.query,
        )

    synthesis_result = await _synthesize_vault_review_answer_impl(
        request.query,
        notes,
        request.llm_provider,
        request.model,
        web_search_result,
        request.system_prompt,
    )

    source_by_path = {
        normalize_vault_path(str(source.get("filepath") or source.get("path") or "")): source
        for source in selected_retrieval_sources
        if source.get("filepath") or source.get("path")
    }
    synthesis_documents = synthesis_result.get("used_documents")
    response_sources: List[Dict[str, Any]] = []
    if isinstance(synthesis_documents, list) and synthesis_documents:
        for document in synthesis_documents:
            if not isinstance(document, dict):
                continue
            normalized_path = normalize_vault_path(
                str(document.get("filepath") or document.get("path") or "")
            )
            retrieval_source = source_by_path.get(normalized_path, {})
            merged_source = {
                **retrieval_source,
                **document,
                "filepath": normalized_path or retrieval_source.get("filepath") or document.get("filepath"),
                "filename": document.get("filename") or retrieval_source.get("filename") or Path(normalized_path).name,
                "source_category": "vault",
            }
            response_sources.append(
                _normalize_cascading_source(
                    merged_source,
                    source_type=str(merged_source.get("source_type") or "direct-excerpt"),
                    default_relevance=float(
                        retrieval_source.get("relevance", merged_source.get("relevance", 50.0)) or 50.0
                    ),
                )
            )
    else:
        response_sources = [
            _normalize_cascading_source(
                source,
                source_type=str(source.get("source_type") or "direct-excerpt"),
                default_relevance=float(source.get("relevance", 50.0) or 50.0),
            )
            for source in selected_retrieval_sources
        ]

    fallback_reason = str(synthesis_result.get("fallback_reason") or "").strip()
    if fallback_reason:
        warnings.append(f"Deep Review synthesis fallback: {fallback_reason}.")

    return {
        "query": request.query,
        "mode": "vault_review",
        "answer": str(synthesis_result.get("answer") or "").strip() or "No review answer was generated.",
        "citations": synthesis_result.get("citations", []),
        "sources": response_sources,
        "web_search": web_search_result,
        "results": {
            "facets": facets,
            "used_documents": response_sources,
            "candidate_sources": selected_retrieval_sources,
            "notes_loaded": len(notes),
            "warnings": warnings,
            "fallback_reason": fallback_reason,
        },
        "metadata": {
            "description": "Deep Review full-note pipeline (MCP semantic search + batch note reads).",
            "facets": facets,
            "requested_mode": requested_mode,
            "auto_routed": auto_routed,
            "evidence": {
                "candidate_source_count": len(selected_retrieval_sources),
                "selected_source_count": len(response_sources),
                "notes_loaded": len(notes),
            },
            "web_search_enabled": bool(request.web_search),
            "warnings": warnings,
        },
    }


# thread pool for running synchronous Deep Thinking agents
executor = ThreadPoolExecutor(max_workers=5)


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

    async def _fetch_graph_health_over_http() -> tuple[str, dict]:
        try:
            async with httpx.AsyncClient() as client:
                graph_resp = await _get_json(
                    client, f"{GRAPH_SERVICE_URL}/health", timeout=2.0, service="graph"
                )
                if graph_resp and graph_resp.status_code == 200:
                    return "healthy", graph_resp.json()
                return "unhealthy", {}
        except:
            return "unreachable", {}

    try:
        from src.services.internal_graph_transport import graph_health, lightrag_health, lightrag_stats

        graph_code, graph_payload = await asyncio.to_thread(graph_health)
        graph_ready = bool(graph_payload.get("graph_loaded")) if isinstance(graph_payload, dict) else False
        graph_nodes = int(graph_payload.get("nodes", 0) or 0) if isinstance(graph_payload, dict) else 0
        graph_edges = int(graph_payload.get("edges", 0) or 0) if isinstance(graph_payload, dict) else 0
        if graph_code == 200 and graph_ready and (graph_nodes > 0 or graph_edges > 0):
            graph_data = graph_payload
            graph_status = "healthy"
        else:
            graph_status, graph_data = await _fetch_graph_health_over_http()
    except:
        graph_status, graph_data = await _fetch_graph_health_over_http()

    try:
        lightrag_code, lightrag_payload = await asyncio.to_thread(lightrag_health)
        if lightrag_code == 200:
            lightrag_data = lightrag_payload
            lightrag_status = "healthy"
        else:
            lightrag_status = "unhealthy"
    except:
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

    try:
        stats_code, stats_payload = await asyncio.to_thread(lightrag_stats)
        if stats_code == 200 and isinstance(stats_payload, dict):
            lightrag_data.update(stats_payload)
    except:
        try:
            async with httpx.AsyncClient() as client:
                stats_resp = await _get_json(
                    client, f"{LIGHTRAG_SERVICE_URL}/stats", timeout=2.0, service="lightrag"
                )
                if stats_resp and stats_resp.status_code == 200:
                    lightrag_data.update(stats_resp.json())
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


async def _probe_local_provider(provider: str, timeout: float = 3.0) -> bool:
    """Return True if the local inference server for *provider* responds within *timeout* seconds."""
    try:
        if provider == "ollama":
            from utils.ollama_runtime import resolve_ollama_host  # type: ignore
            host = resolve_ollama_host()
            url = f"{host}/api/tags"
        elif provider in {"lmstudio", "mlx"}:
            base = (
                _get_env_value("LMSTUDIO_BASE_URL")
                or _get_env_value("MLX_BASE_URL")
                or "http://host.docker.internal:1234/v1"
            ).rstrip("/")
            url = f"{base}/models"
        else:
            return False
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            return resp.status_code < 500
    except Exception:
        return False


async def _list_ollama_models(timeout: float = 3.0) -> list:
    try:
        from utils.ollama_runtime import resolve_ollama_host  # type: ignore
        host = resolve_ollama_host()
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{host}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", []) if "embed" not in m.get("name", "").lower()]
    except Exception:
        pass
    return []


async def _list_lmstudio_models(timeout: float = 3.0) -> list:
    try:
        base = (
            _get_env_value("LMSTUDIO_BASE_URL")
            or _get_env_value("MLX_BASE_URL")
            or "http://host.docker.internal:1234/v1"
        ).rstrip("/")
        api_key = _get_env_value("LMSTUDIO_API_KEY") or _get_env_value("MLX_API_KEY") or "lmstudio"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
    except Exception:
        pass
    return []


@app.get("/api/v1/providers")
async def get_providers():
    """
    Live capability report: which providers are configured, reachable, and what models they expose.

    - available: server actually responded within 3 s
    - configured: API key / URL is set in the environment
    - models: list (local providers) or single string (remote providers)

    Use this endpoint from UI and MCP callers to populate provider/model selectors and
    to know which fallback is active.
    """
    ollama_up, lmstudio_up, ollama_models, lmstudio_models = await asyncio.gather(
        _probe_local_provider("ollama"),
        _probe_local_provider("lmstudio"),
        _list_ollama_models(),
        _list_lmstudio_models(),
    )

    default_provider = _get_env_value("DEFAULT_LLM_PROVIDER", "ollama")
    fallback_provider = _get_env_value("LOCAL_LLM_FALLBACK_PROVIDER", "")

    return {
        "default": default_provider,
        "fallback": fallback_provider or None,
        "providers": {
            "ollama": {
                "available": ollama_up,
                "configured": bool(_get_env_value("OLLAMA_HOST") or _get_env_value("OLLAMA_MODEL")),
                "host": _get_env_value("OLLAMA_HOST", "http://host.docker.internal:11434"),
                "model": _get_env_value("OLLAMA_MODEL", "qwen2.5:7b-instruct"),
                "models": ollama_models,
                "note": "Local inference — Ollama 0.19+ serves MLX natively",
            },
            "lmstudio": {
                "available": lmstudio_up,
                "configured": bool(
                    _get_env_value("LMSTUDIO_BASE_URL")
                    or _get_env_value("MLX_BASE_URL")
                    or _get_env_value("LMSTUDIO_MODEL")
                ),
                "host": _get_env_value("LMSTUDIO_BASE_URL") or _get_env_value("MLX_BASE_URL"),
                "model": _get_env_value("LMSTUDIO_MODEL") or _get_env_value("MLX_MODEL"),
                "models": lmstudio_models,
                "note": "Local inference — LM Studio / MLX server",
            },
            "openrouter": {
                "available": bool(_get_env_value("OPENROUTER_API_KEY")),
                "configured": bool(_get_env_value("OPENROUTER_API_KEY")),
                "model": _get_env_value("OPENROUTER_MODEL", "openrouter/auto"),
                "note": "Cloud routing — model set via OPENROUTER_MODEL in .env",
            },
            "claude": {
                "available": bool(_get_env_value("ANTHROPIC_API_KEY")),
                "configured": bool(_get_env_value("ANTHROPIC_API_KEY")),
                "model": _get_env_value("CLAUDE_MODEL") or "claude-sonnet-4-5-20250929",
                "note": "Anthropic API — uses CLAUDE_MODEL or latest sonnet",
            },
            "gemini": {
                "available": bool(_get_env_value("GEMINI_API_KEY") or _get_env_value("GOOGLE_API_KEY")),
                "configured": bool(_get_env_value("GEMINI_API_KEY") or _get_env_value("GOOGLE_API_KEY")),
                "model": _get_env_value("GEMINI_MODEL") or "gemini-2.5-flash",
                "note": "Google Gemini API — uses GEMINI_MODEL",
            },
            "chatgpt": {
                "available": bool(_get_env_value("OPENAI_API_KEY")),
                "configured": bool(_get_env_value("OPENAI_API_KEY")),
                "model": _get_env_value("OPENAI_MODEL", "gpt-4o"),
                "note": "OpenAI API — uses OPENAI_MODEL",
            },
        },
    }


@app.get("/api/v1/provider-status")
async def get_provider_status():
    """Return provider key/model visibility from the gateway runtime, not the webapp runtime."""
    vault_root = _vault_root()
    return {
        "keys": {
            "gemini": bool(_get_env_value("GEMINI_API_KEY")),
            "anthropic": bool(_get_env_value("ANTHROPIC_API_KEY")),
            "openai": bool(_get_env_value("OPENAI_API_KEY")),
            "lmstudio": bool(
                _get_env_value("LMSTUDIO_BASE_URL")
                or _get_env_value("LMSTUDIO_MODEL")
                or _get_env_value("MLX_BASE_URL")
                or _get_env_value("MLX_MODEL")
            ),
        },
        "models": {
            "ollama": _get_env_value("OLLAMA_MODEL", "mistral"),
            "openrouter": _get_env_value("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free"),
            "chatgpt": _get_env_value("OPENAI_MODEL", "gpt-4o"),
            "gemini": _get_env_value("GEMINI_MODEL", "gemini-3-pro-preview"),
            "claude": _get_env_value("CLAUDE_MODEL", "claude-3-5-sonnet-latest"),
            "lmstudio": _get_env_value("LMSTUDIO_MODEL", _get_env_value("MLX_MODEL", _get_env_value("LLM_MODEL_PATH", "local-model"))),
        },
        "vault": {
            "name": os.getenv("OBSIDIAN_VAULT_NAME") or vault_root.name,
            "root": str(vault_root),
        },
    }


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
    system_prompt: str = None,
    brief_concept_index: bool = True,
    supplemental_context: str = None,
) -> Dict[str, Any]:
    try:
        return await _synthesize_cascading_answer_impl(
            query,
            sources,
            llm_provider,
            model,
            system_prompt,
            brief_concept_index,
            supplemental_context,
        )
    except Exception as e:
        print(f"Error in cascading fallback synthesis: {e}")
        resolved_provider = _canonical_cascading_provider_name(llm_provider)
        raw_provider = str(llm_provider or "").strip().lower()
        if raw_provider == "mlx" or resolved_provider == "mlx":
            raise RuntimeError(str(e)) from e
        raise

class UnifiedQueryRequest(BaseModel):
    query: str
    # Legacy names (vector, cascading, vault_review, mempalace) and canonical
    # names (ask, research, investigate) both accepted. Normalized via
    # src.services.query_dispatch.normalize_legacy_request() at handler entry.
    mode: str = "cascading"
    # Canonical fields — optional. When absent, values are derived from the
    # legacy mode string via LEGACY_MODE_MAP.
    depth: Optional[str] = None   # auto | shallow | staged | full  (research only)
    sources: Optional[List[str]] = None  # vault | mempalace | web
    max_results: int = 10
    llm_provider: str = _get_env_value(
        "CASCADING_LLM_PROVIDER",
        _get_env_value("DEFAULT_LLM_PROVIDER", "openrouter")
    )
    model: Optional[str] = None
    temperature: float = 0.7
    relevance_threshold: float = 0  # 0-100%, 0 = show all results
    distance_threshold: Optional[float] = None  # Legacy support (deprecated)
    system_prompt: Optional[str] = None
    web_search: bool = False
    llm_knowledge: bool = False
    brief_concept_index: bool = True
    entities_mode: Optional[str] = None  # naive, local, global, hybrid


def _canonical_to_legacy_dispatch_key(
    canonical_mode: str,
    canonical_depth: str,
    canonical_sources: tuple,
) -> str:
    """Map a canonical (mode, depth, sources) triple onto the legacy dispatch
    key consumed by the if-chain below (`vector`, `cascading`, `vault_review`,
    `mempalace`).

    Phase 1 migration: dispatch code itself is unchanged; this adapter exists
    so the handler can accept canonical names without a full rewrite. Phase 2
    removes the if-chain and this function.

    Multi-source `ask` is not yet supported — we fall back to the first
    source in priority order (vault > mempalace).
    """
    if canonical_mode == "ask":
        if canonical_sources == ("mempalace",):
            return "mempalace"
        # Default (vault-only or multi-source with vault present).
        if "vault" in canonical_sources:
            return "vector"
        if "mempalace" in canonical_sources:
            return "mempalace"
        return "vector"

    if canonical_mode == "research":
        if canonical_depth == "full":
            return "vault_review"
        if canonical_depth == "shallow":
            return "vector"
        # "staged" and "auto" both land on cascading — the existing
        # auto-routing below (line ~3595) promotes to vault_review when
        # the classifier fires for depth="auto". For explicit depth="staged"
        # we skip the auto-routing to honor the user's override.
        return "cascading"

    raise HTTPException(
        status_code=400,
        detail=f"Mode '{canonical_mode}' is not served on this REST endpoint.",
    )


@app.post("/api/v1/query")
async def unified_query(request: UnifiedQueryRequest, response: Response):
    """
    Enhanced unified query endpoint for the currently supported retrieval modes.

    REST modes (canonical):
    - ask:      Fast single-pass retrieval (replaces: vector, mempalace)
    - research: Staged retrieval + synthesis   (replaces: cascading, vault_review)
                depth ∈ {auto, shallow, staged, full}; auto defaults on.

    Legacy mode names (vector, cascading, vault_review, mempalace) remain
    accepted. Responses for legacy names carry `X-Deprecated-Mode: <legacy>`
    so migration progress is visible in access logs.

    Deep research (`investigate`) is served separately over WebSocket at
    /api/v1/deep-research.
    """
    from src.services.query_dispatch import (
        UnsupportedMode,
        normalize_legacy_request,
    )

    raw_mode = (request.mode or "").strip()
    explicit_depth = (request.depth or "").strip().lower() or None
    explicit_sources = tuple(s.strip().lower() for s in (request.sources or []) if s and s.strip()) or None

    try:
        canonical_mode, canonical_depth, canonical_sources, deprecated = normalize_legacy_request(
            raw_mode,
            explicit_depth=explicit_depth,  # type: ignore[arg-type]
            explicit_sources=explicit_sources,  # type: ignore[arg-type]
            web_search_toggle=bool(request.web_search),
        )
    except UnsupportedMode as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if canonical_mode == "investigate":
        raise HTTPException(
            status_code=400,
            detail=(
                "Mode 'investigate' is served via WebSocket /api/v1/deep-research; "
                "this REST endpoint accepts 'ask' or 'research'."
            ),
        )

    # X-Deprecated-Mode is set by `_tag_deprecated_mode` middleware so it
    # survives HTTPException paths — no per-handler header work here.
    _ = deprecated  # kept in the tuple for future telemetry hooks; silence linters

    # Project canonical shape onto the legacy dispatch key. Phase 2 deletes
    # this adapter along with the if-chain below.
    mode = _canonical_to_legacy_dispatch_key(
        canonical_mode, canonical_depth, canonical_sources
    )
    requested_mode = mode

    auto_routed_to_vault_review = False
    # Honor explicit depth="staged" by skipping auto-routing; depth="auto"
    # (the default for legacy `cascading` and for canonical `research` w/o
    # explicit depth) keeps current behavior.
    allow_auto_route = (canonical_mode != "research") or (canonical_depth != "staged")
    if mode == "cascading" and allow_auto_route and _is_comprehensive_vault_review_query(request.query):
        mode = "vault_review"
        auto_routed_to_vault_review = True

    if request.system_prompt and mode in {"cascading", "vault_review"}:
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
        effective_relevance_threshold = _relevance_threshold_from_distance_threshold_impl(
            request.distance_threshold,
            default=0.0,
        )
    print(
        f"🎯 API Gateway received relevance_threshold: {effective_relevance_threshold}%"
    )

    print(f"DEBUG: Raw Query Input: '{request.query}'") # NEW DEBUG
    request.query, filters = _parse_query_tag_filters(request.query)
    if filters:
        print(f"DEBUG: Parsed filters (UnifiedQuery): {filters}, Cleaned Query: '{request.query}'")

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

    effective_brief_concept_index = (
        bool(request.brief_concept_index)
        and not _prefers_full_vault_answer_impl(request.query)
    )

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
                llm_model=request.model,
                api_key=api_key,
            )

            retrieval_started_at = time.perf_counter()
            result = await retriever.retrieve(
                retrieval_query,
                max_results=request.max_results,
                entities=extracted_entities,
                mem0_context=mem0_context
            )
            retrieval_elapsed_ms = int((time.perf_counter() - retrieval_started_at) * 1000)
            logger.info(
                "cascading_query.retrieval_complete provider=%s max_results=%d retrieval_ms=%d query=%s",
                request.llm_provider,
                request.max_results,
                retrieval_elapsed_ms,
                retrieval_query[:160],
            )

            answer = ""
            anchor_answer = ""
            sources = []
            anchor_sources = []
            vector_sources = []
            stages = result.get("stages", {}) if isinstance(result, dict) else {}
            diagnostics = stages.get("diagnostics", {}) if isinstance(stages, dict) else {}
            warnings: List[str] = []

            # Prefer graph answer if present from the anchor stage
            anchors = stages.get("anchors", {})
            if isinstance(anchors, dict):
                answer = anchors.get("answer", "") or anchors.get("result", "")
                anchor_answer = answer
                anchor_sources = [
                    _normalize_cascading_source(source, source_type="anchor")
                    for source in (anchors.get("sources", []) or [])
                    if isinstance(source, dict)
                ]

            # Build sources from vector stage if available
            vector_snippets_by_identity = {}
            vector_data = stages.get("vectors", {})
            if isinstance(vector_data, dict) and vector_data.get("documents"):
                docs = vector_data.get("documents", [[]])[0]
                metas = vector_data.get("metadatas", [[]])[0]
                dists = vector_data.get("distances", [[]])[0]
                for doc, meta, dist in zip(docs, metas, dists):
                    try:
                        relevance = _distance_to_relevance_impl(dist, default=50.0)
                    except Exception:
                        relevance = 50.0
                    doc_text = doc if isinstance(doc, str) else ""
                    snippet = (
                        (doc_text[:300] + "...") if len(doc_text) > 300 else doc_text
                    )
                    normalized_source = _normalize_cascading_source(
                        {
                            "filename": meta.get("filename", "unknown"),
                            "filepath": meta.get("filepath", "unknown"),
                            "relevance": relevance,
                            "snippet": snippet,
                        },
                        source_type="direct-excerpt",
                    )
                    vector_sources.append(normalized_source)
                    source_identity = normalized_source.get("_source_identity")
                    if source_identity and (
                        source_identity not in vector_snippets_by_identity
                        or normalized_source["relevance"] > vector_snippets_by_identity[source_identity]["relevance"]
                    ):
                        vector_snippets_by_identity[source_identity] = {
                            "snippet": normalized_source["snippet"],
                            "relevance": normalized_source["relevance"],
                        }

            def _is_boilerplate_snippet(text: str) -> bool:
                if not text:
                    return True
                lowered = str(text).strip().lower()
                return (
                    bool(re.match(r"^\s*context\s*:", text, re.IGNORECASE))
                    or lowered.startswith("on explicit graph path.")
                    or lowered.startswith("connected via explicit graph path")
                    or "seed_hits=" in lowered
                )

            if anchor_sources and vector_snippets_by_identity:
                for src in anchor_sources:
                    snippet = src.get("snippet", "")
                    if not _is_boilerplate_snippet(snippet):
                        continue
                    source_identity = canonical_source_identity(src, default_category="vault")
                    replacement = vector_snippets_by_identity.get(source_identity, {}).get("snippet")
                    if replacement:
                        src["snippet"] = replacement

            sources = anchor_sources + vector_sources

            # Deduplicate sources by canonical identity, keep highest relevance
            deduped = {}
            for src in sources:
                source_identity = canonical_source_identity(src, default_category="vault")
                rel = src.get("relevance", 0) or 0
                src["_query_rank_score"] = _cascading_source_rank_score(retrieval_query, src)
                if source_identity not in deduped or rel > deduped[source_identity].get("relevance", 0):
                    deduped[source_identity] = src
            sources = sorted(
                deduped.values(),
                key=lambda s: (
                    float(s.get("_query_rank_score", s.get("relevance", 0)) or 0.0),
                    float(s.get("relevance", 0) or 0.0),
                ),
                reverse=True,
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
            candidate_source_count = len(sources)
            selected_sources = _select_cascading_evidence_set(
                retrieval_query,
                sources,
                max_results=request.max_results,
            )
            if selected_sources:
                sources = selected_sources
            relationship_guardrail = _should_require_vault_relationship_guardrail(
                request.query,
                sources,
            )
            comparison_guardrail = _should_require_vault_comparison_guardrail(
                request.query,
                sources,
            )

            if not answer and isinstance(result, dict):
                answer = result.get("answer", "") or ""

            # Fetch supplemental web evidence before synthesis so the model can use it when requested.
            web_search_result = None
            if request.web_search and not relationship_guardrail and not comparison_guardrail:
                async with httpx.AsyncClient() as client:
                    web_search_result = await _perform_tavily_web_search(
                        client,
                        retrieval_query or request.query,
                    )

            # Always synthesize if we have sources, but pass the existing graph answer in as context
            if sources:
                try:
                    synthesis_started_at = time.perf_counter()
                    supplemental_sections = []
                    if answer and not _looks_like_structural_graph_path_answer(answer):
                        supplemental_sections.append(
                            "The following is a partial analytical answer derived from the knowledge graph. "
                            "Incorporate it into your final response only where it is consistent with the provided vault context.\n"
                            f"{answer}"
                        )
                    web_context = _format_web_search_context_for_synthesis(web_search_result)
                    if web_context:
                        supplemental_sections.append(web_context)
                    synthesis_result = await _synthesize_cascading_answer(
                        request.query,
                        sources,
                        request.llm_provider,
                        request.model,
                        request.system_prompt,
                        effective_brief_concept_index,
                        "\n\n".join(section for section in supplemental_sections if section) or None,
                    )
                    synthesis_elapsed_ms = int((time.perf_counter() - synthesis_started_at) * 1000)
                    if isinstance(synthesis_result, dict):
                        synthesized_answer = str(synthesis_result.get("answer") or "").strip()
                        fallback_reason = str(synthesis_result.get("fallback_reason") or "").strip()
                        synthesis_used_documents = synthesis_result.get("used_documents")
                        synthesis_citations = synthesis_result.get("citations")
                        if isinstance(synthesis_used_documents, list) and synthesis_used_documents:
                            sources = _hydrate_cascading_sources(sources, synthesis_used_documents)
                        multi_facet_query = _has_multi_facet_query(request.query)
                        relationship_query = _is_relation_style_query(request.query)
                        synthesized_covers_facets = _source_set_covers_query_facets(
                            request.query,
                            synthesis_used_documents if isinstance(synthesis_used_documents, list) else [],
                        )
                        if (
                            isinstance(synthesis_used_documents, list)
                            and synthesis_used_documents
                            and (
                                ((not relationship_query and not multi_facet_query) and len(sources) <= 2)
                                or len(synthesis_used_documents) >= min(2, len(sources))
                                or synthesized_covers_facets
                                or _summary_query_targets_source(request.query, synthesis_used_documents[0])
                            )
                        ):
                            sources = [
                                _normalize_cascading_source(
                                    source,
                                    source_type=str(source.get("source_type") or "direct-excerpt"),
                                    default_relevance=float(source.get("relevance", 50.0) or 50.0),
                                )
                                for source in synthesis_used_documents
                                if isinstance(source, dict)
                            ]
                        if (
                            _is_generic_cascading_fallback_answer(synthesized_answer)
                            and anchor_answer
                            and not _is_insufficient_answer(anchor_answer)
                            and not _looks_like_structural_graph_path_answer(anchor_answer)
                            and not relationship_guardrail
                            and not comparison_guardrail
                        ):
                            answer = _build_cascading_degraded_answer(
                                anchor_answer,
                                sources,
                                diagnostics,
                                fallback_reason or "weak_answer",
                            )
                            warnings.append(f"Cascading synthesis degraded; preserved anchor answer ({fallback_reason or 'weak_answer'}).")
                        elif (
                            _is_generic_cascading_fallback_answer(synthesized_answer)
                            and anchor_answer
                            and _looks_like_structural_graph_path_answer(anchor_answer)
                        ):
                            answer = _build_cascading_degraded_answer(
                                anchor_answer,
                                sources,
                                diagnostics,
                                fallback_reason or "weak_answer",
                            )
                            if fallback_reason:
                                warnings.append(f"Cascading synthesis fallback: {fallback_reason}.")
                        else:
                            answer = synthesized_answer
                            if fallback_reason:
                                warnings.append(f"Cascading synthesis fallback: {fallback_reason}.")
                            if relationship_guardrail and fallback_reason == "insufficient_vault_relationship_evidence":
                                warnings.append("Vault relationship guardrail applied; no direct vault connection was established.")
                            if comparison_guardrail and fallback_reason == "insufficient_vault_comparison_evidence":
                                warnings.append("Vault comparison guardrail applied; the vault did not support a grounded comparison.")
                        if isinstance(result, dict):
                            result["citations"] = synthesis_citations if isinstance(synthesis_citations, list) else []
                            result["used_documents"] = (
                                _hydrate_cascading_sources(synthesis_used_documents, sources)
                                if isinstance(synthesis_used_documents, list) and synthesis_used_documents
                                else sources
                            )
                            if fallback_reason:
                                result["synthesis_fallback_reason"] = fallback_reason
                        logger.info(
                            "cascading_query.synthesis_complete provider=%s selected_sources=%d synthesis_ms=%d fallback_reason=%s answer_chars=%d",
                            request.llm_provider,
                            len(sources),
                            synthesis_elapsed_ms,
                            fallback_reason,
                            len(answer),
                        )
                    else:
                        answer = str(synthesis_result or "").strip()
                        logger.info(
                            "cascading_query.synthesis_complete provider=%s selected_sources=%d synthesis_ms=%d fallback_reason=%s answer_chars=%d",
                            request.llm_provider,
                            len(sources),
                            synthesis_elapsed_ms,
                            "",
                            len(answer),
                        )
                except Exception as synth_error:
                    logger.warning(
                        "cascading_query.synthesis_failed provider=%s selected_sources=%d error=%s",
                        request.llm_provider,
                        len(sources),
                        synth_error,
                    )
                    if _is_mlx_runtime_failure(request.llm_provider, synth_error, model=request.model) or _looks_like_mlx_transport_failure_text(str(synth_error)):
                        recovery_payload = _mlx_recovery_error_payload(synth_error)
                        raise HTTPException(status_code=503, detail=recovery_payload)
                    raise
            
            if diagnostics.get("failures"):
                warnings.append("Some retrieval stages failed; answer may be based on partial evidence.")

            if not answer:
                 answer = _build_cascading_degraded_answer(
                     anchor_answer,
                     sources,
                     diagnostics,
                     "empty_answer",
                 )

            if isinstance(result, dict):
                result["answer"] = answer
                result["sources"] = sources
                # Keep used_documents aligned with the final normalized source list
                # returned to the client.
                result["used_documents"] = sources
                if warnings:
                    result["warnings"] = warnings

            return {
                "query": request.query,
                "mode": "cascading",
                "answer": answer,
                "citations": result.get("citations", []) if isinstance(result, dict) else [],
                "sources": sources,
                "web_search": web_search_result,
                "llm_knowledge": mem0_context if request.llm_knowledge and mem0_context else None,
                "results": result,
                "metadata": {
                    "description": "5-Stage Cascading Retrieval (Anchor -> Entity -> Expand -> Vector -> Synthesis)",
                    "stages": [
                        "Note Discovery",
                        "Entity Extraction",
                        "Semantic Expansion",
                        "Vector Search",
                    ],
                    "diagnostics": diagnostics,
                    "evidence": {
                        "candidate_source_count": candidate_source_count,
                        "selected_source_count": len(sources),
                    },
                    "web_search_enabled": bool(request.web_search),
                    "warnings": warnings,
                },
            }
        except HTTPException:
            raise
        except Exception as e:
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=500, detail=f"Cascading retrieval error: {str(e)}"
            )

    async with httpx.AsyncClient() as client:
        # ===== SINGLE-SOURCE MODES =====

        # MemPalace search — calls the host sidecar (mempalace_server.py on port 7788)
        if mode == "mempalace":
            try:
                import urllib.parse as _urlparse
                sidecar_url = (
                    "http://host.docker.internal:7788/search?"
                    + _urlparse.urlencode({"q": request.query, "results": max(1, request.max_results)})
                )
                sidecar_resp = await client.get(sidecar_url, timeout=70.0)
                if sidecar_resp.status_code != 200:
                    raise HTTPException(status_code=502, detail=f"MemPalace sidecar error: {sidecar_resp.text}")
                sources = sidecar_resp.json().get("sources", [])

                synthesized_answer = ""
                if sources:
                    try:
                        compressor_result = await _synthesize_cascading_answer(
                            query=request.query,
                            sources=sources,
                            llm_provider=request.llm_provider,
                            model=request.model,
                            brief_concept_index=False,
                        )
                        if isinstance(compressor_result, dict):
                            synthesized_answer = compressor_result.get("answer", "")
                        else:
                            synthesized_answer = str(compressor_result)
                    except Exception:
                        pass

                if not synthesized_answer or _is_generic_cascading_fallback_answer(synthesized_answer):
                    synthesized_answer = _build_extractive_vector_fallback_answer(request.query, sources)

                return {
                    "query": request.query,
                    "mode": "mempalace",
                    "answer": synthesized_answer,
                    "sources": sources,
                    "metadata": {
                        "source": "MemPalace",
                        "description": "Memory palace indexed search across drawers.",
                    },
                }
            except HTTPException:
                raise
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=503, detail=f"MemPalace error: {str(e)}")

        if mode == "vault_review":
            try:
                return await _vault_review_query(
                    request,
                    retrieval_query,
                    effective_relevance_threshold,
                    client,
                    requested_mode=requested_mode,
                    auto_routed=auto_routed_to_vault_review,
                )
            except HTTPException:
                raise
            except Exception as e:
                import traceback

                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail=f"Vault review error: {str(e)}",
                )

        # Pure vector search
        if mode == "vector":
            try:
                facet_groups = _extract_cascading_query_facets(request.query)
                facet_count = len(facet_groups)
                multi_facet_query = facet_count >= 2
                vector_limit_cap = 5
                if multi_facet_query:
                    vector_limit_cap = min(12, max(6, facet_count * 3))
                vector_limit = min(request.max_results, vector_limit_cap)
                summary_like = bool(re.search(r"\b(summary|summarize)\b", request.query.lower()))
                web_search_result = None
                
                payload = {
                    "query": retrieval_query,
                    "n_results": vector_limit * (4 if multi_facet_query else 3),
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
                
                # 2. Extract and filter sources (query-to-title matching logic)
                sources = []
                query_lower = request.query.lower()
                docs = result.get("documents", [[]])[0]
                metas = result.get("metadatas", [[]])[0]
                dists = result.get("distances", [[]])[0]
                
                for doc, meta, dist in zip(docs, metas, dists):
                    relevance = _distance_to_relevance_impl(dist, default=50.0)
                    doc_text = doc if isinstance(doc, str) else ""
                    filename = meta.get("filename", "unknown")
                    canonical_id = meta.get("canonical_id", "")
                    
                    # Boost exact/partial title matches
                    if filename.lower().endswith(".md"):
                        base_name = filename[:-3].lower()
                        if base_name in query_lower or query_lower in base_name or canonical_id in query_lower:
                            relevance = min(100.0, relevance + 25.0) # Significant boost for file match
                    elif "mind" in filename.lower() or "consciousness" in filename.lower():
                        # Demote generic semantic bleed if query looks like a specific book
                        relevance = max(0.0, relevance - 15.0)

                    snippet = (doc_text[:300] + "...") if len(doc_text) > 300 else doc_text
                    sources.append({
                        "filename": filename,
                        "filepath": meta.get("filepath", "unknown"),
                        "relevance": relevance,
                        "snippet": snippet,
                    })

                # Sort by new relevance and enforce final limit
                sources = sorted(sources, key=lambda s: s.get("relevance", 0), reverse=True)
                sources = _apply_relevance_filter(sources, effective_relevance_threshold)[:vector_limit]
                if (summary_like or multi_facet_query) and sources:
                    selected_sources = _select_cascading_evidence_set(
                        request.query,
                        sources,
                        max_results=min(2, vector_limit) if summary_like else vector_limit,
                    )
                    if selected_sources:
                        sources = selected_sources

                if request.web_search:
                    web_search_result = await _perform_tavily_web_search(
                        client,
                        retrieval_query or request.query,
                    )

                # 3. Micro-compressor logic
                micro_compressor_prompt = (
                    "Create 3-5 bullet points that capture the key ideas in the provided evidence; "
                    "do not add information not present in that evidence."
                )
                if not effective_brief_concept_index:
                    micro_compressor_prompt = (
                        "Answer the query using only the provided evidence. "
                        "Provide a fuller grounded response in complete sentences with concrete details from the evidence. "
                        "Be concise, but do not reduce the answer to a terse concept index or minimal bullets. "
                        "Do not add information not present in the evidence."
                    )
                if summary_like and effective_brief_concept_index:
                    micro_compressor_prompt = (
                        "Create 3-6 bullet points that faithfully summarize only the named note or book from the provided vault evidence. "
                        "Stay grounded in the retrieved vault evidence. "
                        "Do not generalize beyond that evidence. "
                        "If the snippets only cover one theme, summarize only that theme."
                    )
                synthesized_answer = ""
                synthesis_fallback_reason = ""
                synthesis_sources = sources
                response_sources = sources
                supplemental_context = _format_web_search_context_for_synthesis(web_search_result)
                if sources:
                    expand_named_sources = summary_like or _should_expand_named_sources_for_synthesis(
                        request.query,
                        sources,
                    )
                    synthesis_sources = _prepare_vector_sources_for_synthesis(
                        request.query,
                        sources,
                        expand_named_sources=expand_named_sources,
                    )
                    if expand_named_sources:
                        response_sources = _summary_display_sources(synthesis_sources)
                
                if sources:
                    try:
                        # Use cascade synthesizer as the micro compressor since it handles LLM dispatching
                        compressor_result = await _synthesize_cascading_answer_impl(
                            query=request.query,
                            sources=synthesis_sources,
                            llm_provider=request.llm_provider,
                            model=request.model,
                            system_prompt=micro_compressor_prompt,
                            brief_concept_index=effective_brief_concept_index,
                            supplemental_context=supplemental_context,
                        )
                        if isinstance(compressor_result, dict):
                            synthesized_answer = compressor_result.get("answer", "")
                            synthesis_fallback_reason = str(
                                compressor_result.get("fallback_reason", "") or ""
                            ).strip().lower()
                        else:
                            synthesized_answer = str(compressor_result)
                    except Exception as e:
                        print(f"Micro-compressor failed: {e}")
                        synthesized_answer = "" # Fallback to empty if LLM fails

                if (
                    not synthesized_answer
                    or _is_generic_cascading_fallback_answer(synthesized_answer)
                    or _is_insufficient_answer(synthesized_answer)
                    or synthesis_fallback_reason in {
                        "timeout",
                        "unknown_provider",
                        "provider_exception",
                        "empty_answer",
                        "weak_answer",
                    }
                ):
                    synthesized_answer = _build_extractive_vector_fallback_answer(
                        request.query,
                        synthesis_sources,
                    )

                return {
                    "query": request.query,
                    "mode": "vector",
                    "answer": synthesized_answer, # Return the structured output instead of raw UI display
                    "sources": response_sources,
                    "web_search": web_search_result,
                    "results": result,
                    "metadata": {
                        "source": "ChromaDB Vectors",
                        "description": "Pure vector similarity search with micro-compression.",
                        "web_search_enabled": bool(request.web_search),
                    },
                }
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise HTTPException(
                    status_code=503, detail=f"Vector service error: {str(e)}"
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
        requested_provider = data.get("provider")
        provider = _canonical_cascading_provider_name(requested_provider or _deep_research_auto_provider() or "")
        requested_model = str(data.get("model") or "").strip()
        model = requested_model or _deep_research_default_model(provider)
        max_sources_raw = data.get("max_sources")
        try:
            max_sources = int(max_sources_raw) if max_sources_raw is not None else 12
        except (TypeError, ValueError):
            max_sources = 12
        max_sources = max(1, min(100, max_sources))
        query_preview = str(query or "").strip().replace("\n", " ")[:120]
        print(
            f"Deep research request: provider={provider} model={model or '<default>'} "
            f"max_sources={max_sources} query='{query_preview}'"
        )
        supported_providers = {
            "claude",
            "gemini",
            "openrouter",
            "chatgpt",
            "ollama",
            "lmstudio",
            "mlx",
            "perplexity",
        }

        if not query:
            await websocket.send_json({"type": "error", "content": "No query provided"})
            return

        # Normalize provider for Deep Thinking
        if provider not in supported_providers:
            fallback_provider = _deep_research_auto_provider()
            if not fallback_provider:
                await websocket.send_json(
                    {
                        "type": "error",
                        "content": "Deep Thinking supports LM Studio, Perplexity, Claude, Gemini, OpenRouter, ChatGPT, or Ollama. No compatible configuration found.",
                    }
                )
                await websocket.close()
                return
            await websocket.send_json(
                {
                    "type": "log",
                    "message": f"Deep Thinking does not support '{provider or requested_provider}'. Using '{fallback_provider}'.",
                }
            )
            provider = fallback_provider
            model = _deep_research_default_model(provider)

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
            api_key = _get_env_value("GEMINI_API_KEY")
            if not api_key:
                await websocket.send_json(
                    {"type": "error", "content": "GEMINI_API_KEY not configured"}
                )
                await websocket.close()
                return
        elif provider == "openrouter":
            api_key = _get_env_value("OPENROUTER_API_KEY")
            if not api_key:
                await websocket.send_json(
                    {"type": "error", "content": "OPENROUTER_API_KEY not configured"}
                )
                await websocket.close()
                return
        elif provider == "chatgpt":
            api_key = _get_env_value("OPENAI_API_KEY")
            if not api_key:
                await websocket.send_json(
                    {"type": "error", "content": "OPENAI_API_KEY not configured"}
                )
                await websocket.close()
                return
        elif provider == "perplexity":
            api_key = _get_env_value("PERPLEXITY_API_KEY")
            if not api_key:
                await websocket.send_json(
                    {"type": "error", "content": "PERPLEXITY_API_KEY not configured"}
                )
                await websocket.close()
                return
        elif provider in {"lmstudio", "mlx"}:
            api_key = (
                _get_env_value("QUERY_LMSTUDIO_API_KEY")
                or _get_env_value("LMSTUDIO_API_KEY", "lmstudio")
                or _get_env_value("QUERY_MLX_API_KEY")
                or _get_env_value("MLX_API_KEY", "mlx")
            )
        elif provider == "ollama":
            api_key = "ollama"  # No key needed, but passing string to avoid validation errors downstream

        # Initialize Agent with Universal Client
        # Note: We must use the INTERNAL Docker URLs here
        DeepThinkingRAG = _load_deep_thinking_rag()
        deep_thinking_graph_transport = (
            _get_env_value("DEEP_THINKING_GRAPH_TRANSPORT", "").strip().lower()
        )
        graph_service_url = (
            "internal://graph"
            if deep_thinking_graph_transport == "internal"
            else GRAPH_SERVICE_URL
        )

        rag = DeepThinkingRAG(
            provider=provider,
            api_key=api_key,
            model=model,
            vector_service_url=EMBEDDING_SERVICE_URL,
            graph_service_url=graph_service_url,
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
            query_signature = inspect.signature(rag.query)
            query_kwargs = {"status_callback": sync_callback}
            if "max_sources" in query_signature.parameters:
                query_kwargs["max_sources"] = max_sources

            try:
                return rag.query(query, **query_kwargs)
            except TypeError as err:
                if "unexpected keyword argument 'max_sources'" not in str(err):
                    raise
                return rag.query(query, status_callback=sync_callback)

        await websocket.send_json({"type": "status", "content": "Agent started"})

        # Execute in thread
        result = await asyncio.get_running_loop().run_in_executor(executor, run_agent)

        # Safety net: some deep-thinking paths may return transport errors in the
        # synthesized answer instead of raising. Convert these into MLX recovery payloads.
        result_answer = ""
        if isinstance(result, dict):
            raw_answer = result.get("answer")
            if isinstance(raw_answer, str):
                result_answer = raw_answer
        if provider == "mlx" and _looks_like_mlx_transport_failure_text(result_answer):
            await websocket.send_json(
                {
                    "type": "log",
                    "message": "Detected MLX transport failure in synthesized result; starting recovery.",
                    "details": {"provider": provider},
                }
            )
            await websocket.send_json(_mlx_recovery_error_payload(Exception(result_answer)))
            await websocket.close(code=1011)
            return

        # Send final result
        source_counts = {"vault": 0, "web": 0, "unknown": 0}
        for src in (result.get("sources") or []):
            if not isinstance(src, dict):
                source_counts["unknown"] += 1
                continue
            category = str(src.get("source_category") or "").strip().lower()
            if category in {"vault", "web"}:
                source_counts[category] += 1
            else:
                source_counts["unknown"] += 1
        print(
            f"Deep research result: provider={provider} max_sources={max_sources} "
            f"sources={source_counts} warnings={len(result.get('warnings') or [])}"
        )
        await websocket.send_json({"type": "result", "data": result})

        await websocket.close()

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {e}")
        try:
            raw_error = str(e or "")
            if _is_mlx_runtime_failure(provider, e, model=model) or (provider == "mlx" and _looks_like_mlx_transport_failure_text(raw_error)):
                await websocket.send_json(
                    {
                        "type": "log",
                        "message": "MLX local model became unavailable; starting recovery.",
                        "details": {"provider": "mlx"},
                    }
                )
                await websocket.send_json(_mlx_recovery_error_payload(e))
            else:
                await websocket.send_json({"type": "error", "content": str(e)})
            await websocket.close(code=1011)
        except:
            pass


if __name__ == "__main__":
    uvicorn.run("api_gateway:app", host="0.0.0.0", port=3000, reload=True)
