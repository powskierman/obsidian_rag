"""Generic query intent and scope inference helpers.

This module is domain-agnostic: it infers broad intent and optional dynamic
scope prefixes from query text and retrieved source distributions.
"""

from __future__ import annotations

import re
from collections import Counter

GLOBAL_SCOPE_HINTS = (
    "all notes",
    "entire vault",
    "whole vault",
    "across all notes",
    "across the vault",
    "everything",
    "any note",
)

META_INTENT_HINTS = (
    "architecture",
    "implementation",
    "workflow",
    "pipeline",
    "index",
    "indexing",
    "schema",
    "taxonomy",
    "template",
    "runbook",
    "guide",
    "setup",
    "deployment",
    "api",
    "service",
    "graph",
    "retriever",
    "rag",
)

QUERY_SCOPE_PATTERN = re.compile(r"\b([A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+){1,4})\b")
INLINE_TAG_PATTERN = re.compile(r"(?<!\w)#([A-Za-z0-9][A-Za-z0-9/_-]*)")


def normalize_text(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(text or "").lower())
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_path(path: str) -> str:
    clean = str(path or "").replace("\\", "/").strip()
    if clean.startswith("/app/vault/"):
        clean = clean[len("/app/vault/") :]
    return clean.lstrip("/")


def normalize_scope_prefix(prefix: str) -> str:
    clean = normalize_path(prefix).strip()
    if not clean:
        return ""
    if "/" not in clean:
        return f"{clean.rstrip('/')}/"

    parts = [part for part in clean.split("/") if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return f"{parts[0]}/"
    if len(parts) >= 2 and "." in parts[-1]:
        parts = parts[:-1]
    if not parts:
        return ""
    return "/".join(parts) + "/"


def extract_query_scope_prefixes(query_text: str, max_prefixes: int = 3) -> list[str]:
    prefixes: list[str] = []
    for token in QUERY_SCOPE_PATTERN.findall(str(query_text or "")):
        lower = token.lower()
        if lower.startswith(("http/", "https/", "www/")):
            continue
        prefix = normalize_scope_prefix(token)
        if not prefix:
            continue
        if prefix not in prefixes:
            prefixes.append(prefix)
        if len(prefixes) >= max_prefixes:
            break
    return prefixes


def _extract_path_prefixes(text: str) -> list[str]:
    prefixes: list[str] = []
    for token in QUERY_SCOPE_PATTERN.findall(str(text or "")):
        lower = token.lower()
        if lower.startswith(("http/", "https/", "www/")):
            continue
        prefix = normalize_scope_prefix(token)
        if prefix and prefix not in prefixes:
            prefixes.append(prefix)
    return prefixes


def _extract_tags(text: str) -> list[str]:
    tags: list[str] = []
    for match in INLINE_TAG_PATTERN.findall(str(text or "")):
        clean = str(match or "").strip().lower()
        if not clean:
            continue
        value = f"#{clean}"
        if value not in tags:
            tags.append(value)
    return tags


def extract_constraint_filters(query_text: str) -> dict:
    include_prefixes: list[str] = []
    exclude_prefixes: list[str] = []
    tags = _extract_tags(query_text)

    lines = [line.strip() for line in str(query_text or "").splitlines() if line.strip()]
    normalized_text = normalize_text(query_text)
    strict_scope = "scope constraints hard" in normalized_text

    for line in lines:
        lower = normalize_text(line)
        line_prefixes = _extract_path_prefixes(line)
        if not line_prefixes:
            continue
        if any(marker in lower for marker in ("exclude", "omit", "avoid", "except")):
            for prefix in line_prefixes:
                if prefix not in exclude_prefixes:
                    exclude_prefixes.append(prefix)
            continue
        if any(marker in lower for marker in ("only", "under", "prioritize", "scope")):
            for prefix in line_prefixes:
                if prefix not in include_prefixes:
                    include_prefixes.append(prefix)

    output: dict = {}
    if include_prefixes:
        output["path_prefixes"] = include_prefixes
    if exclude_prefixes:
        output["exclude_path_prefixes"] = exclude_prefixes
    if tags:
        output["tags"] = tags
    if strict_scope:
        output["strict_scope"] = True
    return output


def merge_constraint_filters(base_filters: dict | None, constraint_filters: dict | None) -> dict:
    output = dict(base_filters or {})
    constraints = dict(constraint_filters or {})

    def _merge_list(key: str) -> None:
        existing = output.get(key, [])
        incoming = constraints.get(key, [])
        merged: list[str] = []
        for value in list(existing if isinstance(existing, list) else []) + list(
            incoming if isinstance(incoming, list) else []
        ):
            clean = str(value).strip()
            if not clean:
                continue
            if key in {"path_prefixes", "exclude_path_prefixes"}:
                clean = normalize_scope_prefix(clean)
            elif key == "tags":
                clean = clean.lower()
                if not clean.startswith("#"):
                    clean = f"#{clean}"
            if clean and clean not in merged:
                merged.append(clean)
        if merged:
            output[key] = merged

    for key in ("path_prefixes", "exclude_path_prefixes", "tags"):
        _merge_list(key)

    if bool(constraints.get("strict_scope", False)):
        output["strict_scope"] = True
    return output


def _has_meta_intent(normalized_query: str) -> bool:
    hits = sum(1 for marker in META_INTENT_HINTS if marker in normalized_query)
    return hits >= 2


def infer_intent_scope(query_text: str, filters: dict | None = None) -> dict:
    normalized_query = normalize_text(query_text)
    filter_prefixes = []
    raw_filter_prefixes = (filters or {}).get("path_prefixes", [])
    for prefix in raw_filter_prefixes if isinstance(raw_filter_prefixes, list) else []:
        normalized = normalize_scope_prefix(str(prefix))
        if normalized and normalized not in filter_prefixes:
            filter_prefixes.append(normalized)

    query_prefixes = extract_query_scope_prefixes(query_text)
    has_global_scope = any(hint in normalized_query for hint in GLOBAL_SCOPE_HINTS)
    meta_intent = _has_meta_intent(normalized_query)
    explicit_scope = bool(filter_prefixes) or bool(query_prefixes)
    allow_meta_sources = bool(meta_intent or has_global_scope)

    return {
        "normalized_query": normalized_query,
        "has_global_scope": has_global_scope,
        "meta_intent": meta_intent,
        "allow_meta_sources": allow_meta_sources,
        "explicit_scope": explicit_scope,
        "filter_scope_prefixes": filter_prefixes,
        "query_scope_prefixes": query_prefixes,
        "autoscope_enabled": not explicit_scope and not allow_meta_sources,
    }


def source_matches_scope_prefixes(filepath: str, scope_prefixes: list[str] | None) -> bool:
    prefixes = [normalize_scope_prefix(prefix) for prefix in (scope_prefixes or [])]
    prefixes = [prefix for prefix in prefixes if prefix]
    if not prefixes:
        return True
    clean_path = normalize_path(filepath).lower()
    return any(clean_path.startswith(prefix.lower()) for prefix in prefixes)


def infer_scope_prefixes_from_sources(
    sources: list[dict],
    *,
    min_sources: int = 3,
    dominance_threshold: float = 0.68,
) -> list[str]:
    valid_paths = [normalize_path(str(src.get("filepath", ""))) for src in sources if isinstance(src, dict)]
    valid_paths = [path for path in valid_paths if path and "/" in path]
    if len(valid_paths) < min_sources:
        return []

    level1_counts: Counter[str] = Counter()
    level2_counts: Counter[str] = Counter()
    for path in valid_paths:
        parts = [part for part in path.split("/") if part]
        if len(parts) < 2:
            continue
        level1 = f"{parts[0]}/"
        level2 = f"{parts[0]}/{parts[1]}/"
        level1_counts[level1] += 1
        level2_counts[level2] += 1

    total = sum(level2_counts.values())
    if total <= 0:
        return []

    best_l2, best_l2_count = level2_counts.most_common(1)[0]
    if (best_l2_count / total) >= dominance_threshold:
        return [best_l2]

    total_l1 = sum(level1_counts.values())
    if total_l1 <= 0:
        return []
    best_l1, best_l1_count = level1_counts.most_common(1)[0]
    if (best_l1_count / total_l1) >= dominance_threshold:
        return [best_l1]
    return []


def apply_scope_prefixes_to_filters(
    filters: dict | None,
    scope_prefixes: list[str] | None,
    *,
    keep_existing: bool = True,
) -> dict:
    output = dict(filters or {})
    incoming = [normalize_scope_prefix(prefix) for prefix in (scope_prefixes or [])]
    incoming = [prefix for prefix in incoming if prefix]

    existing = output.get("path_prefixes", []) if keep_existing else []
    existing_norm = [normalize_scope_prefix(prefix) for prefix in existing if str(prefix).strip()]
    existing_norm = [prefix for prefix in existing_norm if prefix]

    merged: list[str] = []
    for prefix in existing_norm + incoming:
        if prefix not in merged:
            merged.append(prefix)

    if merged:
        output["path_prefixes"] = merged
    elif "path_prefixes" in output:
        output.pop("path_prefixes", None)
    return output


def gate_sources_by_scope(
    sources: list[dict],
    scope_prefixes: list[str] | None,
    *,
    min_in_scope: int = 3,
    preserve_out_of_scope: int = 1,
) -> list[dict]:
    if not scope_prefixes:
        return sources
    in_scope: list[dict] = []
    out_scope: list[dict] = []
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        if source_matches_scope_prefixes(str(source.get("filepath", "")), scope_prefixes):
            in_scope.append(source)
        else:
            out_scope.append(source)

    if len(in_scope) < min_in_scope:
        return sources
    if preserve_out_of_scope <= 0:
        return in_scope
    return in_scope + out_scope[:preserve_out_of_scope]


def scope_alignment_ratio(sources: list[dict], scope_prefixes: list[str] | None) -> float:
    if not scope_prefixes or not sources:
        return 1.0
    total = 0
    matched = 0
    for source in sources:
        if not isinstance(source, dict):
            continue
        total += 1
        if source_matches_scope_prefixes(str(source.get("filepath", "")), scope_prefixes):
            matched += 1
    if total <= 0:
        return 1.0
    return matched / total
