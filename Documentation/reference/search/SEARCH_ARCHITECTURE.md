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
    Request[User Search Request] --> Dispatch["query_dispatch.py\nnormalize_legacy_request()"]
    Dispatch --> Route{Canonical Mode}

    %% Ask Mode
    Route -->|mode: ask| Ask[Ask — Vector + Synthesis]
    Ask --> Chroma[(ChromaDB)]
    Chroma --> AskResults[Snippets + Compact Answer]
    AskResults --> Return[Return to Client]

    %% Research Mode
    Route -->|mode: research| Research[Research Pipeline]
    Research --> Anchor[1. Graph Anchor Search]
    Anchor --> Expand[2. LightRAG Concept Expansion]
    Expand --> Enhance[3. Context-Aware Vector Search]
    Enhance --> Synthesize[4. LLM Synthesis]
    Synthesize --> ResearchResults[Synthesized Answer + Formatted Sources]
    ResearchResults --> Return

    %% Investigate Mode
    Route -->|investigate websocket| Investigate[Investigate Agent]
    Investigate --> Loop[Iterative Planning & Execution]
    Loop <--> Tools[Search Tools: Vector, Graph, Web]
    Loop --> FinalEval[Evaluation & Refinement]
    FinalEval --> InvestigateResults[Detailed Analysis Report + Citations]
    InvestigateResults --> Return
```

## Key Characteristics

1. **Ask**: Fast, semantic retrieval using embeddings. Returns a compact synthesized answer plus source snippets.
2. **Research**: Thorough staged retrieval pipeline. Anchors the concept via graph, expands via LightRAG, falls back to targeted vector search, and synthesizes a grounded answer. Depth and sources are configurable.
3. **Investigate**: Agentic, multi-step problem solving over the WebSocket. A supervisor agent breaks down complex queries, iteratively gathers information, and synthesizes a comprehensive research report.

## Legacy Mode Compatibility

Legacy mode strings (`vector`, `cascading`, `vault_review`, `deep-thinking`) are normalised at the API boundary by `normalize_legacy_request()`. A `X-Deprecated-Mode` response header is emitted for tracking.

See `Documentation/reference/search/SEARCH_MODES_GUIDE.md` for the full compatibility map.
