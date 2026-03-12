---
name: Comprehensive Eval Audit
description: Audit all search modes (Vector, Graph, Hybrid, Deep Thinking) for efficacy and latency.
---

# Comprehensive Eval Audit

This skill systematically checks every search strategy available in the Obsidian RAG system.

## Goal
To generate a status report (`Documentation/operations/quality/SEARCH_MODE_AUDIT.md`) detailing which modes are functional, how fast they are, and if they return sources.

## Tools & Scripts
*   **Audit Script:** `python Scripts/audit_search_modes.py`

## Instructions

1.  **Prerequisites**
    *   Ensure the Gateway is running: `docker compose ps` -> `gateway` should be Up.
    *   Ensure backend services (embedding, graph) are Up.

2.  **Execution**
    *   Run `python Scripts/audit_search_modes.py`
    *   This script will hit `http://localhost:4000` with a standard query ("What is the treatment for DLBCL?").

3.  **Analysis**
    *   Read `Documentation/operations/quality/SEARCH_MODE_AUDIT.md`.
    *   **FAIL** statuses indicate API errors or Gateway misconfigurations.
    *   **Low Source Counts** (0) indicate indexing issues or overly aggressive filtering.

4.  **Deep Thinking Check**
    *   The audit includes a WebSocket test for "Deep Thinking". If this fails, check the `deep_thinking` module logs.

## Constraints
*   Do not spam the audit; it uses LLM tokens (Ollama by default to save cost, but still uses compute).
