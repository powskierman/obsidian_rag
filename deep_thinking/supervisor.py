import requests
from typing import List, Dict, Any
import time
import concurrent.futures
import logging
import re
from urllib.parse import urlparse
from pathlib import Path, PurePosixPath
from .state import Step, RAGState
from .source_utils import canonicalize_web_url, normalize_vault_path
try:
    from .reranker import Reranker
    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False
    print("Warning: Reranker not available. Install sentence-transformers to enable reranking.")

import os
try:
    from tavily import TavilyClient
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False
    print("Warning: tavily-python not available.")

logger = logging.getLogger(__name__)

try:
    from src.services.cascading_pipeline import (
        has_multi_facet_query,
        source_facet_match_indexes,
        source_set_covers_query_facets,
    )
except ImportError:
    def has_multi_facet_query(query: str) -> bool:
        return False

    def source_facet_match_indexes(source: Dict[str, Any], query: str) -> set[int]:
        return set()

    def source_set_covers_query_facets(query: str, sources: List[Dict[str, Any]]) -> bool:
        return False

try:
    from src.services.query_normalizer import (
        clean_entity_phrase as _clean_entity_phrase_impl,
        normalize_query_structure as _normalize_query_structure_impl,
        query_terms as _query_terms_impl,
    )
except ImportError:

    def _clean_entity_phrase_impl(value: str) -> str:
        return str(value or "").strip()

    def _normalize_query_structure_impl(query: str) -> Dict[str, Any]:
        normalized = re.sub(r"\s+", " ", str(query or "").strip())
        return {
            "original_query": normalized,
            "clean_query": normalized,
            "intent": "lookup",
            "entities": [],
            "relations": [],
            "facets": [],
            "must_terms": [],
        }

    def _query_terms_impl(query: str, *, stopwords=None) -> List[str]:
        terms: List[str] = []
        seen: set[str] = set()
        effective_stopwords = set(stopwords or ())
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{1,}", str(query or "").lower()):
            cleaned = token.strip("._-")
            if len(cleaned) < 2 or cleaned in effective_stopwords:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                terms.append(cleaned)
        return terms

