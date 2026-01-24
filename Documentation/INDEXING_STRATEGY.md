# Indexing Strategy & Maintenance SOP

## Overview
This document defines the strategy for keeping the Obsidian RAG Index (Vector + Graph) synchronized across devices (MacBook + Mac Mini).

### The Challenge
*   **Editing:** Happens on MacBook (via Obsidian).
*   **Indexing/Serving:** Happens on Mac Mini (via Docker).
*   **Sync:** iCloud Drive handles file propagation.
*   **Lag:** The Index on the Mac Mini becomes **stale** until `index_vault.py` is run locally on the Mini.

## 1. Incremental Indexing (Vector)
The script `src/indexing/index_vault.py` is designed for safety and speed.
*   **Mechanism:** Checks MD5 hash of every file.
*   **Behavior:** Only updates chunks for files that have changed (e.g., added Frontmatter).
*   **Cost:** Low (seconds/minutes).

### SOP: Refreshing the Index
**On the Mac Mini:**
1.  Navigate to the project root:
    ```bash
    cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag
    ```
2.  Run the incremental indexer:
    ```bash
    python src/indexing/index_vault.py --refresh
    ```
    *(The `--refresh` flag ensures metadata updates like Tags/Aliases are properly propagated even if the body text didn't change drastically, though explicit MD5 checks should catch it. Use `--refresh` to be safe if fixing metadata issues).*

## 2. Graph Indexing (NetworkX/LightRAG)
The Graph is built from the Index or Raw Files.
*   If Vector Index changes, the Graph might need updates to point to correct chunks.
*   **However**, `kimi_graph_builder.py` usually runs as a batch process.

### SOP: Updating the Graph
If significant structure changes (new MOCs):
1.  Restart the graph service to flush caches:
    ```bash
    docker compose restart graph-service
    ```
2.  (Optional) Rebuild Graph layer if needed (Long process):
    ```bash
    # Only run if you need to extract NEW entities from NEW notes
    # python src/services/build_graph.py
    ```

## 3. Remote Triggering (Recommended Future Workflow)
To avoid switching physical machines, we can implement a "Watch Mode" or a remote trigger.

**Option A: Watch Dog on Mini**
Run a script on the Mini that watches for file changes (using `fswatch` or python `watchdog`) and auto-runs indexer.
*   *Pros:* Zero friction.
*   *Cons:* Can burn CPU if syncing many files.

**Option B: Manual Trigger via SSH**
`ssh mini "cd ... && python src/indexing/index_vault.py"`

## 4. Immediate Fix for "Bread" Frontmatter Issue
1.  **Wait** for iCloud to sync `Authentic-Baguettes.md` to the Mini.
2.  **Run** `python src/indexing/index_vault.py` on the Mini.
3.  **Verify**: The Vector search should now find "bread" in the Tags context.
