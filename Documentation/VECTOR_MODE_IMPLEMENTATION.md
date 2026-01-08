# Vector Mode Implementation

Vector mode is handled in `src/services/graph_query_service.py` and uses the embedding service for retrieval plus an LLM for synthesis.

## Request

```json
{
  "query": "What is DLBCL?",
  "mode": "vector",
  "n_results": 10,
  "llm_provider": "ollama",
  "temperature": 0.7
}
```

## Behavior

- Calls the embedding service with reranking + dedup.
- Applies a relevance threshold (default 75%).
- Builds a context window from the top sources.
- Generates a response via the selected LLM provider.

See `Documentation/UNIFIED_API_IMPLEMENTATION.md` for full request fields.
