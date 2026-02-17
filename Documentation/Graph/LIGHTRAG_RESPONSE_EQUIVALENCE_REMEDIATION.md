# LightRAG Response Equivalence Remediation

## Goal
- Make `entities`/LightRAG responses consistently match the practical value of `notes`/networkx responses:
- In-depth synthesis grounded in vault structure.
- High-relevance, non-hallucinated note references.
- Clickable bottom references with stable filenames/filepaths.

## What NetworkX Is Doing Differently
- It builds an explicit candidate source set from graph context nodes before synthesis.
- It ranks sources with query-term matching and dynamic relevance scoring, then trims to a quality cap.
- It merges graph evidence with vector evidence in hybrid mode (with relevance thresholds and quality gates).
- It runs a dedicated synthesis prompt that explicitly asks for grounded, source-aware answers.
- It returns structured `sources` objects (`filename`, `filepath`, `relevance`, `snippet`) that the UI renders cleanly.

## Why LightRAG Feels Weaker Today
- LightRAG endpoint currently returns mostly free-form text; source/citation objects are sparse or absent.
- LLM output can invent note labels (for example generic titles) when citation grounding is weak.
- Automation/meta notes still leak into retrieval in some cases and can dominate results.
- “Not found” and partial-evidence handling is inconsistent across query types.
- Fallback extractive scoring is chunk-oriented, so answer quality can degrade to fragment lists.

## Remediation Actions (Priority Order)

### P0: Stop hallucinated citations and stabilize outputs
- Enforce a hard citation-grounding gate:
- If claimed note titles are not in retrieved candidate sources, reject LLM answer and return grounded extractive result.
- Keep a canonical `References:` block appended at the end of all non-local LightRAG answers.
- Strip free-form `Notes used:`/`Context used:` text in model output and replace with canonical references.
- Files:
- `src/integrations/lightrag_service.py`
- Acceptance:
- No invented note titles in answers.
- Every LightRAG answer includes `References:` with real note titles.

### P1: Increase retrieval quality parity with networkx
- Add two-stage retrieval before LLM synthesis:
- Stage A: LightRAG semantic retrieval.
- Stage B: local lexical re-ranker over candidate chunks/notes using query coverage and title/path boosts.
- Apply domain noise suppression:
- Down-rank or exclude automation/meta notes unless query explicitly targets automation.
- Add minimum multi-term coverage for multi-concept queries (for example `baking` + `pizza`).
- Files:
- `src/integrations/lightrag_service.py`
- Acceptance:
- `baking and pizza` returns cooking-related notes only (no openclaw/meta artifacts).
- Top 5 references contain at least 80% topic-relevant notes in regression set.

### P2: Add structured sources from LightRAG raw data (networkx-style output contract)
- Switch LightRAG query path from plain `aquery(...)` to structured mode (`aquery_llm(...)` / `raw_data`) and map:
- chunks -> `filename`, `filepath`, `snippet`
- retrieval score/weight -> `relevance`
- Return `sources` list directly from `/query` response, not inferred from generated prose.
- Update gateway mapping to preserve those structured sources through `entities` mode.
- Files:
- `src/integrations/lightrag_service.py`
- `src/services/api_gateway.py`
- Acceptance:
- `entities` mode returns a populated `sources[]` list for normal queries.
- UI shows clickable references without relying on answer text parsing.

### P3: Match networkx synthesis depth
- Replace current generic LightRAG synthesis prompt with a networkx-equivalent synthesis contract:
- Summarize direct and indirect connections.
- Include confidence qualifiers tied to source evidence.
- Explicitly separate observed facts vs unknowns.
- Disallow boilerplate/medical generic filler unless present in retrieved notes.
- Optional:
- Add second-pass synthesis over top-k grounded sources when primary answer is shallow.
- Files:
- `src/integrations/lightrag_service.py`
- Acceptance:
- Lymphoma/Yescarta queries produce multi-section answers (direct links, indirect links, supporting notes, caveats).

### P4: Add parity evaluation harness (must-have for non-regression)
- Build a fixed query benchmark comparing `notes` vs `entities`:
- Clinical: `lymphoma and yescarta`, `yescarta and side-effects`
- Cooking: `baking and pizza`
- Technical: at least 3 non-medical, non-cooking cross-topic queries
- Score dimensions:
- Reference precision (real titles, relevance).
- Answer depth (section completeness rubric).
- Hallucination rate (invented notes or unsupported claims).
- Latency percentile targets.
- Files:
- `Scripts/debug/run_retrieval_eval.py`
- `tests/integration/test_search_modes.py`
- Acceptance:
- LightRAG reaches agreed minimum parity thresholds for precision/depth before rollout.

## Implementation Notes (Code-Level)
- NetworkX source scoring and synthesis baseline:
- `src/services/graph_query_service.py` around query handling/source assembly/synthesis.
- LightRAG service query/fallback/citation logic:
- `src/integrations/lightrag_service.py`
- Gateway entities mode extraction/mapping:
- `src/services/api_gateway.py`

## Rollout Plan
- Phase 1:
- Ship P0 + P1 behind env flags (`LIGHTRAG_STRICT_GROUNDING`, `LIGHTRAG_NOISE_FILTER`, `LIGHTRAG_RERANK`).
- Phase 2:
- Implement P2 structured sources; update UI to prefer explicit `sources[]`.
- Phase 3:
- Implement P3 enhanced synthesis prompt; evaluate with P4 harness.

## Success Criteria
- LightRAG `entities` responses include:
- A substantive multi-point answer.
- A bottom `References:` section with clickable, real notes.
- No invented note names or generic placeholder citations.
- On benchmark queries, LightRAG reference precision and answer depth are within defined parity band of networkx.
