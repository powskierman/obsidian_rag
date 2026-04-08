# AGENTS.md

This file is mirrored across `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md` so the same instructions load in any AI environment.

This project uses GitHub Spec Kit and the Specify CLI to implement Spec‑Driven Development (SDD). AI agents (Gemini CLI, Codex, Antigravity, and others) use the conventions here to read specs, plans, and tasks and to execute project workflows in a consistent way.

## Machine roles

These roles are shared across all agents and should be treated as the source of truth for where services live and where to run commands.

- **Canmore (Mac mini M4 Pro)**  
  Always‑on infrastructure node. Runs `obsidian_rag` and hosts the canonical, triple‑indexed Obsidian vault used for RAG; this vault is synchronized bidirectionally with the MacBook and is the primary RAG data source.

- **Lobster (Mac mini M1)**  
  OpenClaw and memory node. Runs OpenClaw, the `openclaw_memory` project, Lobster’s Obsidian memory vault, and Speckit as the spec/governance layer for spec‑driven development workflows.

- **MacBook (M4 Max)**  
  Thin client and occasional compute node. Used to send tagged prompts into OpenClaw and consume answers; it may host heavier models when available, but does not run long‑lived indexing or RAG services.

When assigning work, prefer:
- RAG and vault indexing work → **Canmore**.  
- OpenClaw orchestration and long‑running memory workflows → **Lobster**.  
- Ad‑hoc heavy model runs or interactive coding sessions → **MacBook**, when online.

## Current Supported Agents

| Agent               | Directory           | Format   | CLI Tool | Description                                                  |
| ------------------- | ------------------- | -------- | -------- | ------------------------------------------------------------ |
| Gemini CLI          | `.gemini/commands/` | TOML     | `gemini` | Google Gemini CLI used as a primary SDD coding agent for this repo. |
| Codex (ChatGPT CLI) | `.codex/commands/`  | MD/TOML  | `codex`  | ChatGPT‑based CLI used for running Spec Kit flows and ad‑hoc orchestration. |
| Antigravity         | `.agent/workflows/` | Markdown | N/A      | Antigravity IDE/workspace that consumes Spec Kit specs, plans, tasks, and custom workflows for `obsidian_rag`. |

These directories should live at the repository root, alongside `directives/`, `Scripts/`, and `src/`.

## Agent Categories

### CLI‑based agents

Require a command‑line tool:

- **Gemini CLI**: `gemini` executable configured as a Spec Kit agent (matching its `AGENT_CONFIG` name).  
- **Codex (ChatGPT CLI)**: `codex` executable used to run Spec Kit prompts and commands from this repository.

### IDE / workspace agents

- **Antigravity**: Google Antigravity IDE pointing at this repository. It reads Spec Kit artifacts (`spec/`, plan/task files such as `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`) and uses `.agent/workflows/` to coordinate multi‑agent execution, often delegating to Gemini CLI or Codex.

## Command File Formats

### Gemini CLI commands

- Location: `.gemini/commands/` at the repo root (sibling to `directives/`, `Scripts/`, `src/`).  
- Format: TOML command files that wrap Spec Kit flows and pass arguments using placeholders such as `{{args}}`, consistent with Spec Kit’s Gemini examples.  
- Typical usage:  
  - `gemini run .gemini/commands/specify.toml` to drive `/speckit.specify`, `/speckit.plan`, `/speckit.tasks` and related commands for `obsidian_rag`.

Each Gemini command file should clearly state:

- Which Spec Kit command(s) it orchestrates (`specify`, `plan`, `tasks`, `implement`).  
- Expected arguments (for example, paths in `directives/`, `src/`, or `Scripts/`).  
- Any environment variables or project‑specific flags required.

### Codex (ChatGPT CLI) commands

- Location: `.codex/commands/` at the repo root.  
- Format: Markdown or TOML describing prompts that call Spec Kit commands and operate on the SDD artifacts (for example, files in `spec/`, plan/task outputs).  
- Typical usage:  
  - `codex run .codex/commands/specify.md` (or equivalent) to step through `/speckit.specify`, `/speckit.plan`, `/speckit.tasks` from the Codex CLI.

Codex command files should:

- Describe how to interpret Spec Kit artifacts (spec, plan, tasks) for `obsidian_rag`.  
- Reference directives in `directives/` rather than inventing new workflows.  
- Call out when to hand off work to deterministic scripts in `Scripts/`.

### Antigravity workflows

- Location: `.agent/workflows/` at the repo root.  
- Format: Markdown workflows that tell Antigravity and its sub‑agents to:  
  - Read specs and plans from Spec Kit directories (for example, `spec/` plus `/speckit.*` artifacts generated here).  
  - Execute implementation tasks in phases, delegating work to Gemini CLI or Codex sub‑agents configured within the Antigravity workspace.  
  - Use the directory layout above (`.gemini/commands/`, `.codex/commands/`, `.agent/skills/`) as the canonical routing map.

## Project Skills for obsidian_rag

This project defines reusable Agent Skills under `.agent/skills/`. Each skill is a folder with a `SKILL.md` file that packages focused instructions and, optionally, scripts or references.

Current skills:

- `comprehensive-eval-audit`: Audit all supported search modes (Vector, Cascading, Deep Thinking) for efficacy and latency. Goal: Generate a status report (`Documentation/operations/quality/SEARCH_MODE_AUDIT.md`) detailing functionality and performance of search strategies.
- `deep-think-trace`: Debug and verify “Deep Thinking” reasoning chains. Goal: Verify that the “System 2” reasoning engine (Planner, Supervisor, Reflector) is selecting correct tools and generating valid plans.
- `full-stack-integration`: Ensure the entire stack is communicating correctly (Frontend → Gateway → Graph → Chroma). Goal: Prevent regressions like 503 errors or broken UI states by running integration tests across the lifecycle.
- `gateway-deployment`: Manage the API Gateway and service containers. Goal: Safely deploy, restart, and validate backend services (API Gateway, Graph Service) without downtime or breakage.
- `obsidian-index-maintenance`: Synchronize the local Obsidian vault with vector and graph stores safely. Goal: Ensure the search index is up‑to‑date with the latest notes while preventing data corruption.
- `rag-eval-runner`: Evaluate search quality using the knowledge graph and test prompts. Goal: Quantitatively and qualitatively assess if search improvements are working by comparing Vector vs. Hybrid results.

Antigravity and compatible agents can load these skills automatically from `.agent/skills/` when relevant to a task.

## Git Workflow

For safe multi‑Mac sync (Canmore ↔ MacBook) use the Git workflow in `Documentation/git-sync-macs.md`; do not use iCloud Drive as the primary project workspace.
