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
- `llm_provider`: `ollama`, `claude`, `gemini`, `openrouter`, `chatgpt`, `lmstudio`, `perplexity`
- `model`: optional provider-specific model ID
- `temperature`: synthesis temperature for the HTTP query path
- `relevance_threshold`: 0-100 relevance filter
- `web_search`: boolean (requires `TAVILY_API_KEY`)
- `llm_knowledge`: boolean (adds vault-adjacent memory context when available)
- `brief_concept_index`: boolean
- `system_prompt`: optional prompt override for the synthesis step

Compatibility notes:
- `mlx` is still accepted as a legacy alias for `lmstudio`.
- Use `model` to pick a specific OpenRouter or LM Studio model.

Deep thinking is not an HTTP `mode` on `POST /api/v1/query`. Use the WebSocket endpoint `ws://localhost:4000/api/v1/deep-research` for agentic deep research.

## Response Notes

- `vector` and `cascading` both return vault `sources`.
- When `web_search` is enabled, both modes may also return `web_search` results.
- `cascading` uses staged retrieval plus synthesis. With `brief_concept_index=false`, the synthesis prompt asks for a fuller grounded answer instead of a terse overview.
- `cascading` now applies provider-specific synthesis guards for local models. Ollama uses separate timeout and prompt-cap settings so large vault-note clusters do not automatically inherit the tighter shared default.
- Web results are intended as lower-priority supplemental evidence and are shown after vault sources in the webapp.

## Cascading Synthesis Tuning

Relevant environment variables for `mode="cascading"`:

- `CASCADING_SYNTHESIS_TIMEOUT_SECONDS`: shared baseline synthesis timeout in seconds.
- `CASCADING_SYNTHESIS_TIMEOUT_SECONDS_OLLAMA`: Ollama-specific synthesis timeout override.
- `CASCADING_SYNTHESIS_TIMEOUT_SECONDS_LMSTUDIO`: LM Studio / MLX synthesis timeout override.
- `CASCADING_SYNTHESIS_MAX_SOURCES_OLLAMA`: max source records retained for Ollama synthesis.
- `CASCADING_SYNTHESIS_MAX_SNIPPET_CHARS_OLLAMA`: per-source snippet cap for Ollama prompt construction.
- `CASCADING_SYNTHESIS_MAX_CONTEXT_SOURCES_OLLAMA`: max prompt snippets actually serialized into the Ollama request.
- `CASCADING_SYNTHESIS_SOURCE_EXPANSION_CHARS_OLLAMA`: max markdown expansion size per Ollama source.
- `CASCADING_SYNTHESIS_MAX_SOURCES_LMSTUDIO`: LM Studio / MLX source cap.
- `CASCADING_SYNTHESIS_MAX_SNIPPET_CHARS_LMSTUDIO`: LM Studio / MLX snippet cap.
- `CASCADING_SYNTHESIS_MAX_CONTEXT_SOURCES_LMSTUDIO`: LM Studio / MLX prompt-snippet cap.

## Timing Logs

For cascading requests, the gateway now emits request-stage timing logs:

- `cascading_query.retrieval_complete`
- `cascading_query.synthesis_complete`
- `cascading_query.synthesis_failed`

The synthesis layer also emits per-attempt timing logs:

- `cascading_synthesis.start`
- `cascading_synthesis.prompt_prepared`
- `cascading_synthesis.model_complete`
- `cascading_synthesis.timeout`
- `cascading_synthesis.complete`

For full request/response details, see `Documentation/reference/api/UNIFIED_API_IMPLEMENTATION.md`.
