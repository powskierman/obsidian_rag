# Obsidian RAG Documentation

Use this file as the canonical index for active documentation. Files not listed here are either intentionally archived under `archive/` or are scaffolding for upstream projects (e.g. `SSD_RAG/`, `git-sync-macs.md`).

## Primary Manual
- `USER_MANUAL.md`

## Quick Start
- `getting-started/SETUP_QUICKSTART.md`
- `getting-started/API_GATEWAY_QUICKSTART.md`
- `getting-started/README_CLI_SEARCH.md`

## Core References
- `reference/search/SEARCH_ARCHITECTURE.md` — overall request flow + per-mode flowchart
- `reference/search/SEARCH_MODES_GUIDE.md` — `ask` / `research` / `investigate` comparison + legacy mode map
- `reference/search/RESEARCH_MODE_FLOW.md` — staged retrieval pipeline (anchor → expand → vector → synthesis)
- `reference/api/UNIFIED_API_IMPLEMENTATION.md` — `POST /api/v1/query` field reference
- `reference/streaming/STREAMING_IMPLEMENTATION.md` — WebSocket streaming for `investigate`
- `reference/architecture/CAPTURE_AND_INBOX.md` — capture-note + URL/YouTube summarization tools
- `reference/architecture/MCP_TOOL_CATALOG.md` — full MCP tool inventory with arguments

## Specifications
- `specs/movie-catalog/spec.md`
- `specs/movie-catalog/plan.md`
- `specs/movie-catalog/tasks.md`
- `compliance/movie-subsystem-compliance-matrix.md`

## Architecture
- `reference/architecture/SYSTEM_ARCHITECTURE_DIAGRAM.md` — services + data stores topology
- `reference/architecture/DEEP_THINKING_FLOW.md` — `investigate` agent loop
- `reference/architecture/GRAPH_STACK_RETIREMENT_MAP.md` — what blocks retiring NetworkX/LightRAG
- `reference/architecture/SECOND_BRAIN_ARCHITECTURE.md` — proposal/aspirational design (not yet implemented)
- `reference/spec.md`

## Operations
- `operations/DATABASE_MANAGEMENT.md`
- `operations/indexing/INDEXING_STRATEGY.md` — when/why to run each indexing path
- `operations/indexing/REINDEXING_PROCEDURE.md`
- `operations/indexing/INDEXING_BENCHMARK_PROCEDURE.md`
- `operations/setup/INDEXING_SCRIPTS_GUIDE.md`
- `operations/setup/API_KEY_VALIDATION_GUIDE.md`
- `operations/setup/LIGHTRAG_PARTIAL_INDEXING_GUIDE.md`
- `operations/setup/MLX_BULLETPROOF_INDEXING_IMPLEMENTATION.md`
- `operations/setup/TESTING.md`
- `operations/troubleshooting/TROUBLESHOOTING_QUERY.md`
- `operations/troubleshooting/DOCKER_TROUBLESHOOTING.md`
- `operations/vault/VAULT_STANDARDIZATION_GUIDE.md`
- `operations/vault/VAULT_ORGANIZATION_GUIDE.md`
- `operations/embeddings/EMBEDDING_MODEL_UPDATE_GUIDE.md`
- `operations/notes/New Note Template.md`
- `operations/quality/KNOWLEDGE_GRAPH_TEST_PROMPTS.md`
- `operations/quality/SEARCH_COMPARISON_RESULTS.md`
- `operations/quality/INDEX_HEALTH_PROCEDURE.md`
- `operations/tuning/SOTA_TUNING_GUIDE.md`
- `operations/graph/GRAPH_DATA_FLOW.md`
- `operations/graph/GRAPH_DATA_README.md`
- `operations/graph/GRAPH_QUALITY_GUIDE.md`
- `operations/graph/IMPROVED_GRAPH_BUILDER_GUIDE.md`
- `operations/graph/TRANSFER_BETWEEN_MACHINES.md`
- `operations/models/README.md`
- `operations/models/SETUP.md`
- `operations/movies/MOVIE_SUBSYSTEM_OPERATOR_GUIDE.md`

