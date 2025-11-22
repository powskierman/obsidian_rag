# Deep-Thinking RAG: Improvement Proposal for Obsidian RAG

**Date:** 2025-11-22
**Status:** Draft - Awaiting Approval
**Reference:** https://github.com/FareedKhan-dev/deep-thinking-rag

---

## Executive Summary

This document proposes enhancing the obsidian_rag system with "Deep-Thinking RAG" capabilities - an agentic approach that moves beyond simple vector retrieval to implement iterative reasoning with multiple specialized agents for handling complex, multi-hop questions.

---

## Current Architecture (Obsidian RAG)

The existing system provides:
- **ChromaDB** for semantic vector search
- **LightRAG** for knowledge graph-based retrieval
- **Streamlit UI** for user interaction
- **Multiple LLM backends** (Ollama, Anthropic, Gemini)
- Single-pass retrieval and response generation

### Current Limitations
1. Single-shot retrieval - no iterative refinement
2. No query decomposition for complex questions
3. No self-critique or reflection on retrieved results
4. Limited synthesis across multiple document sources
5. No adaptive search strategy selection

---

## Proposed Deep-Thinking RAG Architecture

### 1. Strategic Planning Layer

#### 1.1 Tool-Aware Query Planner
Decomposes complex queries into structured research steps:

```python
class QueryPlan:
    steps: List[PlanStep]

class PlanStep:
    sub_question: str
    target_tool: Literal["chromadb", "lightrag", "web_search"]
    keywords: List[str]
    likely_sections: List[str]  # For Obsidian: folder paths, tags
    justification: str
```

**Example Decomposition:**
- User: "What are the best practices for ESP32 Thread networking based on my notes, and what's new in 2024?"
- Step 1: Search internal notes for ESP32 Thread content (lightrag)
- Step 2: Search for Nordic/Thread documentation (chromadb)
- Step 3: Search web for 2024 Thread updates (web_search)

#### 1.2 Query Rewriter
Optimizes retrieval by reformulating questions with:
- Keyword enrichment from past context
- Obsidian-specific syntax awareness (tags, links)
- Metadata filtering hints

### 2. Multi-Stage Retrieval Funnel

#### 2.1 Retrieval Supervisor
Dynamically selects optimal search strategy per sub-question:

| Strategy | Use Case | Implementation |
|----------|----------|----------------|
| `vector_search` | Semantic/conceptual queries | ChromaDB similarity search |
| `graph_search` | Entity relationships, connections | LightRAG graph traversal |
| `hybrid_search` | Combined approach | BM25 + semantic with RRF |
| `keyword_search` | Exact terms, codes, names | Full-text search |

#### 2.2 Three-Stage Funnel
```
Stage 1: Broad Recall (k=10-15 documents)
    ↓
Stage 2: Cross-Encoder Reranking (top 3-5)
    ↓
Stage 3: Contextual Distillation (compressed summaries)
```

**Reranker Options:**
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (fast, local)
- `BAAI/bge-reranker-base` (better quality)
- Cohere Rerank API (cloud option)

### 3. Control Flow & Reflection

#### 3.1 State Management
```python
class DeepRAGState(TypedDict):
    original_question: str
    plan: QueryPlan
    current_step_index: int
    past_steps: List[StepResult]  # Cumulative research history
    retrieved_docs: List[Document]
    reranked_docs: List[Document]
    synthesized_context: str
    final_answer: str
    iteration_count: int
```

#### 3.2 Reflection Agent
After each retrieval step:
- Summarizes findings into one-sentence insights
- Appends to cumulative research history
- Identifies gaps in retrieved information

#### 3.3 Policy Agent (LLM-as-Judge)
Evaluates progress and decides next action:
- `CONTINUE_PLAN`: Execute next planned step
- `REVISE_PLAN`: Modify remaining steps based on findings
- `FINISH`: Sufficient evidence gathered

#### 3.4 Stopping Criteria
- Policy decision to finish
- All plan steps completed
- Max iteration limit (default: 7)
- Confidence threshold met

### 4. Knowledge Synthesis

#### 4.1 Final Answer Generation
- Synthesizes research history with provenance tracking
- Citations reference Obsidian note paths or URLs
- Structured output with confidence indicators

