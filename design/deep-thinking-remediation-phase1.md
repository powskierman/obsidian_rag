# Deep Thinking Remediation Phase 1

## Scope

This note covers the first remediation pass for the two highest-priority findings in the deep-thinking pipeline:

1. Finding #1: the orchestrator executes all remaining plan steps at once.
2. Finding #2: full-content expansion happens too early and too broadly.

The relevant live code is in `deep_thinking/orchestrator.py` and `deep_thinking/supervisor.py`.

## Current Behavior

### How the orchestrator executes plan steps today

`DeepThinkingRAG.query()` initializes state, builds the initial plan, and then enters the main loop in `deep_thinking/orchestrator.py`.

- `state["plan"]` is created once, then optionally prepended/appended with forced vault/web steps.
- Inside the execution loop, the orchestrator takes the entire remaining tail of the plan:
  - `steps_to_run = state["plan"][state["current_step_index"]:]`
- It defines `run_and_reflect(step)`, which does three things for a step:
  - `self.supervisor.execute_step(step, state, trace_callback=update_status)`
  - `self.reflector.reflect(step, docs, state)`
  - return `(step, docs, past_step)`
- It then runs every remaining step concurrently with:
  - `ThreadPoolExecutor(max_workers=len(steps_to_run))`
- Only after all futures complete does it commit results into shared state:
  - append docs into `state["retrieved_documents"]`
  - append truncated copies into `state["raw_context_buffer"]`
  - append `past_step` into `state["past_steps"]`
  - append findings into `state["accumulated_context"]`
  - increment `state["current_step_index"]` by `len(steps_to_run)`

Implications:

- Reflection is not actually incremental. Every `reflect()` call sees the same pre-commit `state["past_steps"]` snapshot because no step has been committed yet.
- Plan revision and policy checks only happen after the whole remaining tail finishes.
- Peak memory is the sum of all in-flight step payloads, not one step's payload.

### Where full-content expansion is triggered today

`RetrievalSupervisor.execute_step()` in `deep_thinking/supervisor.py` performs retrieval, optional reranking, and then expansion.

- Expansion is only considered for `vector` and `hybrid` steps.
- The trigger happens after reranking:
  - if `self.enable_reranking`, results are cut to `top_k=20`
  - if `self.full_content_expansion_bytes > 0`, `execute_step()` calls `_expand_full_content(results, trace)`
- `_expand_full_content()` iterates the full post-rerank result list and, for every eligible local file:
  - resolves a vault path from `OBSIDIAN_VAULT_PATH`
  - checks existence and size
  - reads up to the configured byte limit for text/code files
  - extracts up to 20 pages for PDFs
  - overwrites `doc["content"]` with the expanded text
  - sets `doc["is_full_content"] = True`

Implications:

- Expansion is eager: it happens during retrieval, before synthesis knows which documents it will actually use.
- Expansion is broad: every eligible result in the post-rerank list is considered.
- Expansion is repeated: the same file can be reopened and reread across multiple steps because there is no per-query cache keyed by file identity and freshness.

## Phase A: Orchestrator Serialization

### Goal

Execute one plan step at a time by default, or at most in small bounded groups where independence is explicit, while preserving existing plan/policy behavior and making reflection truly incremental.

### Proposed Changes

1. Replace tail-of-plan execution with a step window.

- Change the execution loop so it selects one step at `state["current_step_index"]` by default.
- Keep a narrow seam for bounded groups later, for example `next_steps = _select_step_batch(state)`.
- Initial implementation should return a single step to minimize behavioral risk.

2. Split "run step" from "commit step".

- Extract a helper that executes one step and returns `(step, docs, past_step)`.
- Extract a helper that commits one step's outputs into shared state:
  - `retrieved_documents`
  - `raw_context_buffer`
  - `past_steps`
  - `accumulated_context`
  - `current_step_index`
- Reuse the current buffer trimming and context compression logic inside the commit path so the state shape stays stable.

3. Commit state immediately after each step.

- Run `execute_step()`.
- Run `reflect()` using the current state.
- Commit that step's docs and findings before moving to the next step.
- This guarantees that the next step, any later `reflect()` call, `planner.extend_plan()`, and `policy.decide()` all see updated state.

