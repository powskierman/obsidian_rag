# Graph Quality Guide

This guide covers the levers that most affect NetworkX graph quality.

## Quality Levers

1. **Chunking**
   - Use overlapping chunks with clear boundaries.
   - Avoid very short chunks (they add noise).

2. **Model choice**
   - Higher quality models produce cleaner entity/relationship extraction.
   - Use a stronger model for critical domains (medical, legal).

3. **Retries**
   - Failed chunks reduce coverage.
   - Re-run failures to improve completeness.

## Quick Checks

- Ensure `data/graph_data/knowledge_graph_full.pkl` exists.
- Check for failed chunks and retry:
  ```bash
  python src/indexing/retry_failed_chunks.py
  ```

## Build Recommendations

- Prefer full builds for major vault changes.
- Rebuild if you reorganize large folders or import new notes.

## Related Docs

- `Documentation/Graph/IMPROVED_GRAPH_BUILDER_GUIDE.md`
- `Documentation/Graph/GRAPH_DATA_FLOW.md`
- `Documentation/Archive/reports/BUILD_STATISTICS.md`
