# Obsidian_RAG V2.0 Roadmap

Goal: reduce capture + indexing friction while improving trust and provenance for RAG syntheses.

## Guiding Principles
- Default to safe behavior: no destructive edits; use dry-run and logs.
- Work with existing vault folders; ask when no clear fit exists.
- Make changes reversible (backups, logs, and clear audit trails).
- Keep outputs small, frequent, and actionable.

## Phase 0: Baseline (prep)
- Inventory existing vault folders and note templates.
- Decide minimal frontmatter schema (whitelist fields, no overwrite by default).
- Define confidence threshold and routing rules.

Deliverable
- `Documentation/V2.0/SCHEMA.md` with frontmatter fields, routing rules, and thresholds.

## Phase 1: Frictionless Capture + Safe Routing
- Add a lightweight “Inbox” capture path (CLI or simple local endpoint).
- Route captures into existing vault folders; if unclear, ask the user to pick or create a folder.
- Apply frontmatter in a safe mode:
  - Only add missing fields from a whitelist.
  - Never overwrite existing frontmatter by default.
  - Log every change to an audit file.

Acceptance
- New capture takes < 10 seconds from paste to file.
- No existing frontmatter is overwritten unless explicitly approved.
- Each routed note includes source + confidence + timestamp.

## Phase 2: Always-On Incremental Indexing
- Extend the file watcher to reindex on create/modify.
- Track hashes and modification time for incremental updates.
- Add a small index state DB (sqlite or json) to prevent reprocessing.

Acceptance
- New or changed notes are indexed within 60 seconds.
- Unchanged notes are not re-embedded.
- System reports a clear “indexed / skipped / failed” summary.

## Phase 3: Synthesis Capture + Provenance
- Add a one-click “Save synthesis” action from UI/CLI/MCP.
- Store the response, sources, and your short judgment in a new note.
- Low-confidence outputs go into a Drafts area instead of main folders.

Acceptance
- Synthesis notes include citations to source notes.
- Drafts are clearly marked and easy to promote.

## Phase 4: Trust + Fix Loop
- Maintain an audit ledger of routing decisions and confidence.
- Add a simple “Fix routing” action that reclassifies and updates the ledger.

Acceptance
- Every routed note can be traced back to raw input.
- Fixing a mistake takes under 1 minute.

## Optional Phase 5: Proactive Surfacing (Digest)
- Daily digest (<150 words) and weekly review (<250 words).
- Prioritize open loops, next actions, and recent changes.

Acceptance
- Digest can be generated on demand and scheduled.

## Open Questions
- Which folders are the canonical destinations in your vault?
- What frontmatter fields are safe to auto-apply?
- Where should Drafts live (folder path)?
