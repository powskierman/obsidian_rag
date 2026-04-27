# Database Management

This repo keeps generated data out of Git. These directories are expected to be local-only and rebuildable:

- `${OBSIDIAN_RAG_DATA_DIR}/chroma_db`: vector embeddings (embedding service).
- `${OBSIDIAN_RAG_DATA_DIR}/lightrag_db`: LightRAG entity graph data.
- `${OBSIDIAN_RAG_DATA_DIR}/graph_data`: NetworkX graph snapshots.

## Why They Are Not Tracked

- Large, machine-specific, and derived from your vault.
- Easier to rebuild than to version.
- May contain private content.

## Rebuild From Scratch

```bash
# Start services
docker compose up -d

# Run the unified indexer (vector + NetworkX graph + LightRAG)
./Scripts/indexing/run_indexing.sh
```

For partial / targeted rebuilds, prefer the per-store scripts under `Scripts/indexing/` — see `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md`.

To force a clean ChromaDB drop+rebuild specifically (destructive, requires `EMBEDDING_CLEAR_TOKEN`):

```bash
python src/indexing/index_vault.py /path/to/vault \
  --url http://localhost:8000 \
  --full \
  --clear \
  --clear-token "$EMBEDDING_CLEAR_TOKEN"
```

## Reindex Embeddings (Clear + Rebuild)

The embedding service now supports a protected clear endpoint.

```bash
export EMBEDDING_CLEAR_TOKEN="your-token"

# Clear and rebuild embeddings with sanitization + metadata validation
python src/indexing/index_vault.py /path/to/vault \
  --url http://localhost:8000 \
  --clear \
  --clear-token "$EMBEDDING_CLEAR_TOKEN"
```

Notes:
- `index_vault.py` normalizes content (line endings, control chars) and validates frontmatter metadata.
- Clearing requires the `EMBEDDING_CLEAR_TOKEN` env var (or `--clear-token`).

## Incremental Updates (Upsert)

`index_vault.py` now upserts chunks so new notes and edits update the existing database. To remove stale chunks (e.g., when files shrink), use:

```bash
export EMBEDDING_CLEAR_TOKEN="your-token"

python src/indexing/index_vault.py /path/to/vault \
  --url http://localhost:8000 \
  --clear-token "$EMBEDDING_CLEAR_TOKEN"
```

## Troubleshooting

### ChromaDB Corruption Fix
**Symptoms:** embedding service fails to start or queries crash.

**Fix:**
1. Stop services:
   ```bash
   docker compose down
   ```
2. Backup and remove the DB:
   ```bash
   mv "$OBSIDIAN_RAG_DATA_DIR/chroma_db" "$OBSIDIAN_RAG_DATA_DIR/chroma_db_backup_$(date +%Y%m%d)"
   ```
3. Restart services:
   ```bash
   docker compose up -d
   ```
4. Reindex:
   ```bash
   ./Scripts/indexing/run_indexing.sh
   ```
