# Obsidian RAG: Deep Thinking Implementation Plan
**Version:** 2.0 (Hybrid Approach)  
**Date:** 2025-11-22  
**Status:** Ready for Implementation  
**Target Timeline:** 6-8 weeks (3 phases)

---

## Executive Summary

This plan transforms your Obsidian RAG system from single-shot retrieval into an iterative reasoning engine capable of handling complex, multi-hop queries. It combines the pragmatic structure of an agentic workflow with proven retrieval enhancements, while avoiding unnecessary complexity and maintaining your local-first philosophy.

**Key Philosophy:**
- Build incrementally on your existing ChromaDB + LightRAG infrastructure
- Use Claude Sonnet 4.5 for all reasoning tasks (already proven in your setup)
- No new external services or complex dependencies
- Focus on solving your specific failure modes (semantic ambiguity, multi-hop queries)
- Each phase delivers testable, immediate value

---

## Current System Limitations (Validated Against Your Use Cases)

1. **Semantic Ambiguity**: "CAR-T therapy" query returns unrelated cardiology notes
2. **Single-Shot Failure**: Cannot synthesize information across multiple note types
3. **No Self-Correction**: Dead-end searches produce empty results instead of trying alternatives
4. **Rigid Tool Selection**: User manually chooses Vector vs Graph search
5. **Missing Context**: Cannot answer "Compare X timeline with Y progression" without multiple manual queries

---

## Core Architecture: Stateful Agentic Workflow

### Data Structures

```python
from typing import TypedDict, List, Literal

class Step(TypedDict):
    step_number: int
    sub_question: str
    search_strategy: Literal["vector", "graph", "hybrid"]
    keywords: List[str]
    target_folders: List[str]  # Obsidian-specific: e.g., ["Medical/", "Tech/ESP32/"]
    reasoning: str

class PastStep(TypedDict):
    step: Step
    documents_found: int
    key_findings: str  # One-sentence summary
    confidence: float  # 0.0 to 1.0

class RAGState(TypedDict):
    # Input
    original_question: str
    user_context: dict  # Optional: vault structure, recent topics
    
    # Planning
    plan: List[Step]
    current_step_index: int
    
    # Execution
    past_steps: List[PastStep]
    accumulated_context: str  # Growing synthesis of findings
    retrieved_documents: List[dict]  # All docs collected so far
    
    # Control
    iteration_count: int
    max_iterations: int  # Safety limit (default: 7)
    should_continue: bool
    
    # Output
    final_answer: str
    citations: List[str]  # Obsidian note paths or graph entities
```

---

## Implementation Phases

## Phase 1: Foundation - Agentic Core (Weeks 1-3)

### Objective
Replace linear query flow with intelligent planning and reflection loop.

### Components

#### 1.1 Planner Agent
**Purpose:** Decompose complex queries into answerable sub-questions.

**Implementation:**
```python
class PlannerAgent:
    def __init__(self, llm_client):
        self.llm = llm_client  # Your existing Claude Sonnet 4.5
        
    def create_plan(self, question: str, vault_context: dict) -> List[Step]:
        """
        Uses Claude to break down the question into 2-5 sub-steps.
        """
        prompt = f"""
        You are a research planner for an Obsidian vault containing:
        - Medical notes (folders: Medical/Scans/, Medical/Treatments/)
        - Technical projects (folders: Tech/ESP32/, Tech/HomeAssistant/)
        - Personal logs (Daily Notes)
        
        User question: "{question}"
        
        Create a research plan with 2-5 steps. For each step:
        1. Write a clear sub-question
        2. Choose search strategy: "vector" (concepts), "graph" (entities/relationships), "hybrid"
        3. List 3-5 keywords
        4. Suggest target folders if relevant
        5. Explain why this step is needed
        
        Return JSON array of steps.
        """
        
        response = self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse JSON response into List[Step]
        plan = json.loads(response.content[0].text)
        return plan
```

**Example Plan for:** "Review my lymphoma treatment timeline and compare side effects between R-CHOP and CAR-T therapy"

