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

3. Minimal vector query:
   ```bash
   curl -s -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"query":"test","n_results":3}'
   ```

## Common Causes

- **No results**: embedding database not built or path not mounted.
- **Graph mode empty**: graph not built or graph path misconfigured.
- **Stale code**: containers not rebuilt after code changes.

## Fixes

- Rebuild graph/embeddings with the scripts in `Scripts/` (see `Documentation/Setup/INDEXING_SCRIPTS_GUIDE.md`).
- Rebuild a service after code changes:
  ```bash
  docker compose build graph-service
  docker compose up -d graph-service
  ```
