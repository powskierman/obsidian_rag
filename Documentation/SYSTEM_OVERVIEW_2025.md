# Obsidian RAG System Overview (2025)

This system combines vector search, a note graph, and an entity graph behind a single API gateway.

## Core Services

- **Embedding service** (port 8000): ChromaDB vector search for vault content.
- **LightRAG service** (port 8001): entity-centric graph for semantic queries.
- **Graph service** (port 8002): NetworkX note graph reasoning and hybrid retrieval.
- **API gateway** (port 4000): unified `/api/v1/query` entry point and health checks.
- **Streamlit UI** (port 8501): interactive UI wired to the gateway.

## Search Modes

- **vector**: semantic similarity search (fast retrieval).
- **graph**: graph reasoning over note relationships.
- **hybrid**: graph answer + vector sources.
- **dual-graph**: combines LightRAG and NetworkX via the gateway.

Optional flags:
- `web_search`: Tavily augmentation (requires API key).
- `llm_knowledge`: add general LLM background section.
- `streaming`: SSE endpoints for streaming results.

## Data Stores

- `chroma_db/` for embeddings.
- `lightrag_db/` for entity graph data.
- `data/graph_data/` for NetworkX graph snapshots.

## Entry Points

- Start services: `docker compose up -d`
- Unified API: `POST http://localhost:4000/api/v1/query`
- Graph service (direct): `POST http://localhost:8002/query`

## Related Docs

- `Documentation/API_GATEWAY_QUICKSTART.md`
- `Documentation/VECTOR_MODE_IMPLEMENTATION.md`
- `Documentation/HYBRID_SEARCH_IMPLEMENTATION.md`
- `Documentation/DUAL_GRAPH_QUERY_API.md`
- `Documentation/Graph/IMPROVED_GRAPH_BUILDER_GUIDE.md`
