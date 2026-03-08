# Cascading Remediation Task List

Status: proposed implementation plan as of March 7, 2026.

## Scope

This task list remediates the `cascading` path so it follows the same design direction as the recent deep-research fixes:

1. staged execution over uncontrolled fan-out
2. bounded and query-aware content expansion
3. authoritative evidence records instead of ad hoc source merging
4. final sources tied only to evidence actually used
5. stricter request-contract handling and provider behavior
6. lower CPU and string churn after correctness is restored

Primary code paths:

- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`

Reference implementations to reuse where possible:

- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/orchestrator.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/supervisor.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/synthesizer.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/source_utils.py`

## Confirmed Problems To Fix

- Valid anchor answers can be overwritten by generic synthesis fallback text.
- Final `sources` are assembled before synthesis and are not guaranteed to match evidence actually used.
- Duplicate vault notes can survive under different display names or collide by basename.
- `tag:` filters and some other request controls do not propagate into cascading retrieval.
- The decisive stage-3 vector pass drops `entities` and `mem0_context`.
- Single-note summary queries retrieve broad, noisy evidence sets.
- Stage failures are mostly silent.
- Existing tests do not protect these behaviors.

## Phase 0: Characterization and Guardrails

1. Add regression fixtures for current cascading failures.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/tests/integration/test_search_modes.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/test_payload_passing.py`
Deliverables:
- failing or characterization tests for:
  - exact-title single-note summary
  - duplicate canonical note rendered twice
  - irrelevant PDF contamination
  - `tag:` filter propagation
  - stage-3 `entities` and `mem0_context` propagation
  - unsupported-provider fallback preserving anchor answer
  - partial stage failure surfacing warnings/metadata
Acceptance:
- the Ahrens-style summary case proves exact-note preference is currently missing
- duplicate path and irrelevant-source regressions are reproducible in tests

2. Add unit tests for canonical source identity and source cleanup helpers.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/tests/unit/`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
Deliverables:
- targeted tests for path normalization, dedupe keys, snippet cleanup, and source ranking inputs
Acceptance:
- same-note/different-label cases collapse to one canonical identity

## Phase 1: Staged Execution and Bounded Concurrency

3. Refactor cascading into an explicit stage scheduler.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
Deliverables:
- replace unconditional three-way fan-out with explicit stages:
  - anchor retrieval
  - anchor evaluation
  - optional expansion
  - targeted vector retrieval
  - synthesis input packaging
- keep bounded concurrency only for clearly independent requests
Acceptance:
- summary queries do not call all backends by default
- metadata reports which stages ran and why

4. Add query-profile gates for summary and exact-note requests.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/supervisor.py`
Deliverables:
- summary-aware stage policy:
  - exact title/path hit short-circuits broad expansion
  - weak anchors allow controlled expansion
  - multi-document research queries still use full cascade
Acceptance:
- exact-note summary queries return 1-2 evidence items before synthesis

## Phase 2: Query-Aware Content Expansion and Snippet Hygiene

5. Normalize and clean snippets before any merge or synthesis.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/source_utils.py`
Deliverables:
- helper(s) to:
  - strip metadata-heavy prefixes
  - collapse whitespace
  - cap snippet length consistently
  - preserve meaningful vault text over source metadata blobs
Acceptance:
- source snippets for single-note summaries display note content, not raw metadata wrappers

6. Add per-request caching for cleaned source records and snippet transforms.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
Deliverables:
- lightweight cache keyed by normalized locator and snippet/source freshness where available
Acceptance:
- repeated source normalization within one cascade happens once per source

## Phase 3: Authoritative Evidence Schema and Deduplication

7. Introduce a canonical evidence record for cascading.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/source_utils.py`
Deliverables:
- one evidence shape used across retrieval and synthesis with fields like:
  - `source_category`
  - `filepath`
  - `canonical_id`
  - `filename`
  - `snippet`
  - `relevance`
  - `stage_origin`
Acceptance:
- anchor and vector evidence can be merged without lossy field translation

8. Replace filename-based dedupe with canonical source identity.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/source_utils.py`
Deliverables:
- dedupe and snippet substitution keyed by normalized vault path or canonical URL, never basename alone
Acceptance:
- the same vault note cannot appear twice under different labels
- different notes with the same basename remain distinct

## Phase 4: Source Pipeline and Evidence-Aligned Synthesis

