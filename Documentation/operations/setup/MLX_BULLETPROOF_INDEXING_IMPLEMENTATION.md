# MLX Bulletproof LightRAG Indexing Implementation

## Document Status
- Date: 2026-02-08
- Owner: Obsidian RAG maintainers
- Scope: Make MLX-backed LightRAG indexing reliable for large vault runs.

## 1. Objective
Guarantee that MLX indexing is operationally safe for full-vault ingestion:
- No unbounded hangs.
- No request-level dead ends that leave documents in permanent `processing`.
- No silent "indexed" outcomes with missing relations due to failed extraction.
- Deterministic restart and recovery after crash/redeploy.

## 2. Current Failure Modes (Observed)
1. Indexing requests can stall at batch 1 on large markdown notes.
2. `/index-vault` HTTP request may time out while worker remains partially active.
3. Document status can remain `processing` without terminal transition.
4. Extraction quality can degrade (format errors), causing weak or partial graph output.
5. "Success" accounting can drift from true extraction completion.

## 3. Reliability Requirements
R1. Every indexing attempt must end in terminal state per document: `processed` or `failed`.
R2. Every document must have a bounded wall-clock budget.
R3. Any stalled worker must be detected and terminated automatically.
R4. A note is only marked indexed after extraction + storage callbacks succeed.
R5. Failed documents are retryable without full reindex.
R6. All state transitions are crash-safe and restart-safe.

## 4. Architecture Changes

### 4.1 Decouple Request From Long-Running Work
Replace synchronous `/index-vault` semantics with job-based execution:
- `POST /index-vault`:
  - Validates payload.
  - Creates `job_id`.
  - Returns `202 Accepted` with `job_id`.
- New endpoint `GET /index-jobs/<job_id>`:
  - Returns job state (`queued`, `running`, `completed`, `failed`, `cancelled`).
  - Includes per-file counts and current file.
- New endpoint `POST /index-jobs/<job_id>/cancel`.

Reason:
- Eliminates client timeout as control-plane failure.
- Makes progress queryable and resumable.

### 4.2 Per-Document Execution Envelope
For each document:
- Start timer.
- Process extraction in an isolated subprocess (not in-process coroutine only).
- Enforce hard timeout (`LIGHTRAG_DOC_TIMEOUT`).
- On timeout:
  - kill subprocess,
  - mark doc `failed`,
  - store reason `timeout`,
  - continue next doc.

Reason:
- Prevents one stuck extraction from blocking whole job.

### 4.3 Heartbeat Watchdog
During doc processing:
- Write heartbeat timestamp every N seconds.
- Background watchdog scans active docs.
- If no heartbeat beyond threshold:
  - terminate worker,
  - mark doc failed with `stalled_worker`.

Reason:
- Covers deadlocks and silent stalls not handled by regular timeout path.

### 4.4 Transactional State and Checkpointing
Add append-only progress journal per job:
- `job_manifest.json`: input set, config hash, creation time.
- `job_progress.jsonl`: one event per state transition.
- `job_snapshot.json`: compact latest view.

Rules:
- Update `doc_status` before and after each terminal transition.
- Write `indexed_files.txt` atomically and only from terminal-success docs.
- Never bulk-overwrite state from potentially partial in-memory counters.

### 4.5 Strong Success Gating
A document is `processed` only if all conditions hold:
1. Full-doc entry persisted.
2. Chunk entries persisted.
3. Entity/relation extraction callback completed.
4. No fatal extraction parser error.

If extraction yields zero relations:
- Keep as `processed_with_warnings` metadata OR retry with fallback strategy.
- Do not count as relation-complete success unless policy allows.

Policy flags:
- `LIGHTRAG_REQUIRE_RELATIONS=1` (strict mode).
- `LIGHTRAG_MIN_RELATIONS_PER_DOC` (default `1`).

### 4.6 MLX-Specific Safety Profile
Use MLX-safe defaults for indexing:
- `LIGHTRAG_BATCH_SIZE=1`
- `LLM_ASYNC=1`
- `EMBED_ASYNC=1`
- `LIGHTRAG_CHUNK_TOKENS=96` (or 128 max)
- `LIGHTRAG_CHUNK_OVERLAP=24`
- `LIGHTRAG_MAX_DOC_CHARS` bounded for first pass.

Adaptive behavior:
- If chunk extraction p95 latency exceeds threshold, auto-reduce chunk size.
- For very large docs, pre-split to sections (headings/page blocks) before extraction.

