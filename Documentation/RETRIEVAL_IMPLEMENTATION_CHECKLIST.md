# Retrieval Improvement Implementation Checklist

This checklist tracks implementation work for improving clinical answer quality and graph-grounded retrieval across indexing, graph build, retriever, and response formatting.

## Status Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete

## Execution Order

### P0 (Foundation: canonicalization + grounding safety)

- [x] `P0-01` Add canonical entity metadata during ingest (`canonical_id`, `aliases_normalized`, `entity_type`, `timeline_date`, `treatment_phase`).
  - Component: Indexing
  - Files: `src/indexing/index_vault.py`, `src/indexing/frontmatter.py`, `src/integrations/lightrag_service.py`
  - Acceptance: Both vector and LightRAG indexing payloads include canonical/timeline metadata.

- [x] `P0-02` Add duplicate-entity reporting (`Yescarta` vs `Yescarta.md`) as a deterministic audit step.
  - Component: Indexing/Graph QA
  - Files: `Scripts/debug/inspect_graph_nodes.py` or `Scripts/debug/report_duplicate_entities.py` (new)
  - Acceptance: Script outputs duplicate candidates and recommended merge/cross-link actions.

- [x] `P0-03` Add canonical node resolution or explicit `SAME_AS` edges in graph build.
  - Component: Graph Build
  - Files: `src/services/networkx_graph_builder.py`
  - Acceptance: Alias variants resolve to one canonical concept in graph queries.

- [x] `P0-04` Add unknowns validator to prevent claiming gaps already present in sources.
  - Component: Response Formatter
  - Files: `src/integrations/lightrag_service.py`
  - Acceptance: “Unknowns / Gaps” does not include facts available in retrieved notes.

- [x] `P0-05` Add unit tests for canonicalization + alias resolution + unknowns validation.
  - Component: Tests
  - Files: `tests/unit/test_indexing_canonicalization.py` (new), `tests/unit/test_networkx_alias_resolution.py` (new), `tests/unit/test_lightrag_formatter.py` (new)
  - Acceptance: Failing tests catch regressions for entity split and false unknowns.

### P1 (Retriever quality: intent routing + ranking)

- [ ] `P1-01` Add intent routing (`clinical_summary`, `timeline`, `graph_navigation`) before mode dispatch.
  - Component: Retriever/Gateway
  - Files: `src/services/api_gateway.py`, `src/services/cascading_retriever.py`, `src/integrations/lightrag_service.py`
  - Acceptance: Medical summary/timeline queries route to synthesis-friendly retrieval paths.

- [ ] `P1-02` Add graph expansion whitelist for clinical retrieval (`treats`, `side_effect`, `follow_up`, `prognosis`, `timeline`).
  - Component: Retriever
  - Files: `src/services/cascading_retriever.py`, `src/services/graph_query_service.py`
  - Acceptance: Structural edges (folder/tag inheritance) are down-weighted unless explicitly requested.

- [ ] `P1-03` Improve link resolution to reduce path/title ambiguity in graph queries.
  - Component: Graph Build
  - Files: `src/services/networkx_graph_builder.py`
  - Acceptance: Ambiguous wikilinks consistently resolve to intended note node.

- [ ] `P1-04` Unify relevance scaling/filter semantics across vector/notes/entities modes.
  - Component: Retriever/Scoring
  - Files: `src/services/embedding_service.py`, `src/services/api_gateway.py`, `src/services/graph_query_service.py`
  - Acceptance: Equivalent thresholds produce comparable filtering behavior across modes.

- [ ] `P1-05` Expand integration tests for routing and source composition in all modes.
  - Component: Tests
  - Files: `tests/integration/test_search_modes.py`
  - Acceptance: Tests assert mode routing and source construction for targeted clinical queries.

### P2 (Formatting consistency + evaluation gates)

- [ ] `P2-01` Standardize response schema: `Summary`, `Direct Connections`, `Indirect Connections`, `Supporting Notes`, `Unknowns / Gaps`, `References`.
  - Component: Response Formatter
  - Files: `src/integrations/lightrag_service.py`, `src/services/api_gateway.py`
  - Acceptance: Notes/entities/hybrid modes return consistent structured sections.

- [ ] `P2-02` Add claim-evidence mapping (`claim -> source file -> confidence`) in output payload.
  - Component: Response Formatter
  - Files: `src/integrations/lightrag_service.py`, `src/services/api_gateway.py`
  - Acceptance: Responses include machine-checkable provenance metadata.

- [ ] `P2-03` Extend parity/eval suite with lymphoma/Yescarta timeline and duplicate-entity cases.
  - Component: Evaluation
  - Files: `Scripts/debug/run_retrieval_eval.py`
  - Acceptance: Evaluation reports precision/depth/hallucination and duplicate-entity split metrics.

- [ ] `P2-04` Enforce audit acceptance thresholds and publish report.
  - Component: Evaluation
  - Files: `Scripts/debug/audit_search_modes.py`, `Documentation/SEARCH_MODE_AUDIT.md`
  - Acceptance: Automated pass/fail gates for source count, latency, and retrieval quality.

## Test Commands

Run from repository root.

### P0 validation

```bash
pytest tests/test_frontmatter.py
pytest tests/unit/test_lightrag_query_mode.py
pytest tests/unit/test_lightrag_phase2_safety.py
pytest tests/unit/test_lightrag_index_jobs.py
pytest tests/unit/test_indexing_canonicalization.py tests/unit/test_networkx_alias_resolution.py tests/unit/test_lightrag_formatter.py
```

### P1 validation

```bash
pytest tests/integration/test_search_modes.py -m integration
pytest tests/integration/test_search_modes.py -k "mode_aliases or entities_mode or hybrid_mode"
```

### P2 validation

```bash
python Scripts/debug/run_retrieval_eval.py
python Scripts/debug/audit_search_modes.py
```

## Release Gate (Recommended)

- [ ] All P0 tasks complete and tests passing.
- [ ] P1 intent routing and source quality tests passing.
- [ ] P2 parity/audit reports generated with no blocking regressions.
