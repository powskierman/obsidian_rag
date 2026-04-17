# Unified API Implementation

The API gateway in `src/services/api_gateway.py` provides a single entry point for all search modes. Mode normalisation is handled by `src/services/query_dispatch.py`.

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
  "mode": "ask|research|investigate",
  "depth": "auto|shallow|staged|full",
  "sources": ["vault", "mempalace", "web"],
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

Legacy mode strings (`vector`, `cascading`, `vault_review`, `deep-thinking`) are still accepted and normalised at the boundary. A `X-Deprecated-Mode` response header is emitted when a legacy string is used.

The HTTP gateway dispatches based on canonical mode. NetworkX and LightRAG remain internal retrieval dependencies behind `research` and `investigate`; they are not public HTTP modes.

Provider notes:
- `mlx` is a backward-compatible alias for `lmstudio`.
- OpenRouter and LM Studio model choice should be passed via `model` or env defaults.
- LM Studio uses an OpenAI-compatible endpoint and expects `response_format.type` values compatible with LM Studio (`text` rather than `json_object`).

HTTP query behaviour:
- `ask` performs vault retrieval from the embedding service, then runs a compact synthesis step.
- `research` performs staged retrieval (anchors, entities, expansion, vectors) and then synthesizes a final answer from the selected evidence set.
- `depth` controls pipeline depth for `research` mode: `auto` (default), `shallow`, `staged`, `full`.
- `sources` controls which data sources are queried: `vault` (always on), `mempalace`, `web`.
- `brief_concept_index=false` asks the synthesizer for a fuller grounded answer.
- Query-aware prompting is used for procedural and relation/comparison queries.
- Incomplete or unsupported-grounded synthesis results degrade to extractive vault-based fallbacks.

Enhanced search behaviour:
- `web_search=true` is shorthand for adding `web` to sources. Requires `TAVILY_API_KEY`.
- `llm_knowledge=true` enables memory-context injection where available.
- Web search results are returned separately from vault sources so clients can render them with lower priority.

Investigate behaviour:
- Use `ws://localhost:4000/api/v1/deep-research` for long-running agentic research.
- `investigate` is not a valid HTTP `mode` on `POST /api/v1/query`.
