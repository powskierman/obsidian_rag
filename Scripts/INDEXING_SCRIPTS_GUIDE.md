# Indexing & Data Sync Guide

## Overview

We have migrated to a **Snapshot Sync Architecture** to avoid iCloud database corruption.
- **Mac Mini (Indexer)**: Indexes data locally, then pushes a snapshot to iCloud.
- **MacBook (Consumer)**: Pulls the snapshot from iCloud to local storage for querying.
- **Safe & Fast**: Databases run on local SSDs. iCloud is only used for transfer.

---

## 🚀 Unified Procedures

### 1. Indexing (Run on Mac Mini)

**Script:** `Scripts/run_indexing.sh`

This unified script performs a complete re-index of your vault into all three databases:
1.  **LightRAG** (Entity Graph) - Port 8001
2.  **NetworkX** (Note Graph) - Port 8002
3.  **ChromaDB** (Vector Search) - Port 8000

**Usage:**
```bash
# Full Re-Index
./Scripts/run_indexing.sh
```
*   You will be prompted to confirm a full re-index (deletes old data).
*   **Time:** ~30-60 mins for 2k notes.
*   **Cost:** ~$1.00 (Kimi/OpenRouter).

---

### 2. Export Data (Run on Mac Mini)

**Script:** `Scripts/sync/push.sh`

After indexing is complete, push the fresh data to the iCloud staging area.
This creates a stable snapshot in `~/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/data/export_stage`.

**Usage:**
```bash
./Scripts/sync/push.sh
```

---

### 3. Import Data (Run on MacBook)

**Script:** `Scripts/sync/pull.sh`

To update your MacBook with the latest SOTA data from the Mini, run the pull script.
This stops your local services, pulls the data from iCloud to your local SSD (`~/obsidian_rag_local_data`), and restarts services.

**Usage:**
```bash
./Scripts/sync/pull.sh
```

---

### 4. Daily Usage (Run on Both)

**Script:** `Scripts/start_obsidian_rag.sh`

To start the system for querying/browsing.

**Usage:**
```bash
# Start Docker Services
./Scripts/start_obsidian_rag.sh

# Stop Services
./Scripts/stop_obsidian_rag.sh
```

---

## Architecture Diagram

```mermaid
graph LR
    subgraph Mini["Mac Mini (Indexer)"]
        direction TB
        SSD_Mini[("Local SSD<br>~/obsidian_rag_local_data")]
        Index(["1. run_indexing.sh"]) --> SSD_Mini
        Push(["2. sync/push.sh"])
    end

    subgraph Cloud["iCloud Drive (Transfer Bus)"]
        Export[("data/export_stage")]
    end

    subgraph Mac["MacBook (Consumer)"]
        direction TB
        Pull(["3. sync/pull.sh"])
        SSD_Mac[("Local SSD<br>~/obsidian_rag_local_data")]
        Query(["4. start_obsidian_rag.sh"])
    end

    SSD_Mini --> Push
    Push -->|Push Snapshot| Export
    Export -->|Pull Snapshot| Pull
    Pull --> SSD_Mac
    SSD_Mac --> Query
```

---

## Troubleshooting

### "Naive" Results on MacBook?
If you see "Naive" mode instead of "Hybrid":
1.  **Check Sync**: Did you run `pull.sh` recently?
2.  **Check Ollama**: Ensure Ollama is running (`ollama serve`). The embedding model (`nomic-embed-text`) must be available for vectors to work.
3.  **Check Logs**:
    ```bash
    docker logs obsidian-lightrag
    ```
    If you see "Refusing result because it starts with 'not found'", it means retrieval failed.

### "Database Locked" Errors?
*   Should NOT happen with this new architecture.
*   If it does, ensure you are NOT trying to index on the MacBook or access the `data/export_stage` directly from Docker. Always use the local copies.

### Scripts Missing?
*   Old/Legacy scripts have been archived to `Scripts/archive_old_v2`.
*   Only use the validated scripts listed above.

---

**Last Updated:** January 22, 2026
