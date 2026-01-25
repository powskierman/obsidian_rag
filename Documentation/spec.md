# Obsidian RAG Spec

## Summary
Obsidian RAG provides a local-first retrieval system for an Obsidian vault, combining
vector search and graph reasoning behind a single API gateway with optional streaming
and deep research workflows.

## Goals
- Provide a unified API for multiple search modes.
- Support fast, local retrieval with predictable latency targets.
- Keep indexing repeatable and safe across machines.
- Preserve privacy by keeping generated data local-only.

## Non-Goals
- Hosted, multi-tenant deployment.
- Storing generated vector/graph databases in Git.

## Primary Users
- Knowledge workers querying a personal Obsidian vault.
- Developers maintaining local indexing and search services.

## User Stories
- As a user, I want a single API to run vector, graph, hybrid, dual-graph, cascading,
  and deep-thinking searches so I do not need to choose backends manually.
- As a user, I want streaming responses for long-running queries so I can see
  progress and partial answers.
- As a maintainer, I want incremental indexing by default so day-to-day edits do
  not require full rebuilds.
- As a maintainer, I want a documented full reindex workflow so I can recover from
  corruption or major vault changes.
- As an operator, I want health endpoints so I can quickly verify services.
- As a security-conscious user, I want API keys and destructive operations gated
  by environment configuration.

## Functional Requirements
- The system shall expose a unified gateway with:
  - `POST /api/v1/query`
  - `GET /api/v1/health`
  - `GET /api/v1/stats`
  - WebSocket deep research at `ws://localhost:4000/api/v1/deep-research`.
- The gateway shall support search modes:
  - `vector`, `graph`, `hybrid`, `dual-graph`, `cascading`, `deep-thinking`.
- The system shall support incremental indexing for vector and graph data stores.
- The system shall support explicit full reindexing of vector, NetworkX, and LightRAG
  stores when requested.
- The system shall run locally with Docker Compose using service boundaries and ports:
  - Embedding service (8000), LightRAG (8001), Graph service (8002), Gateway (4000).
- The system shall allow optional web search augmentation when a valid API key is set.

## Non-Functional Requirements
- Latency targets for typical queries:
  - Vector < 1s
  - Graph < 5s
  - Hybrid < 8s
  - Deep thinking < 120s
- Generated databases shall remain local-only and rebuildable.
- Indexing workflows shall be safe to run repeatedly without data loss.

## Assumptions
- Users provide an Obsidian vault path via environment configuration.
- API keys are stored in `.env` and loaded at runtime.
- The system operates on a single-user local machine or local network.

## Success Criteria
- Health checks pass for gateway and core services.
- Each search mode returns results for a typical query.
- Indexing can be run incrementally and as a full rebuild without errors.

## References
- `Documentation/SYSTEM_OVERVIEW_2025.md`
- `Documentation/UNIFIED_API_IMPLEMENTATION.md`
- `Documentation/DEEP_THINKING_PROTOCOL.md`
- `Documentation/INDEXING_STRATEGY.md`
- `Documentation/REINDEXING_PROCEDURE.md`
- `Documentation/DATABASE_MANAGEMENT.md`
