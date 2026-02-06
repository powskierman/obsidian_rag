# Antigravity Implementation Plan: Obsidian RAG "Ops Layer"

This document outlines the structural changes required to transform `obsidian_rag` into an agent-friendly workspace. This structure treats Antigravity as an "ops layer," enabling autonomous agents to handle repeatable workflows while the human developer focuses on architecture and design.

## 1. Project & Workspace Setup

**Goal:** Create a dedicated, clean workspace rooted at the `obsidian_rag` repo with explicit agent responsibilities divided into "tracks".

### 1.1 Root Configuration
- **Workspace Root:** `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag`
- **Agent Visibility:** Agents will have full visibility of code, docs, and scripts from this root.

### 1.2 Persistent Tracks (Long-Running Tasks)
We will define four distinct tracks to separate concerns, allowing agents to specialize in specific stacks (Python vs TS, Backend vs Frontend).

| Track Name | Focus | Key Directories |
| :--- | :--- | :--- |
| **Track 1: Core Engine & Indexing** | Managing ChromaDB, LightRAG, and NetworkX data structures. | `src/indexing/`, `chroma_db/`, `lightrag_db/` |
| **Track 2: Inference & Reasoning Engine** | Deep Thinking logic, Planner/Supervisor, API Gateway, and Search Services. | `src/services/`, `deep_thinking/`, `Documentation/API_GATEWAY_QUICKSTART.md` |
| **Track 3: Connectors & MCP** | Obsidian vault integration, MCP servers, and tool definitions. | `Documentation/MCP/`, `Scripts/` |
| **Track 4: Frontend & User Experience** | Next.js/React webapp, Visualizations (Force Graph), and UI State. | `webapp/` |

**Action Item:**
- [ ] Create `ANTIGRAVITY_TRACKS.md` (optional internal doc) or simply maintain this mental model when dispatching agent tasks.

## 2. Structured Task Management (`AG_BACKLOG.md`)

**Goal:** Provide agents with structured, labelled tasks containing explicit constraints and acceptance criteria to ensure safe execution.

**Action Item:**
- [ ] Create `AG_BACKLOG.md` in the repo root.

**Structure of `AG_BACKLOG.md`:**
The file will act as a "pick-up" queue for agents.

| Category | Task | Constraints | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Infra** | Automate DB rebuilds | No Git tracking of `lightrag_db` | Script `index_with_lightrag.sh` runs successfully via agent. |
| **Indexing** | Incremental Upsert | Use `index_vault.py` with `--refresh` | Stale chunks removed; metadata validated. |
| **Reasoning** | Tune Deep Thinking Params | Edit `deep_thinking/` config only | `deep-think-trace` skill shows improved logic traces. |
| **Stability** | Regression Suite | Read-only graph check | `pytest` suite passes for `notes` mode without 503 errors. |
| **UX** | Visualize Graph Nodes | No backend API changes | `webapp` builds; Force Graph renders mock data correctly. |

## 3. High-Leverage Skills (`.agent/skills/`)

**Goal:** Encode recurring workflows into programmable "subroutines" (Skills) that travel with the codebase.

**Action Item:**
- [ ] Create directory `.agent/skills/`.
- [ ] Implement the following skill subdirectories:

### Skill 1: `obsidian-index-maintenance`
*   **Path:** `.agent/skills/obsidian-index-maintenance/`
*   **Goal:** Synchronize the local Obsidian vault with vector and graph stores.
*   **Key Files:**
    *   `SKILL.md`: Instructions to use `src/indexing/index_vault.py` and `./Scripts/indexing/index_with_lightrag.sh`.
    *   **Constraint:** Always validate frontmatter metadata. Require `EMBEDDING_CLEAR_TOKEN` for destructive ops.

### Skill 2: `rag-eval-runner`
*   **Path:** `.agent/skills/rag-eval-runner/`
*   **Goal:** Evaluate search quality using the knowledge graph.
*   **Key Files:**
    *   `SKILL.md`: Instructions to run `obsidian_graph_query` against `Documentation/KNOWLEDGE_GRAPH_TEST_PROMPTS.md`.
    *   **Result:** Compare "match strength" against vector-only results.

### Skill 3: `gateway-deployment`
*   **Path:** `.agent/skills/gateway-deployment/`
*   **Goal:** Manage the API Gateway and service containers.
*   **Key Files:**
    *   `SKILL.md`: Instructions for `docker compose up -d graph-service`.
    *   **Validation:** Verify endpoints at `http://localhost:4000/api/v1/health` after every change.

### Skill 4: `deep-think-trace`
*   **Path:** `.agent/skills/deep-think-trace/`
*   **Goal:** Debug and verify "Deep Thinking" reasoning chains (Planner/Supervisor/Reflector).
*   **Key Tools:** `pytest tests/deep_thinking -k "test_trace"`, `debug_search.py`.
*   **Instruction:** Run specific reasoning scenarios and capture the `stdout` trace to ensure the Planner is selecting correct tools.

### Skill 5: `full-stack-integration`
*   **Path:** `.agent/skills/full-stack-integration/`
*   **Goal:** Ensure the entire stack (Frontend -> Gateway -> Graph -> Chroma) is communicating.
*   **Key Tools:** `tests/integration/`.
*   **Instruction:** Run before any major PR merge to prevent 503 regression.

## 4. Guardrails & Command Whitelist

**Goal:** Define a safe command surface for autonomous agents, relying on CI for final validation.

### 4.1 Command Whitelist
Antigravity's shell access will be prioritized for these "safe" commands:

*   **Search/Test:**
    *   `curl` (for API testing)
    *   `python src/indexing/index_vault.py`
    *   `pytest` (where applicable)
*   **Infrastructure:**
    *   `docker compose build`
    *   `docker compose up` (non-destructive starts)
*   **Vault Ops:**
    *   `bash ./Scripts/indexing/index_with_lightrag.sh`

### 4.2 Security Constraints
*   **CI Arbiter:** Agents can open PRs/branches; CI pipelines (GitHub Actions) are the final validity check.
*   **Secret Safety:** Ensure `.env` (containing `EMBEDDING_CLEAR_TOKEN`, Tavily API keys) is strictly `gitignored`.
*   **Destructive Ops:** Explicitly configure Antigravity to Pause on destructive commands (like `rm -rf` on data directories outside of agreed scripts).
