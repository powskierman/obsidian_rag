import asyncio
import json
import math
import os
import re
import sys
from typing import Any, Dict, List, Mapping, Optional


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _ensure_project_root_on_path() -> None:
    root = _project_root()
    if root not in sys.path:
        sys.path.append(root)


try:
    from deep_thinking.source_utils import canonical_source_identity, normalize_source_record
    from deep_thinking.synthesizer import FinalAnswerGenerator
    from deep_thinking.utils import universal_client
except ImportError:
    _ensure_project_root_on_path()
    from deep_thinking.source_utils import canonical_source_identity, normalize_source_record
    from deep_thinking.synthesizer import FinalAnswerGenerator
    from deep_thinking.utils import universal_client


def _get_env_value(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if not isinstance(value, str):
        return default
    return value.strip()


def _extract_query_terms(query: str) -> List[str]:
    if not isinstance(query, str):
        return []
    entities = []
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
        "by", "from", "of", "about", "as", "is", "are", "was", "were", "be", "been",
        "that", "this", "these", "those", "it", "they", "them", "what", "which", "who",
        "when", "where", "why", "how", "all", "any", "both", "each", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
        "so", "than", "too", "very", "can", "will", "just", "should", "now",
    }
    seen = set()
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", query):
        lowered = token.lower()
        if lowered in stopwords or lowered.isdigit() or lowered in seen:
            continue
        seen.add(lowered)
        entities.append(token)
    return entities


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


def distance_to_relevance(distance: Any, default: float = 50.0) -> float:
    try:
        return max(0.0, min(100.0, 100.0 / (1.0 + math.exp(float(distance) / 2.0))))
    except (TypeError, ValueError, OverflowError):
        return default


def relevance_threshold_from_distance_threshold(distance_threshold: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(100.0, distance_to_relevance(float(distance_threshold), default=default)))
    except (TypeError, ValueError):
        return default


def normalize_cascading_source(
    source: Mapping[str, Any],
    *,
    source_type: str,
    default_relevance: float = 50.0,
) -> Dict[str, Any]:
    normalized = normalize_source_record(source, default_category="vault")
    try:
        relevance = float(normalized.get("relevance", default_relevance))
    except (TypeError, ValueError):
        relevance = default_relevance
    snippet = str(normalized.get("snippet") or normalized.get("content") or "").strip()
    normalized["relevance"] = max(0.0, min(100.0, relevance))
    normalized["snippet"] = snippet[:400] + ("..." if len(snippet) > 400 else "")
    normalized["source_type"] = normalized.get("source_type") or source_type
    normalized["_source_identity"] = canonical_source_identity(normalized, default_category="vault")
    return normalized


def _normalize_summary_focus_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = os.path.splitext(os.path.basename(text.replace("\\", "/")))[0]
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def is_summary_style_query(query: str) -> bool:
    lowered = str(query or "").strip().lower()
    if not lowered:
        return False
    return (
        "summary of " in lowered
        or lowered.startswith("summarize ")
        or "point form summary" in lowered
        or "bullet summary" in lowered
    )


def select_cascading_evidence_set(
    query: str,
    sources: List[Dict[str, Any]],
    *,
    max_results: int,
) -> List[Dict[str, Any]]:
    candidate_sources = [
        normalize_cascading_source(
            source,
            source_type=str(source.get("source_type") or "direct-excerpt"),
            default_relevance=float(source.get("relevance", 50.0) or 50.0),
        )
        for source in (sources or [])
        if isinstance(source, Mapping)
    ]
    if not candidate_sources:
        return []

    if is_summary_style_query(query):
        normalized_query = _normalize_summary_focus_text(query)
        exact_matches = [
            source
            for source in candidate_sources
            if _normalize_summary_focus_text(source.get("filename") or source.get("filepath")) in normalized_query
        ]
        if exact_matches:
            exact_matches.sort(key=lambda item: float(item.get("relevance", 0.0)), reverse=True)
            return exact_matches[:1]

    try:
        from deep_thinking.supervisor import RetrievalSupervisor
    except ImportError:
        _ensure_project_root_on_path()
        try:
            from deep_thinking.supervisor import RetrievalSupervisor
        except ImportError:
            return candidate_sources[:max(1, min(max_results, len(candidate_sources)))]

    docs: List[Dict[str, Any]] = []
    for source in candidate_sources:
        doc = dict(source)
        doc["content"] = str(source.get("snippet") or source.get("content") or "")
        doc["source"] = source.get("filepath") or source.get("url") or source.get("filename") or ""
        try:
            doc["score"] = float(source.get("relevance", 0.0) or 0.0) / 100.0
        except (TypeError, ValueError):
            doc["score"] = 0.0
        docs.append(doc)

    selected = RetrievalSupervisor.select_minimal_evidence_set(
        query,
        docs,
        max_docs=max(1, max_results),
    )
    if not selected:
        return candidate_sources[:max(1, min(max_results, len(candidate_sources)))]

    return [
        normalize_cascading_source(
            source,
            source_type=str(source.get("source_type") or "direct-excerpt"),
            default_relevance=float(source.get("relevance", 50.0) or 50.0),
        )
        for source in selected
        if isinstance(source, Mapping)
    ]


