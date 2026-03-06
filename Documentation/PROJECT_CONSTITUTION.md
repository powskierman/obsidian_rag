# Obsidian RAG Constitution

This document is mirrored in:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/PROJECT_CONSTITUTION.md`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/.specify/memory/constitution.md`

Both files must remain aligned.

## Purpose
Obsidian RAG is a local-first retrieval system for a personal Obsidian vault. It combines vector search, staged cascading retrieval, and deep thinking behind a unified API gateway, with repeatable indexing workflows and strong privacy defaults.

## Primary Users and Use Cases
- Knowledge workers querying private vault content.
- Fast vector retrieval and thorough cascading retrieval.
- Deep research flows with streaming updates and multi-step reasoning.

## Scope
In scope:
- Local services: embedding, NetworkX graph, LightRAG graph, API gateway, Streamlit UI, and WebApp.
- Search entry points: `vector`, `cascading`, and deep-research WebSocket.
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
- Streamlit UI: `8501`

Features must respect these boundaries and route client traffic through the gateway public interfaces.

### III. Independent Indexing
Incremental indexing is the default. Graph and vector indexes must be rebuildable independently. Full rebuilds are explicit operations, not side effects.

### IV. Spec-Driven Development
Work is driven by Spec Kit artifacts (spec, plan, tasks). Documentation updates are required for new or changed workflows/APIs.

### V. Quality and Performance Gates
Changes must satisfy functional and performance gates defined in this constitution before being considered done.

## Public Interfaces (API Gateway)
- `POST /api/v1/query`
- `GET /api/v1/health`
- `GET /api/v1/stats`
- `ws://localhost:4000/api/v1/deep-research`

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
- Latency targets:
  - Vector: `< 1s`
  - Cascading: `< 8s`
  - Deep Thinking: `< 120s`

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
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/SYSTEM_OVERVIEW_2025.md`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/UNIFIED_API_IMPLEMENTATION.md`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/INDEXING_STRATEGY.md`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/DEEP_THINKING_PROTOCOL.md`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/STREAMING_IMPLEMENTATION.md`

**Version**: 2.1.1  
**Ratified**: 2025-01-01  
**Last Amended**: 2026-03-06
