# MCP Tool Catalog

Authoritative inventory of tools exposed by the unified MCP server
(`src/mcp/obsidian_rag_unified_mcp.py`). Tool names below are the canonical
identifiers Claude Desktop / ChatGPT Desktop / connector clients see.

For setup, see `Documentation/integrations/mcp/MCP_SETUP_INSTRUCTIONS.md`.

## Vault Search

| Tool | Source of truth | Notes |
| --- | --- | --- |
| `obsidian_semantic_search` | Embedding service (ChromaDB) | 1–10 results, snippets |
| `search_vault_full` | ChromaDB → vault disk | Returns full note text; can extract embedded PDFs |
| `search_vault_text` | Vault disk only | Literal text or regex; supports `path` scoping and grep-style context lines |
| `obsidian_search_mode` | Gateway (`POST /api/v1/query`) | Modes: `ask`, `research`, `investigate` (legacy aliases accepted) |
| `obsidian_unified_query` | Gateway | Picks mode automatically based on query shape |

## Vault File Access

| Tool | Operation |
| --- | --- |
| `get_vault_path` | Returns the active vault root and capture root paths |
| `read_vault_note` | Read a single note by vault-relative path |
| `batch_read_vault_notes` | Read multiple notes in one call |
| `update_vault_note` | Replace the body of an existing note (frontmatter is preserved) |
| `create_vault_note` | Create a new note at a specified path |
| `read_attachment_text` | Extract text from a PDF attachment |

## Vault Health & Hygiene

| Tool | Purpose |
| --- | --- |
| `obsidian_vault_stats` | Document/entity/relationship counts and vault root path |
| `obsidian_index_health` | Stale or missing index-cache entries; helps diagnose path drift |
| `scan_vault_content_warnings` | Flags repeated large blocks (duplicate/stale content) |

## Capture & Note Creation

| Tool | Purpose |
| --- | --- |
| `capture_note` | Append a freeform note into the inbox capture root |
| `summarize_url_to_capture` | Fetch a URL, summarize, save to inbox |
| `summarize_youtube_to_capture` | Fetch a YouTube transcript, summarize, save to inbox |
| `apply_existing_tags_frontmatter_only` | Add already-known vault tags to frontmatter (no body edits) |

See `Documentation/reference/architecture/CAPTURE_AND_INBOX.md` for the
implementation details and the manual end-to-end workflow.

## Knowledge Graph

These tools call the internal NetworkX graph service first and fall back to a
local pickle when the service is unreachable. They are part of the legacy
internal stack — see `Documentation/reference/architecture/GRAPH_STACK_RETIREMENT_MAP.md`.

| Tool | Purpose |
| --- | --- |
| `obsidian_graph_query` | Advanced/internal graph query |
| `get_entity_info` | Entity details (descriptions, neighbors) |
| `find_entity_path` | Connections between two entities |
| `search_entities` | Substring search over entity labels |
| `get_graph_stats` | Graph structural statistics |

## Compatibility Aliases

The server still answers to a few legacy tool names for clients that haven't
been updated:

| Legacy alias | Maps to |
| --- | --- |
| `search_vault` | `obsidian_semantic_search` |
| `get_vault_stats` | `obsidian_vault_stats` |
| `query_knowledge_graph` | `obsidian_graph_query` |

## Choosing the Right Tool

Quick decision rules (matches the guidance in `USER_MANUAL.md` §10):

- **New / non-indexed note?** Use `search_vault_text` first, then `read_vault_note` / `batch_read_vault_notes`.
- **Need a synthesized answer?** Use `obsidian_search_mode` with `mode=ask` (fast) or `mode=research` (grounded).
- **Need long-form, multi-step analysis?** Route through the gateway WebSocket (`investigate`) — most clients access it via `obsidian_search_mode` with `mode=investigate`, which proxies to the WebSocket internally.
- **Editing an existing note?** `read_vault_note` → modify in your client → `update_vault_note`.
- **Capturing a quick note?** Use `capture_note` (or one of the URL/YouTube summarizers).

## Source

All names and shapes are read from the `list_tools()` registration in
`src/mcp/obsidian_rag_unified_mcp.py`. When the implementation drifts, update
that file first, then this catalog.
