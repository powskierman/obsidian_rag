import re
from typing import Any, Dict, List, Set


QUERY_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "between", "by", "connection",
    "does", "for", "how", "in", "is", "it", "of", "on", "or", "related",
    "relationship", "the", "to", "what", "with",
}

RELATION_STOPWORDS = {
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
    "device",
    "devices",
    "network",
    "setup",
    "system",
}

RELATION_PATTERNS = (
    (re.compile(r"how do\s+(?P<left>.+?)\s+relate to\s+(?P<right>.+)", re.IGNORECASE), "conceptual relationship", "relationship"),
    (re.compile(r"what is the relationship between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)", re.IGNORECASE), "relationship", "relationship"),
    (re.compile(r"how are\s+(?P<left>.+?)\s+and\s+(?P<right>.+?)\s+related", re.IGNORECASE), "relationship", "relationship"),
    (re.compile(r"how are\s+(?P<left>.+?)\s+connected to\s+(?P<right>.+)", re.IGNORECASE), "connected to", "relationship"),
    (re.compile(r"how is\s+(?P<left>.+?)\s+connected to\s+(?P<right>.+)", re.IGNORECASE), "connected to", "relationship"),
    (re.compile(r"what is the connection between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)", re.IGNORECASE), "connection between", "relationship"),
    (re.compile(r"what is the link between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)", re.IGNORECASE), "link between", "relationship"),
    (re.compile(r"compare\s+(?P<left>.+?)\s+(?:with|and)\s+(?P<right>.+)", re.IGNORECASE), "compare", "comparison"),
    (re.compile(r"(?:what is )?the difference between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)", re.IGNORECASE), "difference between", "comparison"),
)

SUMMARY_PATTERNS = (
    re.compile(r"\b(?:provide|give|write|create)\s+(?:a\s+)?(?:point\s+form\s+|bullet(?:-point)?\s+)?summary\s+of\s+(?P<topic>.+)$", re.IGNORECASE),
    re.compile(r"\bsummarize\s+(?P<topic>.+)$", re.IGNORECASE),
    re.compile(r"\bsummary\s+of\s+(?P<topic>.+)$", re.IGNORECASE),
)

FACET_STOPWORDS = QUERY_STOPWORDS | RELATION_STOPWORDS | {
    "all",
    "analyse",
    "analyze",
    # "assessment" intentionally omitted — carries meaning in facets like "risk assessment"
    "assess",
    "describe",
    # "detail" / "details" intentionally omitted — "detail" distinguishes facets in structured queries
    "evaluate",
    "evaluation",
    "explain",
    "give",
    "include",
    "interpret",
    "interpretation",
    "look",
    "me",
    "my",
    "note",
    "notes",
    "our",
    "overview",
    "please",
    "provide",
    "review",
    "show",
    "summarize",
    "summary",
    "tell",
    "through",
    "vault",
    "walk",
    "your",
}

_FACET_SEPARATOR_PATTERN = re.compile(r"\s*(?:,|;|\n)\s*")
_FACET_CONJUNCTION_PATTERN = re.compile(r"\s+\band\b\s+", re.IGNORECASE)
_LEADING_FACET_WRAPPER_PATTERN = re.compile(
    r"^\s*(?:please\s+)?(?:review|analy[sz]e|assess|evaluate|summarize|explain|show|give|provide|tell me about|walk me through)\s+",
    re.IGNORECASE,
)
_TRAILING_FACET_WRAPPER_PATTERN = re.compile(
    r"\s+(?:and\s+)?(?:give|provide|share|offer|include)\s+(?:your\s+)?"
    r"(?:assessment|analysis|summary|overview|interpretation|view)\b.*$",
    re.IGNORECASE,
)


def clean_entity_phrase(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip(" \t\r\n\"'`()[]{}.,;:!?"))
    text = re.sub(r"^(the|a|an|my|your|our)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(?:notes?|docs?|documents?|files?)$", "", text, flags=re.IGNORECASE)
    return text.strip()


def query_terms(query: str, *, stopwords: Set[str] | None = None) -> List[str]:
    terms: List[str] = []
    seen: Set[str] = set()
    effective_stopwords = stopwords or QUERY_STOPWORDS
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{1,}", str(query or "").lower()):
        cleaned = token.strip("._-")
        if len(cleaned) < 2 or cleaned in effective_stopwords:
            continue
        if cleaned not in seen:
            seen.add(cleaned)
            terms.append(cleaned)
    return terms


def deterministic_clean_query(query: str) -> str:
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


