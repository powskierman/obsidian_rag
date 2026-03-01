# Query Troubleshooting

## Quick Checks

1. Service status:
   ```bash
   docker compose ps
   ```

2. Embedding stats:
   ```bash
   curl -s http://localhost:8000/stats
   ```

   Interpretation:
   - `documents > 0`: vector service is `Online`
   - `documents = 0`: vector service is `Empty` and reachable
   - request failure / no response: vector service is `Offline`

3. Minimal vector query:
   ```bash
   curl -s -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"query":"test","n_results":3}'
   ```

## Common Causes

- **No results / UI shows Empty**: the service is reachable but the database is unpopulated, or the wrong data path is mounted.
- **Graph mode empty**: graph file is reachable but not built, or graph path is misconfigured.
- **UI shows Offline**: the service itself is unreachable from the webapp or gateway.
- **Stale code**: containers not rebuilt after code changes.

## Fixes

- Rebuild graph/embeddings with the scripts in `Scripts/` (see `Documentation/Setup/INDEXING_SCRIPTS_GUIDE.md`).
- Rebuild a service after code changes:
  ```bash
  docker compose build graph-service
  docker compose up -d graph-service
  ```

## Reliability Controls

The API gateway has retry + circuit-breaker settings:

- `RAG_REQUEST_RETRIES` (default: 2)
- `RAG_REQUEST_BACKOFF` (default: 0.5 seconds)
- `RAG_CIRCUIT_FAILURES` (default: 3)
- `RAG_CIRCUIT_RESET_SECONDS` (default: 30)
- `RAG_ENABLE_FALLBACKS` (default: true)
