# Project Constitution: Obsidian RAG

## Purpose
Obsidian RAG provides a local-first retrieval system for an Obsidian vault, combining
vector search and graph reasoning behind a single API gateway. It is optimized for
personal knowledge work, fast retrieval, and repeatable indexing across machines.

## Primary Users and Use Cases
- Knowledge workers querying a personal Obsidian vault.
- Hybrid retrieval: direct semantic matches plus graph reasoning.
- Deep research flows that need multi-step reasoning and streaming updates.

## Scope
In scope:
- Local services: embedding, graph, LightRAG, API gateway, and Streamlit UI.
- Search modes: vector, graph, hybrid, dual-graph, cascading, and deep-thinking.
- Indexing workflows for vault content and graph rebuilding.
- MCP integration and Docker-based deployment.

Out of scope:
- Tracking generated databases in Git.
- Centralized hosted or multi-tenant deployment (local-first is the default).

## System Architecture (Authoritative)
Core services and ports:
- Embedding service (ChromaDB) on port 8000.
- LightRAG service on port 8001.
- NetworkX graph service on port 8002.
- API gateway on port 4000.
- Streamlit UI on port 8501.

Primary data stores (local-only, rebuildable):
- `chroma_db/` for vector embeddings.
- `lightrag_db/` for entity graph data.
- `data/graph_data/` for NetworkX snapshots.

## Public Interfaces
- `POST /api/v1/search`
- `POST /api/v1/search/stream` (SSE)
- `GET /api/v1/health`
- `GET /api/v1/stats`
- WebSocket deep research: `ws://localhost:4000/api/v1/deep-research`

## Data and Indexing Principles
- Incremental indexing is the default; full rebuilds are explicit.
- Graph and vector indexes can be rebuilt independently when needed.
- Vault standardization (naming, links, templates) improves retrieval quality.

## Quality and Performance Targets
- Mode audit script: `python Scripts/audit_search_modes.py`.
- Pass criteria: status=PASS and non-zero sources where applicable.
- Latency targets:
  - Vector: < 1s
  - Graph: < 5s
  - Hybrid: < 8s
  - Deep Thinking: < 120s

## Security and Privacy
- API keys are loaded from `.env` (e.g., OpenRouter, Gemini, Tavily).
- Destructive embedding clears require `EMBEDDING_CLEAR_TOKEN`.
- Generated databases are local-only because they may contain private content.

## Development Workflow (Spec Kit)
- Use Spec Kit artifacts to drive work: specs, plans, and tasks.
- Implement via the API gateway and service boundaries described above.
- Update Documentation/INDEX.md when adding or replacing documentation.

## Definition of Done for Changes
- Relevant health checks or smoke tests pass.
- Search modes remain functional for the affected path.
- Documentation is updated for new workflows or APIs.
- Indexing and data storage rules remain consistent with this constitution.

## Canonical References
- `Documentation/SYSTEM_OVERVIEW_2025.md`
- `Documentation/INDEX.md`
- `Documentation/API_GATEWAY_QUICKSTART.md`
- `Documentation/UNIFIED_API_IMPLEMENTATION.md`
- `Documentation/INDEXING_STRATEGY.md`
- `Documentation/REINDEXING_PROCEDURE.md`
- `Documentation/DATABASE_MANAGEMENT.md`
- `Documentation/DEEP_THINKING_PROTOCOL.md`
