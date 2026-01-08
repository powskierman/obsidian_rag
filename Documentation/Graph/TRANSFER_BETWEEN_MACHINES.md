# Transfer Graph Data Between Machines

## What to Copy

- `data/graph_data/` (NetworkX graph)
- `lightrag_db/` (LightRAG data)
- `chroma_db/` (vector embeddings)

## On the New Machine

1. Place the directories at the repo root.
2. Ensure `.env` has the correct `OBSIDIAN_VAULT_PATH`.
3. Start services:
   ```bash
   docker compose up -d
   ```

If you skip copying any of these, you must rebuild that component.
