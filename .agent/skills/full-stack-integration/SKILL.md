---
name: Full Stack Integration
description: Ensure the entire stack is communicating correctly (Frontend -> Gateway -> Graph -> Chroma).
---

# Full Stack Integration Skill

This skill is the "final gatekeeper" for stability. It runs integration tests that traverse the entire request lifecycle.

## Goal
To prevent regressions like the 503 Service Unavailable error or broken UI states.

## Tools & Scripts
*   **Integration Tests:** `tests/integration/`
*   **API Test:** `curl`

## Instructions

1.  **Pre-Flight Check**
    *   Ensure all containers are up: `docker compose ps`.
    *   Ensure the Graph Service is healthy.

2.  **Run Integration Suite**
    *   `pytest tests/integration/`
    *   These tests should mock the external LLM calls (to save tokens) but HIT the actual local database/graph service containers if configured for e2e.

3.  **API E2E Check**
    *   Send a real search request via curl (mimicking the frontend):
    *   `curl -X POST http://localhost:4000/api/v1/query -H "Content-Type: application/json" -d '{"query": "test", "mode": "cascading"}'`
    *   Verify response is JSON and contains `results`.

## Constraints
*   If `tests/integration/` does not exist yet, prioritize creating it under the "Stability" track in the Backlog.
*   Do not rely solely on unit tests for 503 500 debugging.
