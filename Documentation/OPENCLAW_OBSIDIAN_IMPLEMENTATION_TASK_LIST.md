# OpenClaw + Obsidian RAG Implementation Task List

## Scope Lock (Confirmed)

- Write node: `Canmore's Mac Mini` only.
- Capture/summarization template: `/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Templates/New Note Template.md`
- Tag update policy: frontmatter `tags` only.
- Video ingestion scope: YouTube only.
- Telegram search response default: concise answer only.
- `/search` default mode: `hybrid` (until explicitly changed).

## Phase 0: Foundation and Guardrails

1. Define node responsibilities and lock write permissions.
Deliverables: architecture note with explicit host roles, no vault write mount on Lobster, write-capable MCP tools only on Canmore.
Acceptance: a write attempt from Lobster filesystem tools is blocked; write through Canmore MCP succeeds.

2. Confirm Canmore MCP endpoint and auth over Tailnet.
Deliverables: reachable MCP URL, API key rotation procedure, health check command.
Acceptance: `curl` health check and `mcporter list` against the Canmore endpoint both succeed.

3. Add this implementation plan and architecture links to docs index.
Deliverables: indexed docs in `Documentation/INDEX.md`.
Acceptance: both files appear in index and are discoverable.

## Phase 1: Retrieval Path (Search First)

4. Add MCP tool for unified mode-aware retrieval.
Deliverables: new tool in `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/mcp/obsidian_rag_unified_mcp.py` that forwards to `/api/v1/query` with `mode`, `query`, and `max_results`.
Acceptance: tool supports at least `hybrid`, `dual-graph`, `cascading`, `notes+vector`; invalid mode returns clear error.

5. Enforce default search mode policy.
Deliverables: default mode set to `hybrid` in MCP tool and OpenClaw command layer.
Acceptance: `/search <query>` runs `hybrid` without requiring mode argument.

6. Add concise response formatter for Telegram.
Deliverables: formatter that returns short answer first, with optional source expansion command.
Acceptance: default Telegram search reply is concise and fits single-screen output.

## Phase 2: Capture (Text and Voice)

7. Implement `capture_note` write tool on Canmore.
Deliverables: MCP tool that writes a markdown note to `00_Inbox/_capture` with timestamped filename and template sections.
Acceptance: invoking tool creates one file with expected path pattern and non-empty body.

8. Add template application using fixed template path.
Deliverables: loader/parser for `/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Templates/New Note Template.md`.
Acceptance: created notes consistently render required sections from the template.

9. Implement voice-note to capture flow.
Deliverables: Telegram voice ingestion, transcription, capture write.
Acceptance: a Telegram voice message produces a saved note and returns the saved vault-relative path.

## Phase 3: Summarization Capture

10. Implement clipboard summarization capture (`/clip`).
Deliverables: summarize provided text/clipboard payload into point form and save via template.
Acceptance: summary note is generated in `00_Inbox/_capture` with bullet-point output.

11. Implement webpage summarization capture (`/sumurl`).
Deliverables: URL fetch, text extraction, point-form summary, templated note save.
Acceptance: valid webpage URL produces capture note with source URL recorded.

12. Implement YouTube-only summarization capture (`/sumvideo`).
Deliverables: YouTube transcript extraction + point-form summary + templated note save.
Acceptance: YouTube URL works; non-YouTube URL is rejected with clear message.

## Phase 4: Tagging

13. Implement existing-tag suggestion tool.
Deliverables: derive candidate tags from existing vault/index tags only.
Acceptance: suggested tags are all present in existing tag corpus.

14. Implement frontmatter-only tag apply tool.
Deliverables: update YAML `tags` array only, no inline tag edits.
Acceptance: note frontmatter updates correctly; note body remains unchanged.

## Phase 5: OpenClaw Command Surface

15. Add slash command contract in OpenClaw config.
Deliverables: `/capture`, `/clip`, `/sumurl`, `/sumvideo`, `/tag`, `/search`, `/searchmodes`.
Acceptance: each command routes to the expected MCP tool and returns predictable output.

16. Add authorization guardrails for Telegram.
Deliverables: allowlist policy for sender IDs and group policy configuration.
Acceptance: unauthorized sender requests are denied and logged.

## Phase 6: Testing, Runbook, and Rollout

17. Build end-to-end smoke tests.
Deliverables: scripted tests for search, text capture, voice capture, URL summary, YouTube summary, and tagging.
Acceptance: all smoke tests pass on Canmore-hosted stack.

18. Create operations runbook.
Deliverables: start/restart commands, health checks, failure triage, API key rotation, rollback steps.
Acceptance: runbook can recover service from a stopped state in one pass.

19. Production rollout in two stages.
Deliverables: Stage A internal test (you only), Stage B daily usage default.
Acceptance: 7-day canary with no data-loss, no unauthorized writes, and acceptable latency.

## Definition of Done

1. All writes happen only through Canmore-hosted write tools.
2. All created notes use the specified template path.
3. Tag updates are frontmatter-only and use existing tags.
4. `/search` defaults to `hybrid` and Telegram replies are concise.
5. YouTube summarization works; non-YouTube videos are explicitly rejected.
6. Command set works from Telegram and OpenClaw app with stable behavior.

