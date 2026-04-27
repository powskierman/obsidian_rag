# Quickstart

## 1) Configure

Create or update `.env` in the repo root:

```bash
OBSIDIAN_VAULT_PATH=/path/to/your/vault
ANTHROPIC_API_KEY=...   # optional
GEMINI_API_KEY=...      # optional
OPENROUTER_API_KEY=...  # optional
TAVILY_API_KEY=...      # optional
```

## 2) Start Services

```bash
docker compose up -d
```

## 3) Verify

```bash
curl -s http://localhost:4000/api/v1/health
```

## 4) Try a Query

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"nextion esp32","mode":"ask","max_results":5}'
```

Modes: `ask` (fast vector + synthesis), `research` (staged anchor → expand → vector → synthesis), and the WebSocket `investigate` agent at `ws://localhost:4000/api/v1/deep-research`. The legacy strings `vector`, `cascading`, `vault_review`, `deep-thinking` are still accepted (the gateway returns a `X-Deprecated-Mode` header).

## 5) Indexing (if empty results)

Run the unified indexer when the vector or graph stores are empty:

```bash
./Scripts/indexing/run_indexing.sh
```

For day-to-day incremental work, prefer the targeted scripts (`update_vector_db.sh`, `update_knowledge_graph.sh`, `partial_index_lightrag.sh`). See `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md`.

See `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md` for options.

## 6) UI Status Labels

The webapp distinguishes service reachability from data population:

- `Online`: the service is reachable and has non-zero indexed data.
- `Empty`: the service is reachable but currently reports zero indexed documents or nodes.
- `Offline`: the service could not be reached.

Examples:

- ChromaDB with `documents: 0` shows `Empty`, not `Offline`.
- NetworkX with zero nodes on a reachable endpoint shows `Empty`.
