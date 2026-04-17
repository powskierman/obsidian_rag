# Graph Stack Retirement Map

This document defines what must change before the legacy graph stack can be fully retired.

## Current State

The public product contract is:

- REST: `ask`, `research` (legacy: `vector`, `cascading` still accepted)
- WebSocket: `investigate` (endpoint: `/api/v1/deep-research`)

The legacy graph stack is no longer a public mode surface, but it is still a live internal dependency:

- `graph-service` provides NetworkX-backed graph retrieval.
- `lightrag-service` provides LightRAG-backed graph/entity expansion.

## Blocking Runtime Call Paths

Full retirement is not safe until the following runtime dependencies are removed or replaced.

### Cascading retrieval

`src/services/cascading_retriever.py` still makes direct internal graph calls:

- `src/services/cascading_retriever.py:216` -> `POST {graph_url}/query`
- `src/services/cascading_retriever.py:273` -> `POST {lightrag_url}/query`

These are the core internal graph lookups used during anchor retrieval and expansion. Retiring the graph stack before replacing these calls will break `cascading`.

### API gateway service wiring

`src/services/api_gateway.py` still wires the graph stack into live runtime behavior:

- `src/services/api_gateway.py:2204` -> `GRAPH_SERVICE_URL` environment configuration
- `src/services/api_gateway.py:2205` -> `LIGHTRAG_SERVICE_URL` environment configuration
- `src/services/api_gateway.py:2396` -> health probe to `{GRAPH_SERVICE_URL}/health`
- `src/services/api_gateway.py:2409` -> health probe to `{LIGHTRAG_SERVICE_URL}/health`
- `src/services/api_gateway.py:2423` -> stats probe to `{LIGHTRAG_SERVICE_URL}/stats`
- `src/services/api_gateway.py:2674-2677` -> `CascadingRetriever(graph_url=..., lightrag_url=...)`
- `src/services/api_gateway.py:3356` -> deep-research supervisor configuration with `graph_service_url=GRAPH_SERVICE_URL`

Retiring the graph stack before removing these references will break gateway startup, health reporting, cascading construction, and deep-research orchestration.

### Deep-research orchestration

The deep-research path still receives `graph_service_url` from the gateway at `src/services/api_gateway.py:3356` and uses graph-backed retrieval during multi-step reasoning. Full retirement is not safe until that orchestration path can complete without NetworkX/LightRAG services.

### MCP internal graph tools

`src/mcp/obsidian_rag_unified_mcp.py` still exposes direct internal graph helpers that call:

- `src/mcp/obsidian_rag_unified_mcp.py:78` -> `GRAPH_SERVICE_URL` configuration
- `src/mcp/obsidian_rag_unified_mcp.py:2809` -> `POST {GRAPH_SERVICE_URL}/query`

Affected internal tools include:

- `obsidian_graph_query`
- `find_entity_path`
- `search_entities`
- `get_graph_stats`

These are not the main public contract, but they remain live internal runtime callers.

## Required Changes Before Full Retirement

### 1. Replace cascading graph dependencies

`cascading_retriever.py` must stop calling both:

- `graph_url/query`
- `lightrag_url/query`

Safe retirement options:

- rewrite cascading to use vector-only retrieval plus reranking, or
- replace the graph services with an in-process retrieval abstraction that preserves current behavior.

### 2. Replace deep-research graph dependencies

The deep-research pipeline must stop requiring `graph_service_url` and must no longer depend on graph-backed retrieval steps for planning or evidence collection.

### 3. Remove gateway graph wiring

`api_gateway.py` must no longer:

- read `GRAPH_SERVICE_URL`
- read `LIGHTRAG_SERVICE_URL`
- probe graph/lightRAG health endpoints
- surface graph/lightRAG stats as active runtime dependencies
- construct `CascadingRetriever` with graph/lightRAG URLs

At that point, the compose `depends_on` entries and related environment variables can be removed safely.

### 4. Remove or isolate MCP graph helpers

The graph-only MCP tools must either:

- be deleted, or
- move into an optional internal-only MCP package that is not started in the default runtime.

### 5. Remove Docker/runtime dependencies

Only after steps 1 through 4 are complete is it safe to remove:

- `graph-service` from Docker compose
- `lightrag-service` from Docker compose
- startup/status script checks for those services
- any health/readiness gating that assumes those containers exist

## Safe Retirement Sequence

1. Refactor `cascading` off graph/lightRAG runtime calls.
2. Refactor `deep-research` off graph-backed runtime calls.
3. Remove internal MCP graph callers or isolate them behind an optional profile.
4. Remove gateway env wiring and health/stats dependencies.
5. Remove Docker services and startup script references.

Until those steps are complete, the graph stack can be treated as internal and legacy, but not retired.
