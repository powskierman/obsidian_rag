# API Gateway Quickstart

Base URL: `http://localhost:4000`

## Core Endpoints

- `GET /api/v1/health`
- `GET /api/v1/stats`
- `POST /api/v1/query` (HTTP search: `vector` or `cascading`)
- `WS /api/v1/deep-research` (deep thinking / deep research agent)
- `GET /docs` (OpenAPI UI)

## Minimal Search Example

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"nextion esp32","mode":"vector","max_results":5}'
```

## Common Request Fields

- `query` (required)
- `mode`: `vector` or `cascading`
- `max_results`: max sources/results for the HTTP query path
- `llm_provider`: `ollama`, `claude`, `gemini`, `gpt-oss`, `kimi`, `openrouter`, `chatgpt`, `perplexity`
- `web_search`: boolean (requires Tavily API key)
- `llm_knowledge`: boolean (adds a general knowledge section)

Note: `kimi` is treated as an OpenRouter provider choice. Use `model` to pick a specific OpenRouter model.

Deep thinking is not an HTTP `mode` on `POST /api/v1/query`. Use the WebSocket endpoint `ws://localhost:4000/api/v1/deep-research` for agentic deep research.

For full request/response details, see `Documentation/UNIFIED_API_IMPLEMENTATION.md`.
