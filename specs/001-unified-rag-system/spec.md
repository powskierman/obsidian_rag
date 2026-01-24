# Feature Specification: Unified RAG System

**Feature Branch**: `001-unified-rag-system`
**Created**: 2026-01-24
**Status**: Draft
**Input**: Baseline specification for the existing Obsidian RAG system

## User Scenarios & Testing

### User Story 1 - Multi-Mode Retrieval (Priority: P1)

As a knowledge worker, I want to perform searches using vector, graph, hybrid, and deep-thinking modes through a single API so that I can retrieve information from my Obsidian vault according to the complexity of my question.

**Why this priority**: Core value proposition of the system; without this, it is just a standard search tool.

**Independent Test**: Can be tested by sending requests to `POST /api/v1/search` with different `mode` parameters (`vector`, `graph`, `hybrid`) and verifying distinct response structures.

**Acceptance Scenarios**:

1. **Given** the API gateway is running, **When** I send a `vector` search request, **Then** I receive semantic search results with source chunks.
2. **Given** the API gateway is running, **When** I send a `graph` search request, **Then** I receive a synthesized answer based on network relationships.
3. **Given** the API gateway is running, **When** I send a `deep-thinking` request via WebSocket, **Then** I receive a multi-step reasoned response.

---

### User Story 2 - Incremental Indexing (Priority: P1)

As a maintainer, I want the system to index only changed files by default so that I can keep the search index up-to-date with my daily notes without waiting for full rebuilds.

**Why this priority**: Essential for usability; full rebuilds are too slow for daily workflows.

**Independent Test**: Add a new note to the vault, run the indexing script, and verify only that note is processed and searchable.

**Acceptance Scenarios**:

1. **Given** an existing index, **When** I modify a single note and run indexing, **Then** only that note is re-embedded and updated in the graph.
2. **Given** a corrupted index, **When** I trigger a full rebuild, **Then** all previous data is wiped and regenerated from scratch.

---

### User Story 3 - Streaming Responses (Priority: P2)

As a user, I want to see search results streaming in real-time so that I don't have to stare at a loading spinner during long-running hybrid or deep-thinking queries.

**Why this priority**: Improves perceived performance and user experience for complex queries.

**Independent Test**: Connect to the SSE endpoint `POST /api/v1/search/stream` and observe chunks arriving over time.

**Acceptance Scenarios**:

1. **Given** a long-running query, **When** I access the streaming endpoint, **Then** I receive partial text tokens immediately as they are generated.

### Edge Cases

- **Service Downtime**: If the Graph service (port 8002) is unreachable during a hybrid search, the system MUST return partial results from the Vector service with a status warning, rather than failing completely.
- **Empty Vault**: If the vault is empty or unindexed, search queries MUST return an empty result set with a user-friendly "Index is empty" message, not a 500 error.
- **Invalid API Key**: If a user attempts a Deep Thinking search without a valid API key, the WebSocket connection MUST close with a specific error code (e.g., 4003) and a descriptive message.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST expose a unified API gateway on port 4000.
- **FR-002**: The gateway MUST support `POST /api/v1/search` for synchronous retrieval.
- **FR-003**: The gateway MUST support `POST /api/v1/search/stream` for Server-Sent Events (SSE).
- **FR-004**: The gateway MUST support `ws://localhost:4000/api/v1/deep-research` for WebSocket-based deep research sessions.
- **FR-005**: The system MUST support the following search modes: `vector`, `graph`, `hybrid`, `dual-graph`, `cascading`, and `deep-thinking`.
- **FR-006**: The system MUST run locally using Docker Compose with defined service boundaries: Embedding (8000), LightRAG (8001), Graph (8002), Gateway (4000).
- **FR-007**: The system MUST support incremental indexing for both ChromaDB (vector) and LightRAG (graph) stores.
- **FR-008**: The system MUST allow explicit full reindexing of all data stores.
- **FR-009**: The system MUST enforce local-only storage for generated databases; no data shall be implicitly pushed to remote servers.
- **FR-010**: The system MUST load API keys from `.env` files at runtime.

### Key Entities

- **Vault**: The local directory containing Obsidian markdown notes.
- **Vector Index**: ChromaDB store containing semantic embeddings of note chunks.
- **Knowledge Graph**: LightRAG/NetworkX structure representing entities and relationships extracted from notes.
- **Search Query**: A user request containing text and a specified execution mode.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Vector search returns results in < 1 second for typical queries.
- **SC-002**: Graph search returns results in < 5 seconds.
- **SC-003**: Hybrid search returns results in < 8 seconds.
- **SC-004**: Deep thinking sessions complete in < 120 seconds.
- **SC-005**: Health check endpoint (`/api/v1/health`) returns 200 OK for all core services.
- **SC-006**: Indexing process successfully updates a vault with 10 new notes in < 1 minute (incremental).

## Assumptions

- Users have a valid Obsidian vault available locally.
- Docker and Docker Compose are installed and running.
- Necessary API keys (OpenRouter, Gemini, etc.) are available if external LLM features are used.
- The system operates in a single-user environment (no multi-tenant isolation).