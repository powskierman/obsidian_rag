# Unified API Implementation

The API gateway in `src/services/api_gateway.py` provides a single entry point for all search modes.

## Base URL

`http://localhost:4000`

## Key Endpoints

- `POST /api/v1/query`
- `GET /api/v1/health`
- `GET /api/v1/stats`
- `WS /api/v1/deep-research`

## Core Request Fields

```json
{
  "query": "...",
  "mode": "vector|cascading",
  "max_results": 10,
  "llm_provider": "ollama|claude|gemini|gpt-oss|kimi|openrouter|chatgpt|perplexity",
  "relevance_threshold": 75,
  "web_search": false,
  "llm_knowledge": false
}
```

The HTTP gateway proxies to the embedding service or cascading retriever based on mode. Deep thinking uses the dedicated WebSocket endpoint.

Provider note:
- `kimi` is an OpenRouter-backed provider label.
- OpenRouter model choice should be passed via `model` (request) or env defaults (`GRAPH_MODEL`, `LIGHTRAG_MODEL`).

Deep thinking behavior:
- Use `ws://localhost:4000/api/v1/deep-research` for long-running agentic research.
- Deep thinking is not a valid HTTP `mode` on `POST /api/v1/query`.