```json
[
  {
    "step_number": 1,
    "sub_question": "When did lymphoma diagnosis occur and what was the initial staging?",
    "search_strategy": "graph",
    "keywords": ["lymphoma", "diagnosis", "staging", "2023"],
    "target_folders": ["Medical/Diagnoses/", "Medical/Scans/"],
    "reasoning": "Establish temporal baseline for timeline"
  },
  {
    "step_number": 2,
    "sub_question": "What was the R-CHOP treatment protocol and documented side effects?",
    "search_strategy": "vector",
    "keywords": ["R-CHOP", "chemotherapy", "side effects", "nausea", "fatigue"],
    "target_folders": ["Medical/Treatments/", "Daily Notes/"],
    "reasoning": "Gather first treatment arm details"
  },
  {
    "step_number": 3,
    "sub_question": "What was the CAR-T (Yescarta) therapy timeline and side effects?",
    "search_strategy": "vector",
    "keywords": ["CAR-T", "Yescarta", "side effects", "CRS", "neurotoxicity"],
    "target_folders": ["Medical/Treatments/CAR-T/"],
    "reasoning": "Gather second treatment arm details for comparison"
  },
  {
    "step_number": 4,
    "sub_question": "Compare side effect severity and duration between the two treatments",
    "search_strategy": "hybrid",
    "keywords": ["compare", "side effects", "severity", "duration"],
    "target_folders": [],
    "reasoning": "Synthesize comparative analysis from previous findings"
  }
]
```

#### 1.2 Retrieval Supervisor
**Purpose:** Route each step to the optimal search strategy.

**Implementation:**
```python
class RetrievalSupervisor:
    def __init__(self, chromadb_client, lightrag_client):
        self.vector_search = chromadb_client
        self.graph_search = lightrag_client
        
    def execute_step(self, step: Step, state: RAGState) -> List[dict]:
        """
        Execute the search strategy specified in the step.
        Apply folder filtering if specified.
        """
        query = step["sub_question"]
        strategy = step["search_strategy"]
        
        # Apply Obsidian folder filtering
        filters = self._build_filters(step["target_folders"])
        
        if strategy == "vector":
            results = self.vector_search.query(
                query_texts=[query],
                n_results=10,
                where=filters
            )
            
        elif strategy == "graph":
            results = self.graph_search.query(
                query=query,
                mode="local"  # Entity-focused
            )
            
        elif strategy == "hybrid":
            # Run both and merge results
            vector_results = self.vector_search.query(query_texts=[query], n_results=10)
            graph_results = self.graph_search.query(query=query, mode="hybrid")
            results = self._merge_results(vector_results, graph_results)
            
        return results
    
    def _build_filters(self, target_folders: List[str]) -> dict:
        """Convert Obsidian folder paths to ChromaDB metadata filters."""
        if not target_folders:
            return {}
        
        # Example: {"$or": [{"file_path": {"$contains": "Medical/"}}, ...]}
        return {
            "$or": [{"file_path": {"$contains": folder}} for folder in target_folders]
        }
```

#### 1.3 Reflection Agent
**Purpose:** Summarize what was learned from each step.

**Implementation:**
```python
class ReflectionAgent:
    def __init__(self, llm_client):
        self.llm = llm_client
        
    def reflect(self, step: Step, documents: List[dict], state: RAGState) -> PastStep:
        """
        Summarize findings from the current step into a single insight.
        """
        prompt = f"""
        Research Step: "{step['sub_question']}"
        
        Retrieved {len(documents)} documents.
        
        Document snippets:
        {self._format_documents(documents[:3])}
        
        Previous findings:
        {self._format_past_steps(state['past_steps'])}
        
        Provide:
        1. One-sentence summary of key finding
        2. Confidence score (0.0-1.0) on answer completeness
        3. Are there gaps that need another search?
        
        Return JSON with: {{"key_finding": "...", "confidence": 0.8, "has_gaps": false}}
        """
        
        response = self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        reflection = json.loads(response.content[0].text)
        
        return PastStep(
            step=step,
            documents_found=len(documents),
            key_findings=reflection["key_finding"],
            confidence=reflection["confidence"]
        )
```

