# Obsidian RAG Documentation

Use this as the entry point for active project documentation.

## Quick Start
1. Configure environment: `./Setup/QUICKSTART.md`
2. Start services: `./Scripts/setup/start_obsidian_rag.sh`
3. Verify health endpoints:
   - Gateway: `curl -s http://localhost:4000/api/v1/health`
   - Embedding service: `curl -s http://localhost:8000/health`
   - LightRAG service: `curl -s http://localhost:8001/health`
   - Graph service: `curl -s http://localhost:8002/health`
4. Run a query with canonical mode names (`vector`, `cascading`, `deep-research`)

## Core References
- System overview: `./SYSTEM_OVERVIEW_2025.md`
- API quickstart: `./API_GATEWAY_QUICKSTART.md`
- Unified API details: `./UNIFIED_API_IMPLEMENTATION.md`
- Web search details: `./WEB_SEARCH_IMPLEMENTATION.md`
- Search modes: `./Features/SEARCH_MODES_GUIDE.md`
- Indexing scripts: `./Setup/INDEXING_SCRIPTS_GUIDE.md`
- Canonical partial LightRAG indexing: `./Setup/LIGHTRAG_PARTIAL_INDEXING_GUIDE.md`
- Reindexing procedure: `./REINDEXING_PROCEDURE.md`
- Database management: `./DATABASE_MANAGEMENT.md`
- MCP setup: `./MCP/MCP_SETUP_INSTRUCTIONS.md`

## Useful Commands
```bash
# Start / stop services
./Scripts/setup/start_obsidian_rag.sh
./Scripts/setup/stop_obsidian_rag.sh

# Full indexing pipeline
./Scripts/indexing/run_indexing.sh

# Targeted indexing
./Scripts/indexing/update_vector_db.sh --refresh
./Scripts/indexing/update_knowledge_graph.sh
./Scripts/indexing/index_with_lightrag.sh
./Scripts/indexing/partial_index_lightrag.sh --batch-size 5 --retry-failed-once
```

## API Endpoints
- `GET /api/v1/health`
- `GET /api/v1/stats`
- `POST /api/v1/query`
- `POST /api/v1/query`
- WebSocket: `ws://localhost:4000/api/v1/deep-research`

Notes:
- `POST /api/v1/query` currently supports `vector` and `cascading`.
- Deep thinking uses `ws://localhost:4000/api/v1/deep-research`.
- `lmstudio` is the supported local OpenAI-compatible provider label; `mlx` remains a compatibility alias in parts of the backend.
- Enhanced search returns supplemental web-search results after vault sources in the webapp.
- Active documentation intentionally excludes archived historical documents from navigation.

## Full Index
- `./INDEX.md`
