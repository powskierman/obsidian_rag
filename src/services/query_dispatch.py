"""Query dispatch — canonical shape for the 3-mode × N-source query API.

Replaces the 500-line if/elif chain in api_gateway.py (~3560–4200) with a
single normalize → dispatch → aggregate path. Legacy mode names stay accepted
via LEGACY_MODE_MAP for one deprecation window.

User-facing mode mapping
------------------------
    Legacy name     →   Canonical mode    depth       sources
    -----------         ---------------   --------    -----------
    vector          →   ask               —           [vault]
    mempalace       →   ask               —           [mempalace]
    cascading       →   research          staged      [vault]
    vault_review    →   research          full        [vault]
    deep-thinking   →   investigate       —           [vault, web]   (WS endpoint)

`research` supports `depth="auto"` which delegates to the classifier at
api_gateway._is_comprehensive_vault_review_query — 88% hit rate on the
eval set, all failures under-route (safe). Depth is exposed as an override
so users can bump it when auto gives a shallow answer.

This module is dispatch-only. It does not own retrieval, synthesis, or
network I/O — it pulls from existing api_gateway helpers so behavior stays
byte-for-byte identical during the migration window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Optional

import httpx

# -----------------------------------------------------------------------------
# Canonical types
# -----------------------------------------------------------------------------

Mode = Literal["ask", "research", "investigate"]
Depth = Literal["auto", "shallow", "staged", "full"]
Source = Literal["vault", "mempalace", "web"]


@dataclass(frozen=True)
class CanonicalQuery:
    """Normalized query shape consumed by the dispatch layer.

    Callers build this via `normalize_legacy_request()` or directly from the
    new API contract. Downstream dispatch never sees legacy mode strings.
    """

    query: str
    mode: Mode
    depth: Depth = "auto"                     # ignored unless mode == "research"
    sources: tuple[Source, ...] = ("vault",)  # union queried in parallel
    max_results: int = 10
    llm_provider: str = "ollama"
    model: str = ""
    brief_concept_index: bool = True
    web_search: bool = False                  # legacy toggle, now implicit via sources
    llm_knowledge: bool = False
    system_prompt: Optional[str] = None
    relevance_threshold: float = 0.0
    distance_threshold: Optional[float] = None
    filters: dict = field(default_factory=dict)
    entities_mode: str = "hybrid"


# -----------------------------------------------------------------------------
# Legacy alias map
# -----------------------------------------------------------------------------

# Keys are the literal mode strings older clients send. Values are the canonical
# projection. `auto_routed_to_full` flags a runtime promotion (cascading →
# vault_review for comprehensive queries); we preserve that behavior inside
# `_run_research` with `depth="auto"`.
LEGACY_MODE_MAP: dict[str, dict[str, Any]] = {
    "vector":       {"mode": "ask",         "sources": ("vault",),     "depth": "shallow"},
    "mempalace":    {"mode": "ask",         "sources": ("mempalace",), "depth": "shallow"},
    "cascading":    {"mode": "research",    "sources": ("vault",),     "depth": "auto"},
    "vault_review": {"mode": "research",    "sources": ("vault",),     "depth": "full"},
}

# Legacy mode names that were never valid production modes but might leak from
# very old clients. These must 400 with a helpful message — do not project
# them onto canonical values or we'll silently change behavior.
DEPRECATED_UNSUPPORTED_MODES: frozenset[str] = frozenset({
    "graph", "networkx", "lightrag",
    "notes", "entities", "notes+vector", "entities+vector",
    "dual-graph", "hybrid",
})

# Modes accepted on the REST /query endpoint. `investigate` is WS-only.
REST_ACCEPTED_MODES: frozenset[Mode] = frozenset({"ask", "research"})


class UnsupportedMode(ValueError):
    """Raised when a client sends a mode name we can't map."""


def normalize_legacy_request(
    raw_mode: str,
    *,
    explicit_depth: Optional[Depth] = None,
    explicit_sources: Optional[tuple[Source, ...]] = None,
    web_search_toggle: bool = False,
) -> tuple[Mode, Depth, tuple[Source, ...], Optional[str]]:
    """Project a legacy request onto the canonical shape.

    Returns: (mode, depth, sources, deprecation_header_value)

    The deprecation header goes back to the caller as `X-Deprecated-Mode: <raw>`
    so we can measure migration progress from access logs without breaking
    anyone. Returns None for that field when the caller already used a
    canonical mode name.
    """
    normalized_raw = (raw_mode or "").strip().lower()

    # Already canonical? honor explicit overrides, skip deprecation header.
    if normalized_raw in ("ask", "research", "investigate"):
        mode: Mode = normalized_raw  # type: ignore[assignment]
        depth: Depth = explicit_depth or ("auto" if mode == "research" else "shallow")
        sources = explicit_sources or (("vault", "web") if web_search_toggle else ("vault",))
        return mode, depth, sources, None

    # Legacy path.
    spec = LEGACY_MODE_MAP.get(normalized_raw)
    if spec is None:
        # Include both canonical and legacy names in the error so older tests
        # and clients both see a message they recognize during deprecation.
        raise UnsupportedMode(
            f"Unsupported mode '{raw_mode}'. "
            "Use one of: ask, research (canonical) or vector, cascading, vault_review, mempalace (legacy). "
            "For investigate / deep research, use WS /api/v1/deep-research."
        )

    mode = spec["mode"]
    depth = explicit_depth or spec.get("depth", "auto")
    sources = explicit_sources or spec["sources"]

    # Legacy `web_search=true` toggle folds into the source set.
    if web_search_toggle and "web" not in sources:
        sources = sources + ("web",)

    return mode, depth, sources, normalized_raw