#### 1.4 Policy Agent (LLM-as-Judge)
**Purpose:** Decide whether to continue searching or generate final answer.

**Implementation:**
```python
class PolicyAgent:
    def __init__(self, llm_client):
        self.llm = llm_client
        
    def decide(self, state: RAGState) -> Literal["CONTINUE", "FINISH", "REVISE_PLAN"]:
        """
        Evaluate progress and decide next action.
        """
        prompt = f"""
        Original Question: "{state['original_question']}"
        
        Research completed so far:
        {self._format_research_summary(state['past_steps'])}
        
        Remaining planned steps: {len(state['plan']) - state['current_step_index']}
        Iterations used: {state['iteration_count']} / {state['max_iterations']}
        
        Decision options:
        - CONTINUE: Execute next planned step
        - FINISH: Sufficient information gathered, generate answer
        - REVISE_PLAN: Current plan won't work, need different approach
        
        Return JSON: {{"decision": "CONTINUE|FINISH|REVISE_PLAN", "reasoning": "..."}}
        """
        
        response = self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        decision = json.loads(response.content[0].text)
        return decision["decision"]
```

#### 1.5 Main Orchestration Loop

```python
class DeepThinkingRAG:
    def __init__(self, claude_client, chromadb_client, lightrag_client):
        self.planner = PlannerAgent(claude_client)
        self.supervisor = RetrievalSupervisor(chromadb_client, lightrag_client)
        self.reflector = ReflectionAgent(claude_client)
        self.policy = PolicyAgent(claude_client)
        self.synthesizer = FinalAnswerGenerator(claude_client)
        
    def query(self, question: str, max_iterations: int = 7) -> dict:
        """
        Main reasoning loop.
        """
        # Initialize state
        state = RAGState(
            original_question=question,
            plan=[],
            current_step_index=0,
            past_steps=[],
            accumulated_context="",
            retrieved_documents=[],
            iteration_count=0,
            max_iterations=max_iterations,
            should_continue=True,
            final_answer="",
            citations=[]
        )
        
        # Step 1: Create plan
        state["plan"] = self.planner.create_plan(question, vault_context={})
        
        # Step 2: Execute plan with reflection loop
        while state["should_continue"] and state["iteration_count"] < max_iterations:
            state["iteration_count"] += 1
            
            # Get current step
            if state["current_step_index"] >= len(state["plan"]):
                break
                
            current_step = state["plan"][state["current_step_index"]]
            
            # Execute retrieval
            documents = self.supervisor.execute_step(current_step, state)
            state["retrieved_documents"].extend(documents)
            
            # Reflect on findings
            past_step = self.reflector.reflect(current_step, documents, state)
            state["past_steps"].append(past_step)
            
            # Update accumulated context
            state["accumulated_context"] += f"\n\nStep {current_step['step_number']}: {past_step['key_findings']}"
            
            # Move to next step
            state["current_step_index"] += 1
            
            # Check if we should continue
            if state["current_step_index"] >= len(state["plan"]):
                # Plan complete - ask policy if we have enough
                decision = self.policy.decide(state)
                
                if decision == "FINISH":
                    state["should_continue"] = False
                elif decision == "REVISE_PLAN":
                    # Generate additional steps
                    new_steps = self.planner.extend_plan(state)
                    state["plan"].extend(new_steps)
        
        # Step 3: Generate final answer
        state["final_answer"], state["citations"] = self.synthesizer.generate(state)
        
        return {
            "answer": state["final_answer"],
            "citations": state["citations"],
            "research_steps": state["past_steps"],
            "total_documents": len(state["retrieved_documents"])
        }
```

### Phase 1 Deliverables
- [ ] `planner_agent.py` - Query decomposition
- [ ] `retrieval_supervisor.py` - Dynamic search routing
- [ ] `reflection_agent.py` - Step summarization
- [ ] `policy_agent.py` - Continue/finish decisions
- [ ] `deep_thinking_rag.py` - Main orchestration loop
- [ ] Unit tests for each agent
- [ ] Integration test with 5 known complex queries from your vault

