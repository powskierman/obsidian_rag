# Obsidian RAG Spec

## Summary
Obsidian RAG provides a local-first retrieval system for an Obsidian vault,
combining fast single-pass vector search, a staged grounded-research pipeline,
and an agentic multi-step research loop, all behind a single API gateway.

## Goals
- Provide a unified API surface (`ask`, `research`, `investigate`) over a single gateway.
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
- As a user, I want a simple three-mode search surface — `ask`, `research`,
  `investigate` — so I do not need to choose among many overlapping graph modes.
- As a user, I want the agentic `investigate` mode to stream progress over a
  WebSocket so I can watch a multi-step plan unfold.
- As a maintainer, I want incremental indexing by default so day-to-day edits do
  not require full rebuilds.
- As a maintainer, I want a documented full reindex workflow so I can recover from
  corruption or major vault changes.
- As an operator, I want health and provider-status endpoints so I can quickly
  verify what is reachable.
- As a security-conscious user, I want API keys and destructive operations gated
  by environment configuration.

## Functional Requirements
- The system shall expose a unified gateway with:
  - `POST /api/v1/query`
  - `GET /api/v1/health`
  - `GET /api/v1/stats`
  - `GET /api/v1/providers`
  - `GET /api/v1/provider-status`
  - WebSocket investigate at `ws://localhost:4000/api/v1/deep-research`.
- The gateway shall support canonical search modes:
  - `ask` and `research` on `POST /api/v1/query`
  - `investigate` on `ws://localhost:4000/api/v1/deep-research`
- The gateway shall continue to accept legacy mode strings (`vector`,
  `cascading`, `vault_review`, `mempalace`, `deep-thinking`) and emit a
  `X-Deprecated-Mode` response header when one is used.
- The gateway shall accept optional `depth` (`auto`|`shallow`|`staged`|`full`)
  and `sources` (`vault`|`mempalace`|`web`) fields on `POST /api/v1/query`.
- The system shall support incremental indexing for vector and graph data stores.
- The system shall support explicit full reindexing of vector, NetworkX, and LightRAG
  stores when requested.
- NetworkX and LightRAG are internal retrieval subsystems, not separate public search modes.
- The system shall run locally with Docker Compose using service boundaries and ports:
  - Embedding service (8000), LightRAG (8001), Graph service (8002), Gateway (4000),
    MCP server (8811), Streamlit (8501), Next.js webapp (3030).
- The system shall allow optional web search augmentation (Tavily) when a valid
  API key is set, and optional MemPalace memory search via the host sidecar at
  port 7788.

## Non-Functional Requirements
- Latency targets for typical queries (canonical names; legacy in parentheses):
  - `ask` (vector) < 1s
  - `research` (cascading) < 8s
  - `investigate` (deep-thinking) < 120s
- Generated databases shall remain local-only and rebuildable.
- Indexing workflows shall be safe to run repeatedly without data loss.

## Assumptions
- Users provide an Obsidian vault path via environment configuration.
- API keys are stored in `.env` and loaded at runtime.
- The system operates on a single-user local machine or local network.

## Success Criteria
- Health checks pass for gateway and core services.
- `ask`, `research`, and `investigate` each return results for a typical query.
- Indexing can be run incrementally and as a full rebuild without errors.

## References
- `reference/architecture/SYSTEM_ARCHITECTURE_DIAGRAM.md`
- `reference/architecture/DEEP_THINKING_FLOW.md`
- `reference/architecture/GRAPH_STACK_RETIREMENT_MAP.md`
- `reference/api/UNIFIED_API_IMPLEMENTATION.md`
- `reference/search/SEARCH_ARCHITECTURE.md`
- `reference/search/RESEARCH_MODE_FLOW.md`
- `operations/indexing/REINDEXING_PROCEDURE.md`
- `operations/DATABASE_MANAGEMENT.md`
