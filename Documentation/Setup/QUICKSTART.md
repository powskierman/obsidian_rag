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
  -d '{"query":"nextion esp32","mode":"hybrid","max_results":5}'
```

## 5) Indexing (if empty results)

Run the appropriate script from `Scripts/`:

```bash
./Scripts/run_indexing.sh
```

To force a full rebuild:

```bash
./Scripts/run_indexing.sh
```

See `Documentation/Setup/INDEXING_SCRIPTS_GUIDE.md` for options.
