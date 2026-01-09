# Deep Thinking Flow

The API gateway exposes a WebSocket endpoint for the deep thinking agent:

- `ws://localhost:4000/api/v1/deep-research`

The agent orchestrates calls to vector and graph services for multi-step reasoning.

Use this only if you need long-form, multi-hop analysis; standard search modes are faster.

## Workflow Diagram

```mermaid
flowchart TD
    Start((User Query)) --> Planner["Planner Agent"]
    subgraph Phase1["Phase 1: Research Strategy"]
        Planner -->|Decompose & Strategize| Plan["Research Plan"]
        Plan --> InitState["Initialize RAG State"]
    end

    subgraph Phase2["Phase 2: The Reasoning Loop"]
        InitState --> LoopStart{More Steps?}
        LoopStart -->|Yes| Supervisor["Retrieval Supervisor"]
        subgraph Retrieval["Multi-Source Retrieval"]
            Supervisor -->|Strategy: Vector| Vector["Vector Search"]
            Supervisor -->|Strategy: Graph| Graph["Graph Service - NetworkX"]
            Supervisor -->|Strategy: Hybrid| Hybrid["Vector + Graph"]
            Supervisor -->|Strategy: Web| Web["Tavily Search (optional)"]
        end

        Vector --> Reranker["Cross-Encoder Reranker (optional)"]
        Graph --> Reranker
        Hybrid --> Reranker
        Web --> Reranker

        Reranker --> Documents["Top 20 Reranked Blocks"]
        Documents --> Reflector["Reflection Agent"]
        Reflector -->|Extract Findings| Context["Update Accumulated Context"]
        Context --> Policy["Policy Agent"]

        Policy --> Decision{Decision?}
        Decision -->|CONTINUE| LoopStart
        Decision -->|REVISE_PLAN| Revise["Planner: Extend Plan"]
        Revise --> LoopStart
        Decision -->|FINISH| Synthesis
        LoopStart -->|Plan Exhausted| Synthesis
    end

    subgraph Phase3["Phase 3: Answer Generation"]
    Synthesis["Synthesizer Agent"] -->|Evidence Fusion|FinalAnswer["Final Response"]
        FinalAnswer --> Citations["Source Citations"]
        FinalAnswer --> Confidence["Confidence Score + Justification"]
    end

    Confidence --> End((Final Output))
```
