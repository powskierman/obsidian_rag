<!--
Sync Impact Report:
- Version Change: Template -> 2.0.0
- Modified Principles:
  - [PRINCIPLE_1] -> I. Local-First & Personal (Derived from Purpose/Scope)
  - [PRINCIPLE_2] -> II. Authoritative Architecture (Derived from System Architecture)
  - [PRINCIPLE_3] -> III. Independent Indexing (Derived from Data Principles)
  - [PRINCIPLE_4] -> IV. Spec-Driven Development (Derived from Development Workflow)
  - [PRINCIPLE_5] -> V. Quality & Performance Gates (Derived from Targets)
- Added Sections:
  - Security & Privacy
  - Public Interfaces
- Templates Checked:
  - .specify/templates/plan-template.md (Compatible)
  - .specify/templates/spec-template.md (Compatible)
  - .specify/templates/tasks-template.md (Compatible)
-->

# Obsidian RAG Constitution

## Core Principles

### I. Local-First & Personal
Obsidian RAG is a local-first retrieval system optimized for personal knowledge work. Generated databases (vector, graph) are local-only and must not be tracked in version control as they may contain private content. No centralized hosted or multi-tenant deployment is supported; the system is designed to run on the user's machine.

### II. Authoritative Architecture
The system architecture defines rigid service boundaries and ports that must be respected: Embedding (ChromaDB) on 8000, LightRAG on 8001, NetworkX Graph on 8002, API Gateway on 4000, and Streamlit UI on 8501. All feature implementations must align with this topology and communicate via the API Gateway.

### III. Independent Indexing
Incremental indexing is the default workflow. Graph and vector indexes must be capable of independent rebuilding. Vault standardization (naming, links, templates) is enforced to ensure retrieval quality. Full rebuilds are explicit operations, not side effects.

### IV. Spec-Driven Development
All development work is driven by Spec Kit artifacts: specifications, implementation plans, and task lists. Implementation must proceed via the defined API gateway and service boundaries. Documentation updates (tracked in `Documentation/INDEX.md`) are mandatory for new workflows or APIs.

### V. Quality & Performance Gates
Changes must pass the mode audit script (`python Scripts/audit_search_modes.py`) with non-zero sources where applicable. Latency targets are strictly enforced: Vector < 1s, Graph < 5s, Hybrid < 8s, and Deep Thinking < 120s.

## Security & Privacy

API keys (e.g., OpenRouter, Gemini, Tavily) must be loaded from environment variables (`.env`). Destructive operations, such as clearing embeddings, require a specific token (`EMBEDDING_CLEAR_TOKEN`). Privacy is paramount; no private vault content should be exposed inadvertently through logging or external transmissions.

## Public Interfaces

The system exposes a defined set of public interfaces via the API Gateway:
- `POST /api/v1/search`: Standard retrieval.
- `POST /api/v1/search/stream`: Server-Sent Events for streaming responses.
- `GET /api/v1/health` & `GET /api/v1/stats`: System monitoring.
- `ws://localhost:4000/api/v1/deep-research`: WebSocket for deep research flows.

## Governance

This constitution supersedes ad-hoc practices. Amendments must be documented in this file and reflected in `Documentation/PROJECT_CONSTITUTION.md`. Compliance is verified via PR reviews and the execution of the `audit_search_modes.py` script. New features must pass the Definition of Done: health checks pass, search modes functional, documentation updated, and indexing rules consistent.

**Version**: 2.0.0 | **Ratified**: 2025-01-01 | **Last Amended**: 2026-01-24