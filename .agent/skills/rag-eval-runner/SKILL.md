---
name: RAG Eval Runner
description: Evaluate search quality using the knowledge graph and test prompts.
---

# RAG Eval Runner Skill

This skill runs evaluation routines to measure the quality of retrieval (Vector vs Graph vs Hybrid).

## Goal
To quantitatively and qualitatively assess if search improvements are actually working.

## Tools & Scripts
*   **Query Tool:** `src/services/graph_query_service.py` (via `obsidian_graph_query` entry point if available, or direct python)
*   **Test Prompts:** `Documentation/operations/quality/KNOWLEDGE_GRAPH_TEST_PROMPTS.md`

## Instructions

1.  **Select Test Cases**
    *   Read `Documentation/operations/quality/KNOWLEDGE_GRAPH_TEST_PROMPTS.md`.
    *   Pick 3-5 queries representing different types (Entity lookup, Relationships, Broad trends).

2.  **Execute Queries**
    *   Use the supported gateway entrypoints first; use graph-specific tools only for internal diagnostics.
    *   Run each query in two modes:
        1.  `mode="vector"`
        2.  `mode="cascading"`

3.  **Analyze Results**
    *   Compare the "sources" returned.
    *   Check if the "Direct Answer" correctly synthesizes the information.
    *   **Metric:** "Match Strength" - does the Cascading result include relevant grounded evidence that Vector missed?

4.  **Reporting**
    *   Append results to `Documentation/operations/quality/SEARCH_COMPARISON_RESULTS.md` (create if missing).
    *   Format: `| Query | Vector Sources | Cascading Sources | Winner |`

## Constraints
*   Do not modify the evaluation code during a run.
*   Ensure the Graph Service is running (`docker compose ps`) before starting tests.
