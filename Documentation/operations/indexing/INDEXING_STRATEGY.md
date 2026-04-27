# Indexing Strategy & Maintenance SOP

> Day-to-day commands live in `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md`. This file documents the *strategy* — when and why to run each path.

## Why Sync Matters

Editing happens on the MacBook (via Obsidian); the canonical query stack runs on Canmore (Mac Mini). The vault is mirrored across both machines, but the **derived indexes** (ChromaDB, NetworkX graph, LightRAG entity store) live only on the indexer and are stale until they are rebuilt or synced.

Three independent stores need to stay current:

| Store | Path inside `${OBSIDIAN_RAG_DATA_DIR}/` | What goes stale when |
| --- | --- | --- |
| ChromaDB (vector) | `chroma_db/` | A note's body text or frontmatter changed, or new notes were added |
| NetworkX graph | `graph_data/` | Wikilinks, headings, or folder structure changed |
| LightRAG entity store | `lightrag_db/` | New entities/relations exist (or notes were deleted) |

## 1. Vector — Incremental by Default

`src/indexing/index_vault.py` upserts chunks. It hashes file bytes (MD5) so unchanged files are skipped. Useful flags:

| Flag | When to use |
| --- | --- |
| (none) | Daily incremental — only changed/new files are processed |
| `--refresh` | Delete existing chunks per file before re-upserting (use after metadata-only edits) |
| `--full` | Ignore the incremental cache and walk every note |
| `--reset-cache` | Reset the cache file then run a clean incremental pass |
| `--clear` (+ `--clear-token`) | Drop the entire embedding collection before reindexing (destructive) |

Wrapper: `./Scripts/indexing/update_vector_db.sh`.

## 2. NetworkX Graph — Fast Structural Rebuild

The NetworkX graph is built from a structural scan and does not need append logic — a rebuild is cheap. Use:

```bash
./Scripts/indexing/update_knowledge_graph.sh
```

If the in-process service caches feel stale: `docker compose restart graph-service`.

## 3. LightRAG — Partial Gap Indexing for Daily Runs

For routine updates, prefer the partial gap indexer over a full LightRAG rebuild — it walks only files missing from `indexed_files.txt`:

```bash
./Scripts/indexing/partial_index_lightrag.sh --batch-size 5 --retry-failed-once --purge-deleted
```

See `Documentation/operations/setup/LIGHTRAG_PARTIAL_INDEXING_GUIDE.md` for the full option matrix. A `--force` flag on the full pipeline (`./Scripts/indexing/index_with_lightrag.sh --force`) is reserved for major reindexes.

## 4. End-to-End Reindex

`./Scripts/indexing/run_indexing.sh` runs all three stores in sequence and is the right entry point for a fresh machine, after a corruption, or after large vault reorganization.

## 5. Cross-Machine Snapshot Sync

Editing on the MacBook and serving on the Mac Mini is handled via snapshot push/pull (`Scripts/sync/push.sh` on the indexer, `Scripts/sync/pull.sh` on the consumer) — this avoids running indexing twice. See `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md` for the full procedure.

## 6. Verifying Freshness

- `python Scripts/debug/check_graph_status.py` — graph mtime vs latest note mtime.
- `obsidian_index_health` MCP tool — surfaces stale/missing index-cache entries (see `Documentation/operations/quality/INDEX_HEALTH_PROCEDURE.md`).
- `curl -s http://localhost:8000/stats` — ChromaDB document count.
- `curl -s http://localhost:8001/stats` — LightRAG entity/relation count.
