# Graph Search Improvements

This note captures the changes made to reduce irrelevant sources in NetworkX graph search results.

## Problem

Queries like "nextion and esp32" were returning unrelated sources (e.g., Xcode/iOS notes). The cause was:

- Graph entity matching allowed low-signal tokens (like "and") to be treated as entities.
- Graph sources were derived from central nodes, not strictly tied to query terms.

## Fixes Applied

### 1) Stopword/Noise Entity Filter

**File:** `src/services/kimi_graph_builder.py`

- Added a stopword and low-signal entity filter inside `query_with_llm`.
- Entities like "and", "the", or numeric-only strings are skipped before matching.
- Prevents noisy entity matches from pulling unrelated context nodes.

### 2) Query-Term Gating for Sources

**File:** `src/services/graph_query_service.py`

- Sources are only collected from context nodes whose entity name/description matches query terms.
- Summary-style queries still allow broader coverage (e.g., "overview").

### 3) Match-Strength Ranking and Capping

**File:** `src/services/graph_query_service.py`

- Each source is scored with a `match_strength` (count of query terms matched).
- Sources are sorted by `match_strength` then relevance.
- Only the top match-strength band is kept and capped to avoid flooding results.

### 4) Integration Keyword Boosting (Generic)

**File:** `src/services/graph_query_service.py`

- Detects integration intent (e.g., queries with multiple entities or "connect/integrate").
- Boosts sources whose entity name/description or filename includes generic integration keywords (UART, serial, wiring, protocol, library, etc.).
- Configurable via `GRAPH_KEYWORD_BOOSTS` JSON env var.

## Deployment Notes

The graph service container copies code at build time, so changes require:

```bash
docker compose build graph-service
docker compose up -d graph-service
```

## Quick Verification

Run a query that previously returned irrelevant sources:

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query":"nextion and esp32","mode":"graph"}'
```

Expected: sources are limited to Nextion/ESP32-related notes, no Xcode/iOS entries.
