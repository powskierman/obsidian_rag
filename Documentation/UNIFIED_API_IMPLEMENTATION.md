# Unified API Implementation

The API gateway in `src/services/api_gateway.py` provides a single entry point for all search modes.

## Base URL

`http://localhost:4000`

## Key Endpoints

- `POST /api/v1/query`
- `POST /api/v1/search/stream`
- `GET /api/v1/health`
- `GET /api/v1/stats`

## Core Request Fields

```json
{
  "query": "...",
  "mode": "vector|graph|hybrid|dual-graph|cascading",
  "max_results": 10,
  "llm_provider": "ollama|claude|gemini|gpt-oss|kimi",
  "relevance_threshold": 75,
  "web_search": false,
  "llm_knowledge": false
}
```

The gateway proxies to the embedding service, graph service, and LightRAG service based on mode.

LightRAG behavior:
- In `entities` mode, if LightRAG returns "Not found in notes", the gateway falls back to vector results (when fallbacks are enabled).