## Integrations
- `integrations/mcp/MCP_SETUP_INSTRUCTIONS.md`
- `integrations/mcp/CHATGPT_DEEP_SEARCH_GUIDE.md`
- `MCP_CLIENT_SETUP.md` — connecting a MacBook client to a remote (Canmore/Tailscale) MCP server
- `SSH_MCP_SETUP.md` — SSH-transport MCP fallback (use HTTP first)
- `integrations/web-search/WEB_SEARCH_IMPLEMENTATION.md`

## Deployments
- `deployments/mac-mini/MAC_MINI_QUICK_START.md`
- `deployments/mac-mini/MAC_MINI_NETWORKING_FIX.md`
- `git-sync-macs.md` — Git-based two-Mac sync (replaces iCloud-as-workspace)
- `operations/models/GEMMA4_MLX_IMPLEMENTATION_PLAN.md` — plan for serving Gemma 4 over MLX

## Subprojects (not part of the active doc surface)
- `SSD_RAG/Documentation/MACBOOK_OPERATOR_CARD.md`
- `SSD_RAG/Documentation/MACBOOK_TEST_CHECKLIST.md`

## Agents & Governance
- `reference/agents/ANTIGRAVITY_SKILLS_MANUAL.md`
- `reference/governance/PROJECT_CONSTITUTION.md`

## Archive

Historical material kept for reference; not part of the active product surface.

- `archive/design/deep-thinking-remediation-phase1.md`
- `archive/agents/AG_BACKLOG.md`
- `archive/agents/AG_INTEGRATION_PLAN.md`
- `archive/agents/implementation_plan.md`
- `archive/search-docs/DEEP_THINKING_PROTOCOL.md` — superseded by `reference/architecture/DEEP_THINKING_FLOW.md`
- `archive/graph-retrospectives/LIGHTRAG_MEMORY_CONTEXT_FAILURE_REMEDIATION.md`
- `archive/graph-retrospectives/LIGHTRAG_RESPONSE_EQUIVALENCE_REMEDIATION.md`
- `archive/graph-retrospectives/NETWORKX_RETRIEVAL_GAP_ASSESSMENT.md`
- `archive/code-reviews/QUERY_MODE_CONSOLIDATION_REVIEW.md` — point-in-time review (Apr 2026)
- `archive/spec-drafts/OC-SPEC-MOVIES_combined_draft.md` — superseded by `specs/movie-catalog/`
- `archive/misc/MCP_IMPROVEMENTS_SUMMARY.md`
- `archive/misc/PROVIDER_CONFIGURATION_FIX.md`
- `archive/misc/QUICK_FIX_MCP_SSH.md`
- `archive/misc/README_SYNC_BUNDLE.txt`

## Public API Summary

- `POST /api/v1/query` — HTTP search; canonical `mode` is `ask` or `research`. Legacy strings `vector`, `cascading`, `vault_review`, `mempalace` still accepted (a `X-Deprecated-Mode` response header is emitted).
- `GET /api/v1/health` — Health check for all services.
- `GET /api/v1/stats` — System statistics.
- `GET /api/v1/providers` — Configured LLM provider list.
- `GET /api/v1/provider-status` — Reachability/health of each configured provider.
- `ws://localhost:4000/api/v1/deep-research` — Investigate (agentic deep research) streaming WebSocket. Legacy mode name `deep-thinking` maps here.
- `GET /docs` — OpenAPI UI.

New fields: `depth` (`auto`|`shallow`|`staged`|`full`) and `sources` (`vault`|`mempalace`|`web`) are accepted on `POST /api/v1/query`.

`lmstudio` and `mlx` are accepted as equivalent aliases for the local LM Studio / MLX provider.

See `getting-started/API_GATEWAY_QUICKSTART.md` for full request/response field reference.
