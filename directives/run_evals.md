# Directive: Run RAG Evals

## Metadata
- **Owner**: API & Search Implementation Track
- **Last Updated**: 2026-01-23
- **Related Scripts**: `src/services/graph_query_service.py`
- **Related Documents**: `Documentation/operations/quality/KNOWLEDGE_GRAPH_TEST_PROMPTS.md`, `Documentation/operations/quality/SEARCH_COMPARISON_RESULTS.md`
- **Version**: 1.0.0

## Contract

### Purpose
Evaluate the quality of retrieval by comparing supported search modes against known test cases.

### Inputs
- **queries** (list of strings, optional): Specific queries to test. If omitted, select from `KNOWLEDGE_GRAPH_TEST_PROMPTS.md`.
- **modes** (list of strings, optional): Modes to test. Defaults to `["vector", "cascading"]`.

### Outputs
- **comparison_log** (markdown string): A qualified comparison of results.
- **metrics** (object):
  - **vector_relevance**: Qualitative score (High/Medium/Low).
  - **cascading_relevance**: Qualitative score (High/Medium/Low).

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
      - Run with `mode="vector"`.
      - Run with `mode="cascading"`.
      - Use the API gateway `POST /api/v1/query`.

3.  **Analysis**
    - **Compare Sources**: Did Cascading find supporting sources that Vector missed?
    - **Compare Answer**: Is the synthesis more accurate?
    - **Determine Winner**: Vector, Cascading, or Tie.

4.  **Reporting**
    - Format output as a Markdown table row: `| Query | Vector Sources | Cascading Sources | Winner |`
    - Append to `Documentation/operations/quality/SEARCH_COMPARISON_RESULTS.md`.

## Error Handling

- **Service Unavailable**:
  - If query fails with Connection Error, check `deploy_gateway` directive to restart service.
- **Empty Results**:
  - Note as "No results" in comparison. Investigate if indexing is needed.

## Cost Profile
- **LLM API**: Each query involves LLM calls for answer synthesis.