def _extract_relation_match(query: str) -> tuple[List[str], List[Set[str]], List[str], str]:
    normalized = re.sub(r"\s+", " ", str(query or "").strip())
    for pattern, relation, intent in RELATION_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        entities = [
            clean_entity_phrase(match.group("left")),
            clean_entity_phrase(match.group("right")),
        ]
        entities = [entity for entity in entities if entity]
        facets = [set(query_terms(entity, stopwords=RELATION_STOPWORDS)) for entity in entities]
        facets = [facet for facet in facets if facet]
        if len(entities) >= 2 and len(facets) >= 2:
            return entities, facets, [relation], intent
    return [], [], [], "lookup"


def _facet_terms(text: str) -> list[str]:
    terms = query_terms(text, stopwords=FACET_STOPWORDS)
    expanded: list[str] = []
    seen: set[str] = set()
    for term in terms:
        candidates = [term]
        if len(term) > 4 and term.endswith("s"):
            candidates.append(term[:-1])
        for candidate in candidates:
            cleaned = candidate.strip("._-")
            if len(cleaned) < 2 or cleaned in seen:
                continue
            seen.add(cleaned)
            expanded.append(cleaned)
    return expanded


def _extract_generic_query_facets(query: str) -> List[Set[str]]:
    normalized = re.sub(r"\s+", " ", str(query or "").strip())
    if not normalized:
        return []

    separator_count = normalized.count(",") + normalized.count(";")
    conjunction_count = len(re.findall(r"\band\b", normalized, flags=re.IGNORECASE))
    if separator_count == 0 and conjunction_count < 2:
        return []

    working = _LEADING_FACET_WRAPPER_PATTERN.sub("", normalized).strip()
    working = _TRAILING_FACET_WRAPPER_PATTERN.sub("", working).strip(" ?.!,:;")
    if not working:
        return []

    raw_fragments: list[str] = []
    primary_fragments = [
        fragment.strip()
        for fragment in _FACET_SEPARATOR_PATTERN.split(working)
        if fragment.strip()
    ]
    for fragment in primary_fragments or [working]:
        sub_fragments = [
            sub.strip()
            for sub in _FACET_CONJUNCTION_PATTERN.split(fragment)
            if sub.strip()
        ]
        if separator_count > 0 and len(sub_fragments) > 1:
            raw_fragments.extend(sub_fragments)
        else:
            raw_fragments.append(fragment)

    facets: List[Set[str]] = []
    seen_keys: set[tuple[str, ...]] = set()
    for fragment in raw_fragments:
        terms = _facet_terms(fragment)
        if not terms:
            continue
        facet = set(terms)
        key = tuple(sorted(facet))
        if not facet or key in seen_keys:
            continue
        seen_keys.add(key)
        facets.append(facet)

    return facets if len(facets) >= 2 else []


def extract_query_facets(query: str) -> List[Set[str]]:
    _entities, facets, _relations, _intent = _extract_relation_match(query)
    if facets:
        return facets
    return _extract_generic_query_facets(query)


def has_multi_facet_query(query: str) -> bool:
    return len(extract_query_facets(query)) >= 2


def is_relation_style_query(query: str) -> bool:
    _entities, facets, _relations, intent = _extract_relation_match(query)
    return len(facets) >= 2 and intent == "relationship"


def _summary_focus_text(query: str) -> str:
    normalized = re.sub(r"\s+", " ", str(query or "").strip()).rstrip("?.! ")
    for pattern in SUMMARY_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        topic = str(match.group("topic") or "").strip(" \"'`")
        if topic:
            return topic
    return ""


def normalize_query_structure(query: str) -> Dict[str, Any]:
    original_query = re.sub(r"\s+", " ", str(query or "").strip())
    clean_query = deterministic_clean_query(original_query)
    entities, facets, relations, intent = _extract_relation_match(clean_query)

    if relations and len(entities) >= 2:
        if intent == "comparison":
            clean_query = f"compare {entities[0]} and {entities[1]}"
        else:
            clean_query = f"relationship between {entities[0]} and {entities[1]}"
        must_terms = [entity for entity in entities if entity]
    else:
        facets = _extract_generic_query_facets(clean_query)
        summary_focus = _summary_focus_text(clean_query)
        intent = "summary" if summary_focus else "lookup"
        if summary_focus:
            entities = [clean_entity_phrase(summary_focus)] if clean_entity_phrase(summary_focus) else []
        else:
            entities = []
        if entities:
            must_terms = list(entities)
        elif facets:
            must_terms = []
            seen_terms: set[str] = set()
            for facet in facets:
                for term in sorted(facet):
                    if term in seen_terms:
                        continue
                    seen_terms.add(term)
                    must_terms.append(term)
        else:
            must_terms = query_terms(clean_query)

    return {
        "original_query": original_query,
        "clean_query": clean_query,
        "intent": intent,
        "entities": entities,
        "relations": relations,
        "facets": [sorted(facet) for facet in facets],
        "must_terms": must_terms,
    }
