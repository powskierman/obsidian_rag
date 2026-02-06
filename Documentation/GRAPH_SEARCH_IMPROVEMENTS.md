# Graph Search Improvements

This note summarizes the current graph-source ranking safeguards in `src/services/graph_query_service.py` and related filters in `src/services/kimi_graph_builder.py`.

## Problem

Graph-only queries were surfacing unrelated sources due to low-signal terms and central-node leakage.

## Current Behavior (Condensed)

1. **Entity noise filtering** (`kimi_graph_builder.py`)
   - Stopwords, dates, and numeric artifacts are excluded before matching.

2. **Query-term gating with normalization** (`graph_query_service.py`)
   - Entity matching uses word boundaries plus normalized text (e.g., `esp-32` -> `esp32`).
   - If entity text does not match, filename matches can still allow the source.

3. **Multi-term coverage requirements**
   - For multi-term queries, sources must match at least two terms (entity or filename) to pass.
   - Low-coverage results are capped to avoid flooding.

4. **Integration boosting (explicit only)**
   - Integration intent requires explicit cues (connect, wiring, uart, etc.).
   - Keyword list is trimmed and boost is capped.

5. **Downranking generic docs**
   - When the query is hardware-centric, AI/RAG docs are downranked.
   - Filenames containing `MoC`, `Agent`, or `Supervisor` are downranked unless requested.

6. **Sorting**
   - Sources are sorted by match strength, then relevance.

## Deployment

```bash
docker compose build graph-service
docker compose up -d graph-service
```

## Quick Check

```bash
curl -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"nextion and esp32","mode":"notes"}'
```

Expected: Nextion/ESP32 notes rise; AI/agent/system notes are suppressed.
