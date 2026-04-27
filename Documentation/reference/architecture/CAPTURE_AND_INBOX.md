# Capture & Inbox

Quick-capture is implemented as a set of MCP tools that write into a fixed
"inbox" folder inside the vault. There is no background watcher today — the
"AI loop" described in `SECOND_BRAIN_ARCHITECTURE.md` is a proposal, not a
running service.

This doc covers what is actually wired up and how the pieces interact.

## Capture Root

The capture tools resolve a single "capture root" inside the vault, normally
`00_Inbox/`. The path is derived in `src/mcp/obsidian_rag_unified_mcp.py`:

- `_get_capture_root()` — looks up the configured root (env override allowed).
- `_ensure_capture_root()` — creates the folder if it doesn't yet exist.
- `_resolve_capture_note_path(raw_path)` — locks writes inside the capture root
  to prevent escapes.

Notes that are saved end up at `<vault>/<capture_root>/<slugified-title>.md`,
with the timestamp folded into the slug to avoid collisions.

## Capture Template

`Documentation/operations/notes/New Note Template.md` is the rendered shape:

- `aliases`, `created`, `tags`, `Backlink` frontmatter
- Sections: `Main Idea`, `References`, `Notes`, `Related Notes`,
  `Questions / Ideas for Further Exploration`, `To-Do`, `Smart Connections Insights`

`_load_capture_template()` reads this file at runtime, and
`_render_capture_note(template, values)` substitutes the per-capture content.

## Tools

### `capture_note`

Create a freeform note in the inbox. Body text is rendered into the template's
`Notes` section.

Inputs:
- `title` — used for the filename slug; falls back to a timestamp if blank.
- `content` — markdown body.
- `tags` (optional) — vault-existing tags to apply via the
  `apply_existing_tags_frontmatter_only` path.

### `summarize_url_to_capture`

Fetches the URL, extracts text, summarizes to bullet points, and writes the
result through `capture_note`. The summarizer prefers OpenAI/Gemini when keys
are configured; otherwise falls back to a heuristic point-form pass.

Quality gates implemented:
- Fragments shorter than the configured threshold are dropped.
- Each bullet is run through `_compress_summary_point` for length normalization.
- A synthesized one-paragraph "details" block is generated from the bullets via
  `_synthesize_details_paragraph` and quality-gated against the source.

### `summarize_youtube_to_capture`

Same shape, but the source is a YouTube transcript. Pipeline:

1. `_extract_youtube_video_id(url)` — pulls the canonical video id.
2. `_fetch_youtube_title(url)` — best-effort title fetch.
3. `_fetch_youtube_transcript(video_id)` — transcript pull.
4. `_summarize_youtube_transcript_to_points(text, max_points)` — transcript-aware
   summarization with `_sanitize_transcript_fragment` and
   `_looks_like_transcript_noise` filters.
5. `capture_note` to write into the inbox.

### `apply_existing_tags_frontmatter_only`

Adds tags to a note's frontmatter **only if those tags already exist somewhere
in the vault**. The tool will not invent new tags. Implementation:

- `_collect_existing_tags()` scans the vault once to build the candidate set.
- `_score_tags_for_note(text, candidates, max_tags)` ranks the existing tags
  by overlap with the note's body and chooses up to `max_tags`.
- Only frontmatter is written; body text is left untouched.

## Manual Workflow Today

Until the auto-loop is implemented, the recommended pattern is:

1. Trigger one of the capture tools from Claude Desktop / ChatGPT / a script.
2. Optionally run `apply_existing_tags_frontmatter_only` to surface vault tags.
3. Manually move the inbox note to its final folder when you're ready.
4. Let the next indexing pass pick it up — or run
   `./Scripts/indexing/update_vector_db.sh` if you want it searchable
   immediately.

## Related Code

- `src/mcp/obsidian_rag_unified_mcp.py` — all capture/summarize tools.
- `Documentation/operations/notes/New Note Template.md` — template loaded at
  runtime.
- `Documentation/integrations/mcp/MCP_SETUP_INSTRUCTIONS.md` — how to wire the
  MCP server into Claude / ChatGPT desktop clients.
- `Documentation/reference/architecture/SECOND_BRAIN_ARCHITECTURE.md` — the
  larger proposed design (not implemented).
