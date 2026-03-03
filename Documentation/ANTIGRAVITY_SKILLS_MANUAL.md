# Antigravity Skills Manual: `obsidian_rag` Edition

> [!NOTE]
> This manual is auto-generated to guide agents and users in leveraging the "Antigravity Skills" tailored for the `obsidian_rag` project. These skills are specialized workflow packages located in `.agent/skills/`.

## 1. Overview

Antigravity Skills are modular "capability packs" that allow agents to perform complex, multi-step operations reliability. They bridge the gap between simple tool use and high-level architectural goals.

**Location**: All skills are stored in `.agent/skills/`

## 2. Skill Catalog

### A. Lifecycle & Planning

#### 1. Eval-Driven Design
**Purpose**: Defines clarity *before* code is written. "Test-Driven Development" for Agents.
- **When to Use**: Before starting any new feature or complex refactor.
- **How to Use**:
  1.  Create `.agent/evals/[feature_name].md`
  2.  Define **Capability Evals** (what must happen) and **Regression Evals** (what must not break).
  3.  Run these evals during implementation.
- **Example in `obsidian_rag`**:
  - *Scenario*: Adding a new "Citation Mode" to search.
  - *Action*: Create `.agent/evals/citation_mode.md`. Define a capability: `query="What is X?"` -> `expect source="[File.md]"`

#### 2. Implementation Planner
**Purpose**: Bridges logic from "What" (Specs) to "How" (Code changes).
- **When to Use**: When you have a requirement/spec but need a concrete file-level plan.
- **How to Use**:
  1.  Read the spec (e.g., `Documentation/spec.md`).
  2.  Generate `implementation_plan.md` in artifacts.
  3.  Detail every file add/modify/delete.
- **Example in `obsidian_rag`**:
  - *Scenario*: Implementing the "Deep Research" WebSocket endpoint.
  - *Action*: Read requirements, then output a plan listing changes to `src/services/api_gateway.py`, `deep_thinking/orchestrator.py`.

### B. Development & Debugging

#### 3. Deep Think Trace
**Purpose**: Debugging the "System 2" reasoning engine (Planner/Supervisor).
- **When to Use**: When "Deep Thinking" loops endlessly, selects wrong tools, or fails to answer.
- **How to Use**:
  1.  Run `pytest tests/deep_thinking -k "test_trace" -s`.
  2.  Inspect logs for `[Planner]` decisions.
  3.  Use `deep_thinking/debug_probe.py` for focused manual tests.
- **Example in `obsidian_rag`**:
  - *Scenario*: Deep Thinking keeps searching Google for "local notes" queries.
  - *Action*: Run the trace, see that `tools.py` description for `obsidian_search` is unclear, update prompt.

#### 4. Full Stack Integration
**Purpose**: The "Smoke Test" for the entire system (Frontend -> Gateway -> Graph).
- **When to Use**: Before merging a PR or after significant backend changes.
- **How to Use**:
  1.  Ensure Docker is up: `docker compose ps`
  2.  Run `pytest tests/integration/`
  3.  Run a manual `curl` to `localhost:4000/api/v1/query`.
- **Example in `obsidian_rag`**:
  - *Scenario*: You changed the `GraphService` response format.
  - *Action*: Run integration tests to ensure the Frontend doesn't crash on the new JSON structure.

### C. Operations & Maintenance

#### 5. Gateway Deployment
**Purpose**: Managing the Dockerized backend services.
- **When to Use**: When `src/services` code changes and needs to be reflected in the running container.
- **How to Use**:
  1.  `docker compose build graph-service`
  2.  `docker compose up -d graph-service`
  3.  Verify: `curl http://localhost:4000/api/v1/health`
- **Example in `obsidian_rag`**:
  - *Scenario*: Updated `networkx_graph_builder.py`.
  - *Action*: Rebuild and restart the container to load the new logic.

#### 6. Obsidian Index Maintenance
**Purpose**: Keeping the Vector/Graph database in sync with your actual Obsidian Vault.
- **When to Use**: When you've added new notes and need them searchable.
- **How to Use**:
  - *Routine*: `python src/indexing/index_vault.py --refresh`
  - *Full Reset*: `bash ./Scripts/indexing/index_with_lightrag.sh` (Caution!)
- **Example in `obsidian_rag`**:
  - *Scenario*: Added 50 new notes about "AI Agents".
  - *Action*: Run the update script so `query="AI Agents"` returns the new content.

#### 7. Comprehensive Eval Audit
**Purpose**: Health check for ALL search modes.
- **When to Use**: If users report "Search is broken" or "Vector works but Graph is empty".
- **How to Use**:
  1.  Run `python Scripts/debug/audit_search_modes.py`
  2.  Compare outcomes against `Documentation/Features/SEARCH_MODES_GUIDE.md`.
- **Example in `obsidian_rag`**:
  - *Scenario*: User says "Hybrid search returns 503".
  - *Action*: Run audit. If audit shows `Vector: PASS`, `Graph: FAIL`, you know the issue is isolated to the Graph Service.

#### 8. RAG Eval Runner
**Purpose**: Quality assurance for retrieval accuracy.
- **When to Use**: To verify if an embedding model change or graph algorithm change actually improved results.
- **How to Use**:
  1.  Select queries from `Documentation/KNOWLEDGE_GRAPH_TEST_PROMPTS.md`.
  2.  Run queries in `vector` vs `hybrid` mode.
  3.  Log results in your task notes or PR description.
- **Example in `obsidian_rag`**:
  - *Scenario*: Switched from `all-MiniLM-L6-v2` to `text-embedding-3-small`.
  - *Action*: Run standard prompts to see if "Match Strength" increased.

## 3. Recommended Workflow

For a standard feature implementation in `obsidian_rag`, follow this "Skill Chain":

1.  **Start**: **Implementation Planner** to map out the work.
    *   *Result*: `implementation_plan.md`
2.  **Define Success**: **Eval-Driven Design** to set the goalposts.
    *   *Result*: `.agent/evals/my_feature.md`
3.  **Build**: (Coding using standard tools)
4.  **Deploy**: **Gateway Deployment** (if backend changed).
5.  **Verify**:
    *   **Full Stack Integration** (does it crash?)
    *   **Comprehensive Eval Audit** (did I break search?)
    *   **RAG Eval Runner** (is the answer quality good?)
6.  **Finish**: Update documentation.

## 4. Troubleshooting Map

| Symptom | Relevant Skill |
| :--- | :--- |
| "503 Service Unavailable" | **Gateway Deployment** (Check logs/health), **Full Stack Integration** |
| "Search returns 0 results" | **Obsidian Index Maintenance** (Re-index), **Comprehensive Eval Audit** |
| "LLM is talking nonsense" | **Deep Think Trace** (Check reasoning), **RAG Eval Runner** (Check context quality) |
| "I don't know where to start" | **Implementation Planner** |
