---
name: Obsidian Index Maintenance
description: Synchronize the local Obsidian vault with vector and graph stores safely.
---

# Obsidian Index Maintenance Skill

This skill handles the process of updating the RAG index (ChromaDB and LightRAG) from the local Obsidian vault.

## Goal
To ensure the search index is up-to-date with the latest notes while preventing data corruption or accidental deletions.

## Tools & Scripts
*   **Vector Indexing:** `src/indexing/index_vault.py`
*   **Graph/Hybrid Indexing:** `./Scripts/index_with_lightrag.sh`

## Instructions

1.  **Preparation**
    *   Ensure the `EMBEDDING_CLEAR_TOKEN` is present in the `.env` file (but do NOT display it).
    *   Check that the Obsidian vault path is accessible.

2.  **Standard Update (Incremental)**
    *   Run `python src/indexing/index_vault.py --refresh`
    *   This will scan for changed files and update embeddings.

3.  **Full Rebuild (Destructive)**
    *   **WARNING:** Only perform this if explicitly requested or if the index is corrupted.
    *   Run `bash ./Scripts/index_with_lightrag.sh`
    *   This script may clear existing graph data. Verify backups exist in `lightrag_db_backup_*`.

4.  **Validation**
    *   Check logs for "0 failed documents".
    *   Verify `index_stats.json` (if generated) or check the modification time of `chroma_db` files.

## Constraints
*   **Do NOT** run `rm -rf` on `chroma_db` or `lightrag_db` manually. Use the scripts.
*   **Do NOT** commit large database files to git. content of `lightrag_db` should appear in `.gitignore`.
