# Antigravity Task Backlog

This file serves as the primary task queue for Antigravity agents. Each item includes context, constraints, and acceptance criteria to ensure autonomous execution is safe and effective.

## 1. Infra & Maintenance
| Status | Task | Context / Paths | Constraints | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **TODO** | Automate DB rebuilds | `Scripts/index_with_lightrag.sh` | No Git tracking of `lightrag_db` | Script runs successfully; verify `lightrag_db` is present, populated, and ignored by git. |
| **TODO** | Gateway Deployment Check | `docker-compose.yml`, `src/services/` | Non-destructive restart | `docker compose up -d` passes; `/health` endpoint returns 200 OK. |

## 2. Indexing & Data
| Status | Task | Context / Paths | Constraints | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **TODO** | Incremental Upsert Logic | `src/indexing/index_vault.py` | Use `--refresh` flag logic | Stale chunks are removed; new notes are indexed; metadata is validated. |

## 3. Reasoning & Inference (Track 2)
| Status | Task | Context / Paths | Constraints | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **TODO** | Tune Deep Thinking Params | `deep_thinking/config`, `deep_thinking/planner.py` | Edit config only, no core logic changes | `deep-think-trace` skill shows improved tool selection; Test `test_trace` passes. |
| **TODO** | Optimize Hybrid Mode | `src/services/search_service.py` | Follow `CASCADING_FLOW.md` | Queries return both Graph answer and vector sources; Response includes "sources" field. |

## 4. Stability & Testing
| Status | Task | Context / Paths | Constraints | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **TODO** | Regression Suite | `tests/integration/` | Read-only graph check | `pytest` suite passes for `notes` mode without 503 errors. |

## 5. UX & Frontend (Track 4)
| Status | Task | Context / Paths | Constraints | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **TODO** | Visualize Graph Nodes | `webapp/src/components/Graph/` | No backend API changes | `webapp` builds; Force Graph renders mock data correctly. |

---
*Agents: When picking a task, mark Status as IN_PROGRESS. When finished, mark as DONE and link the PR or Commit hash.*
