# LightRAG Full Remediation Execution Checklist

Owner: Codex
Status: In Progress
Execution order: P0 -> P1 -> P2
Rule: Do not start next phase until current phase tests pass.

## Baseline context
- Scope files:
  - `src/integrations/lightrag_service.py`
  - `src/services/api_gateway.py`
  - `tests/unit/test_lightrag_query_mode.py`
  - `tests/integration/test_search_modes.py`
- Goal: improve LightRAG precision, grounding, and performance parity for medical timeline/history queries.

## P0 - Routing and retrieval hygiene (critical)
- [x] Wire request-level query controls through LightRAG endpoint (`llm_provider`, `model`, `temperature`, `system_prompt`, `filters`, `max_results`, `force_mode`).
- [x] Stop hardcoding entities mode to LightRAG `hybrid`; allow explicit mode pass-through.
- [x] Add retrieval-query sanitizer to strip instruction boilerplate (`Requirements`, `Output format`, `Citation rule`) before ranking.
- [x] Gate fallback-source merging so extractive fallback is appended only when primary evidence is weak/empty.
- [x] Ensure `tag:` filters are propagated from gateway to LightRAG and applied to source candidates.

### P0 tests
- [x] `./venv/bin/python -m pytest -o addopts='' tests/unit/test_lightrag_query_mode.py`
- [x] `./venv/bin/python -m pytest -o addopts='' tests/integration/test_search_modes.py`
- [ ] Manual check: entities query with long instruction prompt returns medical sources first and no RAG/meta drift in top references.

## P1 - Answer quality and grounding
- [x] Refine mode heuristic to operate on sanitized retrieval query only.
- [x] Add env-gated rerank toggle for LightRAG query params (`enable_rerank`).
- [x] Strengthen citation grounding: every claimed note citation must map to retrieved sources (not just any overlap).
- [x] Allow section-contract override from request (timeline/conflicts/questions sections when explicitly requested).
- [x] Add medical scope bias defaults for oncology terms (prefer `Medical/Lymphoma/` unless user overrides).

### P1 tests
- [x] `./venv/bin/python -m pytest -o addopts='' tests/unit/test_lightrag_query_mode.py`
- [x] `./venv/bin/python -m pytest -o addopts='' tests/integration/test_search_modes.py`
- [x] Add and run new unit tests for citation-grounding and prompt-section override behavior.
- [ ] Manual check: lymphoma history prompt produces timeline/conflicts/unknowns with grounded references.

## P2 - Performance and scaling
- [x] Avoid repeated full extractive scans in one query path (single-pass staged thresholds).
- [x] Build lightweight lexical inverted index cache for extractive fallback.
- [x] Pass and honor `max_results` end-to-end for entities mode.
- [x] Add telemetry for fallback reason and extractive scan counts.

### P2 tests
- [x] `./venv/bin/python -m pytest -o addopts='' tests/unit/test_lightrag_query_mode.py`
- [x] `./venv/bin/python -m pytest -o addopts='' tests/integration/test_search_modes.py`
- [x] Add and run performance-focused unit tests for single-pass scan and index cache hits.
- [ ] Manual latency comparison before/after on representative entities prompts (blocked: gateway not reachable in current run; parity script returned `ERR` rows with `RETRIEVAL_EVAL_TIMEOUT=5`).

## Execution log
- [x] P0 implementation complete
- [x] P0 tests pass
- [x] P1 implementation complete
- [x] P1 tests pass
- [x] P2 implementation complete
- [x] P2 tests pass

## Sign-off criteria
- [ ] Entities mode no longer drifts to meta/RAG notes for medical-history prompts.
- [ ] Output references are fully grounded and stable.
- [ ] Latency and source precision improve without regressions in notes/hybrid modes.
