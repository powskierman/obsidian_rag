# Obsidian RAG Constitution

This document is the authoritative copy. It is also mirrored in `.specify/memory/constitution.md` — both files must remain aligned.

## Purpose
Obsidian RAG is a local-first retrieval system for a personal Obsidian vault. It combines vector search, staged cascading retrieval, and deep thinking behind a unified API gateway, with repeatable indexing workflows and strong privacy defaults.

## Primary Users and Use Cases
- Knowledge workers querying private vault content.
- Fast vector retrieval and thorough cascading retrieval.
- Deep research flows with streaming updates and multi-step reasoning.

## Scope
In scope:
- Local services: embedding, internal NetworkX graph subsystem, internal LightRAG subsystem, API gateway, Streamlit UI, and WebApp (Next.js, host port `3030`).
- Search entry points: `ask` and `research` on `POST /api/v1/query`, plus `investigate` on the deep-research WebSocket. Legacy mode names (`vector`, `cascading`, `vault_review`, `mempalace`, `deep-thinking`) are still accepted at the boundary and normalized via `src/services/query_dispatch.py`.
- Optional external sources: web search via Tavily (`sources=["web"]`), and the host-side MemPalace sidecar (`sources=["mempalace"]`).
- Incremental indexing and explicit rebuild workflows.
- MCP integration and Docker-based local deployment.

Out of scope:
- Multi-tenant or centralized hosted deployments.
- Tracking generated databases in Git.

## Core Principles
### I. Local-First and Personal
Generated databases are local-only and may contain private data. They must not be committed to version control.

### II. Authoritative Architecture
Service boundaries and ports are fixed:
- Embedding (ChromaDB): `8000`
- LightRAG: `8001`
- NetworkX Graph: `8002`
- API Gateway: `4000`
- MCP Server (HTTP transport): `8811`
- Streamlit UI: `8501`
- Next.js WebApp: `3030`
- MemPalace sidecar (host-side, not in compose): `7788`

Features must respect these boundaries and route client traffic through the gateway public interfaces.

### III. Independent Indexing
Incremental indexing is the default. Graph and vector indexes must be rebuildable independently. Full rebuilds are explicit operations, not side effects.

### IV. Spec-Driven Development
Work is driven by Spec Kit artifacts (spec, plan, tasks). Documentation updates are required for new or changed workflows/APIs.

### V. Quality and Performance Gates
Changes must satisfy functional and performance gates defined in this constitution before being considered done.

## Public Interfaces (API Gateway)
- `POST /api/v1/query` — canonical modes `ask`, `research`. Legacy strings still accepted with a deprecation header.
- `GET /api/v1/health` — aggregate service health.
- `GET /api/v1/stats` — index sizes and last-update timestamps.
- `GET /api/v1/providers` — list of configured LLM providers.
- `GET /api/v1/provider-status` — reachability/error state for each provider.
- `ws://localhost:4000/api/v1/deep-research` — `investigate` agentic streaming endpoint.

NetworkX and LightRAG are internal retrieval dependencies. They are not exposed as separate public search modes.

## Data and Indexing Principles
- Primary stores:
  - `${OBSIDIAN_RAG_DATA_DIR}/chroma_db`
  - `${OBSIDIAN_RAG_DATA_DIR}/lightrag_db`
  - `${OBSIDIAN_RAG_DATA_DIR}/graph_data`
- Indexing defaults to incremental refresh.
- Vault standardization (naming, links, metadata, templates) is part of retrieval quality.

## Quality and Performance Targets
Authoritative audit script:
- `python Scripts/debug/audit_search_modes.py`

Pass criteria:
- Status must be `PASS`.
- Non-chat retrieval modes must return non-zero sources.
- Latency targets (canonical names; legacy in parentheses):
  - `ask` (vector): `< 1s`
  - `research` (cascading): `< 8s`
  - `investigate` (deep-thinking, WebSocket): `< 120s`

## Security and Privacy
- API keys are sourced from environment variables (`.env`).
- Destructive embedding operations require `EMBEDDING_CLEAR_TOKEN`.
- Logging and telemetry must avoid exposing private vault content.

## Development Workflow and Definition of Done
Required for completion:
- Relevant tests and health/smoke checks pass.
- Search modes remain functional for the changed path.
- Documentation and public interface references are updated.
- Indexing and data-storage rules remain constitution-compliant.

## Governance
This constitution supersedes ad-hoc practices. Changes must update both mirrored constitution files in the same change set.

## Canonical References
- `Documentation/reference/api/UNIFIED_API_IMPLEMENTATION.md`
- `Documentation/reference/search/SEARCH_ARCHITECTURE.md`
- `Documentation/reference/search/RESEARCH_MODE_FLOW.md`
- `Documentation/reference/architecture/DEEP_THINKING_FLOW.md`
- `Documentation/reference/streaming/STREAMING_IMPLEMENTATION.md`
- `Documentation/operations/indexing/REINDEXING_PROCEDURE.md`
- `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md`

**Version**: 2.2.0
**Ratified**: 2025-01-01
**Last Amended**: 2026-04-26