def canonical_cascading_provider_name(provider: str) -> str:
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
        "mlx": "mlx",
        "perplexity": "perplexity",
    }
    return aliases.get(normalized, normalized)


def default_cascading_model(provider: str) -> Optional[str]:
    provider = canonical_cascading_provider_name(provider)
    defaults = {
        "claude": _get_env_value("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"),
        "gemini": _get_env_value("GEMINI_MODEL", "gemini-3-flash-preview"),
        "chatgpt": _get_env_value("OPENAI_MODEL", "gpt-4o-mini"),
        "openrouter": _get_env_value("OPENROUTER_MODEL", "openrouter/auto"),
        "ollama": _get_env_value("OLLAMA_MODEL", _get_env_value("LLM_MODEL", "qwen2.5:7b-instruct")),
        "mlx": _get_env_value("MLX_MODEL", _get_env_value("LLM_MODEL_PATH", "LiquidAI/LFM2-24B-A2B")),
        "perplexity": _get_env_value("PERPLEXITY_MODEL", "llama-3.1-sonar-large-128k-online"),
    }
    return defaults.get(provider)


def cascading_provider_api_key(provider: str) -> Optional[str]:
    provider = canonical_cascading_provider_name(provider)
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
    if provider == "mlx":
        return _get_env_value("QUERY_MLX_API_KEY") or _get_env_value("MLX_API_KEY", "mlx") or "mlx"
    if provider == "perplexity":
        return _get_env_value("PERPLEXITY_API_KEY") or None
    return None


def is_generic_cascading_fallback_answer(text: Any) -> bool:
    if not isinstance(text, str):
        return True
    cleaned = text.strip().lower()
    if not cleaned:
        return True
    return (
        ("matching snippets in your vault" in cleaned)
        or ("llm synthesis skipped" in cleaned)
        or cleaned == "no results found"
    )


def build_cascading_degraded_answer(
    anchor_answer: str,
    sources: List[Dict[str, Any]],
    diagnostics: Dict[str, Any],
    reason: str,
    is_insufficient_answer_fn,
) -> str:
    stage_failures = len((diagnostics or {}).get("failures", {}) or {})
    if anchor_answer and not is_insufficient_answer_fn(anchor_answer):
        if stage_failures:
            return f"{anchor_answer}\n\nNote: some retrieval stages failed, so this answer is based on partial vault evidence."
        return anchor_answer
    if sources:
        if stage_failures:
            return "Partial answer based on available vault evidence. Some retrieval stages failed; review the attached sources."
        if reason == "empty_answer":
            return "I found relevant vault evidence, but the synthesis step returned an empty answer. Review the attached sources."
        return "I found relevant vault evidence. Review the attached sources for the most reliable details."
    return "No results found."