### Phase 1 Success Criteria
1. Successfully decomposes multi-hop questions into 2-5 sub-steps
2. Executes plan with appropriate search strategies
3. Generates research summary showing step-by-step progress
4. Completes within iteration limit (no infinite loops)

---

## Phase 2: Retrieval Enhancement (Weeks 4-5)

### Objective
Improve precision by reranking retrieved documents and filtering noise.

### Components

#### 2.1 Cross-Encoder Reranking
**Purpose:** Rerank top 10 results to surface the most relevant 3-5.

**Implementation:**
```python
from sentence_transformers import CrossEncoder

class Reranker:
    def __init__(self):
        # Fast, local reranker
        self.model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        
    def rerank(self, query: str, documents: List[dict], top_k: int = 5) -> List[dict]:
        """
        Rerank documents by relevance to query.
        """
        # Prepare query-document pairs
        pairs = [(query, doc["text"]) for doc in documents]
        
        # Score all pairs
        scores = self.model.predict(pairs)
        
        # Sort by score and return top_k
        scored_docs = [
            {**doc, "rerank_score": float(score)}
            for doc, score in zip(documents, scores)
        ]
        scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        return scored_docs[:top_k]
```

**Integration Point:**
```python
# In RetrievalSupervisor.execute_step()
results = self.vector_search.query(query_texts=[query], n_results=10)
results = self.reranker.rerank(query, results, top_k=5)
```

#### 2.2 Contextual Compression
**Purpose:** Extract only relevant passages from long documents.

**Implementation:**
```python
class ContextualCompressor:
    def __init__(self, llm_client):
        self.llm = llm_client
        
    def compress(self, query: str, document: dict) -> str:
        """
        Extract only the sentences relevant to the query.
        """
        prompt = f"""
        Question: "{query}"
        
        Document excerpt:
        {document['text'][:2000]}
        
        Extract ONLY the 2-3 sentences that directly answer the question.
        If nothing is relevant, return "NOT_RELEVANT".
        """
        
        response = self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        compressed = response.content[0].text.strip()
        
        if compressed == "NOT_RELEVANT":
            return None
        
        return compressed
```

#### 2.3 Enhanced Supervisor with Reranking

```python
class RetrievalSupervisor:
    def __init__(self, chromadb_client, lightrag_client):
        self.vector_search = chromadb_client
        self.graph_search = lightrag_client
        self.reranker = Reranker()
        self.compressor = ContextualCompressor(claude_client)
        
    def execute_step(self, step: Step, state: RAGState) -> List[dict]:
        """
        Execute with reranking and compression.
        """
        # Initial retrieval (k=10)
        results = self._retrieve(step, k=10)
        
        # Rerank to top 5
        results = self.reranker.rerank(step["sub_question"], results, top_k=5)
        
        # Compress each document (optional, for long docs)
        for doc in results:
            if len(doc["text"]) > 1000:
                compressed = self.compressor.compress(step["sub_question"], doc)
                if compressed:
                    doc["compressed_text"] = compressed
        
        return results
```

### Phase 2 Deliverables
- [ ] `reranker.py` - Cross-encoder reranking
- [ ] `compressor.py` - Contextual compression (optional)
- [ ] Update `retrieval_supervisor.py` with reranking
- [ ] Benchmark: Compare precision before/after reranking on 10 test queries
- [ ] Add reranking toggle to Streamlit UI

### Phase 2 Success Criteria
1. Reranking improves top-3 relevance by >20% (manual evaluation)
2. Average latency increase < 2 seconds
3. No degradation on simple queries

---

## Phase 3: Self-Correction & Polish (Weeks 6-8)

### Objective
Enable dynamic re-planning when initial searches fail, and add UI transparency.

### Components

#### 3.1 Dynamic Plan Revision

