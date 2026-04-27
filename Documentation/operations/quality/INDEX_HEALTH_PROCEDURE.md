# Index Health Procedure

The MCP `obsidian_index_health` tool reports stale and missing entries in the
local index cache so you can diagnose "search returned a path that doesn't
exist" or "search misses a note I just edited" cases without guessing.

This doc covers when to use it, how to read the output, and how to fix the
classes of problems it surfaces.

## When To Run It

Run `obsidian_index_health` when:

- A search result references a file at a path that no longer exists on disk.
- A note you know exists is invisible to `obsidian_semantic_search`.
- After a large vault reorganization (folder moves, bulk renames).
- After pulling a snapshot from another machine and the answers feel stale.

It does **not** trigger reindexing — it only reports.

## What It Reports

The tool inspects the in-process index-cache state and returns:

- `vault_root` — what the MCP server thinks the vault root is.
- `cache_size` — number of index-cache entries.
- `stale_paths` — entries whose stored path no longer resolves on disk.
- `recovered_paths` — entries that were repaired automatically by the
  conservative path-recovery code in `search_vault_full`.
- `missing_chunks` (when available) — known notes with no chunk records.

## Recommended Response Map

| Symptom | Fix |
| --- | --- |
| `stale_paths` list contains files you renamed | Re-run vector indexing (`./Scripts/indexing/update_vector_db.sh --refresh`) |
| Many recent notes missing | Run `./Scripts/indexing/update_vector_db.sh` (incremental) |
| Cache references a vault root that doesn't match `OBSIDIAN_VAULT_PATH` | The MCP server is wired to a different vault. Check `OBSIDIAN_VAULT_PATH` in the MCP config block (see `Documentation/integrations/mcp/MCP_SETUP_INSTRUCTIONS.md`). Restart the MCP client. |
| LightRAG-backed answers feel stale | Run `./Scripts/indexing/partial_index_lightrag.sh --batch-size 5 --retry-failed-once --purge-deleted` |
| Graph answers feel stale | Run `./Scripts/indexing/update_knowledge_graph.sh` |
| All three look broken | Run `./Scripts/indexing/run_indexing.sh` for a full rebuild |

## Calling The Tool

Through Claude Desktop / ChatGPT Desktop:

> Run `obsidian_index_health`.

Direct JSON-RPC test against an HTTP MCP server:

```bash
curl -X POST http://localhost:8811/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "obsidian_index_health",
      "arguments": {}
    }
  }' | python3 -m json.tool
```

## Why Stale Paths Happen

`search_vault_full` keys results from the embedding index, which stores the
filename and path **at the time of indexing**. If a note is moved or renamed
without a reindex, the stored path drifts. The tool's `recovered_paths` list
shows where the conservative path-recovery in `search_vault_full` was able to
guess the new location; everything in `stale_paths` requires a real reindex.

## Related

- `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md` — script catalog.
- `Documentation/operations/indexing/INDEXING_STRATEGY.md` — when to use which path.
- `Documentation/integrations/mcp/MCP_SETUP_INSTRUCTIONS.md` — wiring the MCP server into your client.