# -----------------------------------------------------------------------------
# Dispatch skeleton
#
# These are the three entry points that replace the dispatch chain in
# api_gateway.py. Each delegates to existing helpers so we can migrate
# incrementally without rewriting retrieval/synthesis.
#
# During the migration, `handle_query()` is called from api_gateway.py's
# /api/v1/query handler AFTER normalization. The legacy if-chain is deleted
# in one go; all mode-specific logic lives here or in the helpers we call.
# -----------------------------------------------------------------------------

# Type alias for the retrieval helpers we'll inject (api_gateway functions).
# Keeping them as callables avoids a circular import and makes the module
# unit-testable without the FastAPI stack.
class Dispatchers:
    """Bag of retrieval/synthesis helpers owned by api_gateway.py.

    Populated once at app startup and passed to `handle_query()`. This is the
    seam that lets us migrate without a big-bang rewrite — each helper keeps
    its current implementation, dispatch just reorganizes the routing.
    """

    def __init__(
        self,
        *,
        vault_vector_retrieve: Callable[..., Awaitable[list[dict]]],
        vault_cascading_retrieve: Callable[..., Awaitable[list[dict]]],
        vault_review_retrieve: Callable[..., Awaitable[list[dict]]],
        mempalace_retrieve: Callable[..., Awaitable[list[dict]]],
        web_retrieve: Callable[..., Awaitable[list[dict]]],
        synthesize: Callable[..., Awaitable[dict]],
        classify_comprehensive: Callable[[str], bool],
        extract_query_context: Callable[..., tuple],
    ) -> None:
        self.vault_vector_retrieve = vault_vector_retrieve
        self.vault_cascading_retrieve = vault_cascading_retrieve
        self.vault_review_retrieve = vault_review_retrieve
        self.mempalace_retrieve = mempalace_retrieve
        self.web_retrieve = web_retrieve
        self.synthesize = synthesize
        self.classify_comprehensive = classify_comprehensive
        self.extract_query_context = extract_query_context


async def handle_query(
    q: CanonicalQuery,
    deps: Dispatchers,
    client: httpx.AsyncClient,
) -> dict:
    """Single entry point replacing the mode if-chain in api_gateway.py.

    Caller (api_gateway.py:/api/v1/query) responsibilities:
        1. Parse request body → raw_mode, raw_depth, raw_sources, toggles
        2. Call `normalize_legacy_request()` — get canonical mode/depth/sources
        3. Build `CanonicalQuery` with normalized fields + shared context
           (parsed filters, extracted entities, mem0 context, etc.)
        4. `await handle_query(q, deps, client)` → response dict
        5. If deprecation_header_value was returned, set X-Deprecated-Mode header
    """
    if q.mode == "investigate":
        # REST callers should be using WS for this. Mirrors existing 400 at
        # api_gateway.py:3584.
        raise UnsupportedMode(
            "Mode 'investigate' is served via WebSocket /api/v1/deep-research."
        )

    if q.mode == "ask":
        return await _run_ask(q, deps, client)

    if q.mode == "research":
        return await _run_research(q, deps, client)

    raise UnsupportedMode(f"Unknown canonical mode: {q.mode!r}")


async def _run_ask(
    q: CanonicalQuery,
    deps: Dispatchers,
    client: httpx.AsyncClient,
) -> dict:
    """Shallow single-pass retrieval + terse synthesis.

    Replaces:
      - Pure-vector branch at api_gateway.py:4109-~4230
      - Pure-mempalace branch at api_gateway.py:4038-4085

    Behavior: one retrieval call per selected source, union sources, one
    synthesis pass with `brief_concept_index=q.brief_concept_index`.
    """
    sources = await _gather_sources(q, deps, client, staged=False)

    if not sources:
        return _empty_response(q, label="ask")

    synth = await deps.synthesize(
        query=q.query,
        sources=sources,
        llm_provider=q.llm_provider,
        model=q.model,
        brief_concept_index=q.brief_concept_index,
    )

    return {
        "query": q.query,
        "mode": "ask",
        "sources_selected": list(q.sources),
        "answer": synth.get("answer", "") if isinstance(synth, dict) else str(synth),
        "sources": sources,
    }