#### 4.2 Citation Format
```markdown
Based on your notes:
- [[Tech/ESP32/Thread Setup]] mentions...
- [[Projects/Home Automation]] describes...

From web search:
- [Thread Group 2024 Update](url) indicates...
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Implement `DeepRAGState` data structure
- [ ] Create Query Planner with tool awareness
- [ ] Add Query Rewriter module
- [ ] Integrate with existing ChromaDB + LightRAG

### Phase 2: Retrieval Enhancement (Week 2-3)
- [ ] Implement Retrieval Supervisor routing logic
- [ ] Add Cross-Encoder reranking layer
- [ ] Implement Reciprocal Rank Fusion for hybrid search
- [ ] Add contextual distillation/compression

### Phase 3: Reasoning Loop (Week 3-4)
- [ ] Implement Reflection Agent
- [ ] Create Policy Agent with decision logic
- [ ] Build LangGraph workflow orchestration
- [ ] Add iteration control and safeguards

### Phase 4: Integration & UI (Week 4-5)
- [ ] Integrate with Streamlit UI
- [ ] Add progress visualization for multi-step reasoning
- [ ] Implement citation tracking
- [ ] Add configuration options for reasoning depth

### Phase 5: Optimization (Week 5-6)
- [ ] Performance tuning
- [ ] Caching for repeated sub-queries
- [ ] Async execution for parallel retrieval
- [ ] Cost optimization (model selection per task)

---

## Technical Requirements

### New Dependencies
```
langgraph>=0.1.0          # Workflow orchestration
sentence-transformers     # Cross-encoder reranking
rank-bm25                 # BM25 keyword search
tavily-python            # Web search (optional)
```

### Model Requirements
| Task | Model | Notes |
|------|-------|-------|
| Planning/Reasoning | llama3.1:8b or Claude | Complex reasoning |
| Fast tasks (rewrite, reflect) | llama3.2:3b | Speed optimization |
| Embeddings | bge-m3 | Already configured |
| Reranking | cross-encoder | New addition |

### Infrastructure
- No new services required
- Runs within existing Docker setup
- Optional: Tavily API key for web search

---

## Configuration Options

```yaml
deep_thinking_rag:
  enabled: true
  max_iterations: 7

  planning:
    enabled: true
    model: "llama3.1:8b"

  retrieval:
    initial_k: 10
    rerank_top_n: 3
    strategy: "auto"  # auto, vector, graph, hybrid

  reranking:
    enabled: true
    model: "cross-encoder/ms-marco-MiniLM-L-6-v2"

  reflection:
    enabled: true
    summarize_each_step: true

  policy:
    model: "llama3.1:8b"
    confidence_threshold: 0.8

  web_search:
    enabled: false  # Optional
    provider: "tavily"
```

---

## Expected Benefits

1. **Complex Query Handling**: Answer multi-hop questions requiring synthesis
2. **Adaptive Retrieval**: Right strategy for each sub-question
3. **Higher Precision**: Reranking filters noise from initial retrieval
4. **Transparency**: Step-by-step reasoning visible to user
5. **Better Citations**: Clear provenance for all claims
6. **Self-Correction**: Reflection enables recovery from dead ends

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Increased latency | High | Parallel retrieval, caching, fast models for simple tasks |
| Higher token costs | Medium | Model tiering, early stopping, result caching |
| Over-engineering simple queries | Medium | Quick-path detection for simple lookups |
| Infinite loops | High | Hard iteration limits, timeout safeguards |

---

## Success Metrics

- [ ] Successfully answers multi-hop queries (manual evaluation)
- [ ] Average response time < 30s for complex queries
- [ ] User satisfaction improvement (qualitative)
- [ ] Reduction in "I don't know" responses for valid queries

---

## Next Steps

1. **Review & Approve** this proposal
2. **Prioritize phases** based on immediate needs
3. **Decide on web search** integration (optional)
4. **Select reranker model** based on performance/speed tradeoff
5. **Begin Phase 1** implementation

---

## References

- [Deep-Thinking RAG Repository](https://github.com/FareedKhan-dev/deep-thinking-rag)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Cross-Encoder Reranking](https://www.sbert.net/examples/applications/cross-encoder/README.html)
- [Reciprocal Rank Fusion](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
