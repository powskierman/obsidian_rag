# Project Improvement Plan: Deep Thinking RAG for Obsidian

## Executive Summary
This document outlines a roadmap to elevate `obsidian_rag` from a standard RAG system to a "Deep Thinking" reasoning engine. By adopting architectural patterns from the `deep-thinking-rag` framework, we can enable the system to handle complex, multi-hop queries (e.g., "Compare the treatment side effects of X vs Y and how they align with my personal history") with far greater accuracy and depth.

## Core Concepts & Architecture

The proposed architecture introduces a **Stateful Agentic Workflow** replacing the current linear/sequential logic.

### 1. Centralized RAG State
Instead of passing simple strings between functions, we will maintain a structured `RAGState` object throughout the lifecycle of a query.

```python
class RAGState(TypedDict):
    original_question: str
    plan: List[Step]          # The roadmap of what to research
    past_steps: List[PastStep]# What has been done and learned so far
    accumulated_context: str  # Synthesized knowledge from all steps
    final_answer: str
```

### 2. The "Brain": Planner Agent
**Current State**: The system treats every query as a single search operation (even with the new sequential hybrid mode).
**Improvement**: Implement a **Planner Agent** (LLM) that decomposes a complex user query into a sequence of granular, answerable sub-steps.

*   **Input**: "Review my lymphoma journey using PET scan results and notes."
*   **Output Plan**:
    1.  `search_vector`: "Find all PET scan results and dates."
    2.  `search_graph`: "Summarize the timeline of lymphoma diagnosis and treatments."
    3.  `search_vector`: "Identify specific side effects mentioned in notes."
    4.  `synthesize`: "Combine findings into a narrative."

### 3. The "Manager": Retrieval Supervisor
**Current State**: We have a global "Search Mode" (Vector/Graph/Hybrid) selected by the user or simple regex.
**Improvement**: Implement a **Supervisor Agent** that dynamically selects the best tool *for each step* of the plan.

*   **Conceptual queries** ("What is the sentiment...?") -> **Vector Search**
*   **Specific entity queries** ("What is the dosage of R-CHOP?") -> **Graph Search** (or Keyword Search)
*   **Complex relationships** -> **Hybrid Search**

### 4. The "Critic": Reflection & Policy Loop
**Current State**: The system returns whatever it finds in one shot. If it misses something, it fails.
**Improvement**: Implement a **Self-Critique Loop**.
*   **Reflection Agent**: After each step, summarize what was learned.
*   **Policy Agent**: Decide: "Do I have enough information to answer the original question?"
    *   If **YES** -> Generate Final Answer.
    *   If **NO** -> Generate a new Step to fill the gap (e.g., "I found the PET scan date but not the result. I need to search for 'PET scan result 2023' specifically.").

## Implementation Roadmap

### Phase 1: Foundation (State & Planner)
*   [ ] Define `RAGState`, `Step`, and `Plan` data structures (Pydantic).
*   [ ] Create the **Planner Agent** using Claude Sonnet 4.5 to decompose queries.
*   [ ] Refactor `streamlit_ui_docker.py` to execute this plan sequentially (replacing the current simple sequential logic).

### Phase 2: Intelligence (Supervisor & Tools)
*   [ ] Create the **Supervisor Agent** to route steps to the appropriate tool (Vector vs. Graph).
*   [ ] Refine the "Graph Search" tool to accept specific sub-queries rather than just the global prompt.

### Phase 3: Autonomy (Reflection Loop)
*   [ ] Implement the **Reflection Agent** to summarize step results.
*   [ ] Implement the **Policy Agent** to allow dynamic re-planning (looping) if information is missing.

## Benefits
*   **Handling Complexity**: Can answer questions that require gathering scattered pieces of information.
*   **Self-Correction**: If a search fails, the agent notices and tries a different query instead of giving up.
*   **Transparency**: The UI can show the "Plan" and the "Thinking Process" (e.g., "Step 1 complete: Found scan dates. Step 2: Searching for results...").

## Recommendation
Start with **Phase 1**. The current "Sequential Hybrid" implementation is a primitive version of this. Formalizing it into a Planner-based workflow is the natural next step.
