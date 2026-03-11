# Implementation Plan: Tune Deep Thinking Params

## 1. Overview
The `deep_thinking` module currently relies on hardcoded system prompts and model parameters within `planner.py` (and likely other files). This makes it difficult to experiment with different prompting strategies to improve tool selection.

This plan involves:
1.  Extracting hardcoded values into a new `deep_thinking/config.py`.
2.  Refactoring `planner.py` to consume this config.
3.  Tuning the prompts to improve "Web" vs "Vector" tool selection logic.

## 2. User Review Required
- **New File**: `deep_thinking/config.py` will be created.
- **Refactor**: `planner.py` `PlannerAgent` class will be modified to load from config.

## 3. Proposed Changes

### [Deep Thinking Module]

#### [NEW] [deep_thinking/config.py](file:///Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/config.py)
- Define `DeepThinkingConfig` class or dictionary.
- Store `PLANNER_SYSTEM_PROMPT`.
- Store `PLANNER_MODEL` (default: "claude-sonnet-4-5-20250929").
- Store `MAX_TOKENS`.

#### [MODIFY] [deep_thinking/planner.py](file:///Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/planner.py)
- Import `config`.
- Replace hardcoded `system_prompt` with `config.PLANNER_SYSTEM_PROMPT`.
- Replace hardcoded model/token params.

## 4. Verification Plan

### Capability Evals ([NEW] .agent/evals/tune-deep-thinking.md)
- [ ] **[Cap-1] Plan Generation**: `PlannerAgent.create_plan` returns valid JSON with extracted config.
- [ ] **[Cap-2] Tool Selection**: Verify "How do I install python?" triggers "web" search, not "vector".

### Regression Evals
- [ ] Run existing tests: `pytest tests/deep_thinking/test_planner.py`
