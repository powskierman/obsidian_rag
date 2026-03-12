# Reindexing Procedure (Vector, NetworkX, LightRAG)

This guide documents the full, repeatable reindexing workflow used in this repo.
It assumes you want all three databases current:

- Vector DB (ChromaDB)
- NetworkX graph (graph_data/knowledge_graph_full.pkl)
- LightRAG entity graph (lightrag_db)

Adjust paths as needed for your machine.

## 1) Paths and environment

Set these once in your shell:

```bash
export RAG_REPO="/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"
export OBSIDIAN_VAULT_PATH="/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
export OPENROUTER_API_KEY="your-openrouter-key"
```

Local data directory (Mac mini):

```bash
export RAG_DATA="/Users/michel/obsidian_rag_local_data"
```

## 2) Vector DB (ChromaDB) reindex

Start the embedding service from the local data directory so it writes to
`$RAG_DATA/chroma_db`.

Terminal A:

```bash
cd "$RAG_DATA"
python "$RAG_REPO/src/services/embedding_service.py"
```

Terminal B (incremental indexing with cache):

```bash
export INDEX_VAULT_CACHE_PATH="$RAG_DATA/index_vault_cache.json"
PYTHONUNBUFFERED=1 python "$RAG_REPO/src/indexing/index_vault.py" "$OBSIDIAN_VAULT_PATH" \
  --url "http://localhost:8000" | tee "$RAG_DATA/index_vault.log"
```

Notes:
- Incremental indexing is enabled by default and will only process new/changed files.
- If you need a full reindex, add `--full`.
- If you need to reset the cache, add `--reset-cache`.
- The indexer falls back to `/add` when `/upsert` is not available.

### PDF support

To index PDFs with the local indexer, install `pypdf` in the same venv:

```bash
pip install pypdf
```

## 3) NetworkX graph reindex (graph_data)

This uses the graph service container but persists to `$RAG_DATA/graph_data`.
It resumes from `knowledge_graph_full.pkl` unless `--force-refresh` is used.

```bash
cd "$RAG_REPO"
docker compose run --rm \
  -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
  -v "$OBSIDIAN_VAULT_PATH":/app/vault:ro \
  -v "$RAG_DATA/graph_data":/app/graph_data \
  -v "$PWD/src/services/build_graph.py":/app/build_graph.py:ro \
  graph-service \
  python /app/build_graph.py
```

## 4) LightRAG reindex (lightrag_db)

Start the LightRAG service (Docker) and call its index endpoint.
The DB lives in the `lightrag_storage` volume (inside container: `/app/lightrag_db`).

```bash
docker compose up -d lightrag-service
curl -s -X POST http://localhost:8001/index-vault \
  -H "Content-Type: application/json" \
  -d "{\"vault_path\": \"/app/vault\"}"
```

To force a full reindex:

```bash
curl -s -X POST http://localhost:8001/index-vault \
  -H "Content-Type: application/json" \
  -d "{\"vault_path\": \"/app/vault\", \"force\": true}"
```

LightRAG indexing now injects note context into each indexed document:
- filename + title
- headings (first 12)
- frontmatter tags + inline `#tags`
- frontmatter aliases

If you change any of these inputs, force a reindex to update the stored chunks.

Optional tuning (no reindex required):
```bash
export LIGHTRAG_COSINE_THRESHOLD=0.03
export LIGHTRAG_COSINE_BETTER_THAN_THRESHOLD=0.03
```

### Recommended for routine updates (partial only)

For future day-to-day indexing, use the canonical partial gap-index command instead
of full reindexing:

```bash
./Scripts/indexing/partial_index_lightrag.sh --batch-size 5 --retry-failed-once
```

This flow computes missing markdown files, indexes in small batches, and writes
resumable logs and a run summary. See:
`Documentation/operations/setup/LIGHTRAG_PARTIAL_INDEXING_GUIDE.md`

## 5) Monitoring

Vector:
```bash
tail -f "$RAG_DATA/index_vault.log"
curl -s http://localhost:8000/stats
```

NetworkX:
```bash
docker logs -f obsidian-graph-service
```

LightRAG:
```bash
docker logs -f obsidian-lightrag
curl -s http://localhost:8001/stats
```

## 6) Backup

Snapshot LightRAG DB:

```bash
docker stop obsidian-lightrag
docker cp obsidian-lightrag:/app/lightrag_db "$RAG_DATA/lightrag_db_$(date +%Y%m%d_%H%M%S)"
docker start obsidian-lightrag
```

Snapshot graph + vector DBs:

```bash
cp -a "$RAG_DATA/graph_data" "$RAG_DATA/graph_data_$(date +%Y%m%d_%H%M%S)"
cp -a "$RAG_DATA/chroma_db" "$RAG_DATA/chroma_db_$(date +%Y%m%d_%H%M%S)"
```

## 7) What each database powers

- Vector DB (ChromaDB): vector mode and the vector portions of cascading/deep thinking.
- NetworkX graph (graph_data): internal graph-backed retrieval used by deep thinking and cascading anchors.
- LightRAG (lightrag_db): internal concept-expansion and graph-backed retrieval used by cascading and deep thinking.

## 8) LLM knobs by component

- Vector DB: no generative LLM setting. Uses embedding + reranker models.
- NetworkX graph defaults:
  - `GRAPH_MODEL` (preferred), fallback `OPENROUTER_MODEL`.
  - Optional endpoint override: `GRAPH_LLM_BASE_URL` + `GRAPH_LLM_API_KEY`.
  - Query API can override with request fields: `llm_provider`, `model`.
- LightRAG defaults:
  - `LIGHTRAG_MODEL` for OpenRouter model selection (preferred).
  - `QUERY_LLM_MODEL` for query-time synthesis override.
  - Backward compatibility: `KIMI_MODEL` is still accepted as a fallback.
