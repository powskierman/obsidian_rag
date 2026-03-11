import ast
import asyncio
import json
import logging
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Mapping, Optional


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _ensure_project_root_on_path() -> None:
    root = _project_root()
    if root not in sys.path:
        sys.path.append(root)


def _vault_root() -> Path:
    return Path(os.getenv("OBSIDIAN_VAULT_PATH", "/app/vault")).expanduser().resolve()


try:
    from deep_thinking.source_utils import canonical_source_identity, normalize_source_record
    from deep_thinking.synthesizer import FinalAnswerGenerator
    from deep_thinking.utils import universal_client
except ImportError:
    _ensure_project_root_on_path()
    from deep_thinking.source_utils import canonical_source_identity, normalize_source_record
    from deep_thinking.synthesizer import FinalAnswerGenerator
    from deep_thinking.utils import universal_client


logger = logging.getLogger(__name__)


def _get_env_value(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if not isinstance(value, str):
        return default
    return value.strip()


def _get_env_int(name: str, default: int, *, minimum: int = 0) -> int:
    try:
        return max(minimum, int(_get_env_value(name, str(default))))
    except (TypeError, ValueError):
        return max(minimum, default)


def _get_env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(_get_env_value(name, str(default))))
    except (TypeError, ValueError):
        return max(minimum, default)


def _query_preview(text: str, limit: int = 120) -> str:
    compact = re.sub(r"\s+", " ", str(text or "").strip())
    if len(compact) <= limit:
        return compact
    return compact[: max(limit - 3, 0)].rstrip() + "..."


def _provider_synthesis_timeout_seconds(provider: str) -> float:
    resolved_provider = canonical_cascading_provider_name(provider)
    base_timeout_seconds = _get_env_float(
        "CASCADING_SYNTHESIS_TIMEOUT_SECONDS",
        25.0,
        minimum=1.0,
    )
    if resolved_provider == "lmstudio":
        lmstudio_timeout_seconds = _get_env_float(
            "CASCADING_SYNTHESIS_TIMEOUT_SECONDS_LMSTUDIO",
            _get_env_float("CASCADING_SYNTHESIS_TIMEOUT_SECONDS_MLX", 180.0, minimum=1.0),
            minimum=1.0,
        )
        return max(base_timeout_seconds, lmstudio_timeout_seconds)
    if resolved_provider == "ollama":
        ollama_timeout_seconds = _get_env_float(
            "CASCADING_SYNTHESIS_TIMEOUT_SECONDS_OLLAMA",
            _get_env_float("CASCADING_SYNTHESIS_TIMEOUT_SECONDS_LOCAL", 90.0, minimum=1.0),
            minimum=1.0,
        )
        return max(base_timeout_seconds, ollama_timeout_seconds)
    return base_timeout_seconds


def _provider_prompt_source_caps(provider: str) -> tuple[Optional[int], Optional[int], int]:
    resolved_provider = canonical_cascading_provider_name(provider)
    if resolved_provider == "lmstudio":
        return (
            _get_env_int("CASCADING_SYNTHESIS_MAX_SOURCES_LMSTUDIO", 4, minimum=1),
            _get_env_int("CASCADING_SYNTHESIS_MAX_SNIPPET_CHARS_LMSTUDIO", 700, minimum=40),
            _get_env_int("CASCADING_SYNTHESIS_MAX_CONTEXT_SOURCES_LMSTUDIO", 4, minimum=1),
        )
    if resolved_provider == "ollama":
        max_sources = _get_env_int("CASCADING_SYNTHESIS_MAX_SOURCES_OLLAMA", 4, minimum=1)
        return (
            max_sources,
            _get_env_int("CASCADING_SYNTHESIS_MAX_SNIPPET_CHARS_OLLAMA", 1400, minimum=40),
            _get_env_int("CASCADING_SYNTHESIS_MAX_CONTEXT_SOURCES_OLLAMA", max_sources, minimum=1),
        )
    return None, None, 15


def _provider_source_expansion_chars(provider: str) -> int:
    resolved_provider = canonical_cascading_provider_name(provider)
    default_expansion_chars = _get_env_int(
        "CASCADING_SYNTHESIS_SOURCE_EXPANSION_CHARS",
        8000,
        minimum=1000,
    )
    if resolved_provider == "ollama":
        return _get_env_int(
            "CASCADING_SYNTHESIS_SOURCE_EXPANSION_CHARS_OLLAMA",
            min(default_expansion_chars, 2500),
            minimum=1000,
        )
    return default_expansion_chars


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