9. Replace pre-synthesis source assembly with evidence-selected synthesis.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/synthesizer.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/supervisor.py`
Deliverables:
- cascading synthesis consumes a selected evidence set, not raw merged source lists
- synthesis returns structured output:
  - `answer`
  - `citations`
  - `used_documents`
Acceptance:
- final `sources` equal the evidence actually used to generate the answer

10. Preserve valid anchor answers when synthesis degrades.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/synthesizer.py`
Deliverables:
- fallback policy that keeps the anchor answer when synthesis returns:
  - empty text
  - unsupported-provider fallback text
  - missing-key/config fallback text
- warnings recorded in response metadata
Acceptance:
- cascading never replaces a useful anchor answer with `Found N matching snippets...`

11. Reuse deep-research evidence selection for summary requests.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/supervisor.py`
Deliverables:
- summary queries prefer:
  - dominant exact note match
  - at most a very small supporting evidence set
  - no unrelated PDFs/notes unless they materially support the answer
Acceptance:
- the Ahrens query resolves to the Ahrens note as the dominant evidence item

## Phase 5: Strict Request Contract and Provider Unification

12. Thread the full request contract through every cascading stage.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
Deliverables:
- propagate:
  - `filters`
  - `relevance_threshold`
  - `entities`
  - `mem0_context`
  - `entities_mode`
  - `require_llm`
- stage-3 vector pass receives the same context envelope as stage-1 fallback vector
Acceptance:
- `tag:` filters affect cascading retrieval results end-to-end

13. Unify provider handling with the deep-research client stack.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py`
Deliverables:
- replace `_synthesize_cascading_answer()` provider matrix with shared provider resolution and response extraction
- consistent error taxonomy and fallback behavior across cascading and deep research
Acceptance:
- provider support and error handling no longer differ materially by mode

14. Unify relevance normalization across vector and cascading modes.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
Deliverables:
- one distance-to-relevance mapping shared across modes
Acceptance:
- the same vector backend score ranks consistently in `vector` and `cascading`

15. Surface degraded-mode metadata instead of failing silently.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
Deliverables:
- response metadata includes:
  - stage success/failure
  - chosen vector query
  - thresholds attempted
  - synthesis fallback reason
  - answer evidence mode: anchor-only, vector-only, mixed
Acceptance:
- partial service failure is visible in the response and testable

## Phase 6: Churn Reduction and Cleanup

16. Remove repeated source rescans and repeated string assembly.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/cascading_retriever.py`
Deliverables:
- precompute canonical keys, cleaned snippets, and relevance-normalized records once
- use list-then-join prompt/context assembly
Acceptance:
- no repeated full rescans of the same merged source collection in one request

17. Remove gateway-only heuristic source surgery where shared utilities exist.
Files:
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py`
- `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/source_utils.py`
Deliverables:
- move normalization and identity logic into shared helpers
- reduce mode-specific duplication between cascading and deep research
Acceptance:
- gateway code no longer performs basename-driven source repair/dedupe

## Test Matrix

Required regression cases:

1. Exact-note summary query returns one dominant vault note.
2. Same canonical note cannot appear twice with different display names.
3. Two different files with the same basename remain distinct.
4. Irrelevant PDFs are excluded from single-note summaries.
5. `tag:` filters propagate through cascading retrieval.
6. Stage-3 vector requests preserve `entities` and `mem0_context`.
7. Unsupported provider fallback preserves a valid anchor answer.
8. Final `sources` equal `used_documents`.
9. Partial backend failure is reflected in metadata.
10. Relevance thresholds behave the same between `vector` and `cascading`.

## Suggested Delivery Order

1. Phase 0 tests
2. Phase 1 stage scheduler
3. Phase 3 canonical evidence identity
4. Phase 4 evidence-aligned source pipeline
5. Phase 5 request contract and provider unification
6. Phase 2 snippet hygiene and summary focus refinements
7. Phase 6 cleanup and churn reduction

This order keeps correctness and provenance ahead of optimization.

## Definition of Done

1. Single-note summary queries resolve to the correct dominant note with a minimal evidence set.
2. Final `sources` are canonical, deduplicated, and exactly aligned to evidence used in the answer.
3. Cascading honors request controls end-to-end, including `tag:` filters and relevance thresholds.
4. Provider behavior and fallback handling are consistent with deep research.
5. Stage failures are visible and do not silently degrade into misleading results.
6. Gateway-side heuristic source surgery is removed or reduced to shared canonical helpers.
