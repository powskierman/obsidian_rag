# Deep Thinking Flow

The API gateway exposes a WebSocket endpoint for the deep thinking agent:

- `ws://localhost:4000/api/v1/deep-research`

The agent orchestrates calls to vector, graph, and optional web services for multi-step reasoning.

Use this only if you need long-form, multi-hop analysis; standard search modes are faster.

## Current Runtime Notes

- Plan execution is serialized by default so reflection and policy decisions see committed intermediate state after each step.
- Summary-style queries such as "point form summary of X" use a vault-first fast path with a minimal evidence set and skip web enrichment unless the user explicitly asks for outside context, reviews, or comparisons.
- Prompt-template and instruction notes are filtered out of normal evidence ranking so workflow helper files do not appear as content sources.
- Graph steps preserve text-only graph outputs as internal reasoning evidence, but those internal reasoning documents are excluded from final citations.
- Final synthesis uses one authoritative citable evidence set for prompt construction, citation normalization, and final source rendering.
- If the model returns an empty answer, synthesis retries once with a smaller evidence set before falling back to the retrieved-context summary.
- Fallback responses now surface the failure mode, for example empty answer, malformed JSON, timeout, or provider error.

## Workflow Diagram

```mermaid
flowchart TD
    Start((User Query)) --> Planner["Planner Agent"]
    subgraph Phase1["Phase 1: Research Strategy"]
        Planner -->|Summary intent?| SummaryFastPath{"Vault-first summary?"}
        SummaryFastPath -->|Yes| Plan["Single-step vector plan"]
        SummaryFastPath -->|No| Plan["Research Plan"]
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

        Reranker --> Documents["Top Evidence Blocks"]
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
    Synthesis["Synthesizer Agent"] -->|Authoritative Evidence Fusion|FinalAnswer["Final Response"]
        FinalAnswer --> Citations["Source Citations"]
        FinalAnswer --> Confidence["Confidence Score + Justification"]
    end

    Confidence --> End((Final Output))
```