```python
class PlannerAgent:
    # ... (existing methods)
    
    def extend_plan(self, state: RAGState) -> List[Step]:
        """
        Generate new steps when current plan is insufficient.
        """
        prompt = f"""
        Original question: "{state['original_question']}"
        
        Research completed:
        {self._format_past_steps(state['past_steps'])}
        
        What information is still missing to answer the question?
        Generate 1-2 additional search steps to fill gaps.
        
        Return JSON array of new steps.
        """
        
        response = self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        new_steps = json.loads(response.content[0].text)
        
        # Assign step numbers continuing from existing plan
        for i, step in enumerate(new_steps):
            step["step_number"] = len(state["plan"]) + i + 1
            
        return new_steps
```

#### 3.2 Final Answer Generator with Citations

```python
class FinalAnswerGenerator:
    def __init__(self, llm_client):
        self.llm = llm_client
        
    def generate(self, state: RAGState) -> tuple[str, List[str]]:
        """
        Synthesize final answer with Obsidian-style citations.
        """
        prompt = f"""
        Original question: "{state['original_question']}"
        
        Research summary:
        {state['accumulated_context']}
        
        All retrieved documents:
        {self._format_documents_for_citation(state['retrieved_documents'])}
        
        Generate a comprehensive answer that:
        1. Directly addresses the original question
        2. Synthesizes findings from all research steps
        3. Cites sources using format: [[Folder/Note Name]] or "Document Title"
        4. Acknowledges any gaps or uncertainties
        
        Return JSON:
        {{
            "answer": "...",
            "citations": ["[[Medical/CAR-T/Treatment Log 2023-05-15]]", "..."]
        }}
        """
        
        response = self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        result = json.loads(response.content[0].text)
        return result["answer"], result["citations"]
```

#### 3.3 Streamlit UI Integration

```python
# In streamlit_ui_docker.py

def render_deep_thinking_mode():
    st.subheader("Deep Thinking RAG (Agentic Mode)")
    
    question = st.text_area("Ask a complex question:", height=100)
    
    max_iterations = st.slider("Max reasoning iterations:", 3, 10, 7)
    
    if st.button("Research"):
        with st.spinner("Planning research strategy..."):
            result = deep_thinking_rag.query(question, max_iterations=max_iterations)
        
        # Show research process
        with st.expander("🧠 Research Process", expanded=True):
            for i, past_step in enumerate(result["research_steps"]):
                step = past_step["step"]
                st.markdown(f"""
                **Step {step['step_number']}**: {step['sub_question']}
                - Strategy: `{step['search_strategy']}`
                - Found: {past_step['documents_found']} documents
                - Key Finding: {past_step['key_findings']}
                - Confidence: {past_step['confidence']:.2f}
                """)
                st.divider()
        
        # Show final answer
        st.markdown("### 📝 Answer")
        st.markdown(result["answer"])
        
        # Show citations
        with st.expander("📚 Sources"):
            for citation in result["citations"]:
                st.markdown(f"- {citation}")
```

### Phase 3 Deliverables
- [ ] `plan_revision.py` - Dynamic re-planning logic
- [ ] `final_answer_generator.py` - Synthesis with citations
- [ ] Update Streamlit UI with "Deep Thinking" mode toggle
- [ ] Add progress visualization showing research steps
- [ ] Configuration file for iteration limits, reranking toggles
- [ ] Documentation with example queries and expected outputs

### Phase 3 Success Criteria
1. Successfully recovers from initial search failures by revising plan
2. Citations correctly reference Obsidian note paths
3. UI clearly shows reasoning process (transparency)
4. End-to-end latency < 45 seconds for 5-step queries

---

## Configuration System

```yaml
# config/deep_thinking.yaml

deep_thinking_rag:
  enabled: true
  
  planning:
    max_steps_initial: 5
    max_steps_total: 10
    model: "claude-sonnet-4-20250514"
  
  retrieval:
    initial_k: 10
    rerank_enabled: true
    rerank_top_k: 5
    compression_enabled: false  # Start disabled
  
  reflection:
    summarize_each_step: true
    confidence_threshold: 0.7
  
  policy:
    iteration_limit: 7
    auto_extend_plan: true
  
  models:
    planner: "claude-sonnet-4-20250514"
    reflector: "claude-sonnet-4-20250514"
    policy: "claude-sonnet-4-20250514"
    synthesizer: "claude-sonnet-4-20250514"
```

