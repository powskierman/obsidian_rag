# Unified API Implementation

The API gateway in `src/services/api_gateway.py` provides a single entry point for all search modes.

## Base URL

`http://localhost:4000`

## Key Endpoints

- `POST /api/v1/query`
- `POST /api/v1/search`
- `POST /api/v1/search/stream` (SSE streaming proxy)
- `GET /api/v1/health`
- `GET /api/v1/stats`

## Core Request Fields

```json
{
  "query": "...",
  "mode": "vector|notes|entities|notes+vector|entities+vector|dual-graph|hybrid|cascading",
  "max_results": 10,
  "llm_provider": "ollama|claude|gemini|gpt-oss|kimi|openrouter|chatgpt|perplexity",
  "relevance_threshold": 75,
  "web_search": false,
  "llm_knowledge": false
}
```

The gateway proxies to the embedding service, graph service, and LightRAG service based on mode.

Provider note:
- `kimi` is an OpenRouter-backed provider label.
- OpenRouter model choice should be passed via `model` (request) or env defaults (`GRAPH_MODEL`, `LIGHTRAG_MODEL`).

Streaming behavior:
- `POST /api/v1/search/stream` returns `text/event-stream` SSE chunks.
- Streaming currently supports `vector`, `notes`/`graph`, and `hybrid` modes.
- The underlying Graph Service endpoint (`POST /query_stream`) is internal-only/deprecated for direct client traffic.

Compatibility aliases:
- `graph` -> `notes`
- `networkx` -> `notes`
- `lightrag` -> `entities`

LightRAG behavior:
- In `entities` mode, if LightRAG returns "Not found in notes", the gateway falls back to vector results (when fallbacks are enabled).
