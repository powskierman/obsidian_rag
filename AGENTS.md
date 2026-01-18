<INSTRUCTIONS>
## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.
### Available skills
- skill-creator: Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Codex's capabilities with specialized knowledge, workflows, or tool integrations. (file: /Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Tech/AI/Agents/codex/skills/.system/skill-creator/SKILL.md)
- skill-installer: Install Codex skills into $CODEX_HOME/skills from a curated list or a GitHub repo path. Use when a user asks to list installable skills, install a curated skill, or install a skill from another repo (including private repos). (file: /Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Tech/AI/Agents/codex/skills/.system/skill-installer/SKILL.md)
- obsidian-rag-indexing: Reindex and manage obsidian_rag databases (Chroma vector, NetworkX graph, LightRAG). Use for requests to reindex, resume indexing, check progress, handle caches/logs, or move databases between machines. (file: /Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Tech/AI/Agents/chatgpt/skills/obsidian-rag-indexing/SKILL.md)
- obsidian-rag-mcp: Configure and troubleshoot obsidian_rag MCP servers for ChatGPT/OpenAI desktop or other MCP clients. Use for MCP server disconnected errors, log inspection, venv dependency issues, and config updates. (file: /Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Tech/AI/Agents/chatgpt/skills/obsidian-rag-mcp/SKILL.md)
- obsidian-rag-medical: Review medical notes in obsidian_rag (lymphoma, PET/CT scans, blood work) and produce a grounded timeline-based assessment from vault sources. Use for scan summaries, lymphoma assessments, and medical note reviews. (file: /Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Tech/AI/Agents/chatgpt/skills/obsidian-rag-medical/SKILL.md)
- obsidian-rag-search: Explain and select obsidian_rag search modes (vector, graph, hybrid, LightRAG, deep thinking). Use when asked which mode to use, why a query missed, or how to troubleshoot retrieval quality. (file: /Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Tech/AI/Agents/chatgpt/skills/obsidian-rag-search/SKILL.md)
### How to use skills
- Discovery: The list above is the skills available in this session (name + description + file path). Skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR the task clearly matches a skill's description shown above, you must use that skill for that turn. Multiple mentions mean use them all. Do not carry skills across turns unless re-mentioned.
- Missing/blocked: If a named skill isn't in the list or the path can't be read, say so briefly and continue with the best fallback.
- How to use a skill (progressive disclosure):
  1) After deciding to use a skill, open its `SKILL.md`. Read only enough to follow the workflow.
  2) If `SKILL.md` points to extra folders such as `references/`, load only the specific files needed for the request; don't bulk-load everything.
  3) If `scripts/` exist, prefer running or patching them instead of retyping large code blocks.
  4) If `assets/` or templates exist, reuse them instead of recreating from scratch.
- Coordination and sequencing:
  - If multiple skills apply, choose the minimal set that covers the request and state the order you'll use them.
  - Announce which skill(s) you're using and why (one short line). If you skip an obvious skill, say why.
- Context hygiene:
  - Keep context small: summarize long sections instead of pasting them; only load extra files when needed.
  - Avoid deep reference-chasing: prefer opening only files directly linked from `SKILL.md` unless you're blocked.
  - When variants exist (frameworks, providers, domains), pick only the relevant reference file(s) and note that choice.
- Safety and fallback: If a skill can't be applied cleanly (missing files, unclear instructions), state the issue, pick the next-best approach, and continue.
</INSTRUCTIONS>