---

## Testing Strategy

### Unit Tests (Per Phase)
```python
# tests/test_planner.py
def test_planner_decomposes_complex_query():
    question = "Compare CAR-T side effects with R-CHOP based on my notes"
    plan = planner.create_plan(question, {})
    
    assert len(plan) >= 2
    assert any("CAR-T" in step["keywords"] for step in plan)
    assert any("R-CHOP" in step["keywords"] for step in plan)

# tests/test_supervisor.py
def test_supervisor_routes_to_graph_search():
    step = Step(
        sub_question="What is the relationship between ESP32 and Home Assistant?",
        search_strategy="graph",
        keywords=["ESP32", "Home Assistant", "relationship"],
        target_folders=[],
        reasoning=""
    )
    
    results = supervisor.execute_step(step, empty_state)
    assert len(results) > 0
```

### Integration Tests (End of Each Phase)
```python
# tests/integration/test_medical_query.py
def test_lymphoma_timeline_query():
    question = "Create a timeline of my lymphoma treatment from diagnosis to latest scan"
    
    result = deep_thinking_rag.query(question, max_iterations=7)
    
    assert "diagnosis" in result["answer"].lower()
    assert "PET scan" in result["answer"].lower()
    assert len(result["citations"]) >= 3
    assert result["research_steps"] >= 2
```

### Validation Queries (Your Specific Use Cases)

```python
TEST_QUERIES = [
    # Medical
    "What were the SUV values across my PET scans and what do they indicate?",
    "Compare side effects between my chemotherapy and CAR-T therapy phases",
    "Timeline of my lymphoma journey from diagnosis to current status",
    
    # Technical
    "What ESP32 boards do I use for ESPHome projects and their configurations?",
    "How is my Home Assistant integrated with weather data and displays?",
    "What automation rules do I have for my garage door system?",
    
    # Multi-Domain
    "During my CAR-T treatment, what home automation projects was I working on?",
    "What technical projects did I pause or complete during medical treatments?",
]
```

---

## Dependency Management

### New Dependencies (Minimal)
```bash
# requirements.txt additions
sentence-transformers>=2.2.0  # For cross-encoder reranking
```

### No Need To Add
- ❌ LangGraph (too complex, custom loop is simpler)
- ❌ Tavily/web search (contradicts local-first)
- ❌ BM25/rank_bm25 (ChromaDB + LightRAG already handle this)
- ❌ Additional LLM models (Claude Sonnet 4.5 handles all reasoning)

---

## Performance Considerations

### Latency Budget (Target: < 45s for complex queries)
| Component | Time Estimate | Optimization |
|-----------|---------------|--------------|
| Planning | 2-4s | Single LLM call |
| Step 1 Retrieval | 3-5s | Existing ChromaDB |
| Reranking | 1-2s | Local cross-encoder |
| Reflection | 2-3s | Fast LLM call |
| Steps 2-4 | 10-20s | Parallel if possible |
| Policy Decision | 2-3s | Fast LLM call |
| Final Synthesis | 5-7s | Single LLM call |
| **Total** | **25-44s** | Within target |

### Cost Optimization
- Use Claude Sonnet 4.5 for all reasoning (you already have API access)
- Local reranking model (no API costs)
- Caching for repeated sub-queries (future enhancement)

---

## Rollout Strategy

### Week 1-2 (Phase 1 Foundation)
- Build core agents (Planner, Supervisor, Reflector, Policy)
- Wire up orchestration loop
- Test with 3-5 simple multi-hop queries
- **Decision Point**: Does planning improve results? If yes → proceed

### Week 3 (Phase 1 Completion)
- Add iteration controls and safeguards
- Integrate with existing Streamlit UI (toggle mode)
- Validate with 10 complex queries from your vault
- **Decision Point**: Are results better than single-shot? If yes → Phase 2

