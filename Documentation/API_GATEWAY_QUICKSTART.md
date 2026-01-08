# API Gateway Quickstart

Base URL: `http://localhost:4000`

## Core Endpoints

- `GET /api/v1/health`
- `POST /api/v1/search`
- `POST /api/v1/search/stream` (SSE)
- `GET /docs` (OpenAPI UI)

## Minimal Search Example

```bash
curl -s -X POST http://localhost:4000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"nextion esp32","mode":"hybrid","n_results":5}'
```

## Common Request Fields

- `query` (required)
- `mode`: `vector`, `graph`, `hybrid`, `dual-graph`
- `n_results`: max sources (vector/hybrid)
- `llm_provider`: `ollama`, `claude`, `gemini`, `gpt-oss`, `kimi`
- `web_search`: boolean (requires Tavily API key)
- `llm_knowledge`: boolean (adds a general knowledge section)

For full request/response details, see `Documentation/UNIFIED_API_IMPLEMENTATION.md`.
