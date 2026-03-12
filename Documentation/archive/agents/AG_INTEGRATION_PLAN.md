# Antigravity Integration Plan: "Everything Claude Code"

This document outlines the strategy for integrating the powerful autonomous coding workflows from [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) into the `obsidian_rag` Antigravity workspace.

## Executive Summary

"Everything Claude Code" is a battle-tested configuration for autonomous coding agents, centered on **Eval-Driven Development (EDD)**, **Task Delegation (Agents/Personas)**, and **Structured Workflows (Skills)**. 

Integrating these concepts will transform `obsidian_rag`'s Antigravity layer from a simple task executor into a rigorous, self-correcting development system.

## 1. Core Integration Strategy

We will map the repository's concepts to Antigravity's existing structure:

| Everything Claude Code Concept | Antigravity Equivalent | Action |
| :--- | :--- | :--- |
| **Agents** (`agents/*.md`) | **Personas / Roles** | Adopt as "Role definitions" within Skills or Workflows. |
| **Skills** (`skills/*`) | **Skills** (`.agent/skills/*`) | Port high-value skills directly. |
| **Commands** (`commands/*.md`) | **Workflows** (`.agent/workflows/*.md`) | Convert slash commands into executable workflows. |
| **Eval Harness** (`skills/eval-harness`) | **Enhanced Eval Skill** | Upgrade `rag-eval-runner` to support `pass@k` metrics and strictly defined capability/regression tests. |

## 2. Recommended Skills to Port

### A. High Priority (Immediate Value)

1.  **Eval-Driven Development (EDD) Harness**
    *   **Source**: `skills/eval-harness` + `commands/eval.md`
    *   **Destination**: `.agent/skills/eval-driven-design/SKILL.md`
    *   **Value**: Formalizes "Success Criteria" into executable tests (`pass@k`). Critical for RAG accuracy.
    *   **Implementation**: Create a workflow that defines, runs, and reports on evals stored in `.agent/evals/`.

2.  **Implementation Planner**
    *   **Source**: `agents/planner.md` + `commands/plan.md`
    *   **Destination**: `.agent/skills/implementation-planner/SKILL.md`
    *   **Value**: Enforces a rigorous planning phase (Architecture -> Steps -> Risks) before any code is written. Matches the `implementation_plan` artifact usage but adds structure.

3.  **Code Reviewer Setup**
    *   **Source**: `agents/code-reviewer.md`
    *   **Destination**: `.agent/workflows/review-changes.md`
    *   **Value**: A dedicated workflow to "self-review" code against a checklist (Security, Performance, Style) before requesting user approval.

### B. Medium Priority (Enhancement)

4.  **TDD Workflow**
    *   **Source**: `skills/tdd-workflow`
    *   **Destination**: `.agent/skills/tdd-workflow/SKILL.md`
    *   **Value**: Standardizes the "Red-Green-Refactor" loop for Python modules.

5.  **Continuous Learning**
    *   **Source**: `skills/continuous-learning`
    *   **Destination**: `.agent/skills/pattern-extraction/SKILL.md`
    *   **Value**: A workflow to extract successful patterns from completed tasks and save them to a `patterns.md` library.

## 3. Application to `obsidian_rag`

### Use Case: "Deep Thinking" Trace tuning
*   **Current State**: Ad-hoc editing of `planner.py`.
*   **With Integration**: 
    1.  Use **Implementation Planner** to define the changes.
    2.  Use **EDD Harness** to define a "Capability Eval" (e.g., "Must correctly choose 'Graph Search' for 'X' query").
    3.  Run the implementation loop until `pass@3 > 90%`.

### Use Case: Graph Visualization (Frontend)
*   **Current State**: "Visualize Graph Nodes" is a TODO in Backlog.
*   **With Integration**:
    1.  Run `workflows/plan-feature` to design the component structure.
    2.  Use `workflows/tdd` to build the components.
    3.  Use `workflows/review-changes` to check for React best practices (re-renders, memoization).

## 4. Next Steps

1.  **Approve Plan**: User confirms this direction.
2.  **Scaffold**: Create `.agent/evals/` directory.
3.  **Port Skills**: Create the SKILL.md files for the High Priority items.
4.  **Update Backlog**: Add these setup tasks to `AG_BACKLOG.md`.