def _decode_json_string_fragment(fragment: str) -> str:
    candidate = str(fragment or "")
    if not candidate:
        return ""
    try:
        return json.loads(f"\"{candidate}\"")
    except json.JSONDecodeError:
        return (
            candidate.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )


def _extract_partial_json_string_field(text: str, field_name: str) -> str:
    if not isinstance(text, str):
        return ""

    marker = f'"{field_name}"'
    field_pos = text.find(marker)
    if field_pos == -1:
        return ""

    colon_pos = text.find(":", field_pos + len(marker))
    if colon_pos == -1:
        return ""

    opening_quote = text.find('"', colon_pos + 1)
    if opening_quote == -1:
        return ""

    chars: List[str] = []
    escaped = False
    for ch in text[opening_quote + 1 :]:
        if escaped:
            chars.append(ch)
            escaped = False
            continue
        if ch == "\\":
            chars.append(ch)
            escaped = True
            continue
        if ch == '"':
            return _decode_json_string_fragment("".join(chars))
        chars.append(ch)

    fragment = "".join(chars).rstrip()
    fragment = re.sub(r'[\s,}\]]+\Z', "", fragment)
    return _decode_json_string_fragment(fragment)


def _normalize_answer_paragraphs(items: List[Any]) -> str:
    paragraphs: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _coerce_answer_text(answer_value: Any, query: str) -> str:
    if isinstance(answer_value, list):
        return _normalize_answer_paragraphs(answer_value)

    text = str(answer_value or "").strip()
    if not text:
        return ""

    if is_summary_style_query(query) and text.startswith("[") and text.endswith("]"):
        parsed_list: Any = None
        try:
            parsed_list = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed_list = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                parsed_list = None
        if isinstance(parsed_list, list):
            return _normalize_answer_paragraphs(parsed_list)

    return text


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


def _source_hydration_score(source: Mapping[str, Any]) -> tuple[int, int, int]:
    snippet = str(source.get("snippet") or "").strip()
    content = str(source.get("content") or "").strip()
    return (
        1 if source.get("is_full_content") else 0,
        0 if _looks_like_boilerplate_source_snippet(snippet or content) else 1,
        max(len(content), len(snippet)),
    )


