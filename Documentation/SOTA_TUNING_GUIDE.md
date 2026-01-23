# SOTA Retrieval Tuning Guide (M4 Pro / Metal Acceleration)

This guide documents the "State of the Art" (SOTA) retrieval upgrade applied to the Obsidian RAG system. It is optimized for Apple Silicon (M-Series) hardware, specifically leveraging the **M4 Pro** via **Metal Performance Shaders (MPS)** for high-speed local indexing.

## 🚀 Upgrade Summary

1.  **Embedding Model**: Switched from `all-MiniLM-L6-v2` (256 context) to **`nomic-embed-text-v1.5`** (8192 context).
    *   *Why?* To solve truncation issues where valid "Impression" sections in scan reports were cut off.
2.  **Chunk Size**: Increased from `1000` to **`4000` characters** (with 500 overlap).
    *   *Why?* To feed larger, complete sections to the Nomic model.
3.  **Acceleration**: Enabled `mps` (Metal) support in the embedding service code.

---

## 🛠️ Execution Procedure (Run on Mac Mini)

Since your Mac Mini is the primary Indexer, execute these steps directly on the Mini's terminal to perform a high-performance re-indexing.

### 1. Preparation
Ensure your code is synced from iCloud.
```bash
cd /path/to/your/obsidian_rag
ls -l src/services/embedding_service.py # Verify recent timestamp
```

### 2. Environment Setup
Install dependencies (including `torch` with MPS support and `einops`) on the host system.
```bash
pip3 install -r requirements.txt
```

### 3. Configure Local Storage Path (Critical)
To maximize SSD performance and avoid iCloud sync issues with the database, define a local storage path.
```bash
# Example: Local SSD folder
export CHROMA_DB_PATH=~/obsidian_rag_local_data/chroma_db
mkdir -p $CHROMA_DB_PATH
```

### 4. Run Tuning Process (MPS Accelerated)

**Step A: Clean Up Docker**
Stop the existing container to release the database lock and ports.
```bash
docker-compose stop embedding-service
```

**Step B: Load Environment Variables**
Ensure the indexer has access to necessary keys.
```bash
export $(grep -v '^#' .env | xargs)
```

**Step C: Start Native Embedding Service**
Open a **new terminal tab** (or run in background). This service will use your M4 Pro's Neural Engine/GPU via Metal.
```bash
export CHROMA_DB_PATH=~/obsidian_rag_local_data/chroma_db
export TOKENIZERS_PARALLELISM=false
python3 src/services/embedding_service.py
```
*Wait until you see: `Loading embedding model (Nomic v1.5) on mps...`*

**Step D: Run Turbo Indexer**
In the **original tab**, run the full re-idexing command.
```bash
# --full (ignores cache) --clear (resets DB)
python3 src/indexing/index_vault.py --full --clear --url http://localhost:8000
```
*Watch the progress bar fly. Nomic v1.5 with 4000-char chunks will provide rich context.*

**Step E: Teardown**
Once indexing is `✅ Indexing complete!`:
1. Stop the python service (Ctrl+C).
2. Exit the terminal tab.

### 5. Persistent Configuration (Docker Override)
To ensure the Docker containers see this new Local DB when they restart, update your `docker-compose.override.yml`:

```yaml
services:
  embedding-service:
    volumes:
      # Map your LOCAL path to the container's path
      - ~/obsidian_rag_local_data/chroma_db:/app/chroma_db:rw,cached
```

### 6. Restart & Verify
```bash
# Rebuild to bake in Nomic dependencies for runtime
docker-compose up -d --build embedding-service
docker-compose up -d

# Verify SOTA Retrieval
python3 Scripts/debug/test_all_modes.py
```

## ✨ Expected Results
Queries like *"Summarize the progression of my Lymphoma"* should now return snippets containing complete, detailed sections (e.g., full "Impression" and "SUV" data) with high relevance scores (>60%), thanks to the 8k context window.
