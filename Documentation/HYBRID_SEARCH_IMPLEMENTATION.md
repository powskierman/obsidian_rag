# Hybrid Search Implementation

Hybrid mode is implemented server-side in `src/services/graph_query_service.py` so all clients behave the same.

## Request

```json
{
  "query": "What are my treatment options?",
  "mode": "hybrid",
  "n_results": 10,
  "max_entities": 20
}
```

## Behavior

- Runs a graph query first (NetworkX + LLM).
- Extracts entities and builds a stronger vector query (HyDE + entities).
- Returns the graph answer plus vector sources.

## Response (shape)

```json
{
  "answer": "...",
  "mode": "hybrid",
  "sources": [
    {"filename": "...", "filepath": "...", "relevance": 87.2, "snippet": "..."}
  ],
  "extracted_entities": ["..."]
}
```

See `Documentation/GRAPH_SEARCH_IMPROVEMENTS.md` for ranking safeguards.
