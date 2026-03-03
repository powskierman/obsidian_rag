# Assessment of [notes](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#810-949) and `notes+vector` Search Modes

## 1. Current Implementation Analysis

### [notes](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#810-949) Mode
**Execution Flow:**
The [api_gateway.py](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py) routes [notes](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#810-949) mode queries to the `GRAPH_SERVICE_URL/query` endpoint. It requests the [graph](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/graph_query_service.py#802-1563) mode from the graph query service. 
**Key observation:** The gateway explicitly sends `use_vector: True` in its payload, but [graph_query_service.py](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/graph_query_service.py) **entirely ignores this parameter**. The graph service processes it as a pure NetworkX graph search. If the graph service fails or returns an error, the API gateway has an `ENABLE_FALLBACKS` mechanism that defaults to a basic pure vector search.

### `notes+vector` Mode
**Execution Flow:**
The `notes+vector` mode acts as a "late-fusion" parallel retriever at the API gateway level. The gateway fires two asynchronous parallel requests:
1. `GRAPH_SERVICE_URL/query` (with `mode: "graph"`, `use_vector: False`)
2. `EMBEDDING_SERVICE_URL/query` (pure semantic vector search)

Once both return, the API gateway executes thousands of lines of bespoke post-processing logic (e.g., [_score_notes_vector_source](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#810-949), [_dedupe_ranked_sources](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#951-984), [_filter_notes_vector_sources_for_query](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#1016-1136)) to merge, re-rank, and deduplicate the sources. It calculates dynamic scores based on heuristics like anchor match hits before sending the final synthesized package to the frontend.

## 2. Constraints and Weaknesses

**A. Disconnected Architectural Contracts (The `use_vector` Ghost Parameter)**
There is a clear disconnect between the API gateway and the graph service. The gateway tries to instruct the graph service to use vector enrichment (`use_vector: True/False`), but the graph service does not parse or respect this flag.

**B. Missed Early-Fusion Opportunities**
Because `notes+vector` executes both searches in strict parallel, the vector search only relies on the user's raw, un-enhanced query.
In contrast, inside [graph_query_service.py](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/graph_query_service.py), there is a native `hybrid` mode that generates a HyDE (Hypothetical Document Embeddings) enhancement *before* calling the vector service. Furthermore, the newly implemented [CascadingRetriever](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py#12-255) extracts entities from the graph to enrich the vector search. `notes+vector` takes advantage of neither of these superior mid/early-fusion techniques.

**C. API Gateway Bloat**
[api_gateway.py](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py) is heavily bloated (~3,100 lines) because it handles incredibly complex retrieval synthesis, deduplication, and heuristic scoring. This violates the API Gateway pattern—these responsibilities belong inside a dedicated Retrieval/Ranking orchestration layer (like [CascadingRetriever](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py#12-255)).

## 3. Phased Recommendations

### Phase 1: Cleanup and Alignment (Immediate)
- **Remove "Ghost" Parameters:** Remove the `use_vector` parameter from the [api_gateway.py](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py) payloads, as it provides a false sense of security and clutters the interface contract.
- **Isolate Gateway Logic:** Consolidate the massive block of heuristics ([_score_notes_vector_source](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#810-949), [_dedupe_ranked_sources](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#951-984)) into a standalone `ranking_service.py` or a dedicated retriever utility to reduce gateway cognitive load.

### Phase 2: Deprecate Late-Fusion for Native Hybrid (Short-Term)
- **Route to Native Hybrid:** Refactor the `notes+vector` gateway route to simply pass `mode="hybrid"` to the [graph_query_service.py](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/graph_query_service.py). The [graph_query_service.py](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/graph_query_service.py)'s native hybrid implementation (which utilizes HyDE and entity context generation prior to vector fetching) is fundamentally more accurate than parallel late-fusion.
- **Evaluate Cascading Alternative:** Alternatively, route `notes+vector` directly through the [CascadingRetriever](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py#12-255), which possesses state-of-the-art fallback constraints and entity extraction. 

### Phase 3: Unification of RAG Strategies (Mid-Term)
- **Deprecate Extraneous Modes:** [cascading](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#1913-1975) and `deep-research` modes essentially solve the problem `notes+vector` was trying to solve, but with greater accuracy and intelligent contextual routing. Plan to deprecate `notes+vector` entirely from the UI, simplifying the user experience to core declarative modes (e.g., "Standard/Fast", "Thorough/Cascading", "Deep Research"). 
- **Consolidate Backend Pipelines:** Retire custom deduplication heuristics written specifically for `notes+vector` inside the gateway once the mode is phased out, significantly reducing technical debt.