def hydrate_cascading_sources(
    base_sources: List[Dict[str, Any]],
    hydrated_sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not base_sources:
        return [dict(source) for source in (hydrated_sources or []) if isinstance(source, Mapping)]
    if not hydrated_sources:
        return [dict(source) for source in base_sources if isinstance(source, Mapping)]

    best_by_identity: Dict[tuple[str, str], Dict[str, Any]] = {}
    for source in hydrated_sources:
        if not isinstance(source, Mapping):
            continue
        prepared = dict(source)
        source_identity = canonical_source_identity(prepared, default_category="vault")
        current = best_by_identity.get(source_identity)
        if current is None or _source_hydration_score(prepared) > _source_hydration_score(current):
            best_by_identity[source_identity] = prepared

    merged: List[Dict[str, Any]] = []
    for source in base_sources:
        if not isinstance(source, Mapping):
            continue
        prepared = dict(source)
        source_identity = canonical_source_identity(prepared, default_category="vault")
        hydrated = best_by_identity.get(source_identity)
        if hydrated:
            hydrated_snippet = str(hydrated.get("snippet") or "").strip()
            hydrated_content = str(hydrated.get("content") or "").strip()
            if hydrated_snippet:
                prepared["snippet"] = hydrated_snippet
            if hydrated_content:
                prepared["content"] = hydrated_content
            if hydrated.get("is_full_content"):
                prepared["is_full_content"] = True
        merged.append(prepared)
    return merged


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


def is_procedural_style_query(query: str) -> bool:
    lowered = str(query or "").strip().lower()
    if not lowered:
        return False
    procedural_markers = (
        "recipe",
        "how to ",
        "how do i ",
        "steps for ",
        "instructions for ",
        "ingredients for ",
        "procedure for ",
    )
    return any(marker in lowered for marker in procedural_markers)


def _relation_query_sides(query: str) -> tuple[set[str], set[str]]:
    lowered = str(query or "").strip().lower()
    if not lowered:
        return set(), set()

    relation_stopwords = {
        "how",
        "what",
        "does",
        "relate",
        "related",
        "between",
        "compare",
        "difference",
        "connected",
        "connection",
        "link",
        "linked",
        "my",
        "your",
        "our",
        "notes",
        "note",
        "docs",
        "doc",
        "documents",
        "files",
        "file",
    }

    patterns = (
        r"how do\s+(?P<left>.+?)\s+relate to\s+(?P<right>.+)",
        r"what is the relationship between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)",
        r"how are\s+(?P<left>.+?)\s+and\s+(?P<right>.+?)\s+related",
        r"how are\s+(?P<left>.+?)\s+connected to\s+(?P<right>.+)",
        r"how is\s+(?P<left>.+?)\s+connected to\s+(?P<right>.+)",
        r"what is the connection between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)",
        r"what is the link between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)",
        r"compare\s+(?P<left>.+?)\s+(?:with|and)\s+(?P<right>.+)",
        r"difference between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        left = {
            token for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", match.group("left"))
            if token not in relation_stopwords
        }
        right = {
            token for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", match.group("right"))
            if token not in relation_stopwords
        }
        if left and right:
            return left, right
    return set(), set()


def extract_query_facets(query: str) -> List[set[str]]:
    left, right = _relation_query_sides(query)
    facets: List[set[str]] = []
    if left:
        facets.append(set(left))
    if right:
        facets.append(set(right))
    return facets


def has_multi_facet_query(query: str) -> bool:
    return len(extract_query_facets(query)) >= 2


def is_relation_style_query(query: str) -> bool:
    return has_multi_facet_query(query)


def _relation_query_source_score(query: str, source: Dict[str, Any]) -> float:
    left_terms, right_terms = _relation_query_sides(query)
    if not left_terms or not right_terms:
        return 0.0

    haystack = " ".join(
        _normalize_summary_focus_text(value)
        for value in (
            source.get("filename"),
            source.get("filepath"),
            source.get("snippet"),
            source.get("content"),
            source.get("canonical_id"),
        )
    )
    if not haystack.strip():
        return 0.0

    left_hits = sum(1 for term in left_terms if term in haystack)
    right_hits = sum(1 for term in right_terms if term in haystack)
    if not left_hits and not right_hits:
        return 0.0
    both_bonus = 20.0 if left_hits and right_hits else 0.0
    return both_bonus + (left_hits * 8.0) + (right_hits * 8.0)


def _relation_query_side_hits(query: str, source: Dict[str, Any]) -> tuple[int, int]:
    facets = extract_query_facets(query)
    if len(facets) < 2:
        return 0, 0
    left_terms, right_terms = facets[0], facets[1]

    haystack = " ".join(
        _normalize_summary_focus_text(value)
        for value in (
            source.get("filename"),
            source.get("filepath"),
            source.get("snippet"),
            source.get("content"),
            source.get("canonical_id"),
        )
    )
    if not haystack.strip():
        return 0, 0

    left_hits = sum(1 for term in left_terms if term in haystack)
    right_hits = sum(1 for term in right_terms if term in haystack)
    return left_hits, right_hits


def source_facet_match_indexes(source: Dict[str, Any], query: str) -> set[int]:
    facets = extract_query_facets(query)
    if not facets:
        return set()
    haystack = " ".join(
        _normalize_summary_focus_text(value)
        for value in (
            source.get("filename"),
            source.get("filepath"),
            source.get("snippet"),
            source.get("content"),
            source.get("canonical_id"),
        )
    )
    if not haystack.strip():
        return set()
    return {
        idx
        for idx, facet in enumerate(facets)
        if facet and any(term in haystack for term in facet)
    }


def source_set_covers_query_facets(query: str, sources: List[Dict[str, Any]]) -> bool:
    facets = extract_query_facets(query)
    if len(facets) < 2:
        return True
    covered: set[int] = set()
    for source in sources or []:
        if not isinstance(source, Mapping):
            continue
        covered.update(source_facet_match_indexes(source, query))
        if len(covered) >= len(facets):
            return True
    return False


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

    if is_relation_style_query(query):
        ranked_relation_sources = sorted(
            candidate_sources,
            key=lambda source: (
                _relation_query_source_score(query, source),
                float(source.get("relevance", 0.0) or 0.0),
            ),
            reverse=True,
        )
        positive_relation_sources = [
            source for source in ranked_relation_sources
            if _relation_query_source_score(query, source) > 0
        ]
        if positive_relation_sources:
            limit = max(2, min(max_results, len(positive_relation_sources)))
            selected: List[Dict[str, Any]] = []
            covered_facets: set[int] = set()

            for source in positive_relation_sources:
                match_indexes = source_facet_match_indexes(source, query)
                if len(match_indexes) >= 2:
                    selected.append(source)
                    covered_facets.update(match_indexes)
                    break

            for source in positive_relation_sources:
                if len(selected) >= limit:
                    break
                if source in selected:
                    continue
                match_indexes = source_facet_match_indexes(source, query)
                new_coverage = match_indexes - covered_facets
                if new_coverage:
                    selected.append(source)
                    covered_facets.update(match_indexes)

            for source in positive_relation_sources:
                if len(selected) >= limit:
                    break
                if source in selected:
                    continue
                selected.append(source)

            return selected[:limit]

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
        "lmstudio": "lmstudio",
        "mlx": "lmstudio",
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
        "lmstudio": _get_env_value("LMSTUDIO_MODEL", _get_env_value("MLX_MODEL", _get_env_value("LLM_MODEL_PATH", "local-model"))),
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


def _prepare_synthesis_prompt_sources(
    provider: str,
    sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    prepared_sources = [
        dict(source)
        for source in sources
        if isinstance(source, Mapping)
    ]
    max_sources, max_snippet_chars, _ = _provider_prompt_source_caps(provider)
    if max_sources is not None:
        prepared_sources = prepared_sources[:max_sources]
    if max_snippet_chars is None:
        return prepared_sources

    limited_sources: List[Dict[str, Any]] = []
    for source in prepared_sources:
        snippet = str(source.get("snippet") or source.get("content") or "")
        if len(snippet) > max_snippet_chars:
            clipped = f"{snippet[:max_snippet_chars].rstrip()}..."
            source["snippet"] = clipped
            if source.get("content"):
                source["content"] = clipped
        limited_sources.append(source)
    return limited_sources


def _resolve_vault_source_path(source: Mapping[str, Any]) -> Optional[Path]:
    raw_path = str(source.get("filepath") or source.get("source") or "").strip()
    if not raw_path or raw_path.startswith(("http://", "https://")):
        return None

    raw_path = raw_path.replace("\\", "/").lstrip("/")
    vault_root = _vault_root()
    try:
        resolved = (vault_root / raw_path).resolve()
        resolved.relative_to(vault_root)
    except Exception:
        return None
    return resolved if resolved.is_file() else None


def _looks_like_boilerplate_source_snippet(text: str) -> bool:
    snippet = str(text or "").strip()
    if not snippet:
        return True
    lowered = snippet.lower()
    return (
        lowered.startswith("context:")
        or lowered.startswith("on explicit graph path.")
        or lowered.startswith("connected via explicit graph path")
        or (len(snippet) < 140 and "mentioned." in lowered)
    )


def _expand_sources_for_synthesis(
    query: str,
    sources: List[Dict[str, Any]],
    provider: str = "",
) -> List[Dict[str, Any]]:
    expansion_limit = _provider_source_expansion_chars(provider)

    query_terms = {
        token for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", str(query or "").lower())
        if token not in {"what", "when", "where", "which", "with", "from", "into", "about", "how"}
    }

    expanded_sources: List[Dict[str, Any]] = []
    for source in sources or []:
        prepared = dict(source)
        resolved = _resolve_vault_source_path(prepared)
        if not resolved or resolved.suffix.lower() not in {".md", ".txt"}:
            expanded_sources.append(prepared)
            continue

        source_label = " ".join(
            _normalize_summary_focus_text(value)
            for value in (
                prepared.get("filename"),
                prepared.get("filepath"),
                prepared.get("canonical_id"),
            )
        )
        should_expand = _looks_like_boilerplate_source_snippet(prepared.get("snippet") or prepared.get("content"))
        if not should_expand and query_terms:
            overlap = sum(1 for term in query_terms if term in source_label)
            should_expand = overlap > 0 and len(str(prepared.get("snippet") or "")) < 500
        if not should_expand:
            expanded_sources.append(prepared)
            continue

        try:
            with resolved.open("r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read(expansion_limit).strip()
        except OSError:
            expanded_sources.append(prepared)
            continue

        if content and len(content) > len(str(prepared.get("snippet") or "")):
            prepared["content"] = content
            prepared["snippet"] = content
            prepared["is_full_content"] = True
        expanded_sources.append(prepared)

    return expanded_sources


def _clean_extractive_fallback_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    text = re.sub(r"^---\s*.*?\s*---\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"(?:\[[^\]]+:\s[^\]]+\]\s*)+", "", text)
    text = re.sub(r"<mark[^>]*>", "", text, flags=re.IGNORECASE)
    text = text.replace("</mark>", "")
    text = text.replace("==", "")
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extractive_fallback_candidates(text: str) -> List[str]:
    cleaned = _clean_extractive_fallback_text(text)
    if not cleaned:
        return []

    numbered = re.split(r"\s(?=\d+\.\s)", cleaned)
    fragments: List[str] = []
    for chunk in numbered:
        fragments.extend(re.split(r"(?<=[.!?])\s+", chunk))

    candidates: List[str] = []
    for fragment in fragments:
        candidate = re.sub(r"^\d+\.\s*", "", fragment).strip(" -\n\t")
        if len(candidate) < 20:
            continue
        if len(candidate) > 320:
            continue
        lowered = candidate.lower()
        if _looks_like_boilerplate_source_snippet(candidate):
            continue
        if "depth=" in lowered or "seed_hits=" in lowered:
            continue
        if lowered.startswith(("source:", "date:", "canonical id:", "entity type:", "timeline date:", "tags:")):
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


_GROUNDED_DETAIL_PATTERN = re.compile(
    r"\b\d+(?:[./]\d+)?\s*(?:°\s*[fc]|degrees?\s*[fc]|cups?|tbsp|tsp|teaspoons?|tablespoons?|"
    r"g|gr|kg|ml|l|oz|lbs?|pounds?|minutes?|mins?|hours?|hrs?)\b",
    re.IGNORECASE,
)


def _answer_has_unsupported_grounded_details(
    answer_text: str,
    sources: List[Dict[str, Any]],
) -> bool:
    combined_source_text = " ".join(
        _clean_extractive_fallback_text(source.get("content") or source.get("snippet") or "")
        for source in (sources or [])
        if isinstance(source, Mapping)
    ).lower()
    if not combined_source_text:
        return False

    answer_details = {
        re.sub(r"\s+", " ", match.group(0).lower()).strip()
        for match in _GROUNDED_DETAIL_PATTERN.finditer(str(answer_text or ""))
    }
    if not answer_details:
        return False

    for detail in answer_details:
        normalized_detail = detail.replace("degrees ", "").replace("° ", "°")
        if detail not in combined_source_text and normalized_detail not in combined_source_text:
            return True
    return False


def _build_extractive_cascading_fallback_answer(
    query: str,
    sources: List[Dict[str, Any]],
) -> str:
    if not sources:
        return "No results found."

    ranked: List[tuple[float, str]] = []
    seen: set[str] = set()
    query_terms = {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", str(query or ""))
        if token
    }

    for source_index, source in enumerate(sources[:5]):
        snippet = str(source.get("content") or source.get("snippet") or "")
        relevance = float(source.get("relevance", 0.0) or 0.0)
        for candidate_index, candidate in enumerate(_extractive_fallback_candidates(snippet)[:6]):
            normalized = re.sub(r"[^a-z0-9]+", " ", candidate.lower()).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            term_hits = sum(1 for term in query_terms if term in normalized)
            measurement_bonus = 150 if _GROUNDED_DETAIL_PATTERN.search(candidate) else 0
            score = (term_hits * 1000) + measurement_bonus + (relevance * 10) - (source_index * 10) - candidate_index
            ranked.append((score, candidate.rstrip(". ") + "."))

    if not ranked:
        return "I found relevant vault evidence. Review the attached sources for the most reliable details."

    ranked.sort(key=lambda item: item[0], reverse=True)
    top_candidates = [candidate for _, candidate in ranked[:4]]
    return "\n".join(f"- {candidate}" for candidate in top_candidates)


def _looks_incomplete_answer(text: str) -> bool:
    answer_text = str(text or "").strip()
    if not answer_text:
        return True
    if answer_text.endswith((".", "!", "?", "]", ")", "\"")):
        return False
    word_count = len(answer_text.split())
    if word_count < 8:
        return False

    trailing_terms = {
        "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "is",
        "of", "on", "or", "that", "the", "to", "was", "were", "with",
    }
    last_token_match = re.search(r"([A-Za-z]+)\s*$", answer_text)
    last_token = last_token_match.group(1).lower() if last_token_match else ""
    if last_token in trailing_terms:
        return True
    if answer_text.endswith((",", ";", ":", "-", "(", "/", "—")):
        return True
    if answer_text.count("(") > answer_text.count(")"):
        return True
    if re.search(r"\b(however|but|therefore|thus|additionally|moreover|because|which means)\b", answer_text.lower()):
        return True
    if word_count >= 12:
        return True
    return False


def _salvage_structured_response(text: str) -> Dict[str, Any]:
    citations: List[str] = []
    answer_text = ""
    answer_match = re.search(r'"answer"\s*:\s*"(?P<answer>(?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if answer_match:
        try:
            answer_text = json.loads(f"\"{answer_match.group('answer')}\"")
        except json.JSONDecodeError:
            answer_text = answer_match.group("answer")
    elif '"answer"' in str(text):
        answer_text = _extract_partial_json_string_field(text, "answer")
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
    brief_concept_index: bool = True,
    supplemental_context: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_provider = canonical_cascading_provider_name(llm_provider)
    synthesis_timeout_seconds = _provider_synthesis_timeout_seconds(resolved_provider)
    max_prompt_sources, max_prompt_snippet_chars, max_context_sources = _provider_prompt_source_caps(
        resolved_provider
    )

    try:
        synthesis_temperature = max(
            0.0,
            min(1.0, float(_get_env_value("CASCADING_SYNTHESIS_TEMPERATURE", "0"))),
        )
    except (TypeError, ValueError):
        synthesis_temperature = 0.0

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
        answer_text = _coerce_answer_text(parsed.get("answer"), query)
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

    supplemental_context_text = str(supplemental_context or "").strip()
    has_web_supplemental_context = "Supplemental web evidence:" in supplemental_context_text
    resolved_model = model or default_cascading_model(resolved_provider) or ""
    overall_started_at = time.perf_counter()
    logger.info(
        "cascading_synthesis.start provider=%s model=%s sources=%d brief=%s timeout_s=%.1f max_prompt_sources=%s max_snippet_chars=%s query=%s",
        resolved_provider,
        resolved_model,
        len(sources),
        brief_concept_index,
        synthesis_timeout_seconds,
        max_prompt_sources if max_prompt_sources is not None else "unbounded",
        max_prompt_snippet_chars if max_prompt_snippet_chars is not None else "unbounded",
        _query_preview(query),
    )

    procedural_query = is_procedural_style_query(query)
    relation_query = is_relation_style_query(query)

    if system_prompt:
        sys_prompt = system_prompt
    elif procedural_query and not brief_concept_index:
        sys_prompt = (
            "You are a helpful AI assistant. Answer the user's query using ONLY the provided vault context. "
            "Return JSON only with keys: answer, citations. "
            "Provide a fuller grounded procedural answer, not a terse synopsis. "
            "Include the available ingredients, measurements, timings, temperatures, and ordered steps from the vault evidence. "
            "Prefer a usable step-by-step answer over a one-sentence summary when the context supports it. "
            "If a needed detail is not present in the context, say that it is not specified in the vault evidence. "
            "Citations must be an array of vault citations using exact paths like [[Folder/Note.md]]. "
            "Do not invent citations."
        )
    elif procedural_query:
        sys_prompt = (
            "You are a helpful AI assistant. Answer the user's query using ONLY the provided vault context. "
            "Return JSON only with keys: answer, citations. "
            "For recipe or how-to queries, provide a compact but usable procedural answer. "
            "Include concrete ingredients, measurements, timings, temperatures, and ordered steps when they appear in the context. "
            "Do not stop at a one-line overview if the sources contain a fuller procedure. "
            "If an important detail is missing from the context, say that it is not specified in the vault evidence. "
            "Citations must be an array of vault citations using exact paths like [[Folder/Note.md]]. "
            "Do not invent citations."
        )
    elif relation_query and not brief_concept_index:
        sys_prompt = (
            "You are a helpful AI assistant. Answer the user's query using ONLY the provided vault context. "
            "Return JSON only with keys: answer, citations. "
            "Provide a fuller grounded explanation of how the queried concepts relate to each other. "
            "State the connection explicitly, note any important differences or limits, and tie each point to the retrieved evidence. "
            "Do not drift into generic background definitions if the relation can be explained directly from the context. "
            "Citations must be an array of vault citations using exact paths like [[Folder/Note.md]]. "
            "Do not invent citations. If the context is insufficient, say so."
        )
    elif relation_query:
        sys_prompt = (
            "You are a helpful AI assistant. Answer the user's query using ONLY the provided vault context. "
            "Return JSON only with keys: answer, citations. "
            "Give a concise explanation of how the queried concepts relate, including the most important connection or contrast from the evidence. "
            "Avoid generic textbook framing when the relation can be stated directly. "
            "Citations must be an array of vault citations using exact paths like [[Folder/Note.md]]. "
            "Do not invent citations. If the context is insufficient, say so."
        )
    elif not brief_concept_index:
        sys_prompt = (
            "You are a helpful AI assistant. Answer the user's query using ONLY the provided vault context. "
            "Return JSON only with keys: answer, citations. "
            "Provide a fuller grounded answer, not a terse concept index. "
            "Explain the main points in complete sentences, and include concrete details from the retrieved evidence when relevant. "
            "Be concise, but do not compress the answer so aggressively that useful detail is lost. "
            "Citations must be an array of vault citations using exact paths like [[Folder/Note.md]]. "
            "Do not invent citations. If the context does not contain the answer, say so."
        )
    else:
        sys_prompt = (
            "You are a helpful AI assistant. Answer the user's query using ONLY the provided vault context. "
            "Return JSON only with keys: answer, citations. "
            "The answer must be a brief executive concept index or high-level overview. "
            "Do NOT provide didactic, step-by-step explanations or walk through processes unless strictly necessary. "
            "Instead, rapidly name and list the core concepts, frameworks, or relationships present in the context. "
            "Keep it tight and concise, under 200 words if possible. "
            "Citations must be an array of vault citations using exact paths like [[Folder/Note.md]]. "
            "Do not invent citations. If the context does not contain the answer, say so."
        )
    if has_web_supplemental_context:
        sys_prompt = (
            f"{sys_prompt} "
            "Supplemental web evidence may also be provided. "
            "Prioritize vault evidence. If the vault is insufficient but the supplemental web evidence is relevant, you may use it carefully to answer the question. "
            "When you do so, say clearly that the specific point comes from supplemental web evidence rather than the vault."
        )
    if resolved_provider not in {"claude", "gemini", "openrouter", "chatgpt", "ollama", "lmstudio", "perplexity"}:
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
            attempt_started_at = time.perf_counter()
            signature = tuple(source.get("_source_identity") for source in active_sources if isinstance(source, Mapping))
            if signature in attempted_signatures:
                continue
            attempted_signatures.add(signature)
            prompt_prep_started_at = time.perf_counter()
            prompt_sources = _prepare_synthesis_prompt_sources(
                resolved_provider,
                active_sources,
            )
            prompt_sources = _expand_sources_for_synthesis(
                query,
                prompt_sources,
                provider=resolved_provider,
            )
            prompt_sources = _prepare_synthesis_prompt_sources(
                resolved_provider,
                prompt_sources,
            )
            hydrated_active_sources = hydrate_cascading_sources(active_sources, prompt_sources)
            context_sources = prompt_sources[:max_context_sources]
            active_context = "\n\n".join([
                f"Snippet {i+1} from {s.get('filename', 'Unknown')}:\n{s.get('snippet', '')}"
                for i, s in enumerate(context_sources)
            ])
            active_sections = []
            if supplemental_context_text:
                active_sections.append(f"Supplemental context:\n{supplemental_context_text}")
            active_sections.append(f"Context:\n{active_context}")
            active_prompt = (
                f"{'\n\n'.join(active_sections)}\n\n"
                f"Query: {query}\n\n"
                "Return JSON only in the form "
                '{"answer": "concise grounded answer", "citations": ["[[Exact/Path.md]]"]}.'
            )
            prompt_prep_elapsed_ms = int((time.perf_counter() - prompt_prep_started_at) * 1000)
            logger.info(
                "cascading_synthesis.prompt_prepared provider=%s model=%s attempt=%d source_count=%d context_sources=%d context_chars=%d prep_ms=%d",
                resolved_provider,
                resolved_model,
                attempt_index + 1,
                len(prompt_sources),
                len(context_sources),
                len(active_context),
                prompt_prep_elapsed_ms,
            )
            llm_started_at = time.perf_counter()
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        universal_client.UniversalClient(
                            provider=resolved_provider,
                            api_key=cascading_provider_api_key(resolved_provider),
                        ).messages.create,
                        model=resolved_model,
                        messages=[{"role": "user", "content": active_prompt}],
                        max_tokens=1024,
                        temperature=synthesis_temperature,
                        system=sys_prompt,
                        response_format={"type": "json_object"},
                    ),
                    timeout=synthesis_timeout_seconds,
                )
            except asyncio.TimeoutError:
                llm_elapsed_ms = int((time.perf_counter() - llm_started_at) * 1000)
                total_elapsed_ms = int((time.perf_counter() - overall_started_at) * 1000)
                logger.warning(
                    "cascading_synthesis.timeout provider=%s model=%s attempt=%d source_count=%d context_chars=%d prep_ms=%d llm_ms=%d total_ms=%d timeout_s=%.1f",
                    resolved_provider,
                    resolved_model,
                    attempt_index + 1,
                    len(prompt_sources),
                    len(active_context),
                    prompt_prep_elapsed_ms,
                    llm_elapsed_ms,
                    total_elapsed_ms,
                    synthesis_timeout_seconds,
                )
                return fallback_payload(
                    "I found relevant vault evidence, but the synthesis step timed out. Review the attached sources.",
                    hydrated_active_sources,
                    reason="timeout",
                )
            llm_elapsed_ms = int((time.perf_counter() - llm_started_at) * 1000)
            raw_response_text = universal_client.extract_response_text(response)
            parsed = parse_structured_response(raw_response_text, prompt_sources)
            answer_text = str(parsed.get("answer") or "").strip()
            logger.info(
                "cascading_synthesis.model_complete provider=%s model=%s attempt=%d llm_ms=%d answer_chars=%d citations=%d fallback_reason=%s",
                resolved_provider,
                resolved_model,
                attempt_index + 1,
                llm_elapsed_ms,
                len(answer_text),
                len(parsed.get("citations") or []),
                str(parsed.get("fallback_reason") or ""),
            )
            if _answer_has_unsupported_grounded_details(answer_text, active_sources):
                parsed = fallback_payload(
                    _build_extractive_cascading_fallback_answer(query, prompt_sources),
                    prompt_sources,
                    reason="unsupported_grounded_detail",
                )
                answer_text = str(parsed.get("answer") or "").strip()
                logger.warning(
                    "cascading_synthesis.unsupported_detail provider=%s model=%s attempt=%d fallback_reason=%s total_ms=%d",
                    resolved_provider,
                    resolved_model,
                    attempt_index + 1,
                    parsed.get("fallback_reason"),
                    int((time.perf_counter() - attempt_started_at) * 1000),
                )
            if _looks_incomplete_answer(answer_text):
                if attempt_index < len(attempt_sources_list) - 1:
                    logger.info(
                        "cascading_synthesis.retry_reduced_evidence provider=%s model=%s attempt=%d answer_chars=%d",
                        resolved_provider,
                        resolved_model,
                        attempt_index + 1,
                        len(answer_text),
                    )
                    continue
                parsed = fallback_payload(
                    _build_extractive_cascading_fallback_answer(query, prompt_sources),
                    prompt_sources,
                    reason="incomplete_answer",
                )
                answer_text = str(parsed.get("answer") or "").strip()
                logger.warning(
                    "cascading_synthesis.incomplete_answer provider=%s model=%s attempt=%d fallback_reason=%s total_ms=%d",
                    resolved_provider,
                    resolved_model,
                    attempt_index + 1,
                    parsed.get("fallback_reason"),
                    int((time.perf_counter() - attempt_started_at) * 1000),
                )
            if answer_text and not is_generic_cascading_fallback_answer(answer_text):
                if attempt_index:
                    parsed["fallback_reason"] = "retry_reduced_evidence"
                logger.info(
                    "cascading_synthesis.complete provider=%s model=%s attempt=%d total_ms=%d fallback_reason=%s used_documents=%d",
                    resolved_provider,
                    resolved_model,
                    attempt_index + 1,
                    int((time.perf_counter() - overall_started_at) * 1000),
                    str(parsed.get("fallback_reason") or ""),
                    len(parsed.get("used_documents") or []),
                )
                return parsed
            if attempt_index == len(attempt_sources_list) - 1:
                parsed["fallback_reason"] = parsed.get("fallback_reason") or "weak_answer"
                logger.warning(
                    "cascading_synthesis.weak_answer provider=%s model=%s attempt=%d total_ms=%d fallback_reason=%s",
                    resolved_provider,
                    resolved_model,
                    attempt_index + 1,
                    int((time.perf_counter() - overall_started_at) * 1000),
                    parsed["fallback_reason"],
                )
                return parsed
    except Exception as exc:
        logger.exception(
            "cascading_synthesis.provider_exception provider=%s model=%s total_ms=%d",
            resolved_provider,
            resolved_model,
            int((time.perf_counter() - overall_started_at) * 1000),
        )
        raise exc

    payload = fallback_payload(
        f"Found {len(sources)} matching snippets in your vault.",
        sources,
        reason="provider_exception",
    )
    logger.warning(
        "cascading_synthesis.provider_fallback provider=%s model=%s total_ms=%d fallback_reason=%s",
        resolved_provider,
        resolved_model,
        int((time.perf_counter() - overall_started_at) * 1000),
        payload.get("fallback_reason"),
    )
    return payload
