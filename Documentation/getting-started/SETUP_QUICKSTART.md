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
  -d '{"query":"nextion esp32","mode":"vector","max_results":5}'
```

## 5) Indexing (if empty results)

Run the appropriate script from `Scripts/`:

```bash
./Scripts/indexing/run_indexing.sh
```

To force a full rebuild:

```bash
./Scripts/indexing/run_indexing.sh
```

See `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md` for options.

## 6) UI Status Labels

The webapp distinguishes service reachability from data population:

- `Online`: the service is reachable and has non-zero indexed data.
- `Empty`: the service is reachable but currently reports zero indexed documents or nodes.
- `Offline`: the service could not be reached.

Examples:

- ChromaDB with `documents: 0` shows `Empty`, not `Offline`.
- NetworkX with zero nodes on a reachable endpoint shows `Empty`.
