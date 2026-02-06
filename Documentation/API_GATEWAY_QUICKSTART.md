# API Gateway Quickstart

Base URL: `http://localhost:4000`

## Core Endpoints

- `GET /api/v1/health`
- `GET /api/v1/stats`
- `POST /api/v1/query` (Unified Search)
- `GET /docs` (OpenAPI UI)

## Minimal Search Example

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"nextion esp32","mode":"hybrid","max_results":5}'
```

## Common Request Fields

- `query` (required)
- `mode`: `vector`, `notes`, `entities`, `notes+vector`, `entities+vector`, `dual-graph`, `hybrid`, `cascading`
- `max_results`: max sources (vector/hybrid)
- `llm_provider`: `ollama`, `claude`, `gemini`, `gpt-oss`, `kimi`, `openrouter`, `chatgpt`, `perplexity`
- `web_search`: boolean (requires Tavily API key)
- `llm_knowledge`: boolean (adds a general knowledge section)

Compatibility note: `graph` is still accepted as an alias for `notes`.

For full request/response details, see `Documentation/UNIFIED_API_IMPLEMENTATION.md`.
