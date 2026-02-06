# Obsidian RAG Implementation Document

**Date:** 2026-01-29  
**Objective:** Extend Obsidian with reliable retrieval + synthesis across multiple related notes, producing accurate, note-grounded answers with sources.

## 1) Current State (Observed)
**Retrieval**
- Vector retrieval is fast and returns relevant note titles.
- LightRAG local/hybrid sometimes returns generic answers or “Not found” even when notes exist.
- Hybrid queries can be slow or time out under LLM load.

**Synthesis**
- LLM responses can be generic and not grounded in notes.
- When LLM is used, it does not consistently cite or reflect the retrieved context.

**Indexing**
- LightRAG graph has very low node/edge counts compared to vault size (e.g., 20 nodes/20 edges vs. 2k+ notes).
- This indicates entity extraction or graph-building is not operating end‑to‑end.
**NetworkX Graph (Reasoning Graph Service)**
- NetworkX graph service can load large graphs (nodes/edges) but is currently not consistently used for synthesis.
- Query paths often bypass NetworkX for LLM synthesis, resulting in weaker graph‑based reasoning.

**Ops/Runtime**
- Lightrag service now uses gunicorn; init happens lazily at runtime.
- Query timeout behavior is now configurable but was previously not wired into the container environment.

## 2) Root Causes (Most Likely)
1. **LLM not consistently used or times out**  
   Hybrid queries fall back or return “not found” when the LLM stalls or fails.
2. **Weak grounding controls**  
   The LLM can answer without strong note context; no strict “notes-only” gating.
3. **Entity extraction/graph build incomplete**  
   Low graph sizes point to extraction failures, model misconfiguration, or timeouts during indexing.
4. **Inconsistent retrieval → synthesis handoff**  
   Retrieved chunks are not guaranteed to be injected into the final synthesis prompt with citations.
5. **NetworkX not contributing to synthesis**  
   Graph data exists but is not consistently fused into the final answer pipeline.

## 3) Target Behavior
1. **Notes-only synthesis** by default for Obsidian queries.  
2. **Consistent citations** that tie claims back to note titles/chunks.  
3. **Fast local/hybrid retrieval** with bounded latency.  
4. **Complete graph extraction** or explicit disablement if not viable.  

## 4) Implementation Plan

### Phase A — Retrieval & Grounding (Highest impact)
**Goal:** Ensure answers are grounded in notes.

1) **Notes-only guardrail**
   - Require ≥N relevant chunks (configurable) or return “Not found in notes.”
   - Add `notes_only=true` behavior for hybrid/local modes.

2) **Explicit citation enforcement**
   - Inject retrieved chunks with short source labels: `[[Note Title]]`.
   - Post-process LLM output to include citations (or reject if missing).

3) **Reranker (optional)**
   - Enable rerank model when available; otherwise ensure deterministic top‑k by score.

**Verification**
- Query set: `1st pet scan`, `Yescarta`, `Initial Diagnosis Scan`, `Home Assistant`.
- Expected: Answers mention correct note titles and only include facts present in notes.

### Phase A2 — Data Extraction & Indexing Review (New)
**Goal:** Ensure extraction produces complete, high-quality chunks and metadata.

1) **Vault ingest correctness**
   - Verify `OBSIDIAN_VAULT_PATH` is correct and not stale.
   - Confirm file filters (md/pdf) and attachment limits match expected coverage.
   - Ensure iCloud sync state is stable during indexing.

2) **Chunking quality**
   - Check max chunk size vs. embedding model context limits.
   - Validate chunks include title/filename/heading metadata.
   - Reject empty/near-empty chunks to prevent noisy vectors.

3) **Extraction pipeline integrity**
   - Audit extraction logs for:
     - “Complete delimiter not found”
     - “input length exceeds context length”
     - repeated “unknown_source”
   - Track per‑file extraction success/failure rates.

4) **Index state correctness**
   - Ensure index history resets when vault path changes.
   - Verify cache invalidation is based on hashes + mtime.

