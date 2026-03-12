# NetworkX Retrieval Gap Assessment

This retrospective compares an external SOTA write-up that is no longer present in the repository against the legacy `notes` query method that previously existed here.

## Scope

- Source document reviewed: external `NetworkX Retrieval SOTA.pdf` artifact removed from this repository during documentation cleanup.
- Current implementation reviewed:
  - `src/services/networkx_graph_builder.py`
  - `src/services/graph_query_service.py`
  - Legacy `Documentation/Features/SEARCH_METHOD_DIAGRAMS.md` artifact removed from this repository during documentation cleanup.

## Overall Assessment

- The PDF is useful as a directional survey, but it is not a rigorous implementation spec.
- Our current `notes` mode is not SOTA graph retrieval in the sense described by the PDF.
- It is better described as a pragmatic note-graph QA pipeline:
  - deterministic structural graph build
  - lexical seed matching
  - immediate-neighborhood context assembly
  - LLM synthesis over that context
- The current system is operationally simpler and easier to debug than many heavier GraphRAG stacks, but it leaves a large amount of graph-retrieval value unused.

## Current Notes Method

### Structural graph build

- The graph is built as a deterministic structural graph from the Obsidian vault.
- Node types:
  - `("note", path)`
  - `("pdf", path)`
  - `("tag", tag)`
  - `("folder", path)`
- Edge types:
  - `LINK`
  - `TAGGED_AS`
  - `IN_FOLDER`
  - `INHERITS_FOLDER`
  - `SAME_AS`
- Relevant implementation:
  - `src/services/networkx_graph_builder.py:210`
  - `src/services/networkx_graph_builder.py:276`

### Query path

- `GraphQuerier` builds a lexical index over:
  - note paths
  - note stems
  - aliases
  - canonical IDs
  - tags
  - folder names
- Query-time node retrieval is based on regex-style matching over indexed names.
- Retrieved nodes contribute a local context block consisting of:
  - node label
  - tags
  - outgoing edges
  - incoming edges
- Relevant implementation:
  - `src/services/networkx_graph_builder.py:557`
  - `src/services/networkx_graph_builder.py:707`

### Source ranking

- `graph_query_service.py` post-processes graph context nodes into ranked sources.
- Ranking is based on:
  - query term coverage
  - filename term coverage
  - heuristic boosts and penalties
  - some domain-specific suppression
- This is fundamentally lexical reranking over graph-derived candidates, not graph-native retrieval.
- Relevant implementation:
  - `src/services/graph_query_service.py:1036`

## Strengths

- Deterministic and explainable graph build.
- Strong note/file provenance from actual Obsidian structure.
- Good operational simplicity relative to heavier graph systems.
- Alias and canonicalization support reduces duplicate-note fragmentation.
- Current graph size is still well within a practical NetworkX range for this style of retrieval.
- Recent graph selection logic now prefers the structural tuple-node graph over legacy entity-graph snapshots.

## Weaknesses

### Retrieval depth is shallow

- The current notes retriever does not perform real subgraph retrieval.
- It does not use:
  - k-hop subgraph extraction
  - shortest-path retrieval
  - Steiner tree retrieval
  - query-conditioned graph expansion

### Ranking is not graph-native

- There is no use of:
  - PageRank
  - Personalized PageRank
  - betweenness/closeness/eigenvector centrality
  - path salience
  - community relevance
  - edge weighting in ranking
- The ranking loop is still primarily lexical and heuristic.

### The structural graph is semantically thin

- The graph encodes note structure well, but not semantic relations beyond note links, tags, folders, and canonical equivalence.
- There is no extracted relation ontology for note content.

### No hierarchical retrieval

- The PDF emphasizes coarse-to-fine retrieval using communities and subgraphs.
- Our notes mode has no community detection and no staged narrowing.

### No semantic node retrieval inside NetworkX

- Semantic support exists only indirectly through hybrid mode and the separate embedding service.
- Notes mode itself has no embedded note-node retrieval layer or semantic community routing.

### No query-aware traversal policy

- Queries like:
  - “How are A and B connected?”
  - “What is the timeline?”
  - “Which notes cluster around X?”
  should not use the same retrieval strategy.
- Today they mostly do.

### Temporal metadata is underused

- Notes and PDFs already carry:
  - `timeline_date`
  - `treatment_phase`
- These are not meaningfully used in notes-mode retrieval or ranking.

## Comparison To The PDF

### Areas where the PDF is directionally correct

