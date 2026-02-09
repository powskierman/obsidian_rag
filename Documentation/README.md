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
4. Run a query with canonical mode names (`vector`, `notes`, `entities`, `notes+vector`, `entities+vector`, `dual-graph`, `hybrid`, `cascading`)

## Core References
- System overview: `./SYSTEM_OVERVIEW_2025.md`
- API quickstart: `./API_GATEWAY_QUICKSTART.md`
- Unified API details: `./UNIFIED_API_IMPLEMENTATION.md`
- Search modes: `./Features/SEARCH_MODES_GUIDE.md`
- Indexing scripts: `./Setup/INDEXING_SCRIPTS_GUIDE.md`
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
```

## API Endpoints
- `GET /api/v1/health`
- `GET /api/v1/stats`
- `POST /api/v1/search`
- `POST /api/v1/query`
- WebSocket: `ws://localhost:4000/api/v1/deep-research`

Notes:
- `graph` is still accepted as a backward-compatible alias for `notes`.
- Active documentation intentionally excludes archived historical documents from navigation.

## Full Index
- `./INDEX.md`