async def _run_research(
    q: CanonicalQuery,
    deps: Dispatchers,
    client: httpx.AsyncClient,
) -> dict:
    """Staged retrieval + synthesis. Depth selects the retrieval pipeline.

    Replaces:
      - Cascading branch at api_gateway.py:3643-4032
      - Auto-routing to vault_review at api_gateway.py:3587-3589
      - Full vault_review branch at api_gateway.py:4087-4106

    Depth resolution:
        auto     → classify_comprehensive(query) ? "full" : "staged"
        shallow  → single-pass (equivalent to `ask` but with research response shape)
        staged   → anchor → expand → target → synthesis (current cascading)
        full     → staged + multi-facet + full-note MCP reads (current vault_review)
    """
    resolved_depth: Depth = q.depth
    if resolved_depth == "auto":
        resolved_depth = "full" if deps.classify_comprehensive(q.query) else "staged"

    # Per-depth retrieval. Mempalace/web sources ride alongside via _gather_sources.
    if resolved_depth == "shallow":
        vault_sources = await deps.vault_vector_retrieve(q, client)
    elif resolved_depth == "staged":
        vault_sources = await deps.vault_cascading_retrieve(q, client)
    elif resolved_depth == "full":
        vault_sources = await deps.vault_review_retrieve(q, client)
    else:
        raise UnsupportedMode(f"Unknown depth: {resolved_depth!r}")

    extra_sources = await _gather_extra_sources(q, deps, client)
    all_sources = _merge_sources(vault_sources, extra_sources)

    if not all_sources:
        return _empty_response(q, label="research", depth=resolved_depth)

    synth = await deps.synthesize(
        query=q.query,
        sources=all_sources,
        llm_provider=q.llm_provider,
        model=q.model,
        brief_concept_index=q.brief_concept_index,
    )

    return {
        "query": q.query,
        "mode": "research",
        "depth": resolved_depth,
        "depth_was_auto_resolved": q.depth == "auto",
        "sources_selected": list(q.sources),
        "answer": synth.get("answer", "") if isinstance(synth, dict) else str(synth),
        "sources": all_sources,
    }


# -----------------------------------------------------------------------------
# Source aggregation
# -----------------------------------------------------------------------------

async def _gather_sources(
    q: CanonicalQuery,
    deps: Dispatchers,
    client: httpx.AsyncClient,
    *,
    staged: bool,
) -> list[dict]:
    """Parallel fan-out across selected sources for `ask` mode."""
    import asyncio

    tasks = []
    if "vault" in q.sources:
        tasks.append(deps.vault_vector_retrieve(q, client))
    if "mempalace" in q.sources:
        tasks.append(deps.mempalace_retrieve(q, client))
    if "web" in q.sources:
        tasks.append(deps.web_retrieve(q, client))

    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    merged: list[dict] = []
    for r in results:
        if isinstance(r, Exception):
            # Source failures are non-fatal — log and continue. The caller
            # can surface per-source status in metadata if desired.
            continue
        if isinstance(r, list):
            merged.extend(r)
    return _dedupe_by_filepath(merged)


async def _gather_extra_sources(
    q: CanonicalQuery,
    deps: Dispatchers,
    client: httpx.AsyncClient,
) -> list[dict]:
    """Fetch mempalace/web results alongside the primary vault retrieval.

    Used by `research` mode where vault retrieval is already depth-specific
    and runs separately. Vault is skipped here.
    """
    import asyncio

    tasks = []
    if "mempalace" in q.sources:
        tasks.append(deps.mempalace_retrieve(q, client))
    if "web" in q.sources:
        tasks.append(deps.web_retrieve(q, client))

    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    merged: list[dict] = []
    for r in results:
        if isinstance(r, list):
            merged.extend(r)
    return merged


def _merge_sources(primary: list[dict], extra: list[dict]) -> list[dict]:
    """Combine vault-primary sources with extra (mempalace/web) hits."""
    if not extra:
        return primary
    return _dedupe_by_filepath(list(primary) + list(extra))


def _dedupe_by_filepath(sources: list[dict]) -> list[dict]:
    """Drop duplicates keyed on filepath; first occurrence wins (highest rank)."""
    seen: set[str] = set()
    out: list[dict] = []
    for s in sources:
        key = str(s.get("filepath") or s.get("filename") or id(s))
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _empty_response(q: CanonicalQuery, *, label: str, depth: Optional[str] = None) -> dict:
    resp = {
        "query": q.query,
        "mode": label,
        "sources_selected": list(q.sources),
        "answer": "No results found in the selected sources.",
        "sources": [],
    }
    if depth is not None:
        resp["depth"] = depth
    return resp
