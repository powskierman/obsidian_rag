# LightRAG `memory_context` Query Failure: Root Cause and Corrective Measures

Date: 2026-02-20  
Status: Investigation complete, implementation pending approval

## Executive Summary

`LightRAG` queries can return:

`Query failed: 'memory_context'`

This is caused by unresolved Python `.format(...)` placeholders in a custom `system_prompt` passed to LightRAG. The currently running `obsidian-lightrag` container does not apply `{memory_context}` substitution before prompt formatting, so the prompt renderer raises `KeyError('memory_context')`.

## Confirmed Evidence

1. Reproduced directly against LightRAG:
   - `POST http://127.0.0.1:8001/query`
   - Payload includes: `"system_prompt": "Summary:\n{memory_context}"`
   - Response includes: `"answer":"Query failed: 'memory_context'"`

2. Reproduced through API Gateway:
   - `POST http://127.0.0.1:4000/api/v1/query`
   - Mode `entities` with same prompt
   - Gateway forwards LightRAG response containing the same failure string.

3. Running container code is missing placeholder handling:
   - `/app/lightrag_service.py` in container has no `mem0_context` extraction and no `{memory_context}` replacement in `/query`.
   - Workspace file `src/integrations/lightrag_service.py` does include this handling.

4. Prompt formatting path that fails:
   - `src/lightrag_overrides/lightrag/operate.py` calls `.format(...)` on `system_prompt`.
   - Allowed format keys are prompt internals (`response_type`, `user_prompt`, `context_data`/`content_data`).
   - Any unresolved placeholder (such as `memory_context`) raises `KeyError`.

## Root Cause

The issue is a combination of two failures:

1. Template-variable mismatch at runtime:
   - User/system prompt includes `{memory_context}`.
   - LightRAG prompt formatting does not define `memory_context` as a formatting key.
   - `.format(...)` raises `KeyError('memory_context')`.

2. Service deployment drift:
   - LightRAG entrypoint runs `/app/lightrag_service.py` copied at image build time.
   - The current container is running an older copy that lacks the pre-format substitution guard.
   - Therefore the guard present in workspace source is not active in production runtime.

## Additional Reliability Gap

On failure, LightRAG returns HTTP 200 with a payload containing an error message string (`"Query failed: ..."`). This masks operational failures as successful responses and can bypass gateway fallback/error routing.

## Proposed Corrective Measures (No Implementation Yet)

## 1) Immediate Operational Remediation

1. Rebuild and recreate `lightrag-service` from current source.
2. Verify runtime file in container includes `{memory_context}` substitution logic.
3. Re-test with:
   - plain query (`lymphoma yescarta`)
   - custom prompt containing `{memory_context}`.

## 2) Prompt Formatting Hardening

1. Add a safe formatting layer before `.format(...)`:
   - allow known variables only
   - default unknown placeholders to empty/safe text
   - never raise `KeyError` to end users.
2. Normalize accepted memory placeholder aliases:
   - `{memory_context}`
   - `{mem0_context}` (optional compatibility alias).
3. If unresolved placeholders remain, return explicit `400` with actionable error detail.

## 3) Error Semantics and Gateway Behavior

1. In LightRAG `/query`, map internal `"status":"failure"` to non-200 HTTP status.
2. In API Gateway, treat `"Query failed:"`/failure-status payloads as service errors, not valid answers.
3. Trigger existing fallback paths when entities mode fails.

## 4) Tests to Prevent Regression

1. Unit tests:
   - prompt with `{memory_context}` succeeds (with and without mem0 content)
   - unknown placeholder handled deterministically.
2. Integration tests:
   - `/api/v1/query` entities mode returns non-200 on internal template failure
   - fallback behavior validated when LightRAG fails.
3. Deployment test:
   - smoke test that checks runtime `/app/lightrag_service.py` version/marker on container startup.

## 5) Deployment Guardrails

1. Document that LightRAG code is copied into image (`Dockerfile.lightrag`) and requires rebuild on code changes.
2. Add startup/version logging so running container code version is visible in logs.
3. Optional: adjust runtime to execute service directly from mounted source path to reduce drift risk.

## Acceptance Criteria for Fix

1. Query `lymphoma yescarta` in entities mode no longer returns `Query failed: 'memory_context'`.
2. Custom prompt containing `{memory_context}` returns a normal answer or an explicit validation error (never raw `KeyError`).
3. LightRAG internal failures are surfaced with non-200 status and trigger gateway error/fallback handling.
4. New tests pass in CI and reproduce prevention locally.

## Change Control

No code changes were implemented as part of this investigation.  
Proceed only after explicit approval.
