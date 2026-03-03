# Search Architecture

This document outlines the simplified 3-mode search architecture for Obsidian RAG, as well as the overall application data flow.

## Application Data Flow

The following flowchart describes how the frontend application, API Gateway, and backend services interact.

```mermaid
graph TD
    Client[Frontend Client / Streamlit / Next.js] -->|HTTP POST /api/v1/query| Gateway[API Gateway]
    Client -->|WebSocket /ws/chat| Gateway
    
    Gateway -->|Vector Mode| Embed[Embedding Service / ChromaDB]
    Gateway -->|Cascading Mode| Cascading[Cascading Retriever]
    Gateway -->|Deep Research Mode| DeepThinking[Deep Thinking Orchestrator]
    
    Cascading -->|1. Anchor| GraphService[Graph Service / NetworkX]
    Cascading -->|2. Expand| LightRAG[LightRAG Service]
    Cascading -->|3. Enhance| Embed
    Cascading -->|4. Synthesize| LLM[LLM Provider]
    
    DeepThinking -->|Multi-step Reasoning| GraphService
    DeepThinking -->|Validation| Embed
    DeepThinking -->|Synthesis| LLM
```

## Search Modes Flowchart

The API Gateway supports exactly 3 distinct search modes: `vector`, `cascading`, and `deep-research`.

```mermaid
flowchart TD
    Request[User Search Request] --> Route{Select Mode}
    
    %% Vector Mode
    Route -->|mode: vector| Vector[Vector Search]
    Vector --> Chroma[(ChromaDB)]
    Chroma --> VectorResults[Raw Snippets & Metadata]
    VectorResults --> Return[Return to Client]
    
    %% Cascading Mode
    Route -->|mode: cascading| Cascading[Cascading Pipeline]
    Cascading --> Anchor[1. Graph Anchor Search]
    Anchor --> Expand[2. LightRAG Concept Expansion]
    Expand --> Enhance[3. Context-Aware Vector Search]
    Enhance --> Synthesize[4. LLM Synthesis]
    Synthesize --> CascadingResults[Synthesized Answer + Formatted Sources]
    CascadingResults --> Return
    
    %% Deep Research Mode
    Route -->|mode: deep-research| DeepResearch[Deep Thinking Agent]
    DeepResearch --> Loop[Iterative Planning & Execution]
    Loop <--> Tools[Search Tools: Vector, Graph, Web]
    Loop --> FinalEval[Evaluation & Refinement]
    FinalEval --> DeepResearchResults[Detailed Analysis Report + Citations]
    DeepResearchResults --> Return
```

## Key Characteristics

1. **Vector**: Fast, raw retrieval using embeddings. Returns source snippets directly without LLM synthesis.
2. **Cascading**: Thorough, hybrid retrieval pipeline. Uses graph topology to anchor the concept, expands understanding via LightRAG, falls back to targeted vector search, and uses an LLM to synthesize a concise answer.
3. **Deep Research**: Agentic, multi-step problem solving. Uses a supervisor agent to break down complex queries, iteratively gather information using various tools, and syntheize a comprehensive research report.
