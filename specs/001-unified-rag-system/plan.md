# Implementation Plan: Unified RAG System

**Branch**: `001-unified-rag-system` | **Date**: 2026-01-24 | **Spec**: [specs/001-unified-rag-system/spec.md](spec.md)
**Input**: Feature specification from `specs/001-unified-rag-system/spec.md`

## Summary

Implement a unified RAG system for Obsidian vaults, exposing a single API gateway (port 4000) that orchestrates vector (ChromaDB), graph (LightRAG/NetworkX), and hybrid search modes. The system leverages Docker Compose for service orchestration, supports incremental indexing to maintain up-to-date retrieval, and offers streaming capabilities for complex queries.

## Technical Context

**Language/Version**: Python 3.11 (backend services), TypeScript/React (optional webapp components)
**Primary Dependencies**: 
- **FastAPI**: API Gateway and service interfaces.
- **ChromaDB**: Vector storage and retrieval (port 8000).
- **NetworkX**: Graph structure and pathfinding (port 8002).
- **LightRAG**: Entity-centric graph reasoning (port 8001).
- **Docker/Docker Compose**: Container orchestration.
**Storage**: Local filesystem (`chroma_db/`, `lightrag_db/`, `data/graph_data/`) - **Git-ignored**.
**Testing**: `pytest` for backend integration and unit tests.
**Target Platform**: Local macOS (Darwin) environment, Docker Desktop.
**Project Type**: Microservices architecture orchestrated via Docker Compose.
**Performance Goals**: Vector < 1s, Graph < 5s, Hybrid < 8s, Deep Thinking < 120s.
**Constraints**: Local-only data storage (privacy), standard ports (4000, 8000-8002), incremental indexing default.
**Scale/Scope**: Personal knowledge vault (thousands of notes), single-user.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Local-First & Personal**: ✅ System runs locally via Docker; generated DBs are git-ignored (`chroma_db`, `lightrag_db`).
- **II. Authoritative Architecture**: ✅ Adheres to defined ports (4000, 8000, 8001, 8002) and service boundaries.
- **III. Independent Indexing**: ✅ Plan includes independent incremental indexing logic.
- **IV. Spec-Driven Development**: ✅ Following Spec Kit workflow (Spec -> Plan).
- **V. Quality & Performance Gates**: ✅ Success criteria align with latency targets (SC-001 to SC-004).

## Project Structure

### Documentation (this feature)

```text
specs/001-unified-rag-system/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/
├── services/
│   ├── gateway/         # API Gateway (Port 4000)
│   ├── embedding/       # ChromaDB Wrapper (Port 8000)
│   ├── graph/           # NetworkX Service (Port 8002)
│   └── lightrag/        # LightRAG Integration (Port 8001)
├── indexing/            # Indexing scripts and logic
│   ├── index_vault.py
│   └── index_graph.py
├── deep_thinking/       # Deep research modules
└── utils/               # Shared utilities

webapp/                  # Streamlit UI (Port 8501)
├── src/
└── ...

docker-compose.yml       # Service orchestration
Dockerfile               # Common or specific service images
```

**Structure Decision**: Microservices approach (Option 2 variant) best fits the "Authoritative Architecture" principle, separating concerns by runtime service while keeping shared logic in `src/`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A       |            |                                     |