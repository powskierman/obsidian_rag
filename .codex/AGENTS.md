# Codex Agents for Deep-Thinking Algorithm Remediation

This project uses multiple Codex agents, each aligned with a specific finding from the ChatGPT 5.4 review of the deep-thinking algorithm. The goal is to gradually reshape the pipeline while preserving behavior and improving memory/CPU usage.

## Coordinator

**Agent name:** `coordinator`  
**Config:** `agents/coordinator.toml`  

**Purpose**  
- Orchestrates all remediation work across specialist agents.  
- Enforces the recommended fix order:
  1. Orchestrator serialization / bounded concurrency
  2. Content expansion / caching
  3. State deduplication
  4. Source pipeline
  5. Planner format strictness
  6. Churn reduction

**Typical prompts**  
- “Plan a phased refactor of the deep-thinking pipeline using all specialists.”  
- “Integrate the latest proposals from `orchestrator_serializer` and `content_limiter` into a coherent patch plan.”  

---

## Orchestrator Serializer (Finding #1)

**Agent name:** `orchestrator_serializer`  
**Config:** `agents/orchestrator_serializer.toml`  

**Finding focus**  
- Orchestrator executes all remaining plan steps concurrently, inflating peak RAM and blocking true incremental reflection.  

**Responsibilities**  
- Turn the orchestrator into a mostly sequential or bounded-concurrency scheduler.  
- Ensure `reflect()` and similar loops see updated state between steps.  
- Define safe patterns for explicitly independent step groups.

**Typical prompts**  
- “Redesign the orchestration loop to run one step at a time with optional bounded parallelism for independent groups.”  
- “Show how to wire reflection so that later steps can be pruned based on updated `past_steps`.”  

---

## Content Limiter (Finding #2)

**Agent name:** `content_limiter`  
**Config:** `agents/content_limiter.toml`  

**Finding focus**  
- Full-content expansion is applied too early and too broadly; no caching; state bloated by full documents.  

**Responsibilities**  
- Introduce lazy expansion of document content.  
- Implement per-query caching keyed by something like `(filepath, mtime)`.  
- Ensure only a small, bounded subset of docs is fully expanded, ideally those used in synthesis.

**Typical prompts**  
- “Refactor `execute_step()` and `_expand_full_content()` to use lightweight handles plus lazy expansion.”  
- “Design a per-query expansion cache and describe how it interacts with the synthesizer and source builder.”  

---

## State Deduper (Finding #3)

**Agent name:** `state_deduper`  
**Config:** `agents/state_deduper.toml`  

**Finding focus**  
- Evidence is duplicated across `past_steps`, `accumulated_context`, `retrieved_documents`, and `raw_context_buffer`.  

**Responsibilities**  
- Propose a simplified state schema with a single authoritative evidence representation for synthesis.  
- Relegate other fields to derived views or lightweight indices (e.g., for sources).  
- Align state layout with the new lazy expansion and caching model.

**Typical prompts**  
- “Map how each state field is produced and consumed across orchestrator, planner, reflector, policy, and synthesizer.”  
- “Propose a minimal state layout and show how each consumer should be updated.”  

---

## Source Pipeline Fixer (Finding #4)

**Agent name:** `source_pipeline_fixer`  
**Config:** `agents/source_pipeline_fixer.toml`  

**Finding focus**  
- Source-building rescans large strings, and late web fetches can add sources the model never saw.  

**Responsibilities**  
- Tighten coupling between synthesis and source-building so sources only reference evidence used during synthesis.  
- Make `_build_structured_sources()` operate on lightweight snippets/metadata instead of full text.  
- Remove or redesign post-synthesis web fetch behavior.

**Typical prompts**  
- “Redesign `_build_structured_sources()` to operate on lightweight source records only.”  
- “Specify invariants ensuring every final source was accessible during synthesis.”  

---

## Planner Strictifier (Finding #5)

**Agent name:** `planner_strictifier`  
**Config:** `agents/planner_strictifier.toml`  

**Finding focus**  
- Planner prompt expects a JSON array, but `response_format` demands a JSON object, causing parse failures and fallback retrieval.  

**Responsibilities**  
- Align planner prompt, `response_format`, and parsing logic on a single JSON schema.  
- Make fallback retrieval a deliberate, documented behavior instead of an accidental side effect of format mismatch.  
- Add tests for multi-step plans, repeated-source hits, and final-source consistency.

**Typical prompts**  
- “Define the canonical JSON schema for planner output and align all planner call sites to it.”  
- “Harden planner error-handling so format mismatches are rare and well-instrumented.”  

---

## Churn Reducer (Finding #6)

**Agent name:** `churn_reducer`  
**Config:** `agents/churn_reducer.toml`  

**Finding focus**  
- Repeated `sum(...)` over large buffers and large-string concatenations add unnecessary CPU churn.  

**Responsibilities**  
- Identify hot paths that repeatedly scan or rebuild large buffers.  
- Introduce incremental counters or buffered string-building patterns with identical semantics.  
- Keep changes small, low-risk, and easy to review.

**Typical prompts**  
- “Locate hot spots where raw buffers are re-scanned on each append and propose incremental alternatives.”  
- “Refactor synthesizer string assembly to use a list-then-join pattern with identical output.”  

---

## Usage Notes

- Prefer talking to `coordinator` for end-to-end changes; it will dispatch work to the specialist agents.  
- Use specialist agents directly when you want deep, focused proposals on a single finding.  
- Keep this file updated if you rename agents, change their configs, or add new roles (e.g., dedicated test harness or benchmarking agents).

