# AGENTS.md

This file is mirrored across `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md` so the same instructions load in any AI environment.

This project uses GitHub Spec Kit and the Specify CLI to implement Spec‑Driven Development (SDD). AI agents (Gemini CLI, Codex, Antigravity, and others) use the conventions here to read specs, plans, and tasks and to execute project workflows in a consistent way.[web:1][web:31]

## Current Supported Agents

| Agent                | Directory              | Format   | CLI Tool | Description |
|----------------------|------------------------|----------|----------|-------------|
| Gemini CLI           | `.gemini/commands/`    | TOML     | `gemini` | Google Gemini CLI used as a primary SDD coding agent for this repo.[web:1][web:21] |
| Codex (ChatGPT CLI)  | `.codex/commands/`     | MD/TOML  | `codex`  | ChatGPT‑based CLI used for running Spec Kit flows and ad‑hoc orchestration. |
| Antigravity          | `.agent/workflows/`    | Markdown | N/A      | Antigravity IDE/workspace that consumes Spec Kit specs, plans, tasks, and custom workflows for obsidian_rag.[web:20][web:32][web:35] |

These directories should live at the repository root, alongside `directives/`, `Scripts/`, and `src/`.

## Agent Categories

### CLI‑based agents

Require a command‑line tool:

- **Gemini CLI**: `gemini` executable configured as a Spec Kit agent (matching its `AGENT_CONFIG` name).[web:1][web:21]  
- **Codex (ChatGPT CLI)**: `codex` executable used to run Spec Kit prompts and commands from this repository.

### IDE / workspace agents

- **Antigravity**: Google Antigravity IDE pointing at this repository. It reads Spec Kit artifacts (`spec/`, plan/task files such as `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`) and uses `.agent/workflows/` to coordinate multi‑agent execution, often delegating to Gemini CLI or Codex.[web:20][web:32][web:35]

## Command File Formats

### Gemini CLI commands

- Location: `.gemini/commands/` at the repo root (sibling to `directives/`, `Scripts/`, `src/`).  
- Format: TOML command files that wrap Spec Kit flows and pass arguments using placeholders such as `{{args}}`, consistent with Spec Kit’s Gemini examples.[web:1][web:21]  
- Typical usage:  
  - `gemini run .gemini/commands/specify.toml` to drive `/speckit.specify`, `/speckit.plan`, `/speckit.tasks` and related commands for obsidian_rag.[web:20][web:31]

Each Gemini command file should clearly state:

- Which Spec Kit command(s) it orchestrates (specify, plan, tasks, implement).  
- Expected arguments (for example, paths in `directives/`, `src/`, or `Scripts/`).  
- Any environment variables or project‑specific flags required.

### Codex (ChatGPT CLI) commands

- Location: `.codex/commands/` at the repo root.  
- Format: Markdown or TOML describing prompts that call Spec Kit commands and operate on the SDD artifacts (for example, files in `spec/`, plan/task outputs).  
- Typical usage:  
  - `codex run .codex/commands/specify.md` (or equivalent) to step through `/speckit.specify`, `/speckit.plan`, `/speckit.tasks` from the Codex CLI.

Codex command files should:

- Describe how to interpret Spec Kit artifacts (spec, plan, tasks) for obsidian_rag.  
- Reference directives in `directives/` rather than inventing new workflows.  
- Call out when to hand off work to deterministic scripts in `Scripts/`.

### Antigravity workflows

- Location: `.agent/workflows/` at the repo root.  
- Format: Markdown workflows that tell Antigravity and its sub‑agents to:[web:20][web:32][web:35]  
  - Read specs and plans from Spec Kit directories (for example, `spec/` plus `/speckit.*` artifacts generated here).[web:31]  
  - Execute implementation tasks in phases, delegating work to Gemini CLI or Codex sub‑agents configured within the Antigravity workspace.  
  - Use the direct

## Project Skills for obsidian_rag

This project defines reusable Agent Skills under `.agent/skills/`. Each skill is a folder with a `SKILL.md` file that packages focused instructions and, optionally, scripts or references.

Current skills:

- `comprehensive-eval-audit`: Audit all search modes (Vector, Graph, Hybrid, Deep Thinking) for efficacy and latency. Goal: Generate a status report (Documentation/SEARCH_MODE_AUDIT.md) detailing functionality and performance of search strategies.
- `deep-think-trace`: Debug and verify "Deep Thinking" reasoning chains. Goal: Verify that the "System 2" reasoning engine (Planner, Supervisor, Reflector) is selecting correct tools and generating valid plans.
- `full-stack-integration`: Ensure the entire stack is communicating correctly (Frontend -> Gateway -> Graph -> Chroma). Goal: Prevent regressions like 503 errors or broken UI states by running integration tests across the lifecycle.
- `gateway-deployment`: SManage the API Gateway and service containers. Goal: Safely deploy, restart, and validate backend services (API Gateway, Graph Service) without downtime or breakage.
- `obsidian-index-maintenance`: Synchronize the local Obsidian vault with vector and graph stores safely. Goal: Ensure the search index is up-to-date with the latest notes while preventing data corruption.
- `rag-eval-runner`: Evaluate search quality using the knowledge graph and test prompts. Goal: Quantitatively and qualitatively assess if search improvements are working by comparing Vector vs. Hybrid results.

Antigravity and compatible agents can load these skills automatically from `.agent/skills/` when relevant to a task.[web:54][web:60]