---
name: Deep Think Trace
description: Debug and verify "Deep Thinking" reasoning chains.
---

# Deep Think Trace Skill

This skill is for debugging the `deep_thinking` module, specifically the Planner, Supervisor, and Reflector components.

## Goal
To verify that the "System 2" reasoning engine is selecting the correct tools and generating valid plans, without needing to run the full UI.

## Tools & Scripts
*   **Test Runner:** `pytest`
*   **Debug Script:** `debug_search.py` (ensure it handles `deep_thinking` flow)

## Instructions

1.  **Trace Reasoning Chain**
    *   Run a test case with standard output capture enabled:
    *   `pytest tests/deep_thinking -k "test_trace" -s`
    *   Review the `stdout` for `[Planner]`, `[Supervisor]`, and `[Tool]` logs.

2.  **Verify Tool Selection**
    *   Check if the Planner selected `web_search` for external queries vs `obsidian_search` for internal ones.
    *   Check if the Supervisor correctly determined "completeness".

3.  **Manual Probe**
    *   If tests are inconclusive, write a small script in `deep_thinking/debug_probe.py`:
        ```python
        from deep_thinking.planner import Planner
        p = Planner()
        plan = p.create_plan("How does X relate to Y in my notes?")
        print(plan)
        ```
    *   Run it and check the generated JSON structure.

## Constraints
*   Focus on **logic verification**, not just code coverage.
*   If the LLM is hallucinating tools, check `src/services/tools.py` definitions.
