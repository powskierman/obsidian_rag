# Directive: Manage RAG Index

## Metadata
- **Owner**: Core Engine & Indexing Track
- **Last Updated**: 2026-01-23
- **Related Scripts**: `src/indexing/index_vault.py`, `Scripts/index_with_lightrag.sh`
- **Version**: 1.0.0

## Contract

### Purpose
Synchronize the local Obsidian vault with the vector (ChromaDB) and graph (LightRAG) search indices.

### Inputs
- **mode** (string, required): One of:
  - `"incremental"`: Updates existing index with changed files.
  - `"full_rebuild"`: Completely wipes and rebuilds the index.
- **vault_path** (string, optional): Path to Obsidian vault. Defaults to configured env var.

### Outputs
- **status** (string): "success" or "failure".
- **details** (object):
  - **processed_count** (int): Number of documents processed.
  - **failed_count** (int): Number of documents that failed indexing.

### Preconditions
- `EMBEDDING_CLEAR_TOKEN` must be present in `.env`.
- Obsidian vault path must be accessible.
- For `full_rebuild`: User must explicitly verify intention due to destructive nature.

### Postconditions
- `chroma_db` and `lightrag_db` state reflects the current vault content.
- `index_stats.json` (if applicable) is updated.

## Flow

1.  **Preparation**
    - Load environment variables.
    - Validate `vault_path`.

2.  **Execution**
    - **If mode == "incremental":**
      - Run `python src/indexing/index_vault.py --refresh`
      - Monitor stdout for progress bar and error logs.
    - **If mode == "full_rebuild":**
      - **WARNING**: This is destructive.
      - Run `bash ./Scripts/index_with_lightrag.sh`
      - This script will clear existing graph data. Ensure `lightrag_db_backup_*` exists if rollback is needed.

3.  **Validation**
    - Check exit code of the script.
    - Parse logs for "0 failed documents".
    - Check modification time of `chroma_db` files to ensure write occurred.

## Error Handling

- **Script Failure (Non-zero exit code)**:
  - Capture stderr.
  - Return `status: failure` with error message.
  - **Recovery**: If incremental fails, suggest checking specific file syntax or running full rebuild (with caution).
- **Missing Token**:
  - Error immediately if `EMBEDDING_CLEAR_TOKEN` is missing.
- **Locked Database**:
  - If ChromaDB or LightRAG is locked, ensure no other processes (like the API server) are holding a write lock. Suggest stopping the `graph-service` container temporarily.

## Cost Profile
- **Embedding API**: Costs apply per token for embedding generation.
- **LLM API**: `full_rebuild` using LightRAG is **expensive** (thousands of calls) and time-consuming. Use `incremental` whenever possible.