4. Keep the existing outer loop and policy contract.

- Preserve:
  - forced vault/web step insertion
  - `max_iterations`
  - policy decisions `FINISH`, `REVISE_PLAN`, `CONTINUE`
  - fallback web retrieval paths
- The key change is sequencing, not planner semantics.

5. Add bounded-group execution only behind an explicit selector.

- If grouped execution is still desired, only batch steps that are explicitly marked independent.
- Commit results group-by-group, never for the entire remaining tail.
- Reflection should still run after each committed step, not only after the whole group.

### Expected Outcome

- Peak memory drops because only one step payload is live at a time by default.
- Reflection becomes real feedback instead of post-hoc summarization over stale state.
- Planner extension and policy decisions can react to intermediate findings.

### Validation for Phase A

- Add tests for a multi-step plan proving:
  - step 2 sees step 1 in `state["past_steps"]`
  - `current_step_index` advances one step at a time
  - `policy.decide()` is reached with committed intermediate state
- Add a regression test ensuring final output shape stays unchanged for a representative multi-step query.

## Phase B: Lazy Content Expansion and Per-Query Cache

### Goal

Stop expanding full content during every retrieval step. Keep retrieval results lightweight, expand only the small set of documents that synthesis will actually consume, and avoid rereading the same file within a query.

### Proposed Changes

1. Introduce a query-scoped expansion cache.

- Create a per-query cache object at the start of `DeepThinkingRAG.query()`.
- Pass it through to `RetrievalSupervisor.execute_step()` and `_expand_full_content()`.
- Key entries by a stable file freshness key:
  - preferred: `(full_path, mtime_ns)`
  - acceptable: `(full_path, mtime)`
- Cache value should contain expanded content and lightweight metadata such as size/ext.

2. Separate lightweight retrieval docs from expanded docs.

- Treat retrieval output as snippet-first documents.
- Preserve current fields like `filepath`, `source`, `filename`, `snippet`, `content`, and scores.
- Use `is_full_content` only as an annotation when expansion actually occurs.

3. Make expansion lazy.

- Remove unconditional full expansion from the normal `execute_step()` path for `vector` and `hybrid`.
- Introduce a helper that expands only selected docs on demand.
- First consumer should be synthesis, because that is where the final prompt budget is known.

4. Expand only a bounded synthesis set.

- Before prompt assembly, choose a small set of docs that synthesis will actually use.
- Expand only those docs, for example:
  - top-N ranked vault docs selected for the prompt
  - any explicitly promoted support docs if such a mechanism is added
- Keep final source rendering snippet-based unless a source explicitly needs expanded text.

5. Preserve ranking semantics.

- Expansion must not affect ranking, dedupe, or source selection order.
- Retrieval, hybrid merge, and reranking continue to work on lightweight docs.
- Expansion only changes content fidelity for a chosen subset.

6. Add caps and observability.

- Add config for:
  - max docs to expand per query
  - max total bytes/chars to expand per query
  - optional max docs to expand per synthesis call
- Trace:
  - cache hits/misses
  - docs expanded
  - docs skipped due to caps

### Recommended Rollout

Phase B should be delivered in two substeps:

1. Phase B1: add the per-query cache first, while keeping the current expansion trigger.
2. Phase B2: move expansion out of retrieval and into synthesis-time selection.

This keeps risk down:

- B1 removes repeated file reads without changing which docs become full-content.
- B2 changes when expansion happens, but only after the cache and instrumentation exist.

### Validation for Phase B

- Add tests proving repeated hits to the same file in one query reuse the cache.
- Add tests proving synthesis expands only the selected top-N docs.
- Add tests proving non-selected docs remain snippet-sized in state.
- Add a regression test for repeated vector/hybrid hits to the same file.

## Implementation Order

1. Phase A: serialize orchestrator execution and commit state after each step.
2. Phase B1: add per-query expansion cache with no behavioral change in selection.
3. Phase B2: move to lazy synthesis-driven expansion with bounded document selection.

## Approval Boundary

This document is planning only. No implementation code has been changed yet.

Before editing `deep_thinking/orchestrator.py`, `deep_thinking/supervisor.py`, or related runtime code, get explicit approval.
