# ChatGPT Parity Implementation Report

Goal: make ChatGPT responses as useful and grounded as Claude responses when using obsidian_rag, with consistent tool-driven retrieval and minimal, non-intrusive safety language.

Status: implemented on branch `chatgpt-parity`, pending review/merge.

## Summary of the Gap

- Claude currently performs multi-step retrieval (semantic search, batch fetch, gap-filling searches) and produces structured timelines.
- ChatGPT often underuses tools, returns generic safety disclaimers, and lacks a stable output format.
- Outcome: Claude answers feel specific and actionable; ChatGPT answers feel cautious and vague.

## Target Behavior

- Always retrieve notes before responding.
- Use a repeatable, agentic search loop that fills missing scans.
- Produce a consistent timeline summary (PET and CT series, sizes, SUVs, Deauville).
- Include a minimal safety line only when required, not as the main content.

## Implementation Plan

### Phase 1: Provider configuration and system prompt

1. Confirm ChatGPT provider is enabled and uses the same tool access as Claude.
2. Add a ChatGPT-specific system prompt with strict instructions:
   - Use retrieved notes first.
   - Do not answer without tool calls unless explicitly told.
   - Keep any safety note to 1-2 lines at the end.
3. Raise ChatGPT `max_tokens` / output budget so long summaries are possible.

Likely files:
- `src/services/api_gateway.py`
- `src/services/graph_query_service.py`
- `src/ui/streamlit_ui_docker.py`

### Phase 2: Agentic retrieval loop

Implement a multi-step retrieval loop (the same behavior Claude showed):

1. Run semantic search for PET/PET-CT terms.
2. Batch fetch the full contents of all hits.
3. Search for CT scans not found in step 1.
4. Batch fetch CT scan notes.
5. If any scan is referenced but missing, run a filename/keyword search.
6. If still missing, surface a short "referenced but not found" note.

Likely files:
- `src/services/api_gateway.py`
- `src/services/cascading_retriever.py`
- `src/services/graph_query_service.py`

### Phase 3: Retrieval fallback and expansion

1. If semantic retrieval returns few or low-score chunks, run a lexical fallback.
2. Expand the user query into multiple medical synonyms and re-run retrieval.
3. Merge and dedupe results before synthesis.

Likely files:
- `src/services/cascading_retriever.py`
- `src/services/api_gateway.py`

### Phase 4: Structured output template

Add a stable format for clinical timelines:

- Imaging timeline (date, modality, size, SUV, Deauville).
- Changes over time (SUV and size deltas).
- Interpretation with confidence and uncertainty markers.
- Questions for oncologist (non-prescriptive).

Implement an internal JSON shape to assemble the final narrative.

Likely files:
- `src/services/graph_query_service.py`
- `src/services/api_gateway.py`

### Phase 5: Tests and evaluation

Add focused tests for medical retrieval:

- PET scan note retrieval.
- CT scan August 2025 retrieval.
- D12 compression fracture extraction.
- Structured timeline assembly.

Likely files:
- `tests/`

### Phase 6: Observability

Add logs for:

- tool invocation count per request
- retrieval hit counts
- fallback usage (semantic -> lexical)

Likely files:
- `src/services/api_gateway.py`

## Safety Language Policy

- Keep safety language minimal and non-blocking.
- Only add a short note at the end when needed.
- Do not lead with disclaimers or replace the answer with a warning.

## Rollback Plan

- Disable ChatGPT agentic mode and revert to the previous retrieval pipeline.
- Leave Claude behavior untouched.

## Approval Gate

Code changes completed on the feature branch; review before merge.

## Implementation Details (Current)

- Prompt builder utility added: `src/utils/prompt_builder.py`
  - ChatGPT guardrails (no permission requests, minimal safety note)
  - Medical imaging template for PET/CT timelines
- Graph query prompts now use the shared builder for vector + streaming modes.
- Hybrid synthesis prompt now appends ChatGPT guardrails + imaging template when relevant.
- Deep Thinking synthesis now:
  - Appends guardrails for ChatGPT
  - Uses imaging template when query mentions scans
  - Supports `DEEP_THINKING_OPENAI_MAX_TOKENS`
- Tests added:
  - `tests/unit/test_prompt_builder.py`
  - Expanded `tests/unit/test_deep_thinking_synthesizer.py`
