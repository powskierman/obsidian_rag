# Directive: Run RAG Evals

## Metadata
- **Owner**: API & Search Implementation Track
- **Last Updated**: 2026-04-17
- **Related Scripts**: `src/services/graph_query_service.py`, `Scripts/debug/eval_comprehensive_classifier.py`
- **Related Documents**: `Documentation/operations/quality/KNOWLEDGE_GRAPH_TEST_PROMPTS.md`, `Documentation/operations/quality/SEARCH_COMPARISON_RESULTS.md`
- **Version**: 2.0.0

## Contract

### Purpose
Evaluate the quality of retrieval by comparing supported search modes against known test cases.

### Inputs
- **queries** (list of strings, optional): Specific queries to test. If omitted, select from `KNOWLEDGE_GRAPH_TEST_PROMPTS.md`.
- **modes** (list of strings, optional): Modes to test. Defaults to `["ask", "research"]`.

### Outputs
- **comparison_log** (markdown string): A qualified comparison of results.
- **metrics** (object):
  - **ask_relevance**: Qualitative score (High/Medium/Low).
  - **research_relevance**: Qualitative score (High/Medium/Low).

### Preconditions
- Graph Service must be running (`docker compose ps`).
- The API gateway must be reachable for REST mode checks.

### Postconditions
- Results are appended to `Documentation/operations/quality/SEARCH_COMPARISON_RESULTS.md`.

## Flow

1.  **Selection**
    - If `queries` not provided, read `Documentation/operations/quality/KNOWLEDGE_GRAPH_TEST_PROMPTS.md` and pick 3-5 diverse queries.

2.  **Execution**
    - For each query:
      - Run with `mode="ask"`.
      - Run with `mode="research"`.
      - Use the API gateway `POST /api/v1/query`.

3.  **Analysis**
    - **Compare Sources**: Did Research find supporting sources that Ask missed?
    - **Compare Answer**: Is the synthesis more accurate?
    - **Determine Winner**: Ask, Research, or Tie.

4.  **Reporting**
    - Format output as a Markdown table row: `| Query | Ask Sources | Research Sources | Winner |`
    - Append to `Documentation/operations/quality/SEARCH_COMPARISON_RESULTS.md`.

## Auto-Depth Classifier Eval

Run `Scripts/debug/eval_comprehensive_classifier.py` to evaluate the `_is_comprehensive_vault_review_query()` auto-depth classifier separately. The classifier determines whether a research query gets `depth=shallow` or `depth=staged`. Target hit rate is ≥80%.

## Error Handling

- **Service Unavailable**:
  - If query fails with Connection Error, check `deploy_gateway` directive to restart service.
- **Empty Results**:
  - Note as "No results" in comparison. Investigate if indexing is needed.

## Cost Profile
- **LLM API**: Each query involves LLM calls for answer synthesis.