### 4.7 Recovery on Startup
At service start:
1. Find docs in `processing` older than stale threshold.
2. Convert them to `failed` with reason `recovered_from_stale`.
3. Add to retry queue for next run.

Reason:
- Prevents permanent limbo after crash/restart.

## 5. Extraction Quality Hardening

### 5.1 Parser-Robust Extraction Pipeline
When LLM output is malformed:
1. Retry with strict JSON-only prompt.
2. Retry with lower temperature and smaller chunk.
3. If still invalid, mark doc failed (not processed).

### 5.2 Relation Completeness Guard
Track per-doc metrics:
- `entities_extracted`
- `relations_extracted`
- `chunks_processed`
- `chunks_failed`

Fail doc when:
- relation count is below threshold and strict mode is enabled,
- or extraction error ratio exceeds threshold.

## 6. Concrete Code Changes

### 6.1 `src/integrations/lightrag_service.py`
- Add job model and job registry.
- Convert `/index-vault` to enqueue job and return `job_id`.
- Add `/index-jobs/<job_id>`, cancel endpoint.
- Implement per-doc worker with hard timeout + heartbeat.
- Write atomic index state updates.
- Add strict success gating and relation thresholds.

### 6.2 New module: `src/indexing/lightrag_index_worker.py`
- Isolated doc processor entrypoint.
- Handles one doc at a time.
- Returns structured result payload.

### 6.3 New module: `src/indexing/lightrag_job_store.py`
- JSONL journal utilities.
- Atomic snapshot writes.
- Recovery scan utilities.

### 6.4 `Scripts/indexing/reindex_remaining_md_only.sh`
- Switch to job API:
  - submit job,
  - poll job state,
  - retry only failed docs.

### 6.5 `Scripts/indexing/list_remaining_missing_files.sh`
- Distinguish:
  - not submitted,
  - failed,
  - processed_without_relations,
  - processed_relation_complete.

## 7. Testing Strategy

### 7.1 Unit Tests
- State transitions:
  - `queued -> running -> processed/failed`.
- Timeout path marks failed and continues.
- Atomic write helpers.
- Recovery logic for stale `processing`.

### 7.2 Integration Tests
- Simulated hung LLM endpoint (sleep/no response).
- Simulated malformed extraction output.
- Crash mid-job then restart and resume.
- Full 5-file and 50-file runs with deterministic expected counts.

### 7.3 Chaos Tests
- Kill LightRAG container during run.
- Restart and verify no doc remains permanently `processing`.
- Ensure rerun indexes only unfinished docs.

## 8. Operational Runbook

### 8.1 Default Production Env (MLX)
- `LLM_PROVIDER=mlx`
- `LIGHTRAG_BATCH_SIZE=1`
- `LLM_ASYNC=1`
- `EMBED_ASYNC=1`
- `LIGHTRAG_DOC_TIMEOUT=180`
- `LIGHTRAG_DOC_RETRY_ATTEMPTS=2`
- `LIGHTRAG_REQUIRE_RELATIONS=1`
- `LIGHTRAG_MIN_RELATIONS_PER_DOC=1`
- `LIGHTRAG_STALE_PROCESSING_SECONDS=300`

### 8.2 SLO Alerts
Alert if:
- any doc in `processing` older than 5 minutes,
- job has no heartbeat for 60 seconds,
- failed ratio > 5% in rolling 100 docs.

## 9. Rollout Plan

Phase 1: Foundations
- Add job API + journaling + recovery.
- Keep old endpoint behavior behind compatibility flag.

Phase 2: Safety
- Add per-doc subprocess timeout + watchdog.
- Add strict success gating.

Phase 3: Quality
- Add malformed-output fallback retries.
- Add relation completeness policy.

Phase 4: Migration
- Update scripts to job API.
- Run staged reindex on 5, view the results and optimize model parameters for speed and accuracy.
- Run this test with Mistral-22B then with qwen2.5:14b Provide complete benchmark results including speed and accuracy

## 10. Acceptance Criteria
A run is accepted only if:
1. No document remains in `processing` longer than stale threshold.
2. Every submitted document reaches terminal status.
3. Index jobs survive restart without duplication/corruption.
4. `indexed_files.txt` count matches successful terminal docs.
5. In strict mode, no processed doc has zero relations.
6. 511-file remaining run completes without manual intervention loops.

## 11. Immediate Next Implementation Steps
1. Implement job API and persistent job store.
2. Implement per-doc subprocess timeout + heartbeat.
3. Implement strict relation-gated success accounting.
4. Update reindex scripts to poll jobs and retry failed docs only.
5. Run validation ladder: 5 docs -> 50 docs -> remaining docs.