### Week 4-5 (Phase 2 Enhancement)
- Add reranking layer
- Benchmark precision improvement
- Optional: Add compression for very long documents
- **Decision Point**: Does reranking justify latency cost? Adjust config

### Week 6-8 (Phase 3 Polish)
- Add dynamic plan revision
- Build citation system
- Polish UI with research visualization
- Write documentation and examples

---

## Success Metrics

### Quantitative
- [ ] Answer complex queries requiring 3+ note synthesis (currently fails)
- [ ] Top-3 relevance > 80% (vs current ~50% with semantic ambiguity)
- [ ] Average latency < 45s for 5-step queries
- [ ] Zero infinite loops (iteration control works)

### Qualitative (Manual Evaluation)
- [ ] Answers make sense and are accurate
- [ ] Citations correctly reference your Obsidian notes
- [ ] Research process is transparent and logical
- [ ] System recovers from dead-end searches

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Increased latency | High | Medium | Optimize model calls, add caching |
| Plan quality inconsistent | Medium | High | Extensive prompt engineering, fallback to simple mode |
| Reranking slows system | Medium | Low | Make reranking optional, benchmark before deploy |
| Infinite loops | Low | High | Hard iteration limits (7 max), timeout safeguards |
| Claude API costs | Low | Medium | Monitor token usage, optimize prompts |

---

## Future Enhancements (Post-Phase 3)

### Quick Wins
- [ ] Caching for repeated sub-queries
- [ ] Parallel retrieval for independent steps
- [ ] User feedback loop (thumbs up/down on steps)

### Advanced Features
- [ ] Memory of past successful plans (learn from experience)
- [ ] Automatic folder classification (ML model predicts target folders)
- [ ] Query auto-completion based on vault structure
- [ ] Weekly digest: "Questions you might want to ask about your notes"

