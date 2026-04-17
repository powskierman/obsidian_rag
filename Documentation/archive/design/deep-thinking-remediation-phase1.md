# Deep Thinking Remediation Phase 1

Status: implemented and partially extended beyond the original phase-1 scope as of March 7, 2026.

## Scope

This note originally covered the first remediation pass for the two highest-priority findings in the deep-thinking pipeline:

1. Finding #1: the orchestrator executes all remaining plan steps at once.
2. Finding #2: full-content expansion happens too early and too broadly.

The relevant live code is in `deep_thinking/orchestrator.py`, `deep_thinking/supervisor.py`, `deep_thinking/synthesizer.py`, `deep_thinking/planner.py`, and `deep_thinking/policy.py`.

## Pre-Remediation Behavior

### How the orchestrator executed plan steps before remediation

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

### Where full-content expansion was triggered before lazy selection

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

## Implemented Status

### Orchestrator serialization is now the default

- The serialized scheduler is now the default runtime path.
- State is committed after each step, so reflection, policy, and replanning see the latest `past_steps`, `retrieved_documents`, and accumulated context.
- The legacy fan-out path remains available only as an explicit fallback path.

### Evidence selection is now authoritative and bounded

- Prompt construction, citation normalization, and final source rendering all use the same authoritative citable evidence set.
- Post-synthesis source mutation was removed, so final sources are no longer backfilled with unseen web documents.
- Text-only graph outputs are preserved as internal reasoning evidence, but they are excluded from final citations.

### Summary-query handling was tightened after phase 1

- Summary-style queries now use a vault-first fast path with a single-step plan unless the user explicitly asks for outside context.
- Prompt-template and instruction notes are filtered out of normal evidence ranking.
- Summary queries prefer an exact vault-note match plus at most a very small supporting set, rather than broad mixed web retrieval.

### Synthesis failure handling is now explicit

- If the model returns an empty answer, synthesis retries once with a reduced authoritative evidence set.
- Fallback responses now record and surface the failure reason, including `empty_answer`, `json_parse_failure`, `timeout`, and `provider_exception`.
- Retrieved-context fallback remains available, but it is no longer silent about why it happened.

## Expected Outcome

- Peak memory drops because only one step payload is live at a time by default.
- Reflection becomes real feedback instead of post-hoc summarization over stale state.
- Planner extension and policy decisions can react to intermediate findings.
- Summary queries stay focused on vault evidence and avoid unnecessary web expansion.
- Source lists now better match the evidence the model actually saw.

## Validation

- Regression coverage includes multi-step plan tests proving:
  - step 2 sees step 1 in `state["past_steps"]`
  - `current_step_index` advances one step at a time
  - `policy.decide()` is reached with committed intermediate state
- Regression tests preserve final output shape for representative multi-step queries.
- Regression coverage for summary queries proves:
  - a dominant vault note is preferred
  - prompt-template notes are excluded
  - web enrichment is skipped by default
  - empty-answer retries reduce the evidence set
  - failure-mode fallbacks are surfaced explicitly
