# LightRAG Partial Indexing Guide (Canonical)

## Short answer
The previous setup worked, but it was not ideal for future partial indexing because the workflow was split across multiple scripts and ad-hoc commands.

This guide defines a single, repeatable path for gap-only markdown indexing.

## Canonical command
Run this from repo root (`obsidian_rag`):

```bash
./Scripts/indexing/partial_index_lightrag.sh --batch-size 5 --retry-failed-once --purge-deleted
```

What it does:
- Detects true missing `.md` notes (vault minus `indexed_files.txt`), excluding structural junk paths.
- Indexes in batches (default 5, adjustable).
- Writes JSONL batch logs and a final summary under `/tmp`.
- Retries failed docs once (optional flag already shown above).
- Optionally purges stale indexed docs whose source note files no longer exist (`--purge-deleted`).

## Defaults used by the script
- Service URL: `http://localhost:8001`
- Vault: `$OBSIDIAN_VAULT_PATH` or `/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel`
- DB dir: `$OBSIDIAN_RAG_DATA_DIR/lightrag_db` or `/Users/michel/obsidian_rag_local_data/lightrag_db`
- Excluded path patterns:
  - `venv/*,.venv/*,**/site-packages/*,.trash/*,.obsidian/*`

## Recommended mini workflow
1. Start service and verify health.
```bash
docker compose up -d lightrag-service
curl -sS http://localhost:8001/health | python -m json.tool
```

2. Run gap-only partial indexing.
```bash
./Scripts/indexing/partial_index_lightrag.sh --batch-size 5 --retry-failed-once --purge-deleted
```

3. Check summary and failed list paths printed at the end.

## Useful options
Index only a specific list of notes:

```bash
./Scripts/indexing/partial_index_lightrag.sh \
  --include-list-file /tmp/my_notes.txt \
  --batch-size 5 \
  --retry-failed-once
```

Create list only (no indexing):

```bash
./Scripts/indexing/partial_index_lightrag.sh --list-only
```

Limit run size (smoke test):

```bash
./Scripts/indexing/partial_index_lightrag.sh --max-files 20 --batch-size 5
```

Preview stale indexed docs without deleting:

```bash
./Scripts/indexing/partial_index_lightrag.sh --purge-deleted --purge-dry-run --list-only
```

## Monitoring
Current in-service job:

```bash
watch -n 2 'curl -sS http://localhost:8001/index-progress | python -m json.tool'
```

Service logs:

```bash
docker logs -f --tail 200 obsidian-lightrag
```

## Resuming
This command is safe to re-run. It recomputes missing markdown against current `indexed_files.txt` and continues from remaining files.

## Validation after run
```bash
./Scripts/indexing/list_remaining_missing_files.sh | rg 'Missing md|Missing pdf|processed:|failed:|pending:'
```

## Notes
- This workflow does not modify original notes.
- It targets markdown only; PDFs are intentionally excluded from this partial-index path.
- For full reindexing, continue using `./Scripts/indexing/index_with_lightrag.sh --force`.