### Integration Options
- [ ] MCP server for Claude Desktop (you're already exploring this)
- [ ] Obsidian plugin for in-app querying
- [ ] Voice interface for hands-free research

---

## Decision Points & Off-Ramps

### After Phase 1
**If planning doesn't improve results:**
- Fall back to enhanced single-shot (just add reranking)
- Investigate root cause: prompt quality? vault structure?

### After Phase 2
**If reranking adds latency without improving precision:**
- Disable reranking, focus on better retrieval strategies
- Consider pre-filtering by metadata before semantic search

### After Phase 3
**If system is too complex to maintain:**
- Simplify to 3 core agents (Plan, Execute, Synthesize)
- Remove dynamic re-planning, stick to fixed plans

---

## Appendix A: Example Execution Trace

**Query:** "Compare the side effects I experienced with R-CHOP vs CAR-T therapy"

```
🧠 PLANNING PHASE
Generated 4-step plan:
1. Search for R-CHOP treatment notes (vector, Medical/Treatments/)
2. Search for CAR-T therapy notes (vector, Medical/Treatments/CAR-T/)
3. Search for side effect mentions in daily logs (hybrid, Daily Notes/)
4. Synthesize comparison (hybrid)

🔍 STEP 1: Search for R-CHOP treatment notes
Strategy: Vector Search in Medical/Treatments/
Retrieved: 8 documents
Reranked top 5:
- [[Medical/Treatments/R-CHOP Protocol]] (score: 0.92)
- [[Medical/Treatments/Cycle 3 Notes]] (score: 0.87)
- [[Daily Notes/2023-03-15]] (score: 0.81)

💭 REFLECTION: Found 6 R-CHOP cycles with documented side effects including nausea, fatigue, and neutropenia.
Confidence: 0.85

🔍 STEP 2: Search for CAR-T therapy notes
Strategy: Vector Search in Medical/Treatments/CAR-T/
Retrieved: 12 documents
Reranked top 5:
- [[Medical/Treatments/CAR-T/Yescarta Timeline]] (score: 0.95)
- [[Medical/Treatments/CAR-T/Day +7 Assessment]] (score: 0.89)
- [[Daily Notes/2023-06-22]] (score: 0.83)

💭 REFLECTION: Found CAR-T infusion date, CRS Grade 1, neurotoxicity monitoring, complete response.
Confidence: 0.90

🔍 STEP 3: Search for side effect mentions in daily logs
Strategy: Hybrid Search in Daily Notes/
Retrieved: 15 documents
Reranked top 5:
- [[Daily Notes/2023-03-20]] - "Nausea manageable with ondansetron" (score: 0.88)
- [[Daily Notes/2023-06-25]] - "Mild confusion resolved by day 10" (score: 0.85)

💭 REFLECTION: Daily logs provide subjective severity ratings and duration of side effects.
Confidence: 0.80

✅ POLICY DECISION: FINISH (Sufficient evidence gathered, 3/4 steps complete)

📝 SYNTHESIZING FINAL ANSWER...

ANSWER:
Based on your treatment notes, here's a comparison of side effects:

**R-CHOP (6 cycles, March-May 2023):**
- Nausea and vomiting (moderate, managed with ondansetron)
- Fatigue (persistent, improved between cycles)
- Neutropenia (required GCSF support in cycles 3 and 5)
- Hair loss (gradual, started cycle 2)

**CAR-T Therapy (Yescarta, June 2023):**
- CRS Grade 1 (mild fever, managed without tocilizumab)
- Mild neurotoxicity (confusion on days 7-9, fully resolved by day 12)
- Fatigue (less severe than R-CHOP)
- No nausea or vomiting

Overall, CAR-T therapy had a shorter side effect window (10 days vs 4 months) but required closer monitoring. R-CHOP effects were cumulative across cycles.

CITATIONS:
- [[Medical/Treatments/R-CHOP Protocol]]
- [[Medical/Treatments/CAR-T/Yescarta Timeline]]
- [[Daily Notes/2023-03-20]]
- [[Daily Notes/2023-06-25]]

Total research time: 28 seconds
```

---

## Appendix B: Implementation Checklist

### Phase 1 (Weeks 1-3)
- [ ] Set up project structure: `agents/`, `tests/`, `config/`
- [ ] Implement `PlannerAgent` with Claude integration
- [ ] Implement `RetrievalSupervisor` with folder filtering
- [ ] Implement `ReflectionAgent`
- [ ] Implement `PolicyAgent`
- [ ] Build main `DeepThinkingRAG` orchestration loop
- [ ] Write unit tests for each agent
- [ ] Integration test with 5 test queries
- [ ] Add toggle to Streamlit UI
- [ ] Document Phase 1 architecture

### Phase 2 (Weeks 4-5)
- [ ] Install sentence-transformers
- [ ] Implement `Reranker` class
- [ ] Integrate reranking into `RetrievalSupervisor`
- [ ] Benchmark precision improvement on 10 queries
- [ ] Optional: Implement `ContextualCompressor`
- [ ] Add reranking toggle to config
- [ ] Update Streamlit UI with reranking indicator
- [ ] Performance profiling and optimization

### Phase 3 (Weeks 6-8)
- [ ] Implement `extend_plan()` in PlannerAgent
- [ ] Implement `FinalAnswerGenerator` with citations
- [ ] Add research process visualization to UI
- [ ] Build citation formatter for Obsidian links
- [ ] End-to-end testing with 20 complex queries
- [ ] Write user documentation with examples
- [ ] Create troubleshooting guide
- [ ] Plan Phase 4 enhancements (if needed)

---

## Contact & Support

**Maintainer:** Michel (Product Manager, Magog QC)  
**Technical Stack:** Python 3.11+, ChromaDB, LightRAG, Claude Sonnet 4.5, Streamlit  
**Primary Use Cases:** Medical documentation synthesis, technical project research  
**Vault Size:** 1,560 notes, 6,848 chunks indexed  

For questions during implementation:
- Check `docs/troubleshooting.md`
- Review test queries in `tests/fixtures/queries.json`
- Validate against known failure modes in `docs/failure_modes.md`

---

**Next Action:** Review this plan, then begin Phase 1 Week 1 by implementing the `PlannerAgent`.