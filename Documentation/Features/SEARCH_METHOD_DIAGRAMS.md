# Obsidian RAG Search Method Diagrams

This document summarizes the nine canonical search methods exposed by Obsidian RAG's public interfaces. The authoritative mode list comes from the project constitution and the unified API gateway. In practice, these methods fall into three groups:

- single-source retrieval: `vector`, `notes`, `entities`
- combined retrieval: `notes+vector`, `entities+vector`, `dual-graph`, `hybrid`
- orchestrated research flows: `cascading`, `deep-thinking`

Compatibility aliases:

- `graph` -> `notes`
- `networkx` -> `notes`
- `lightrag` -> `entities`

## 1. Vector

`vector` is the fastest retrieval path. It asks the embedding service to find semantically similar chunks in ChromaDB and returns ranked note fragments.

Example query: `How did I configure ESPHome for the garage sensor?`

```mermaid
flowchart LR
    U["User query"] --> G["API Gateway"]
    G --> E["Embedding service"]
    E --> C["ChromaDB vector search"]
    C --> R["Ranked document chunks"]
    R --> O["Vector results"]
```

Use this for fast recall, direct topic lookup, and source-first exploration.

## 2. Notes

`notes` is the note-centric graph mode. It routes the query to the NetworkX graph service, which reasons over wiki-link structure and note relationships, then synthesizes an answer from graph context.

Example query: `How are my lymphoma treatment notes connected to follow-up scan notes?`

```mermaid
flowchart LR
    U["User query"] --> G["API Gateway"]
    G --> N["NetworkX graph service"]
    N --> X["Note graph traversal"]
    X --> S["Graph answer synthesis"]
    S --> O["Notes answer plus sources"]
```

Use this when the question is about how notes connect, relate, or cluster structurally.

## 3. Entities

`entities` is the entity-centric graph mode. It sends the query to LightRAG, which works over semantic entities and relationships rather than note links.

Example query: `What entities and treatments are associated with DLBCL in my notes?`

```mermaid
flowchart LR
    U["User query"] --> G["API Gateway"]
    G --> L["LightRAG service"]
    L --> K["Entity graph retrieval"]
    K --> S["Semantic answer synthesis"]
    S --> O["Entity answer plus sources"]
```

Use this for concept discovery, entity relationships, and multi-hop semantic retrieval.

## 4. Notes+Vector

`notes+vector` runs note-graph retrieval and vector retrieval in parallel. The gateway does not fuse them into one answer; it returns both result sets side by side.

Example query: `Show both linked-note context and direct note excerpts for Home Assistant dashboard setup.`

```mermaid
flowchart LR
    U["User query"] --> G["API Gateway"]
    G --> N["NetworkX graph service"]
    G --> E["Embedding service"]
    N --> NR["Notes result"]
    E --> VR["Vector result"]
    NR --> O["Combined response"]
    VR --> O
```

Use this when you want structural note reasoning and semantic chunk recall without committing to a single fused synthesis.

## 5. Entities+Vector

`entities+vector` runs LightRAG and vector search in parallel, again returning both result sets separately in one response.

Example query: `Show entity relationships and supporting note chunks for Yescarta side effects.`

```mermaid
flowchart LR
    U["User query"] --> G["API Gateway"]
    G --> L["LightRAG service"]
    G --> E["Embedding service"]
    L --> ER["Entity graph result"]
    E --> VR["Vector result"]
    ER --> O["Combined response"]
    VR --> O
```

Use this when you want semantic entity reasoning plus direct document evidence from the vector index.

## 6. Dual-Graph

`dual-graph` queries both graph systems in parallel: NetworkX for note-link structure and LightRAG for semantic entities. No vector search is included.

Example query: `Compare what the note graph and entity graph say about my AI agent architecture.`

```mermaid
flowchart LR
    U["User query"] --> G["API Gateway"]
    G --> N["NetworkX graph service"]
    G --> L["LightRAG service"]
    N --> NR["Notes graph result"]
    L --> ER["Entity graph result"]
    NR --> O["Dual-graph response"]
    ER --> O
```

Use this when you want two graph perspectives on the same question without adding vector recall.

## 7. Hybrid

`hybrid` is the broadest synchronous search mode. The gateway queries NetworkX, LightRAG, and ChromaDB in parallel and returns all three result channels together.

Example query: `What do my notes say about integrating Nextion with ESP32, with sources?`

```mermaid
flowchart LR
    U["User query"] --> G["API Gateway"]
    G --> N["NetworkX graph service"]
    G --> L["LightRAG service"]
    G --> E["Embedding service"]
    N --> NR["Notes result"]
    L --> ER["Entities result"]
    E --> VR["Vector result"]
    NR --> O["Hybrid response"]
    ER --> O
    VR --> O
```

Use this as the default general-purpose mode when you want graph reasoning, semantic entities, and source chunks in one request.

## 8. Cascading

`cascading` is a staged retrieval pipeline. It starts with anchor notes, extracts terms, expands them through LightRAG, then runs a more targeted vector search before synthesis.

Example query: `Research the best notes related to supervisor patterns in my multi-agent system.`

```mermaid
flowchart LR
    U["User query"] --> A["Stage 1: Anchor notes"]
    A --> B["Stage 2: Extract entities"]
    B --> C["Stage 3: Expand with LightRAG"]
    C --> D["Stage 4: Targeted vector search"]
    D --> E["Stage 5: Synthesis"]
    A -. "fallback" .-> D
```

Use this for focused research tasks where the first retrieval pass should actively improve the later passes.

## 9. Deep-Thinking

`deep-thinking` is the long-form research agent exposed over the `deep-research` WebSocket. It plans, executes multiple retrieval steps, reflects on findings, revises the plan if needed, and then synthesizes a final answer.

Example query: `Analyze how my RAG architecture evolved, what bottlenecks remain, and which changes would likely improve reliability most.`

```mermaid
flowchart TD
    U["User query"] --> P["Planner"]
    P --> PL["Research plan"]
    PL --> S{"More steps?"}
    S -->|"Yes"| SV["Supervisor"]
    SV --> V["Vector search"]
    SV --> N["Notes graph search"]
    SV --> H["Hybrid retrieval"]
    SV --> W["Optional web search"]
    V --> R["Rerank and collect evidence"]
    N --> R
    H --> R
    W --> R
    R --> F["Reflector"]
    F --> PO["Policy decision"]
    PO -->|"Continue"| S
    PO -->|"Revise"| P
    PO -->|"Finish"| Y["Synthesizer"]
    S -->|"No"| Y
    Y --> O["Final answer with citations"]
```

Use this when the query needs multi-step reasoning, plan revision, evidence accumulation, or optional external enrichment. It is much slower than the standard synchronous modes, but it handles the most complex questions.

## References

- `Documentation/PROJECT_CONSTITUTION.md`
- `src/services/api_gateway.py`
- `src/services/cascading_retriever.py`
- `Documentation/CASCADING_FLOW.md`
- `Documentation/architecture/DEEP_THINKING_FLOW.md`
