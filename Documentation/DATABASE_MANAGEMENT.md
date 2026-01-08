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
./Scripts/index_with_lightrag.sh
```

If you use a different indexing path, pick the relevant script from `Scripts/`.
