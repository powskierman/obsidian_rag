# Implementation Checklist

Use this checklist before merging implementation work in `obsidian_rag`.

## 1. Scope

- [ ] The change is covered by a spec, plan, task list, or an explicitly scoped maintenance task.
- [ ] The change respects the project constitution.
- [ ] Service boundaries remain intact: embedding `8000`, LightRAG `8001`, graph `8002`, gateway `4000`.

## 2. Retrieval Safety

- [ ] Vector retrieval still works for the changed path.
- [ ] Cascading retrieval still works for the changed path.
- [ ] Deep-research behavior is unchanged or intentionally updated.
- [ ] Public search traffic still goes through the API gateway, not direct internal-service exposure.

## 3. Data And Indexing

- [ ] Incremental indexing remains the default unless the change explicitly documents otherwise.
- [ ] Graph and vector indexes can still be rebuilt independently.
- [ ] Generated databases or private local data are not added to Git.
- [ ] Metadata, path handling, and note identity behavior remain stable or are explicitly migrated.

## 4. API And Contracts

- [ ] If gateway behavior changed, public API docs or references were updated.
- [ ] If MCP behavior changed, MCP-facing docs or tool descriptions were updated.
- [ ] If ranking, filtering, or graph semantics changed, tests cover the new contract.

## 5. Testing

- [ ] Relevant unit tests were run.
- [ ] Relevant integration or public-contract tests were run when interfaces changed.
- [ ] Health or smoke checks were run for touched services.
- [ ] New behavior has at least one regression test when practical.

## 6. Performance

- [ ] The change does not obviously regress latency or memory usage.
- [ ] For search-path changes, `Scripts/debug/audit_search_modes.py` was considered or run as appropriate.
- [ ] Non-chat retrieval still returns non-zero sources.

## 7. Documentation

- [ ] User-facing or operator-facing documentation was updated where needed.
- [ ] New scripts, workflows, or maintenance steps are documented.
- [ ] If this work changes governance or architecture assumptions, the constitution or references were updated.

## 8. Codex Handoff

- [ ] Files changed are intentional and limited to scope.
- [ ] Any assumptions, follow-ups, or known gaps are recorded in the final summary or commit message.
- [ ] If there are residual risks, they are stated explicitly.
