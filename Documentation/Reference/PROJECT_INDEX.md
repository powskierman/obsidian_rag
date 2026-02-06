# Obsidian RAG Project - Complete Index

## Files Overview

This project uses a Docker-based architecture for RAG (Retrieval Augmented Generation).

1. **Documentation/Setup/INDEXING_SCRIPTS_GUIDE.md** - The definitive guide for indexing.
2. **src/indexing/** - Core Python indexing logic.
3. **Scripts/** - Shell scripts for orchestration.

---

## Quick Navigation

### For First-Time Users
1. Read: **Documentation/Setup/QUICKSTART.md**
2. Run: `./Scripts/setup/start_obsidian_rag.sh`
3. Open: `http://localhost:3000`

### For Indexing
1. Full Rebuild: `./Scripts/indexing/run_indexing.sh`
2. Vector Only: `python src/indexing/index_vault.py`
3. Graph Only: `python src/services/build_graph.py`

### For Troubleshooting
1. Read: **Documentation/DATABASE_MANAGEMENT.md**
2. Check Services: `docker compose ps`
3. View Logs: `docker compose logs -f`

---

## Key Entry Points

```bash
# 1. Start System
./Scripts/setup/start_obsidian_rag.sh

# 2. Stop System
./Scripts/setup/stop_obsidian_rag.sh

# 3. Full Re-Index
./Scripts/indexing/run_indexing.sh

# 4. Sync to iCloud (for multi-device)
./Scripts/sync/push.sh
```

---

## Project Structure at a Glance

```
obsidian_rag/
├── Scripts/                          ⭐ Entry points
│   ├── setup/start_obsidian_rag.sh   Start services
│   ├── setup/stop_obsidian_rag.sh    Stop services
│   ├── indexing/run_indexing.sh      Master indexing script
│   └── sync/                         Data sync scripts
│
├── src/                              ⭐ Source Code
│   ├── indexing/                     Indexing logic (vectors/graph)
│   ├── services/                     API Gateway & Microservices
│   └── deep_thinking/                Advanced reasoning modules
│
├── Documentation/                    ⭐ Guides
│   ├── Setup/                        Installation & Indexing
│   ├── DATABASE_MANAGEMENT.md        Maintenance & Troubleshooting
│   └── Reference/                    This index
│
├── docker-compose.yml                ⭐ Service Orchestration
└── .env                              ⭐ Configuration
```

---

## Validated Dependencies

### Required
*   Docker Desktop
*   Python 3.11+
*   Ollama (for local embeddings)
*   API Keys (Anthropic/OpenAI/Gemini for reasoning)

### Databases (Local - Not Tracked)
*   `chroma_db/`: Vector Store
*   `data/graph_data/`: NetworkX Graph
*   `lightrag_db/`: Entity Graph

---

*Last Updated: January 2026*