def _salvage_structured_response(text: str) -> Dict[str, Any]:
    citations: List[str] = []
    answer_text = ""
    answer_match = re.search(r'"answer"\s*:\s*"(?P<answer>(?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if answer_match:
        try:
            answer_text = json.loads(f"\"{answer_match.group('answer')}\"")
        except json.JSONDecodeError:
            answer_text = answer_match.group("answer")
    citations_match = re.search(r'"citations"\s*:\s*\[(?P<body>.*?)\]', text, re.DOTALL)
    if citations_match:
        citations = re.findall(r'"((?:[^"\\]|\\.)*)"', citations_match.group("body"))
        normalized: List[str] = []
        for item in citations:
            try:
                normalized.append(json.loads(f"\"{item}\""))
            except json.JSONDecodeError:
                normalized.append(item)
        citations = normalized
    if not answer_text and text.strip():
        answer_text = text.strip()
    return {"answer": answer_text, "citations": citations}


async def synthesize_cascading_answer(
    query: str,
    sources: List[Dict[str, Any]],
    llm_provider: str,
    model: str,
    system_prompt: Optional[str],
) -> Dict[str, Any]:
    def fallback_payload(answer_text: str, active_sources: List[Dict[str, Any]], reason: str = "fallback") -> Dict[str, Any]:
        citations = []
        seen = set()
        for source in active_sources[: min(len(active_sources), 8)]:
            if not isinstance(source, Mapping):
                continue
            filepath = str(source.get("filepath") or "").strip()
            url = str(source.get("url") or "").strip()
            if filepath:
                citation = f"[[{filepath}]]"
            elif url:
                citation = url
            else:
                filename = str(source.get("filename") or "").strip()
                citation = f"[[{filename}]]" if filename else ""
            if citation and citation not in seen:
                seen.add(citation)
                citations.append(citation)
        query_entities = _extract_query_terms(query)
        normalized_citations = FinalAnswerGenerator._normalize_citations(
            citations,
            active_sources,
            query_entities,
        )
        used_documents = FinalAnswerGenerator._resolve_used_documents(normalized_citations, active_sources)
        return {
            "answer": answer_text,
            "citations": normalized_citations,
            "used_documents": used_documents or active_sources,
            "fallback_reason": reason,
        }

    def parse_structured_response(text: str, active_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        parsed = _extract_json_object(text)
        if not parsed:
            parsed = _salvage_structured_response(text)
        answer_text = str(parsed.get("answer") or "").strip()
        citations_raw = parsed.get("citations")
        citations = citations_raw if isinstance(citations_raw, list) else []
        query_entities = _extract_query_terms(query)
        normalized_citations = FinalAnswerGenerator._normalize_citations(
            citations,
            active_sources,
            query_entities,
        )
        used_documents = FinalAnswerGenerator._resolve_used_documents(normalized_citations, active_sources)
        if answer_text:
            return {
                "answer": answer_text,
                "citations": normalized_citations,
                "used_documents": used_documents or active_sources,
            }
        raw_text = str(text or "").strip()
        if raw_text:
            return fallback_payload(raw_text, active_sources, reason="empty_answer")
        return fallback_payload(
            f"Found {len(active_sources)} matching snippets in your vault.",
            active_sources,
            reason="empty_answer",
        )

    if not sources:
        return {"answer": "No results found", "citations": [], "used_documents": [], "fallback_reason": "no_sources"}

    context_text = "\n\n".join([
        f"Snippet {i+1} from {s.get('filename', 'Unknown')}:\n{s.get('snippet', '')}"
        for i, s in enumerate(sources[:15])
    ])

    sys_prompt = system_prompt or (
        "You are a helpful AI assistant. Answer the user's query using ONLY the provided vault context. "
        "Return JSON only with keys: answer, citations. "
        "The answer must be a brief executive concept index or high-level overview. "
        "Do NOT provide didactic, step-by-step explanations or walk through processes unless strictly necessary. "
        "Instead, rapidly name and list the core concepts, frameworks, or relationships present in the context. "
        "Keep it tight and concise, under 200 words if possible. "
        "Citations must be an array of vault citations using exact paths like [[Folder/Note.md]]. "
        "Do not invent citations. If the context does not contain the answer, say so."
    )
    prompt = (
        f"Context:\n{context_text}\n\n"
        f"Query: {query}\n\n"
        "Return JSON only in the form "
        '{"answer": "concise grounded answer", "citations": ["[[Exact/Path.md]]"]}.'
    )

    resolved_provider = canonical_cascading_provider_name(llm_provider)
    if resolved_provider not in {"claude", "gemini", "openrouter", "chatgpt", "ollama", "mlx", "perplexity"}:
        return fallback_payload(
            f"Found {len(sources)} matching snippets in your vault. (LLM synthesis skipped: unknown provider '{llm_provider}')",
            sources,
            reason="unknown_provider",
        )

    try:
        attempted_signatures = set()
        attempt_sources_list = [sources]
        if len(sources) > 1:
            retry_limit = 1 if is_summary_style_query(query) else min(2, len(sources) - 1)
            reduced_sources = select_cascading_evidence_set(
                query,
                sources,
                max_results=max(1, retry_limit),
            )
            reduced_signature = tuple(source.get("_source_identity") for source in reduced_sources if isinstance(source, Mapping))
            full_signature = tuple(source.get("_source_identity") for source in sources if isinstance(source, Mapping))
            if reduced_sources and reduced_signature and reduced_signature != full_signature:
                attempt_sources_list.append(reduced_sources)

        for attempt_index, active_sources in enumerate(attempt_sources_list):
            signature = tuple(source.get("_source_identity") for source in active_sources if isinstance(source, Mapping))
            if signature in attempted_signatures:
                continue
            attempted_signatures.add(signature)
            active_context = "\n\n".join([
                f"Snippet {i+1} from {s.get('filename', 'Unknown')}:\n{s.get('snippet', '')}"
                for i, s in enumerate(active_sources[:15])
            ])
            active_prompt = (
                f"Context:\n{active_context}\n\n"
                f"Query: {query}\n\n"
                "Return JSON only in the form "
                '{"answer": "concise grounded answer", "citations": ["[[Exact/Path.md]]"]}.'
            )
            response = await asyncio.to_thread(
                universal_client.UniversalClient(
                    provider=resolved_provider,
                    api_key=cascading_provider_api_key(resolved_provider),
                ).messages.create,
                model=model or default_cascading_model(resolved_provider),
                messages=[{"role": "user", "content": active_prompt}],
                max_tokens=1024,
                temperature=0.3,
                system=sys_prompt,
                response_format={"type": "json_object"},
            )
            parsed = parse_structured_response(universal_client.extract_response_text(response), active_sources)
            answer_text = str(parsed.get("answer") or "").strip()
            if answer_text and not is_generic_cascading_fallback_answer(answer_text):
                if attempt_index:
                    parsed["fallback_reason"] = "retry_reduced_evidence"
                return parsed
            if attempt_index == len(attempt_sources_list) - 1:
                parsed["fallback_reason"] = parsed.get("fallback_reason") or "weak_answer"
                return parsed
    except Exception as exc:
        raise exc

    return fallback_payload(
        f"Found {len(sources)} matching snippets in your vault.",
        sources,
        reason="provider_exception",
    )
