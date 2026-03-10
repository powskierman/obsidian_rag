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
  "llm_provider": "ollama|claude|gemini|openrouter|chatgpt|lmstudio|perplexity",
  "model": "optional-model-id",
  "temperature": 0.3,
  "relevance_threshold": 75,
  "web_search": false,
  "llm_knowledge": false,
  "brief_concept_index": true,
  "system_prompt": null
}
```

The HTTP gateway proxies to the embedding service or cascading retriever based on mode. Deep thinking uses the dedicated WebSocket endpoint.

Provider note:
- `mlx` is a backward-compatible alias for `lmstudio`.
- OpenRouter and LM Studio model choice should be passed via `model` (request) or env defaults.
- LM Studio uses an OpenAI-compatible endpoint and currently expects `response_format.type` values compatible with LM Studio (`text` rather than `json_object`).

HTTP query behavior:
- `vector` performs vault retrieval from the embedding service, then runs a compact synthesis step.
- `cascading` performs staged retrieval (anchors, entities, expansion, vectors) and then synthesizes a final answer from the selected evidence set.
- `brief_concept_index=false` asks the synthesizer for a fuller grounded answer.
- Query-aware prompting is used for procedural queries and relation/comparison queries.
- Incomplete or unsupported-grounded synthesis results degrade to extractive vault-based fallbacks instead of being returned as-is.

Enhanced search behavior:
- `web_search=true` enables a supplemental Tavily lookup when `TAVILY_API_KEY` is configured.
- `llm_knowledge=true` enables memory-context injection where available.
- Web search results are returned separately from vault sources so clients can render them with lower priority.

Deep thinking behavior:
- Use `ws://localhost:4000/api/v1/deep-research` for long-running agentic research.
- Deep thinking is not a valid HTTP `mode` on `POST /api/v1/query`.
