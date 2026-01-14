# Indexing Scripts Guide

Use these scripts in `Scripts/` to build or rebuild indexes.

## Common Choices

- `index_with_lightrag.sh`: build the LightRAG entity graph.
- `index_with_graphrag.sh`: run GraphRAG indexing (if configured).
- `index_with_kimi.sh`: index using Kimi/OpenRouter.
- `build_knowledge_graph.sh`: build the NetworkX graph.

## When to Run

- After large vault changes or folder reorganizations.
- After cloning to a new machine.

Pick the script that matches your desired graph mode. If unsure, start with `index_with_lightrag.sh`.

## LightRAG indexing notes

`index_with_lightrag.sh` now accepts `--force` to reindex everything:

```bash
./Scripts/index_with_lightrag.sh --force "$OBSIDIAN_VAULT_PATH"
```

LightRAG indexing prepends note context to each document so title searches are reliable:
- filename + title
- headings (first 12)
- frontmatter tags + inline `#tags`
- frontmatter aliases

If you change any of the above behavior, reindex LightRAG to apply it.
