# Codex House Rules

These are the repo-specific operating rules for Codex work in `obsidian_rag`.

Primary references:
- `AGENTS.md`
- `.codex/AGENTS.md`
- `Documentation/git-sync-macs.md`

## Working Rules

1. Read the repo context first.
- Prefer existing specs, plans, tasks, directives, and scripts over inventing new workflows.

2. Follow Spec-Driven Development.
- Use Spec Kit artifacts when work is feature-shaped.
- Keep implementation aligned with spec, plan, and task outputs.

3. Respect machine roles.
- RAG and vault indexing work belongs on Canmore by default.
- OpenClaw and long-running memory orchestration belongs on Lobster.
- Interactive coding and ad-hoc heavy model runs can happen on the MacBook.

4. Preserve architecture boundaries.
- Keep the API gateway as the public entrypoint.
- Treat embedding, LightRAG, and NetworkX graph as internal dependencies unless intentionally changing public contracts.

5. Prefer deterministic project scripts.
- Reuse `Scripts/` and `directives/` where they already encode the workflow.
- Do not replace existing documented procedures with ad-hoc alternatives without a good reason.

6. Be careful with local data.
- Do not commit generated databases, indexes, or private vault data.
- Assume local data may be sensitive.

7. Keep documentation in sync.
- If behavior, APIs, indexing, or operations change, update the relevant docs in the same change.

8. Be explicit about retrieval-risk changes.
- If a change affects metadata handling, ranking, graph identity, deduplication, or indexing, call that out clearly.
- Prefer adding or updating tests for those paths.

9. Use Codex agents intentionally.
- Use the coordinator or specialist Codex agents in `.codex/AGENTS.md` only when the task matches their scoped purpose.
- Keep deep-thinking remediation work aligned with the staged fix order documented there.

10. Follow the project Git workflow.
- Use the multi-Mac sync workflow in `Documentation/git-sync-macs.md`.
- Do not treat iCloud Drive as the primary project workspace.
