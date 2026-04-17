# Obsidian RAG Documentation

Use this file as the canonical index for active documentation.

## Primary Manual
- `USER_MANUAL.md`

## Quick Start
- `getting-started/SETUP_QUICKSTART.md`
- `getting-started/API_GATEWAY_QUICKSTART.md`
- `getting-started/README_CLI_SEARCH.md`

## Core References
- `reference/search/SEARCH_ARCHITECTURE.md`
- `reference/search/SEARCH_MODES_GUIDE.md`
- `reference/search/RESEARCH_MODE_FLOW.md`
- `reference/api/UNIFIED_API_IMPLEMENTATION.md`
- `reference/streaming/STREAMING_IMPLEMENTATION.md`

## Specifications
- `specs/movie-catalog/spec.md`
- `specs/movie-catalog/plan.md`
- `specs/movie-catalog/tasks.md`
- `compliance/movie-subsystem-compliance-matrix.md`

## Architecture
- `reference/architecture/SYSTEM_ARCHITECTURE_DIAGRAM.md`
- `reference/architecture/DEEP_THINKING_FLOW.md`
- `reference/architecture/SECOND_BRAIN_ARCHITECTURE.md`
- `reference/architecture/GRAPH_STACK_RETIREMENT_MAP.md`
- `reference/spec.md`

## Operations
- `operations/DATABASE_MANAGEMENT.md`
- `operations/indexing/INDEXING_STRATEGY.md`
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
- `integrations/web-search/WEB_SEARCH_IMPLEMENTATION.md`

## Deployments
- `deployments/mac-mini/MAC_MINI_QUICK_START.md`
- `deployments/mac-mini/MAC_MINI_NETWORKING_FIX.md`

## Agents
- `reference/agents/ANTIGRAVITY_SKILLS_MANUAL.md`
- `reference/governance/PROJECT_CONSTITUTION.md`

## Archive
- `archive/design/deep-thinking-remediation-phase1.md`
- `archive/agents/AG_BACKLOG.md`
- `archive/agents/AG_INTEGRATION_PLAN.md`
- `archive/agents/implementation_plan.md`
- `archive/search-docs/DEEP_THINKING_PROTOCOL.md`
- `archive/graph-retrospectives/LIGHTRAG_MEMORY_CONTEXT_FAILURE_REMEDIATION.md`
- `archive/graph-retrospectives/LIGHTRAG_RESPONSE_EQUIVALENCE_REMEDIATION.md`
- `archive/graph-retrospectives/NETWORKX_RETRIEVAL_GAP_ASSESSMENT.md`
- `archive/misc/MCP_IMPROVEMENTS_SUMMARY.md`
- `archive/misc/PROVIDER_CONFIGURATION_FIX.md`
- `archive/misc/QUICK_FIX_MCP_SSH.md`
- `archive/misc/README_SYNC_BUNDLE.txt`

## Public API Summary

- `POST /api/v1/query` — HTTP search; `mode` is `ask` or `research`. Legacy strings `vector`, `cascading`, `vault_review` still accepted.
- `GET /api/v1/health` — Health check for all services.
- `GET /api/v1/stats` — System statistics.
- `ws://localhost:4000/api/v1/deep-research` — Investigate (agentic deep research) streaming WebSocket.
- `GET /docs` — OpenAPI UI.

New fields: `depth` (`auto`|`shallow`|`staged`|`full`) and `sources` (`vault`|`mempalace`|`web`) are accepted on `POST /api/v1/query`.

`lmstudio` and `mlx` are accepted as equivalent aliases for the local LM Studio provider.

See `getting-started/API_GATEWAY_QUICKSTART.md` for full request/response field reference.