class RetrievalSupervisor:
    GRAPH_SUMMARY_SOURCES = {"Graph Synthesis Summary", "LightRAG Knowledge Graph"}
    QUERY_STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "be", "between", "by", "connection",
        "does", "for", "how", "in", "is", "it", "of", "on", "or", "related",
        "relationship", "the", "to", "treat", "used", "what", "with",
    }
    RELATIONSHIP_PATTERNS = (
        re.compile(r"\bwhat(?:'s| is)? the connection between (?P<a>.+?) and (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bwhat(?:'s| is)? the link between (?P<a>.+?) and (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bhow is (?P<a>.+?) related to (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bhow are (?P<a>.+?) connected to (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bhow is (?P<a>.+?) connected to (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bhow are (?P<a>.+?) linked to (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bis (?P<a>.+?) used to treat (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bdoes (?P<a>.+?) treat (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bis (?P<a>.+?) indicated for (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bhow does (?P<a>.+?) relate to (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bdoes (?P<a>.+?) cause (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bdoes (?P<a>.+?) indicate (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bdoes (?P<a>.+?) diagnose (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bwhat is the role of (?P<a>.+?) in (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bis (?P<a>.+?) associated with (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bis (?P<a>.+?) a marker for (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
    )
    RELATIONSHIP_HINTS = (
        "connection", "related to", "relationship", "used to treat", "treat",
        "indicated for", "linked to", "connected to", "role of", "associated with", "marker for",
        "cause", "diagnose", "indicate",
    )
    RELATIONSHIP_EVIDENCE_HINTS = (
        "approved for", "indicated for", "used to treat", "treats", "treat",
        "large b-cell lymphoma", "diffuse large b-cell lymphoma", "dlbcl",
        "targets cd19", "cd19-directed", "car-t", "car t",
    )
    GENERIC_OVERVIEW_HINTS = (
        "diagnosis", "options", "overview", "general", "management", "guideline",
        "regimen", "r-chop", "treatment approach", "treatment options", "workup",
    )
    OUTCOME_HINTS = (
        "trial", "study", "zuma", "survival", "outcome", "efficacy", "ash",
    )
    OPTION_QUERY_HINTS = (
        "option", "options", "compare", "comparison", "versus", " vs ", "sequence",
        "line of therapy", "next line", "first-line", "second-line",
    )
    OUTCOME_QUERY_HINTS = (
        "outcome", "survival", "efficacy", "response rate", "trial", "study", "zuma",
    )
    MODALITY_HINTS = {
        "car_t": ("car-t", "car t", "axi-cel", "axicabtagene", "ciloleucel", "yescarta"),
        "immunotherapy": ("immunotherapy", "cd19", "monoclonal antibody", "cell therapy", "car-t", "car t"),
        "chemotherapy": ("chemotherapy", "chemo", "r-chop", "cyclophosphamide", "vincristine", "doxorubicin"),
        "lymphoma": ("lymphoma", "dlbcl", "large b-cell lymphoma", "b-cell lymphoma"),
    }
    MODALITY_TAGS = {"car_t", "immunotherapy", "chemotherapy"}
    MEDICAL_ALLOWED_PREFIXES_DEFAULT = ("Medical/", "Health/", "Oncology/")
    MEDICAL_SUSPICIOUS_PREFIXES_DEFAULT = ("Tech/", "Electronics/", "Finance/", "Projects/")
    MEDICAL_QUERY_HINTS = (
        "lymphoma", "leukemia", "cancer", "tumor", "oncology", "therapy", "treatment",
        "diagnosis", "diagnose", "marker", "biomarker", "chemotherapy", "immunotherapy",
        "car-t", "car t", "antibody", "disease", "syndrome", "diffuse large b-cell lymphoma",
        "dlbcl", "follicular lymphoma", "axicabtagene", "ciloleucel", "yescarta",
    )
    GENERIC_BRIDGE_STOPWORDS = {
        "about", "access", "application", "article", "author", "based", "book", "books",
        "chapter", "content", "context", "definition", "details", "document", "evidence",
        "framework", "general", "guide", "history", "idea", "information", "introduction",
        "main", "management", "method", "note", "notes", "options", "overview", "page",
        "project", "reference", "references", "role", "setting", "shared", "summary",
        "system", "topic", "topics", "treatment", "used", "using", "whenever", "writing",
    }
    SUMMARY_REQUEST_PATTERNS = (
        re.compile(r"\b(?:provide|give|write|create)\s+(?:a\s+)?(?:point\s+form\s+|bullet(?:-point)?\s+)?summary\s+of\s+(?P<topic>.+)$", re.IGNORECASE),
        re.compile(r"\bsummarize\s+(?P<topic>.+)$", re.IGNORECASE),
        re.compile(r"\bsummary\s+of\s+(?P<topic>.+)$", re.IGNORECASE),
    )
    EXTERNAL_SUMMARY_HINTS = (
        "review", "reviews", "reception", "critique", "external context", "outside context",
        "web", "internet", "goodreads", "guardian", "blinkist", "shortform",
    )
    CURRENT_INFO_HINTS = (
        "latest", "recent", "currently", "current", "today", "now", "newest",
        "up to date", "up-to-date", "as of", "release notes", "changelog",
    )
    AUTHORITATIVE_SOURCE_HINTS = (
        "official", "authoritative", "guideline", "guidelines", "standard", "standards",
        "regulation", "regulations", "law", "laws", "statute", "statutes",
        "policy", "policies", "api reference", "reference docs", "documentation",
        "datasheet", "specification", "specifications", "spec", "specs", "manual",
    )
    CONCEPTUAL_EXPLANATION_PATTERNS = (
        re.compile(r"\bhow do(?:es)? (?P<a>.+?) relate to (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bwhat is the difference between (?P<a>.+?) and (?P<b>.+?)(?:\?|$)", re.IGNORECASE),
        re.compile(r"\bexplain (?:the )?(?:relationship|difference|intuition|concept)\b", re.IGNORECASE),
        re.compile(r"\bwhy do(?:es)?\b", re.IGNORECASE),
        re.compile(r"\bhow does\b.+\bwork\b", re.IGNORECASE),
    )
    CONCEPTUAL_EXPLANATION_HINTS = (
        "first principles", "conceptually", "intuition", "why does", "why do",
        "difference between", "relate to", "relationship between", "connected to", "how does",
    )
    INSTRUCTION_QUERY_HINTS = (
        "prompt", "prompts", "template", "templates", "instruction", "instructions",
        "copilot", "agent", "workflow",
    )
    INSTRUCTION_PATH_HINTS = (
        "copilot/", "/copilot/", "prompt", "prompts", "workflow", "workflows",
    )

    def __init__(
        self,
        vector_service_url: str,
        graph_service_url: str,
        enable_reranking: bool = True,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ):
        self.vector_service_url = vector_service_url
        self.graph_service_url = graph_service_url
        self.enable_reranking = enable_reranking and RERANKER_AVAILABLE
        self.llm_provider = (llm_provider or "").strip()
        self.llm_model = (llm_model or "").strip()
        self.full_content_expansion_bytes = self._full_file_expansion_limit(self.llm_provider)
        
        # Initialize reranker if available
        if self.enable_reranking:
            self.reranker = Reranker()
            print("✅ Reranker initialized")
        else:
            self.reranker = None
            if enable_reranking:
                print("⚠️  Reranking disabled (sentence-transformers not installed)")

    @staticmethod
    def _use_lazy_expansion_v2() -> bool:
        return os.getenv("DEEP_THINKING_LAZY_EXPANSION_V2", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }

    @classmethod
    def _is_graph_summary_doc(cls, doc: Dict[str, Any]) -> bool:
        if not isinstance(doc, dict):
            return False
        if doc.get("is_summary"):
            return True
        source = str(doc.get("source") or doc.get("filepath") or "").strip()
        if source in cls.GRAPH_SUMMARY_SOURCES:
            return True
        source_type = str(doc.get("source_type") or "").strip().lower()
        return source_type == "graph-summary"

    @classmethod
    def _filter_reasoning_docs(cls, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [doc for doc in docs if not cls._is_graph_summary_doc(doc)]

    @classmethod
    def _is_internal_reasoning_doc(cls, doc: Dict[str, Any]) -> bool:
        if not isinstance(doc, dict):
            return False
        if doc.get("internal_only"):
            return True
        source_type = str(doc.get("source_type") or "").strip().lower()
        return source_type in {"graph-reasoning", "internal-graph-reasoning"}

    @classmethod
    def _is_citable_doc(cls, doc: Dict[str, Any]) -> bool:
        return isinstance(doc, dict) and not cls._is_graph_summary_doc(doc) and not cls._is_internal_reasoning_doc(doc)

    @classmethod
    def _filter_citable_docs(cls, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [doc for doc in docs or [] if cls._is_citable_doc(doc)]

    @classmethod
    def _graph_reasoning_doc(cls, content: Any, mode: str) -> Dict[str, Any]:
        text = str(content or "").strip()
        snippet = text if len(text) <= 600 else text[:597].rstrip() + "..."
        return {
            "content": text,
            "source": "Graph Reasoning Result",
            "filepath": "Graph Reasoning Result",
            "filename": f"Graph Reasoning ({mode})",
            "snippet": snippet,
            "type": "graph",
            "source_category": "vault",
            "source_type": "graph-reasoning",
            "score": 0.6,
            "internal_only": True,
        }

    @staticmethod
    def _env_flag(key: str, default: bool) -> bool:
        value = os.getenv(key, "true" if default else "false").strip().lower()
        return value in {"1", "true", "yes", "on"}

    @classmethod
    def _enable_connection_mode(cls) -> bool:
        return cls._env_flag("DEEP_THINKING_ENABLE_CONNECTION_MODE", True)

    @classmethod
    def _max_sources_for_simple_relationship(cls) -> int:
        try:
            return max(1, min(5, int(os.getenv("DEEP_THINKING_RELATIONSHIP_MAX_SOURCES", os.getenv("DEEP_THINKING_MAX_SOURCES_SIMPLE_RELATIONSHIP", "3")))))
        except (TypeError, ValueError):
            return 3

    @classmethod
    def _prefix_list_env(cls, key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        raw = os.getenv(key, "").strip()
        if not raw:
            return default
        items = []
        for part in raw.split(","):
            normalized = normalize_vault_path(part).strip()
            if normalized and not normalized.endswith("/"):
                normalized = f"{normalized}/"
            if normalized:
                items.append(normalized)
        return tuple(items) or default

    @classmethod
    def _medical_allowed_prefixes(cls) -> tuple[str, ...]:
        return cls._prefix_list_env("DEEP_THINKING_ALLOWED_PREFIXES", cls.MEDICAL_ALLOWED_PREFIXES_DEFAULT)

    @classmethod
    def _medical_suspicious_prefixes(cls) -> tuple[str, ...]:
        return cls._prefix_list_env("DEEP_THINKING_SUSPICIOUS_PREFIXES", cls.MEDICAL_SUSPICIOUS_PREFIXES_DEFAULT)

    @classmethod
    def _metadata_strictness(cls) -> str:
        value = os.getenv("DEEP_THINKING_METADATA_STRICTNESS", "moderate").strip().lower()
        if value in {"off", "false", "0"}:
            return "off"
        if value == "strict":
            return "strict"
        return "moderate"

    @staticmethod
    def _clean_entity_phrase(value: str) -> str:
        return _clean_entity_phrase_impl(value)

    @classmethod
    def _extract_relationship_entities(cls, query: str) -> List[str]:
        payload = _normalize_query_structure_impl(query)
        return [entity for entity in payload.get("entities", []) if entity]

    @classmethod
    def _query_terms(cls, query: str) -> List[str]:
        return _query_terms_impl(query, stopwords=cls.QUERY_STOPWORDS)

    @staticmethod
    def _normalize_match_text(value: Any) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()

    @classmethod
    def _summary_focus_text(cls, query: str) -> str:
        normalized = re.sub(r"\s+", " ", str(query or "").strip()).rstrip("?.! ")
        for pattern in cls.SUMMARY_REQUEST_PATTERNS:
            match = pattern.search(normalized)
            if not match:
                continue
            topic = str(match.group("topic") or "").strip(" \"'`")
            if topic:
                return topic
        return ""

    @classmethod
    def is_summary_request(cls, query: str) -> bool:
        lower = str(query or "").lower()
        if "summary" not in lower and "summarize" not in lower:
            return False
        return bool(cls._summary_focus_text(query))

    @classmethod
    def is_current_info_query(cls, query: str) -> bool:
        lower = str(query or "").lower()
        return any(hint in lower for hint in cls.CURRENT_INFO_HINTS)

    @classmethod
    def needs_authoritative_external_sources(cls, query: str) -> bool:
        lower = str(query or "").lower()
        return cls.is_current_info_query(query) or any(
            hint in lower for hint in cls.AUTHORITATIVE_SOURCE_HINTS
        )

    @classmethod
    def is_conceptual_explanation_query(cls, query: str) -> bool:
        normalized = re.sub(r"\s+", " ", str(query or "").strip())
        lower = normalized.lower()
        if (
            not normalized
            or cls.is_summary_request(normalized)
            or cls._allows_instruction_docs(lower)
            or cls.needs_authoritative_external_sources(normalized)
        ):
            return False
        if any(pattern.search(normalized) for pattern in cls.CONCEPTUAL_EXPLANATION_PATTERNS):
            return True
        return any(hint in lower for hint in cls.CONCEPTUAL_EXPLANATION_HINTS)

    @classmethod
    def _allows_instruction_docs(cls, query_lower: str) -> bool:
        return any(hint in str(query_lower or "") for hint in cls.INSTRUCTION_QUERY_HINTS)

    @classmethod
    def _is_instruction_doc(cls, doc: Dict[str, Any]) -> bool:
        if not isinstance(doc, dict):
            return False
        path = normalize_vault_path(doc.get("filepath") or doc.get("source") or "")
        title = str(doc.get("title") or doc.get("filename") or "").lower()
        lowered_path = path.lower()
        return any(hint in lowered_path for hint in cls.INSTRUCTION_PATH_HINTS) or any(
            hint in title for hint in ("prompt", "template", "workflow")
        )

    @classmethod
    def _preferred_tags_for_query(cls, query_lower: str, anchors: List[str]) -> set[str]:
        tags: set[str] = set()
        combined = " ".join([query_lower, *[anchor.lower() for anchor in anchors if anchor]])
        for tag, hints in cls.MODALITY_HINTS.items():
            if any(hint in combined for hint in hints):
                tags.add(tag)
        return tags

    @classmethod
    def is_relationship_query(cls, query: str) -> bool:
        normalized = re.sub(r"\s+", " ", str(query or "").strip())
        lower = normalized.lower()
        if any(hint in lower for hint in cls.OPTION_QUERY_HINTS):
            return False
        if re.search(r"\bwhat are (?:the )?(?:treatment )?options for\b", lower):
            return False
        if any(pattern.search(normalized) for pattern in cls.RELATIONSHIP_PATTERNS):
            return True
        return any(hint in lower for hint in cls.RELATIONSHIP_HINTS)

    @classmethod
    def is_medical_query(cls, query: str, anchors: List[str] | None = None) -> bool:
        lower = str(query or "").lower()
        if any(hint in lower for hint in cls.MEDICAL_QUERY_HINTS):
            return True
        anchor_text = " ".join(anchors or []).lower()
        return any(hint in anchor_text for hint in cls.MEDICAL_QUERY_HINTS)

    @classmethod
    def build_query_profile(cls, query: str) -> Dict[str, Any]:
        normalized = re.sub(r"\s+", " ", str(query or "").strip())
        lower = normalized.lower()
        normalized_query = _normalize_query_structure_impl(normalized)
        anchors = [entity for entity in normalized_query.get("entities", []) if entity]
        compare_mode = any(hint in lower for hint in cls.OPTION_QUERY_HINTS)
        needs_outcomes = any(hint in lower for hint in cls.OUTCOME_QUERY_HINTS)
        is_relationship = (
            cls._enable_connection_mode()
            and (
                normalized_query.get("intent") == "relationship"
                or cls.is_relationship_query(normalized)
            )
        )
        is_summary_request = cls.is_summary_request(normalized)
        summary_focus = cls._summary_focus_text(normalized)
        requires_current_information = cls.is_current_info_query(normalized)
        needs_authoritative_sources = cls.needs_authoritative_external_sources(normalized)
        is_conceptual_explanation = cls.is_conceptual_explanation_query(normalized)
        prefers_vault_only_summary = is_summary_request and not any(
            hint in lower for hint in cls.EXTERNAL_SUMMARY_HINTS
        )
        is_medical = cls.is_medical_query(normalized, anchors)
        needs_external_authority = bool(
            requires_current_information or needs_authoritative_sources or is_medical
        )
        prefers_reasoning_first = bool(
            is_conceptual_explanation and not needs_external_authority
        )
        max_sources = None
        if is_relationship:
            max_sources = cls._max_sources_for_simple_relationship()
        elif is_summary_request:
            max_sources = 2
        elif prefers_reasoning_first:
            max_sources = 3
        return {
            "query": normalized,
            "normalized_query": normalized_query,
            "clean_query": str(normalized_query.get("clean_query") or normalized),
            "lower": lower,
            "terms": cls._query_terms(normalized),
            "anchor_entities": anchors,
            "anchor_terms": cls._query_terms(" ".join(anchors)),
            "relations": list(normalized_query.get("relations") or []),
            "facets": list(normalized_query.get("facets") or []),
            "intent": str(normalized_query.get("intent") or "lookup"),
            "is_relationship": is_relationship,
            "is_summary_request": is_summary_request,
            "summary_focus": summary_focus,
            "prefers_vault_only_summary": prefers_vault_only_summary,
            "is_conceptual_explanation": is_conceptual_explanation,
            "requires_current_information": requires_current_information,
            "needs_authoritative_sources": needs_authoritative_sources,
            "needs_external_authority": needs_external_authority,
            "prefers_reasoning_first": prefers_reasoning_first,
            "allows_instruction_docs": cls._allows_instruction_docs(lower),
            "is_medical": is_medical,
            "allows_generic_overview": compare_mode,
            "needs_outcomes": needs_outcomes,
            "preferred_tags": cls._preferred_tags_for_query(lower, anchors),
            "max_sources": max_sources,
        }

    @staticmethod
    def _normalize_tag(value: Any) -> str:
        text = str(value or "").strip().lower().replace("#", "")
        text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
        return text

    @staticmethod
    def _document_lookup_key(doc: Dict[str, Any]) -> tuple[str, str]:
        source = str(doc.get("filepath") or doc.get("url") or doc.get("source") or doc.get("filename") or "").strip()
        category = str(doc.get("source_category") or "").strip().lower()
        if category != "web" and not source.startswith("http://") and not source.startswith("https://"):
            return "vault", normalize_vault_path(source).lower()
        canonical = canonicalize_web_url(doc.get("canonical_url") or source) or source
        return "web", canonical.lower()

    @classmethod
    def _doc_title_text(cls, doc: Dict[str, Any]) -> str:
        parts = [
            doc.get("title"),
            doc.get("filename"),
            doc.get("filepath"),
            doc.get("source"),
            doc.get("canonical_id"),
            doc.get("entity_type"),
        ]
        return " ".join(str(part or "") for part in parts).lower()

    @classmethod
    def _doc_full_text(cls, doc: Dict[str, Any]) -> str:
        return f"{cls._doc_title_text(doc)} {cls._doc_body_text(doc)}"

    @classmethod
    def _doc_contains_anchor(cls, doc: Dict[str, Any], anchor: str) -> bool:
        lowered = cls._clean_entity_phrase(anchor).lower()
        if not lowered:
            return False
        return lowered in cls._doc_full_text(doc)

    @classmethod
    def _doc_contains_all_anchors(cls, doc: Dict[str, Any], anchors: List[str]) -> bool:
        required = [cls._clean_entity_phrase(anchor) for anchor in anchors if cls._clean_entity_phrase(anchor)]
        if not required:
            return False
        return all(cls._doc_contains_anchor(doc, anchor) for anchor in required)

    @classmethod
    def _is_vault_doc_under_prefixes(cls, doc: Dict[str, Any], prefixes: tuple[str, ...]) -> bool:
        path = normalize_vault_path(doc.get("filepath") or doc.get("source") or "")
        lowered = path.lower()
        return any(lowered.startswith(prefix.lower()) for prefix in prefixes)

    @classmethod
    def filter_vault_docs_by_domain_and_entities(
        cls,
        docs: List[Dict[str, Any]],
        query_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not query_profile.get("is_medical"):
            return docs

        anchors = query_profile.get("anchor_entities", [])
        suspicious_prefixes = cls._medical_suspicious_prefixes()
        allowed_prefixes = cls._medical_allowed_prefixes()
        filtered: List[Dict[str, Any]] = []

        for doc in docs or []:
            if not isinstance(doc, dict):
                continue
            source_category = str(doc.get("source_category") or "").strip().lower()
            if source_category != "vault":
                filtered.append(doc)
                continue

            in_suspicious = cls._is_vault_doc_under_prefixes(doc, suspicious_prefixes)
            in_allowed = cls._is_vault_doc_under_prefixes(doc, allowed_prefixes)
            if in_suspicious and not cls._doc_contains_all_anchors(doc, anchors):
                continue

            if not in_allowed and suspicious_prefixes and not cls._doc_contains_all_anchors(doc, anchors):
                # Medical queries should stay in medical areas unless the note explicitly contains the anchors.
                continue

            filtered.append(doc)

        return filtered

    @classmethod
    def _informative_tokens(cls, text: str, anchor_terms: List[str]) -> set[str]:
        tokens: set[str] = set()
        anchor_block = set(anchor_terms or [])
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", str(text or "").lower()):
            cleaned = token.strip("-")
            if len(cleaned) < 3 or cleaned in cls.QUERY_STOPWORDS or cleaned in cls.GENERIC_BRIDGE_STOPWORDS:
                continue
            if cleaned in anchor_block:
                continue
            tokens.add(cleaned)
        return tokens

    @classmethod
    def _bridge_overlap_score(cls, left: Dict[str, Any], right: Dict[str, Any], profile: Dict[str, Any]) -> int:
        left_tokens = cls._informative_tokens(cls._doc_full_text(left), profile.get("anchor_terms", []))
        right_tokens = cls._informative_tokens(cls._doc_full_text(right), profile.get("anchor_terms", []))
        token_overlap = len(left_tokens & right_tokens)

        def ngrams(text: str, n: int) -> set[str]:
            words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text.lower()) if w not in cls.GENERIC_BRIDGE_STOPWORDS]
            return {" ".join(words[i:i+n]) for i in range(len(words) - n + 1)}

        left_text = cls._doc_full_text(left)
        right_text = cls._doc_full_text(right)
        phrase_overlap = len((ngrams(left_text, 2) | ngrams(left_text, 3)) & (ngrams(right_text, 2) | ngrams(right_text, 3)))
        return max(token_overlap, phrase_overlap * 2)

    @classmethod
    def _doc_body_text(cls, doc: Dict[str, Any]) -> str:
        content = str(doc.get("snippet") or doc.get("content") or "")
        if len(content) > 2400:
            content = content[:2400]
        tags = doc.get("tags")
        tags_text = ""
        if isinstance(tags, list):
            tags_text = " ".join(str(tag or "") for tag in tags)
        elif isinstance(tags, str):
            tags_text = tags
        phase = str(doc.get("treatment_phase") or "")
        return " ".join([content, tags_text, phase]).lower()

    @classmethod
    def _infer_semantic_tags(cls, doc: Dict[str, Any]) -> set[str]:
        content = str(doc.get("snippet") or doc.get("content") or "")
        if len(content) > 2400:
            content = content[:2400]
        text = f"{cls._doc_title_text(doc)} {content.lower()}"
        inferred: set[str] = set()
        for tag, hints in cls.MODALITY_HINTS.items():
            if any(hint in text for hint in hints):
                inferred.add(tag)
        return inferred

    @classmethod
    def _effective_metadata(cls, doc: Dict[str, Any]) -> Dict[str, Any]:
        strictness = cls._metadata_strictness()
        tags: set[str] = set()
        raw_tags = doc.get("tags")
        if isinstance(raw_tags, list):
            tags.update(cls._normalize_tag(tag) for tag in raw_tags if tag)
        elif isinstance(raw_tags, str):
            tags.update(cls._normalize_tag(tag) for tag in re.split(r"[,\s]+", raw_tags) if tag)

        phase = cls._normalize_tag(doc.get("treatment_phase"))
        if phase and phase != "unspecified":
            tags.add(phase)

        inferred = cls._infer_semantic_tags(doc)
        inferred_modalities = inferred & cls.MODALITY_TAGS
        raw_modalities = tags & cls.MODALITY_TAGS

        if strictness != "off" and inferred_modalities and raw_modalities and raw_modalities.isdisjoint(inferred_modalities):
            tags -= raw_modalities
            if phase in cls.MODALITY_TAGS:
                phase = ""

        if strictness == "strict":
            tags |= inferred
        elif strictness == "moderate":
            tags |= inferred - raw_modalities

        return {
            "tags": tags,
            "phase": phase,
            "entity_type": cls._normalize_tag(doc.get("entity_type")),
            "canonical_id": str(doc.get("canonical_id") or "").strip().lower(),
        }

    @classmethod
    def _analyze_doc_for_query(cls, doc: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        title_text = cls._doc_title_text(doc)
        body_text = cls._doc_body_text(doc)
        full_text = f"{title_text} {body_text}"
        title_match_text = cls._normalize_match_text(" ".join([
            str(doc.get("title") or ""),
            str(doc.get("filename") or ""),
        ]))
        summary_focus = cls._normalize_match_text(profile.get("summary_focus") or "")
        anchor_hits_title = []
        anchor_hits_any = []
        for entity in profile.get("anchor_entities", []):
            lowered = entity.lower()
            if lowered and lowered in title_text:
                anchor_hits_title.append(lowered)
            if lowered and lowered in full_text:
                anchor_hits_any.append(lowered)

        query_term_hits = sum(1 for term in profile.get("terms", []) if term and term in full_text)
        metadata = cls._effective_metadata(doc)
        metadata_matches = metadata["tags"] & set(profile.get("preferred_tags", set()))
        generic_overview = any(hint in title_text for hint in cls.GENERIC_OVERVIEW_HINTS)
        trial_outcome = any(hint in full_text for hint in cls.OUTCOME_HINTS)
        relation_hint = any(hint in full_text for hint in cls.RELATIONSHIP_EVIDENCE_HINTS)
        summary_focus_title_match = bool(summary_focus and summary_focus in title_match_text)
        summary_focus_exact_match = bool(summary_focus and (
            summary_focus == title_match_text
            or title_match_text.endswith(summary_focus)
            or title_match_text.startswith(summary_focus)
        ))

        return {
            "title_text": title_text,
            "full_text": full_text,
            "anchor_hits_title": anchor_hits_title,
            "anchor_hits_any": anchor_hits_any,
            "anchor_coverage": len(set(anchor_hits_any)),
            "covers_all_anchors": bool(profile.get("anchor_entities")) and len(set(anchor_hits_any)) >= len(profile["anchor_entities"]),
            "query_term_hits": query_term_hits,
            "metadata_matches": metadata_matches,
            "generic_overview": generic_overview,
            "trial_outcome": trial_outcome,
            "explicit_relation": relation_hint and (
                len(set(anchor_hits_any)) >= max(1, min(2, len(profile.get("anchor_entities", [])) or 1))
            ),
            "summary_focus_title_match": summary_focus_title_match,
            "summary_focus_exact_match": summary_focus_exact_match,
        }

    @classmethod
    def rank_sources_for_query(
        cls,
        query: str,
        docs: List[Dict[str, Any]],
        max_results: int | None = None,
        apply_relationship_limit: bool = True,
    ) -> List[Dict[str, Any]]:
        profile = cls.build_query_profile(query)
        docs = cls.filter_vault_docs_by_domain_and_entities(docs, profile)
        ranked: List[Dict[str, Any]] = []

        for doc in docs or []:
            if not isinstance(doc, dict) or cls._is_graph_summary_doc(doc):
                continue
            if cls._is_instruction_doc(doc) and not profile.get("allows_instruction_docs"):
                continue

            signals = cls._analyze_doc_for_query(doc, profile)
            base_score = cls._coerce_score(doc.get("rerank_score", doc.get("score", doc.get("relevance", 0.0))))
            if base_score > 1.0:
                base_score /= 100.0

            rank = base_score * 4.0
            rank += len(signals["anchor_hits_title"]) * 2.5
            rank += signals["anchor_coverage"] * 1.25
            rank += min(signals["query_term_hits"], 6) * 0.35
            rank += min(len(signals["metadata_matches"]), 3) * 1.1
            if signals["covers_all_anchors"]:
                rank += 3.0
            if signals["explicit_relation"]:
                rank += 3.5

            source_category = str(doc.get("source_category") or "").strip().lower()
            source_type = str(doc.get("source_type") or "").strip().lower()
            if source_category == "vault":
                rank += 0.4
            if source_type in {"direct_excerpt", "direct-excerpt", "entity_context", "entity-context"}:
                rank += 0.4

            if profile["is_relationship"] and signals["anchor_coverage"] == 0:
                rank -= 2.5
            if profile.get("is_summary_request"):
                if source_category == "vault":
                    rank += 2.0
                else:
                    rank -= 1.5
                if signals["summary_focus_title_match"]:
                    rank += 4.0
                if signals["summary_focus_exact_match"]:
                    rank += 5.0
            if profile.get("prefers_reasoning_first"):
                if source_category == "vault":
                    rank += 1.25
                else:
                    rank -= 1.25
            if signals["generic_overview"] and not profile["allows_generic_overview"]:
                rank -= 3.5
            if signals["trial_outcome"] and not profile["needs_outcomes"]:
                rank -= 2.0

            doc["_query_rank_score"] = rank
            doc["_query_profile_kind"] = "relationship" if profile["is_relationship"] else "default"
            doc["_anchor_entities_found"] = list(dict.fromkeys(signals["anchor_hits_any"]))
            doc["_relationship_explicit"] = bool(signals["explicit_relation"])
            doc["_generic_overview"] = bool(signals["generic_overview"])
            doc["_covers_all_anchors"] = bool(signals["covers_all_anchors"])
            doc["_summary_focus_title_match"] = bool(signals["summary_focus_title_match"])
            doc["_summary_focus_exact_match"] = bool(signals["summary_focus_exact_match"])
            ranked.append(doc)

        ranked.sort(
            key=lambda item: (
                -float(item.get("_query_rank_score", 0.0)),
                0 if str(item.get("source_category") or "").strip().lower() == "vault" else 1,
                str(item.get("filename") or item.get("source") or "").lower(),
            )
        )

        deduped: List[Dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for doc in ranked:
            source_category = str(doc.get("source_category") or "").strip().lower() or (
                "web" if cls._is_web_url(doc.get("filepath") or doc.get("source") or "") else "vault"
            )
            locator = str(doc.get("filepath") or doc.get("url") or doc.get("source") or doc.get("filename") or "").strip()
            if source_category == "web":
                locator = canonicalize_web_url(doc.get("canonical_url") or locator) or locator
            else:
                locator = normalize_vault_path(locator)
            key = (source_category, locator.lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(doc)

        if profile["is_relationship"]:
            useful = [
                doc for doc in deduped
                if doc.get("_relationship_explicit")
                or doc.get("_covers_all_anchors")
                or (doc.get("_anchor_entities_found") and not doc.get("_generic_overview"))
                or (
                    float(doc.get("_query_rank_score", 0.0)) >= 2.0
                    and not doc.get("_generic_overview")
                )
            ]
            if useful:
                deduped = useful
            if apply_relationship_limit:
                limit = min(max_results or profile["max_sources"] or 5, 5, profile["max_sources"] or 5)
                return deduped[:max(1, limit)]
            if max_results is None:
                return deduped
            return deduped[:max_results]

        if max_results is None:
            return deduped
        return deduped[:max_results]

    @classmethod
    def _preserve_multi_facet_query_coverage(
        cls,
        query: str,
        selected_docs: List[Dict[str, Any]],
        candidate_docs: List[Dict[str, Any]],
        max_results: int,
    ) -> List[Dict[str, Any]]:
        if not has_multi_facet_query(query):
            return selected_docs[:max_results]
        if source_set_covers_query_facets(query, selected_docs):
            return selected_docs[:max_results]

        covered = set()
        for doc in selected_docs:
            covered.update(source_facet_match_indexes(doc, query))

        supplemented = list(selected_docs)
        seen_keys = {
            cls._document_lookup_key(doc)
            for doc in supplemented
            if isinstance(doc, dict)
        }

        def uncovered_count(doc: Dict[str, Any]) -> int:
            return len(source_facet_match_indexes(doc, query) - covered)

        ordered_candidates = sorted(
            [doc for doc in candidate_docs if isinstance(doc, dict)],
            key=lambda doc: (
                -uncovered_count(doc),
                -float(doc.get("_query_rank_score", 0.0)),
            ),
        )

        for doc in ordered_candidates:
            if len(supplemented) >= max_results:
                break
            key = cls._document_lookup_key(doc)
            if key in seen_keys:
                continue
            match_indexes = source_facet_match_indexes(doc, query)
            if not match_indexes:
                continue
            if match_indexes - covered:
                supplemented.append(doc)
                seen_keys.add(key)
                covered.update(match_indexes)
                if source_set_covers_query_facets(query, supplemented):
                    break

        return supplemented[:max_results]

    @classmethod
    def select_minimal_evidence_set(
        cls,
        query: str,
        docs: List[Dict[str, Any]],
        max_docs: int | None = None,
    ) -> List[Dict[str, Any]]:
        docs = cls._filter_citable_docs(docs)
        profile = cls.build_query_profile(query)
        filtered_docs = cls.filter_vault_docs_by_domain_and_entities(docs, profile)
        ranked = cls.rank_sources_for_query(query, filtered_docs, max_results=max_docs or len(filtered_docs or []))
        if profile.get("is_summary_request"):
            limit = max(1, min(max_docs or profile.get("max_sources") or 2, profile.get("max_sources") or 2))
            vault_docs = [doc for doc in ranked if str(doc.get("source_category") or "").strip().lower() == "vault"]
            selected: List[Dict[str, Any]] = []
            for doc in vault_docs:
                if doc.get("_summary_focus_exact_match"):
                    selected.append(doc)
                    break
            for doc in vault_docs:
                if len(selected) >= limit:
                    break
                if doc in selected:
                    continue
                selected.append(doc)
            if selected:
                return selected[:limit]
            return ranked[:limit]
        if not profile["is_relationship"]:
            return ranked[: max_docs or len(ranked)]

        limit = min(max_docs or profile["max_sources"] or 3, 5, profile["max_sources"] or 3)
        selected: List[Dict[str, Any]] = []
        selected_keys: set[tuple[str, str]] = set()
        covered = set()

        def dedupe_key(doc: Dict[str, Any]) -> tuple[str, str]:
            source_category = str(doc.get("source_category") or "").strip().lower() or (
                "web" if cls._is_web_url(doc.get("filepath") or doc.get("source") or "") else "vault"
            )
            locator = str(doc.get("filepath") or doc.get("url") or doc.get("source") or doc.get("filename") or "").strip()
            if source_category == "web":
                locator = canonicalize_web_url(doc.get("canonical_url") or locator) or locator
            else:
                locator = normalize_vault_path(locator)
            return source_category, locator.lower()

        for doc in ranked:
            if doc.get("_relationship_explicit"):
                key = dedupe_key(doc)
                selected.append(doc)
                selected_keys.add(key)
                covered.update(doc.get("_anchor_entities_found", []))
                break

        if not selected and len(profile.get("anchor_entities", [])) >= 2:
            all_anchor_docs = [doc for doc in ranked if doc.get("_covers_all_anchors")]
            if all_anchor_docs:
                first = all_anchor_docs[0]
                selected.append(first)
                selected_keys.add(dedupe_key(first))
                covered.update(first.get("_anchor_entities_found", []))

        for doc in ranked:
            if len(selected) >= limit:
                break
            key = dedupe_key(doc)
            if key in selected_keys:
                continue

            anchors_found = set(doc.get("_anchor_entities_found", []))
            unique_anchors = anchors_found - covered
            if not selected:
                selected.append(doc)
                selected_keys.add(key)
                covered.update(anchors_found)
                continue

            if unique_anchors:
                selected.append(doc)
                selected_keys.add(key)
                covered.update(anchors_found)
                continue

            if not any(item.get("_relationship_explicit") for item in selected) and doc.get("_relationship_explicit"):
                selected.append(doc)
                selected_keys.add(key)
                covered.update(anchors_found)

        if len(selected) < min(2, limit) and len(profile.get("anchor_entities", [])) >= 2:
            anchors = profile["anchor_entities"][:2]
            anchor_specific: List[Dict[str, Any]] = []
            for anchor in anchors:
                match = next((doc for doc in ranked if cls._doc_contains_anchor(doc, anchor)), None)
                if match and dedupe_key(match) not in selected_keys:
                    anchor_specific.append(match)
            for doc in anchor_specific:
                if len(selected) >= limit:
                    break
                key = dedupe_key(doc)
                if key in selected_keys:
                    continue
                selected.append(doc)
                selected_keys.add(key)

        if len(selected) >= 2 and len(profile.get("anchor_entities", [])) >= 2:
            bridges: List[Dict[str, Any]] = []
            for doc in ranked:
                key = dedupe_key(doc)
                if key in selected_keys:
                    continue
                if any(cls._bridge_overlap_score(doc, chosen, profile) >= 2 for chosen in selected):
                    bridges.append(doc)
            for doc in bridges[: max(0, limit - len(selected))]:
                key = dedupe_key(doc)
                if key in selected_keys:
                    continue
                selected.append(doc)
                selected_keys.add(key)

        if not selected:
            selected = ranked[:limit]

        selected = cls._preserve_multi_facet_query_coverage(
            query,
            selected,
            ranked,
            max_results=limit,
        )

        return selected[:limit]
        
    def execute_step(self, step: Step, state: RAGState, trace_callback=None) -> List[Dict[str, Any]]:
        """
        Execute the search strategy specified in the step.
        """
        def trace(message: str, details: Dict[str, Any] | None = None) -> None:
            line = f"{message}"
            if details:
                line = f"{line} {details}"
            print(line)
            if trace_callback:
                trace_callback(message, details)

        def summarize(results: List[Dict[str, Any]], limit: int = 3) -> Dict[str, Any]:
            sample = []
            for item in results[:limit]:
                sample.append({
                    "source": item.get("source"),
                    "type": item.get("type"),
                    "score": round(float(item.get("score", 0.0)), 4)
                })
            return {"count": len(results), "sample": sample}

        # For vault searches (vector/hybrid), use keywords if available.
        # Keywords have better signal than sub_questions which may include generic words.
        strategy = step["search_strategy"]
        if strategy in ["vector", "hybrid"]:
            query = step["sub_question"]
            if step.get("keywords"):
                query = f"{query} {' '.join(step['keywords'])}"
            original_question = state.get("original_question", "")
            if original_question and original_question.lower() not in query.lower():
                query = f"{query} {original_question}"
            if step.get("target_folders"):
                folder_tokens = []
                for folder in step["target_folders"]:
                    parts = [part for part in folder.replace("\\", "/").split("/") if part]
                    folder_tokens.extend(parts)
                if folder_tokens:
                    query = f"{query} {' '.join(folder_tokens)}"
        else:
            query = step["sub_question"]
        
        # Apply Obsidian folder filtering
        filters = self._build_filters(step["target_folders"])
        
        results = []
        min_results = 3
        debug_prefix = f"[DeepThinking] Step {step.get('step_number', '?')}"
        
        if strategy == "vector":
            # Retrieve more results for reranking
            n_results = 60 if self.enable_reranking else 20
            trace(
                f"{debug_prefix} vector query",
                {"query": query, "filters": filters or None, "n_results": n_results}
            )
            results = self._query_vector(query, filters, n_results=n_results, trace_callback=trace)
            trace(f"{debug_prefix} vector output", summarize(results))

            if step.get("target_folders") and results:
                filtered_results = self._filter_results_by_target_folders(results, step["target_folders"])
                if filtered_results and len(filtered_results) >= min_results:
                    results = filtered_results
                    trace(f"{debug_prefix} vector path filter", summarize(results))

            # Fallback: If filtered search returns too few, try without filters
            if filters and len(results) < min_results:
                trace(
                    f"{debug_prefix} vector retry without filters",
                    {"reason": "too_few_results", "count": len(results)}
                )
                results = self._query_vector(query, filters=None, n_results=n_results, trace_callback=trace)
                if step.get("target_folders") and results:
                    filtered_results = self._filter_results_by_target_folders(results, step["target_folders"])
                    if filtered_results and len(filtered_results) >= min_results:
                        results = filtered_results
                trace(f"{debug_prefix} vector retry output", summarize(results))
            
        elif strategy.startswith("graph"):
            # Use 'local' mode for specific entity questions, 'global' for summaries
            mode = "global" if strategy == "graph-global" else "local"
            results = self._query_graph(query, mode=mode, trace_callback=trace)
            results = self._filter_reasoning_docs(results)
            trace(f"{debug_prefix} graph output", summarize(results))
            
        elif strategy == "hybrid":
            # True Hybrid: Combine Graph and Vector results in parallel
            n_results = 60 if self.enable_reranking else 25
            trace(
                f"{debug_prefix} hybrid query",
                {"query": query, "filters": filters or None, "n_results": n_results}
            )
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                vec_future = executor.submit(self._query_vector, query, filters, n_results, trace)
                graph_future = executor.submit(self._query_graph, query, "hybrid", trace)
                
                vec_results = vec_future.result()
                graph_results = self._filter_reasoning_docs(graph_future.result())

            if step.get("target_folders") and vec_results:
                filtered_vec = self._filter_results_by_target_folders(vec_results, step["target_folders"])
                if filtered_vec and len(filtered_vec) >= min_results:
                    vec_results = filtered_vec

            results = self._combine_hybrid_results(vec_results, graph_results)
            trace(
                f"{debug_prefix} hybrid output",
                {
                    "vector": summarize(vec_results),
                    "graph": summarize(graph_results),
                    "total": len(results)
                }
            )
            
            # Fallback: If filtered vector search returns too few, retry without filters
            if filters and len(vec_results) < min_results:
                trace(
                    f"{debug_prefix} hybrid retry without filters",
                    {"reason": "too_few_vector_results", "vector_count": len(vec_results)}
                )
                vec_results = self._query_vector(query, filters=None, n_results=n_results, trace_callback=trace)
                if step.get("target_folders") and vec_results:
                    filtered_vec = self._filter_results_by_target_folders(vec_results, step["target_folders"])
                    if filtered_vec and len(filtered_vec) >= min_results:
                        vec_results = filtered_vec
                results = self._combine_hybrid_results(vec_results, graph_results)
                trace(
                    f"{debug_prefix} hybrid retry output",
                    {"vector": summarize(vec_results), "total": len(results)}
                )
            
        elif strategy == "web":
            results, web_issue = self._query_web(query, trace_callback=trace)
            if web_issue:
                warnings = state.setdefault("warnings", [])
                if web_issue not in warnings:
                    warnings.append(web_issue)
            elif not results:
                warnings = state.setdefault("warnings", [])
                empty_msg = f"Web search returned no results for query: {query}"
                if empty_msg not in warnings:
                    warnings.append(empty_msg)
            trace(f"{debug_prefix} web output", summarize(results))

        filtered_count = len(results)
        results = self._filter_reasoning_docs(results)
        removed_count = filtered_count - len(results)
        if removed_count > 0:
            trace(
                f"{debug_prefix} filtered internal graph summaries",
                {"removed": removed_count}
            )
        
        # Apply reranking if enabled
        if self.enable_reranking and results and len(results) > 0:
            results = self.reranker.rerank(query, results, top_k=20)
            trace(f"{debug_prefix} reranked output", summarize(results))

        ranking_query = state.get("original_question") or query
        if results:
            candidate_results = self.rank_sources_for_query(
                ranking_query,
                results,
                max_results=min(len(results), 20),
                apply_relationship_limit=False,
            )
            results = self._preserve_multi_facet_query_coverage(
                ranking_query,
                candidate_results[: min(len(candidate_results), 5)],
                candidate_results,
                max_results=min(len(candidate_results), 5),
            )
            trace(f"{debug_prefix} query-shaped output", summarize(results))
            
        # [NEW] Full Content Expansion for Critical Medical Files
        # If we found a file that looks like a medical report, read the WHOLE file.
        if strategy in ["vector", "hybrid"] and results:
            if self.full_content_expansion_bytes > 0:
                if self._use_lazy_expansion_v2():
                    trace("   ℹ️ Lazy expansion deferred to synthesis", {"count": len(results)})
                else:
                    results = self._expand_full_content(results, state, trace)
            elif trace:
                trace("   ℹ️ Full file expansion disabled for small-context provider", {
                    "provider": self.llm_provider,
                    "provider_total_context_chars": self._provider_limits(self.llm_provider)[1],
                })

        return results

    @staticmethod
    def _coerce_score(value: Any, default: float = 0.0) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return default
        if score != score or score in {float("inf"), float("-inf")}:
            return default
        return score

    @staticmethod
    def _normalize_scores(docs: List[Dict[str, Any]], score_field: str = "score") -> List[float]:
        if not docs:
            return []

        values = [RetrievalSupervisor._coerce_score(doc.get(score_field, 0.0)) for doc in docs]
        min_score = min(values)
        max_score = max(values)

        if min_score == max_score:
            return [0.0 if max_score <= 0.0 else 1.0 for _ in values]

        span = max_score - min_score
        if span <= 0:
            return [0.0 for _ in values]

        return [(value - min_score) / span for value in values]

    @staticmethod
    def _get_float_env(key: str, default: float) -> float:
        value = os.getenv(key, str(default))
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _combine_hybrid_results(self, vec_results: List[Dict[str, Any]], graph_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        vector_weight = self._get_float_env("DEEP_THINKING_HYBRID_VECTOR_WEIGHT", 0.7)
        graph_weight = self._get_float_env("DEEP_THINKING_HYBRID_GRAPH_WEIGHT", 0.3)
        total_weight = vector_weight + graph_weight
        if total_weight <= 0:
            vector_weight = 0.7
            graph_weight = 0.3
            total_weight = 1.0

        vector_weight /= total_weight
        graph_weight /= total_weight

        vec_norm = self._normalize_scores(vec_results, "score")
        graph_norm = self._normalize_scores(graph_results, "score")

        for doc, norm in zip(vec_results, vec_norm):
            doc["raw_score"] = self._coerce_score(doc.get("score"))
            doc["normalized_score"] = norm
            doc["hybrid_score"] = norm * vector_weight
            doc["score"] = doc["hybrid_score"]

        for doc, norm in zip(graph_results, graph_norm):
            doc["raw_score"] = self._coerce_score(doc.get("score"))
            doc["normalized_score"] = norm
            doc["hybrid_score"] = norm * graph_weight
            doc["score"] = doc["hybrid_score"]

        return sorted(
            vec_results + graph_results,
            key=lambda doc: doc.get("score", 0.0),
            reverse=True
        )

    @staticmethod
    def _provider_limits(provider: str) -> tuple[int, int]:
        provider = (provider or "").lower()
        if provider in ("lmstudio", "mlx"):
            default_doc_chars = os.getenv("DEEP_THINKING_LMSTUDIO_BUFFER_DOC_CHARS", os.getenv("DEEP_THINKING_MLX_BUFFER_DOC_CHARS", "4000"))
            default_total_chars = os.getenv("DEEP_THINKING_LMSTUDIO_BUFFER_TOTAL_CHARS", os.getenv("DEEP_THINKING_MLX_BUFFER_TOTAL_CHARS", "18000"))

            return (
                int(os.getenv("DEEP_THINKING_LMSTUDIO_DOC_CHARS", os.getenv("DEEP_THINKING_MLX_DOC_CHARS", default_doc_chars))),
                int(os.getenv("DEEP_THINKING_LMSTUDIO_TOTAL_CONTEXT_CHARS", os.getenv("DEEP_THINKING_MLX_TOTAL_CONTEXT_CHARS", default_total_chars))),
            )

        return (
            int(os.getenv("DEEP_THINKING_DOC_CHARS", "12000")),
            int(os.getenv("DEEP_THINKING_TOTAL_CONTEXT_CHARS", "60000")),
        )

    @staticmethod
    def _full_file_expansion_limit(provider: str) -> int:
        provider = (provider or "").lower()
        per_doc_chars, total_context_chars = RetrievalSupervisor._provider_limits(provider)

        # Bypass expansion for genuinely small-context providers.
        if total_context_chars <= int(os.getenv("DEEP_THINKING_SMALL_CONTEXT_THRESHOLD_CHARS", "10000")):
            return 0

        if provider not in ("lmstudio", "mlx"):
            return int(os.getenv("DEEP_THINKING_FULL_FILE_EXPANSION_BYTES", "102400"))

        # Keep local LM Studio expansion bounded to ~3-4KB to avoid overflowing small local contexts.
        return min(4 * 1024, max(1, min(per_doc_chars, total_context_chars // 4)))

    @staticmethod
    def _is_web_url(value: str) -> bool:
        if not isinstance(value, str):
            return False
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _supported_expansion_extensions() -> set[str]:
        return {".md", ".txt", ".pdf", ".py", ".js", ".json", ".yml", ".yaml", ".sh", ".css", ".html"}

    @staticmethod
    def _expansion_cache(state: RAGState) -> Dict[Any, Dict[str, Any]]:
        return state.setdefault("_expansion_cache_v2", {})

    @staticmethod
    def _vault_root() -> Path:
        return Path(os.getenv("OBSIDIAN_VAULT_PATH", "/app/vault")).expanduser().resolve()

    @classmethod
    def _normalize_index_filepath(cls, raw_path: Any) -> str:
        text = normalize_vault_path(raw_path)
        if not text:
            return ""

        candidate = Path(text).expanduser()
        vault_root = cls._vault_root()

        if candidate.is_absolute():
            try:
                candidate = candidate.resolve().relative_to(vault_root)
            except Exception:
                return ""

        return str(PurePosixPath(*candidate.parts))

    @classmethod
    def _resolve_case_insensitive_path(cls, relative_path: str) -> Path | None:
        current = cls._vault_root()
        for part in PurePosixPath(relative_path).parts:
            try:
                children = list(current.iterdir())
            except OSError:
                return None

            exact_match = next((child for child in children if child.name == part), None)
            if exact_match is not None:
                current = exact_match
                continue

            lowered = part.lower()
            match = next((child for child in children if child.name.lower() == lowered), None)
            if match is None:
                return None
            current = match
        return current

    @classmethod
    def _resolve_expansion_target(cls, doc: Dict[str, Any]) -> Dict[str, Any] | None:
        raw_source = doc.get("filepath") or doc.get("source", "")
        if not raw_source or cls._is_web_url(raw_source):
            return None

        source = cls._normalize_index_filepath(raw_source)
        if not source:
            return None

        ext = os.path.splitext(source)[1].lower()
        if ext not in cls._supported_expansion_extensions():
            return None

        vault_root = cls._vault_root()
        resolved_path = (vault_root / source).resolve(strict=False)
        repaired = cls._resolve_case_insensitive_path(source)
        if repaired is not None:
            resolved_path = repaired.resolve(strict=False)
            try:
                source = str(PurePosixPath(*resolved_path.relative_to(vault_root).parts))
            except ValueError:
                pass

        try:
            resolved_path.relative_to(vault_root)
        except ValueError:
            logger.warning(
                "Expansion path escaped vault root raw_source=%s normalized_source=%s resolved_path=%s vault_root=%s",
                raw_source,
                source,
                resolved_path,
                vault_root,
            )
            return None

        return {
            "raw_source": str(raw_source),
            "source": source,
            "ext": ext,
            "full_path": str(resolved_path),
        }

    @staticmethod
    def _cache_key_for_target(target: Dict[str, Any]) -> tuple[Any, os.stat_result | None]:
        full_path = target["full_path"]
        source = target["source"]
        try:
            stat = os.stat(full_path)
        except FileNotFoundError:
            return (source, "missing"), None
        except OSError:
            return (source, "error"), None

        mtime_ns = getattr(stat, "st_mtime_ns", None)
        if mtime_ns is None:
            mtime_ns = int(stat.st_mtime * 1_000_000_000)
        return (source, int(mtime_ns)), stat

    @staticmethod
    def _apply_expansion_entry(doc: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
        if entry.get("status") == "ok":
            content = entry.get("content", "")
            if content:
                doc["content"] = content
                doc["is_full_content"] = True
                doc["full_content_length"] = len(content)
        return doc

    @classmethod
    def _load_full_content(
        cls,
        full_path: str,
        ext: str,
        max_size_bytes: int,
        doc: Dict[str, Any],
        trace_func,
    ) -> str:
        content = ""
        if ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(full_path)
                max_pages = 20
                text = []
                for i, page in enumerate(reader.pages):
                    if i >= max_pages:
                        break
                    text.append(page.extract_text())
                content = "\n".join(text)
                trace_func(f"   📖 Expanded PDF: {doc.get('filepath') or doc.get('source', '')}", {"pages": len(text)})
            except Exception as e:
                trace_func(
                    f"   ⚠️ PDF Read Failed: {doc.get('filepath') or doc.get('source', '')}",
                    {"error": str(e)}
                )
                content = doc.get("content", "")
        else:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(max_size_bytes)
            trace_func(
                f"   📖 Expanded File: {doc.get('filepath') or doc.get('source', '')}",
                {"length": len(content)}
            )
        return content

    @classmethod
    def estimate_expansion_bytes(
        cls,
        doc: Dict[str, Any],
        provider: str,
        max_size_bytes: int | None = None,
    ) -> int:
        target = cls._resolve_expansion_target(doc)
        if not target:
            return 0

        try:
            size_bytes = os.path.getsize(target["full_path"])
        except OSError:
            return 0

        expansion_limit = max_size_bytes if max_size_bytes is not None else cls._full_file_expansion_limit(provider)
        if expansion_limit <= 0:
            return 0
        return min(size_bytes, expansion_limit)

    @classmethod
    def expand_doc_with_cache(
        cls,
        doc: Dict[str, Any],
        state: RAGState,
        max_size_bytes: int,
        trace_func=None,
    ) -> Dict[str, Any]:
        def trace(message: str, details: Dict[str, Any] | None = None) -> None:
            if trace_func:
                trace_func(message, details)

        target = cls._resolve_expansion_target(doc)
        if not target or max_size_bytes <= 0:
            return doc

        cache = cls._expansion_cache(state)
        cache_key, stat = cls._cache_key_for_target(target)
        cached = cache.get(cache_key)
        if cached is not None:
            trace("   ♻️ Expansion cache hit", {"source": target["source"], "status": cached.get("status")})
            return cls._apply_expansion_entry(doc, cached)

        if stat is None:
            status = "missing" if cache_key[1] == "missing" else "error"
            cache[cache_key] = {"status": status}
            if status == "missing":
                logger.warning(
                    "Full-content expansion file missing raw_source=%s normalized_source=%s resolved_path=%s vault_root=%s doc_type=%s source_category=%s",
                    target.get("raw_source"),
                    target["source"],
                    target["full_path"],
                    cls._vault_root(),
                    doc.get("type"),
                    doc.get("source_category"),
                )
            else:
                logger.error(
                    "Full-content expansion path error raw_source=%s normalized_source=%s resolved_path=%s vault_root=%s doc_type=%s source_category=%s",
                    target.get("raw_source"),
                    target["source"],
                    target["full_path"],
                    cls._vault_root(),
                    doc.get("type"),
                    doc.get("source_category"),
                )
            trace(
                f"   ⚠️ Expansion Skipped: {target['source']}",
                {"status": status, "resolved_path": target["full_path"]},
            )
            return doc

        file_size = stat.st_size
        if file_size > max_size_bytes and target["ext"] != ".pdf":
            cache[cache_key] = {"status": "too_large", "size_bytes": file_size}
            trace(f"   ⚠️ File too large to expand: {target['source']}", {"size": file_size, "limit": max_size_bytes})
            return doc

        try:
            content = cls._load_full_content(
                target["full_path"],
                target["ext"],
                max_size_bytes,
                doc,
                trace,
            )
            if content:
                cache[cache_key] = {
                    "status": "ok",
                    "content": content,
                    "size_bytes": file_size,
                    "mtime_ns": cache_key[1],
                }
            else:
                cache[cache_key] = {"status": "empty", "size_bytes": file_size, "mtime_ns": cache_key[1]}
            return cls._apply_expansion_entry(doc, cache[cache_key])
        except Exception as e:
            cache[cache_key] = {"status": "error", "error": str(e)}
            logger.error(
                "Full-content expansion failed raw_source=%s normalized_source=%s resolved_path=%s vault_root=%s doc_type=%s source_category=%s error=%s",
                target.get("raw_source"),
                target["source"],
                target["full_path"],
                cls._vault_root(),
                doc.get("type"),
                doc.get("source_category"),
                e,
            )
            trace(f"   ⚠️ Expansion Failed: {target['source']}", {"error": str(e)})
            return doc

    @classmethod
    def expand_for_synthesis(
        cls,
        docs: List[Dict[str, Any]],
        state: RAGState,
        provider: str,
        trace_func=None,
        max_size_bytes: int | None = None,
        max_docs: int | None = None,
        max_total_bytes: int | None = None,
    ) -> List[Dict[str, Any]]:
        expansion_limit = max_size_bytes if max_size_bytes is not None else cls._full_file_expansion_limit(provider)
        if expansion_limit <= 0:
            return docs

        expanded_docs = 0
        expanded_total_bytes = 0
        for doc in docs:
            if max_docs is not None and expanded_docs >= max_docs:
                break

            estimated_bytes = cls.estimate_expansion_bytes(doc, provider, expansion_limit)
            if max_total_bytes is not None and estimated_bytes > 0 and expanded_total_bytes + estimated_bytes > max_total_bytes:
                if trace_func:
                    trace_func(
                        "   ⚠️ Lazy expansion byte cap reached",
                        {"expanded_total_bytes": expanded_total_bytes, "next_doc_bytes": estimated_bytes}
                    )
                break

            before = bool(doc.get("is_full_content"))
            cls.expand_doc_with_cache(doc, state, expansion_limit, trace_func=trace_func)
            if doc.get("is_full_content") and not before:
                expanded_docs += 1
                expanded_total_bytes += max(
                    estimated_bytes,
                    len(str(doc.get("content", "")).encode("utf-8", errors="ignore"))
                )

        return docs
    
    def _expand_full_content(self, results: List[Dict[str, Any]], state: RAGState, trace_func) -> List[Dict[str, Any]]:
        """
        Universal Content Expansion:
        Load full content from disk for ANY local file to ensure high-fidelity context.
        Expansion size is set dynamically from provider limits to avoid context overflow.
        """
        expanded_results = []
        max_size_bytes = self.full_content_expansion_bytes
        
        for doc in results:
            expanded_results.append(
                self.expand_doc_with_cache(doc, state, max_size_bytes, trace_func=trace_func)
            )
                
        return expanded_results
    
    def _build_filters(self, target_folders: List[str]) -> Dict[str, Any]:
        """Convert Obsidian folder paths to ChromaDB metadata filters."""
        if not target_folders:
            return {}

        def folder_filter(folder_path: str) -> Dict[str, Any]:
            parts = [part for part in folder_path.replace("\\", "/").split("/") if part]
            if not parts:
                return {}
            if len(parts) == 1:
                return {f"dir_{parts[0]}": True}
            return {"$and": [{f"dir_{part}": True} for part in parts]}

        filters = [folder_filter(folder) for folder in target_folders]
        filters = [flt for flt in filters if flt]
        if not filters:
            return {}
        if len(filters) == 1:
            return filters[0]
        return {"$or": filters}

    @staticmethod
    def _filter_results_by_target_folders(results: List[Dict[str, Any]], target_folders: List[str]) -> List[Dict[str, Any]]:
        if not results or not target_folders:
            return results
        normalized_folders = []
        for folder in target_folders:
            norm = folder.replace("\\", "/").strip()
            if not norm.endswith("/"):
                norm = f"{norm}/"
            normalized_folders.append(norm.lower())

        filtered = []
        for item in results:
            source = item.get("source") or ""
            source_norm = source.replace("\\", "/").lower()
            if any(folder in source_norm for folder in normalized_folders):
                filtered.append(item)
        return filtered
    
    def _query_vector(
        self,
        query: str,
        filters: Dict[str, Any] = None,
        n_results: int = 10,
        trace_callback=None
    ) -> List[Dict[str, Any]]:
        def trace(message: str, details: Dict[str, Any] | None = None) -> None:
            line = f"{message}"
            if details:
                line = f"{line} {details}"
            print(line)
            if trace_callback:
                trace_callback(message, details)

        retries = 2
        backoff = 0.5
        for attempt in range(retries + 1):
            try:
                trace("[DeepThinking] vector request", {"query": query, "filters": filters, "n_results": n_results, "attempt": attempt + 1})
                response = requests.post(
                    f'{self.vector_service_url}/query',
                    json={
                        "query": query,
                        "n_results": n_results,
                        "filters": filters,
                        "reranking": False,  # We do our own reranking
                        "deduplicate": True
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    # Normalize format - embedding service returns documents/metadatas/distances arrays
                    normalized = []
                    if "documents" in data:
                        documents = data.get("documents", [[]])[0]
                        metadatas = data.get("metadatas", [[]])[0]
                        distances = data.get("distances", [[]])[0]

                        for doc, meta, dist in zip(documents, metadatas, distances):
                            normalized.append({
                                "content": doc,
                                "source": meta.get("filepath", "Unknown"),
                                "filepath": meta.get("filepath", "Unknown"),
                                "filename": meta.get("filename") or os.path.basename(meta.get("filepath", "Unknown")),
                                "snippet": doc,
                                "type": "vector",
                                "source_category": "vault",
                                "source_type": "direct-excerpt",
                                "score": float(1 - dist) if dist < 1 else 0.0,  # Convert distance to similarity score
                                "tags": meta.get("tags", []),
                                "canonical_id": meta.get("canonical_id", ""),
                                "entity_type": meta.get("entity_type", ""),
                                "treatment_phase": meta.get("treatment_phase", ""),
                            })
                    elif "results" in data:
                        for item in data.get("results", []):
                            meta = item.get("metadata", {}) or {}
                            source = meta.get("file_path") or meta.get("filepath") or meta.get("source")
                            if not source:
                                source = item.get("source", "Unknown")
                            score = item.get("score")
                            normalized.append({
                                "content": item.get("text") or item.get("content") or "",
                                "source": source,
                                "filepath": source,
                                "filename": meta.get("filename") or os.path.basename(source),
                                "snippet": item.get("text") or item.get("content") or "",
                                "type": "vector",
                                "source_category": "vault",
                                "source_type": "direct-excerpt",
                                "score": float(score) if score is not None else 0.0,
                                "tags": meta.get("tags", []),
                                "canonical_id": meta.get("canonical_id", ""),
                                "entity_type": meta.get("entity_type", ""),
                                "treatment_phase": meta.get("treatment_phase", ""),
                            })
                    trace("[DeepThinking] vector response", {"status": response.status_code, "count": len(normalized)})
                    return normalized

                error_body = response.text[:500] if response.text else ""
                trace("[DeepThinking] vector error", {"status": response.status_code, "body": error_body})
            except Exception as e:
                trace("[DeepThinking] vector exception", {"error": str(e)})

            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
        return []

    def _query_graph(
        self,
        query: str,
        mode: str = "hybrid",
        trace_callback=None
    ) -> List[Dict[str, Any]]:
        def trace(message: str, details: Dict[str, Any] | None = None) -> None:
            line = f"{message}"
            if details:
                line = f"{line} {details}"
            print(line)
            if trace_callback:
                trace_callback(message, details)

        retries = 2
        backoff = 0.5
        transport_override = os.getenv(
            "DEEP_THINKING_GRAPH_TRANSPORT", ""
        ).strip().lower()
        use_internal_transport = (
            transport_override == "internal"
            or str(self.graph_service_url or "").startswith("internal://")
        )
        for attempt in range(retries + 1):
            try:
                trace("[DeepThinking] graph request", {"query": query, "mode": mode, "attempt": attempt + 1})
                if use_internal_transport:
                    from src.services.internal_graph_transport import query_networkx_graph

                    status_code, data = query_networkx_graph(
                        {
                            "query": query,
                            "mode": mode,
                            "llm_provider": self.llm_provider or None,
                            "model": self.llm_model or None,
                            "top_k": 30,
                            "chunk_top_k": 10,
                        }
                    )
                    error_body = str(data)[:500] if data else ""
                else:
                    response = requests.post(
                        f'{self.graph_service_url}/query',
                        json={
                            "query": query,
                            "mode": mode,
                            "llm_provider": self.llm_provider or None,
                            "model": self.llm_model or None,
                            "top_k": 30,
                            "chunk_top_k": 10
                        },
                        timeout=300  # Increased from 180 to 300 seconds
                    )
                    status_code = response.status_code
                    data = response.json() if response.content else {}
                    error_body = response.text[:500] if response.text else ""

                if status_code == 200:
                    if isinstance(data, str):
                        results = [self._graph_reasoning_doc(data, mode)] if str(data).strip() else []
                        trace(
                            "[DeepThinking] graph response",
                            {"status": status_code, "count": len(results), "internal_reasoning": bool(results)}
                        )
                        return results
                    elif isinstance(data, dict):
                        results = []
                        # Extract real sources from the Graph/LightRAG payload
                        sources = data.get("sources", [])
                        if sources:
                            for src in sources[:15]:
                                filepath = src.get("filepath") or src.get("file_path") or src.get("filename") or "Knowledge Graph"
                                is_web = self._is_web_url(filepath)
                                results.append({
                                    "content": src.get("snippet", ""),
                                    "source": filepath,
                                    "filepath": filepath,
                                    "filename": src.get("filename") or src.get("title") or filepath,
                                    "snippet": src.get("snippet", ""),
                                    "type": "graph",
                                    "source_category": "web" if is_web else "vault",
                                    "source_type": src.get("source_type") or ("web-result" if is_web else "entity-context"),
                                    "relevance": float(src.get("relevance", 100)) if "relevance" in src else 100.0,
                                    "score": float(src.get("relevance", 100)) / 100.0 if "relevance" in src else 1.0,
                                    "tags": src.get("tags", []),
                                    "canonical_id": src.get("canonical_id", ""),
                                    "entity_type": src.get("entity_type", ""),
                                    "treatment_phase": src.get("treatment_phase", ""),
                                })
                                
                        content = data.get("answer") or data.get("response")
                        if content and not results:
                            results.append(self._graph_reasoning_doc(content, mode))

                        if results:
                            trace("[DeepThinking] graph response", {"status": status_code, "count": len(results)})
                            return results
                    return []

                trace("[DeepThinking] graph error", {"status": status_code, "body": error_body})
            except requests.exceptions.Timeout:
                trace("[DeepThinking] graph timeout", {"query": f"{query[:50]}..."})
            except Exception as e:
                trace("[DeepThinking] graph exception", {"error": str(e)})

            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
        return []

    def _query_web(self, query: str, n_results: int = 5, trace_callback=None) -> tuple[List[Dict[str, Any]], str | None]:
        def trace(message: str, details: Dict[str, Any] | None = None) -> None:
            line = f"{message}"
            if details:
                line = f"{line} {details}"
            print(line)
            if trace_callback:
                trace_callback(message, details)

        if not WEB_SEARCH_AVAILABLE:
            reason = "Tavily web search is unavailable: tavily-python not installed."
            trace("[DeepThinking] web disabled", {"reason": reason})
            return [], reason
            
        api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
        if not api_key:
            reason = "Tavily web search is unavailable: TAVILY_API_KEY not set."
            trace("[DeepThinking] web disabled", {"reason": reason})
            return [], reason

        try:
            trace("[DeepThinking] web request", {"query": query, "n_results": n_results})
            tavily_client = TavilyClient(api_key=api_key)
            # Use 'search' method with image support
            response = tavily_client.search(
                query, 
                search_depth="advanced", 
                max_results=n_results,
                include_images=True  # Enable image retrieval
            )
            
            formatted_results = []
            images = response.get('images', [])
            seen_urls = set()
            
            if 'results' in response:
                for i, res in enumerate(response['results']):
                    raw_url = str(res.get("url") or "").strip()
                    canonical_url = canonicalize_web_url(raw_url) or raw_url
                    if canonical_url in seen_urls:
                        continue
                    seen_urls.add(canonical_url)
                    doc = {
                        "content": f"Title: {res['title']}\nSnippet: {res['content']}",
                        "source": canonical_url,
                        "filepath": canonical_url,
                        "url": canonical_url,
                        "canonical_url": canonical_url,
                        "raw_url": raw_url,
                        "filename": res['title'],
                        "title": res['title'],
                        "snippet": res['content'],
                        "type": "web",
                        "source_category": "web",
                        "source_type": "web-result",
                        "relevance": float(res.get('score', 1.0)) * 100.0,
                        "score": res.get('score', 1.0)
                    }
                    # Add first 2 images to first result if available
                    if i == 0 and images:
                        doc['images'] = images[:2]
                    formatted_results.append(doc)
            
            # If we got images but no results, log it
            if images and not formatted_results:
                trace("[DeepThinking] web no text results", {"images": len(images)})

            trace("[DeepThinking] web response", {"count": len(formatted_results)})
            return formatted_results, None
        except Exception as e:
            reason = f"Tavily web search failed: {str(e)}"
            trace("[DeepThinking] web error", {"error": reason})

            return [], reason