- Graph-based retrieval should move beyond isolated document treatment.
- Subgraph retrieval is more appropriate than raw neighborhood dumping.
- Community-based filtering is a strong scaling and precision tactic.
- Hybrid vector + graph retrieval is the most realistic near-term path.
- Query-aware traversal is more valuable than generic graph expansion.
- Production scaling may eventually require a more optimized retrieval backend than plain NetworkX.

### Areas where the PDF is weaker

- It is broad and partly aspirational.
- It cites mixed-quality sources, including blog-style and summary sources.
- It should be treated as roadmap input, not as implementation authority.

## Gap Analysis

### Gap 1: Notes mode uses NetworkX mainly as storage, not as a retrieval engine

- Current state:
  - adjacency access
  - local neighborhood formatting
  - lexical source reranking
- Missing:
  - graph-native retrieval algorithms
  - graph-native scoring
  - structured subgraph extraction

### Gap 2: Connection queries are not path-centric

- Example:
  - “How are my lymphoma treatment notes connected to follow-up scan notes?”
- Ideal behavior:
  - identify seed notes
  - compute candidate connection paths
  - rank paths
  - synthesize from explicit connecting notes/edges
- Current behavior:
  - gather nodes by lexical match
  - dump local edges
  - let the LLM infer the connection story

### Gap 3: Timeline and treatment-phase metadata are present but not exploited

- This is especially costly for clinical note retrieval.
- Timeline questions should use date-aware and phase-aware ranking.

### Gap 4: No coarse-to-fine retrieval

- The PDF’s hierarchical retrieval model is absent.
- There is no notion of:
  - top-level scope selection
  - community refinement
  - focused subgraph extraction

### Gap 5: No semantic seed retrieval within the notes graph

- If note titles or aliases do not match well lexically, notes mode weakens quickly.
- This is where semantic seed selection should help.

## Phased Recommendations

## Phase 0: Measurement and Safety

- Build a dedicated `notes` eval set covering:
  - structural connection questions
  - timeline questions
  - cluster/topic questions
  - false-friend/noise cases
- Log:
  - seed-node hits
  - rejected candidates
  - path lengths
  - source coverage
  - answer/source agreement
- Ensure all graph loaders use the same structural-graph selection logic.

## Phase 1: Make Notes Mode Actually Graph-Retrieval-Oriented

- Add query-intent routing for:
  - `connection`
  - `timeline`
  - `cluster`
  - `summary`
- For connection queries:
  - find seed notes
  - retrieve shortest or bounded k-shortest paths
  - synthesize from the path subgraph rather than generic neighborhood text
- For timeline queries:
  - rank with `timeline_date`, `treatment_phase`, path, tags, and canonical matches
- Add k-hop ego-subgraph extraction with edge-type filtering.

## Phase 2: Add Graph-Native Ranking

- Precompute:
  - degree-normalized centrality
  - Personalized PageRank for seeded retrieval
  - community labels
- Replace current source scoring with fused scoring:
  - seed relevance
  - path relevance
  - community relevance
  - lexical evidence
  - metadata relevance
- Penalize hub-only explanations that lack path evidence.

## Phase 3: Add Semantic Retrieval To The Note Graph

- Attach embeddings to note nodes or community centroids.
- Retrieve semantic seed notes before structural expansion.
- Fuse vector recall with structural traversal using:
  - Reciprocal Rank Fusion
  - or a lightweight learned reranker
- Consider query-local graph construction from top vector candidates for weakly linked domains.

## Phase 4: Scale Beyond Plain NetworkX If Needed

- If graph size or query volume grows materially:
  - move heavy retrieval logic to an optimized backend
  - keep NetworkX for graph construction, debugging, and analysis
- Candidates:
  - `igraph`
  - `graph-tool`
  - an RGL-style retrieval layer
- Defer GNN-RAG until the simpler graph-retrieval upgrades plateau on measured evals.

## Recommended Priority Order

- Highest priority:
  - Phase 1
  - graph-native ranking from Phase 2
- Medium priority:
  - semantic seed retrieval from Phase 3
- Lowest priority:
  - GNN-RAG
  - Graph pretrained retrievers
  - multimodal graph expansion

## Practical Conclusion

- The current notes mode is a useful structural QA layer, but it is not yet a modern graph retrieval system.
- The best next step is not a jump to GNNs.
- The best next step is to upgrade the current notes path into:
  - intent-aware
  - path-aware
  - date-aware
  - graph-ranked retrieval
- That will close most of the meaningful gap identified by the PDF while preserving the system’s current debuggability and operational simplicity.
