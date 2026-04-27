# Search Architecture

This document outlines the 3-mode search architecture for Obsidian RAG, as well as the overall application data flow.

Internal note:
- NetworkX and LightRAG remain deployed as internal retrieval subsystems behind `research` and `investigate`.
- They are not part of the supported public mode surface.

## Application Data Flow

```mermaid
graph TD
    Client[Frontend Client / Next.js] -->|HTTP POST /api/v1/query| Gateway[API Gateway]
    Client -->|WebSocket /api/v1/deep-research| Gateway

    Gateway -->|Ask Mode| Embed[Embedding Service / ChromaDB]
    Gateway -->|Research Mode| Cascading[Cascading Pipeline]
    Gateway -->|Investigate Mode| DeepThinking[Investigate Orchestrator]

    Cascading -->|1. Anchor| GraphService[Graph Service / NetworkX]
    Cascading -->|2. Expand| LightRAG[LightRAG Service]
    Cascading -->|3. Enhance| Embed
    Cascading -->|4. Synthesize| LLM[LLM Provider]

    DeepThinking -->|Multi-step Reasoning| GraphService
    DeepThinking -->|Validation| Embed
    DeepThinking -->|Synthesis| LLM
```

## Search Modes Flowchart

The API Gateway supports three public search modes: `ask`, `research`, and `investigate`.

```mermaid
flowchart TD
    Request[User Search Request] --> Dispatch["query_dispatch.py<br/>normalize_legacy_request()"]
    Dispatch --> Tagged{"X-Deprecated-Mode<br/>middleware"}
    Tagged --> Route{Canonical Mode}

    %% Ask Mode
    Route -->|"mode: ask<br/>(legacy: vector, mempalace)"| AskRoute{"sources?"}
    AskRoute -->|"vault (default)"| Ask[Ask — Vector + Compact Synthesis]
    AskRoute -->|"mempalace"| MP["MemPalace sidecar<br/>host:7788"]
    Ask --> Chroma[(ChromaDB)]
    Chroma --> AskResults[Snippets + Compact Answer]
    MP --> AskResults
    AskResults --> Return[Return to Client]

    %% Research Mode
    Route -->|"mode: research<br/>(legacy: cascading, vault_review)"| Depth{depth?}
    Depth -->|shallow| ShallowVec[Single-pass vector search]
    ShallowVec --> Synthesize
    Depth -->|"auto (default)"| AutoCheck{"Comprehensive vault-review query?"}
    AutoCheck -->|yes| Full
    AutoCheck -->|no| Staged
    Depth -->|staged| Staged
    Depth -->|full| Full

    Staged[Staged Pipeline] --> Anchor[1. Graph Anchor Search]
    Full[Staged Pipeline + Full-note MCP reads] --> Anchor
    Anchor --> Expand[2. LightRAG Concept Expansion]
    Expand --> Enhance[3. Context-Aware Vector Search]
    Enhance --> Synthesize[4. LLM Synthesis]
    Synthesize --> ResearchResults[Synthesized Answer + Formatted Sources]
    ResearchResults --> Return

    %% Investigate Mode
    Route -->|"investigate<br/>(WebSocket only)"| Investigate[Investigate Agent]
    Investigate --> Loop[Iterative Planning & Execution]
    Loop <--> Tools["Search Tools:<br/>Vector / Graph / LightRAG / Tavily"]
    Loop --> FinalEval[Evaluation & Refinement]
    FinalEval --> InvestigateResults[Detailed Analysis Report + Citations]
    InvestigateResults --> Return
```

Implementation notes (cross-checked against `src/services/api_gateway.py` and `src/services/query_dispatch.py` on 2026-04-26):

- The `X-Deprecated-Mode` header is set by middleware (registered after CORS) so it survives both success and `HTTPException` paths.
- Auto-routing from `research` (depth=auto) to the legacy `vault_review` path is gated by `_is_comprehensive_vault_review_query` and is skipped when the user passes `depth=staged`.
- `mode=ask` with `sources=["mempalace"]` calls the host sidecar at `http://host.docker.internal:7788/search`. `mode=ask` with `sources=["web"]` is currently dispatched to the vault path (web-only ask is not yet a first-class mode).

## Key Characteristics

1. **Ask**: Fast, semantic retrieval using embeddings. Returns a compact synthesized answer plus source snippets.
2. **Research**: Thorough staged retrieval pipeline. Anchors the concept via graph, expands via LightRAG, falls back to targeted vector search, and synthesizes a grounded answer. Depth and sources are configurable.
3. **Investigate**: Agentic, multi-step problem solving over the WebSocket. A supervisor agent breaks down complex queries, iteratively gathers information, and synthesizes a comprehensive research report.

## Legacy Mode Compatibility

Legacy mode strings (`vector`, `cascading`, `vault_review`, `deep-thinking`) are normalised at the API boundary by `normalize_legacy_request()`. A `X-Deprecated-Mode` response header is emitted for tracking.

See `Documentation/reference/search/SEARCH_MODES_GUIDE.md` for the full compatibility map.