**Recommendations**
- Add an extraction report after indexing:
  - notes processed, chunks created, entities/relations extracted, failures.
- Enforce chunk length caps before embedding (split long blocks).
- Drop or truncate oversized PDFs to avoid embedding errors.
- Add a “reindex mode” that ignores cache when requested.

**Verification**
- Run a small sample vault and confirm:
  - No “context length” embedding errors.
  - Chunk counts align with note sizes.
  - “unknown_source” is near zero.

### Phase B — Graph / LightRAG indexing correctness
**Goal:** Ensure graph/relations are real or disable if broken.

1) **Rebuild LightRAG graph with stable LLM**
   - Use a local model configured with adequate context length.
   - Confirm entity extraction succeeds (node/edge counts increase beyond a trivial size).

2) **Indexing diagnostics**
   - Log counts of extracted entities/relations per document batch.
   - Emit a summary after indexing (notes processed, entities/relations, failures).

**Verification**
- Stats endpoint should show non-trivial graph size.
- Query mode `local/hybrid` should return actual note‑specific results.

### Phase B2 — NetworkX graph integration
**Goal:** Use NetworkX for higher‑order relationship discovery and synthesis.

1) **Validate graph freshness**
   - Verify `GRAPH_PATH` points to the latest graph snapshot.
   - Confirm node/edge counts align with vault size.

2) **Integrate NetworkX context into synthesis**
   - For hybrid queries, append relevant graph subgraph summaries to the LLM prompt.
   - Include edge‑based citations: `[[Note A]] ↔ [[Note B]] (relationship)`.

3) **Graph-based reranking**
   - Use graph proximity (e.g., shortest path) to re-rank chunks for synthesis.

**Verification**
- Graph queries return connected note clusters for topic queries.
- Hybrid answers include explicit cross‑note links (not just vector neighbors).

### Phase C — Performance & Timeouts
**Goal:** Prevent user-visible stalls.

1) **Time‑boxed LLM usage**
   - Keep `RAG_QUERY_TIMEOUT` at 20–30s for full synthesis.
   - For interactive UI, provide “fast” mode with shorter timeouts.

2) **Warmup**
   - Optional background warmup call to the LLM after service start.

3) **Cache policy**
   - Avoid caching responses that are “Not found” unless explicitly requested.

**Verification**
- Re-run smoke tests with timeouts.
- Ensure query endpoints respond within the configured window.

## 5) Concrete File-Level Changes (Proposed)
**Services**
- `src/integrations/lightrag_service.py`
  - Add `notes_only` guardrail and citation enforcement.
  - Log retrieved chunks in debug mode.
  - Optional `min_chunks` config for hybrid/local.

**Config**
- `.env`
  - `RAG_QUERY_TIMEOUT=30`
  - `RAG_NOTES_ONLY=true`
  - `RAG_MIN_CHUNKS=2`

**Docs**
- Update runbooks: `Documentation/SOTA_TUNING_GUIDE.md` and `Documentation/Setup/TESTING.md`

## 6) Acceptance Criteria
1. **Grounded answers**: At least 4/5 test queries cite correct note titles.
2. **No generic answers**: If insufficient evidence, returns “Not found in notes.”
3. **Latency**: Local/hybrid < 10s for typical queries.
4. **Graph health**: Node/edge counts > 1k (or graph explicitly disabled).
5. **NetworkX integration**: Hybrid answers include at least 2 graph‑derived cross‑note links when available.

## 7) Risks / Mitigations
- **LLM slow / timeouts** → introduce fast mode + strict fallback.
- **Graph extraction cost** → allow opt‑out or periodic batch rebuild.
- **Over‑strict notes‑only** → add “allow_general_knowledge” toggle for research mode.

## 8) Next Steps (Immediate)
1. Add `notes_only` + `min_chunks` enforcement to LightRAG.
2. Rebuild indexing to ensure non‑trivial graph.
3. Run structured retrieval eval and document results.
