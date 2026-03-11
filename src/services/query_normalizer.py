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
    (re.compile(r"how do\s+(?P<left>.+?)\s+relate to\s+(?P<right>.+)", re.IGNORECASE), "conceptual relationship"),
    (re.compile(r"what is the relationship between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)", re.IGNORECASE), "relationship"),
    (re.compile(r"how are\s+(?P<left>.+?)\s+and\s+(?P<right>.+?)\s+related", re.IGNORECASE), "relationship"),
    (re.compile(r"how are\s+(?P<left>.+?)\s+connected to\s+(?P<right>.+)", re.IGNORECASE), "connected to"),
    (re.compile(r"how is\s+(?P<left>.+?)\s+connected to\s+(?P<right>.+)", re.IGNORECASE), "connected to"),
    (re.compile(r"what is the connection between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)", re.IGNORECASE), "connection between"),
    (re.compile(r"what is the link between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)", re.IGNORECASE), "link between"),
    (re.compile(r"compare\s+(?P<left>.+?)\s+(?:with|and)\s+(?P<right>.+)", re.IGNORECASE), "compare"),
    (re.compile(r"difference between\s+(?P<left>.+?)\s+and\s+(?P<right>.+)", re.IGNORECASE), "difference between"),
)

SUMMARY_PATTERNS = (
    re.compile(r"\b(?:provide|give|write|create)\s+(?:a\s+)?(?:point\s+form\s+|bullet(?:-point)?\s+)?summary\s+of\s+(?P<topic>.+)$", re.IGNORECASE),
    re.compile(r"\bsummarize\s+(?P<topic>.+)$", re.IGNORECASE),
    re.compile(r"\bsummary\s+of\s+(?P<topic>.+)$", re.IGNORECASE),
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


def _extract_relation_match(query: str) -> tuple[List[str], List[Set[str]], List[str]]:
    normalized = re.sub(r"\s+", " ", str(query or "").strip())
    for pattern, relation in RELATION_PATTERNS:
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
            return entities, facets, [relation]
    return [], [], []


def extract_query_facets(query: str) -> List[Set[str]]:
    _entities, facets, _relations = _extract_relation_match(query)
    return facets


def has_multi_facet_query(query: str) -> bool:
    return len(extract_query_facets(query)) >= 2


def is_relation_style_query(query: str) -> bool:
    return has_multi_facet_query(query)


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
    entities, facets, relations = _extract_relation_match(clean_query)

    if relations and len(entities) >= 2:
        clean_query = f"relationship between {entities[0]} and {entities[1]}"
        intent = "relationship"
        must_terms = [entity for entity in entities if entity]
    else:
        summary_focus = _summary_focus_text(clean_query)
        intent = "summary" if summary_focus else "lookup"
        if summary_focus:
            entities = [clean_entity_phrase(summary_focus)] if clean_entity_phrase(summary_focus) else []
        else:
            entities = []
        must_terms = list(entities) if entities else query_terms(clean_query)

    return {
        "original_query": original_query,
        "clean_query": clean_query,
        "intent": intent,
        "entities": entities,
        "relations": relations,
        "facets": [sorted(facet) for facet in facets],
        "must_terms": must_terms,
    }
