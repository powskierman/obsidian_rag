# Database Management

This repo keeps generated data out of Git. These directories are expected to be local-only and rebuildable:

- `chroma_db/`: vector embeddings (embedding service).
- `lightrag_db/`: LightRAG entity graph data.
- `data/graph_data/`: NetworkX graph snapshots.

## Why They Are Not Tracked

- Large, machine-specific, and derived from your vault.
- Easier to rebuild than to version.
- May contain private content.

## Rebuild From Scratch

```bash
# Start services
docker compose up -d

# Index your vault (choose the script that matches your graph mode)
# Index your vault (Unified script)
./Scripts/indexing/run_indexing.sh
```

If you use a different indexing path, pick the relevant script from `Scripts/`.

Force a full rebuild:

```bash
./Scripts/indexing/run_indexing.sh
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
   mv chroma_db chroma_db_backup_$(date +%Y%m%d)
   ```
3. Restart services:
   ```bash
   docker compose up -d
   ```
4. Reindex:
   ```bash
   ./Scripts/indexing/run_indexing.sh
   ```
