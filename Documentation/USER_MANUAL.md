# Obsidian RAG User Manual

This manual is the practical, end-to-end guide for using `obsidian_rag` as a daily system. It is written for someone who wants to search, query, browse, and maintain an Obsidian vault through the local web UI, API, CLI, and MCP tools.

Use this document as the primary entry point. Use the linked docs for deeper reference.

## 1. What This System Does

`obsidian_rag` turns an Obsidian vault into a queryable knowledge system with four main access paths:

- **Webapp** for interactive searching and answer generation
- **API Gateway** for scripted HTTP queries
- **MCP server** for ChatGPT Desktop / Claude Desktop / connector workflows
- **CLI tools and scripts** for indexing, diagnostics, and direct local operations

The system combines:

- **Vector search** through ChromaDB for fast semantic retrieval
- **Cascading retrieval** through staged retrieval and synthesis
- **Deep research / deep thinking** for longer-running, agentic analysis
- **Direct vault file access** through MCP tools for exact text search and note editing workflows

## 2. Core Components

The default Docker stack exposes these services:

| Component | Purpose | Default Host Port |
| --- | --- | --- |
| Embedding service | Semantic indexing and vector retrieval | `8000` |
| LightRAG service | Internal graph/entity retrieval support | `8001` |
| Graph service | Internal graph retrieval support | `8002` |
| API gateway | Main search/query API | `4000` |
| MCP server | ChatGPT / Claude / connector tools | `8811` |
| Streamlit UI | Legacy/simple UI | `8501` |
| Next.js webapp | Main browser UI | `3030` |

## 3. Recommended Ways To Use It

Choose the interface based on the task:

| Goal | Best Interface |
| --- | --- |
| Ask normal vault questions | Webapp or API gateway |
| Use ChatGPT/Claude against the vault | MCP server |
| Find exact strings, code, or Mermaid blocks | MCP `search_vault_text` |
| Read or update existing notes from an agent workflow | MCP `read_vault_note`, `batch_read_vault_notes`, `update_vault_note` |
| Run a full reindex or diagnostics | Scripts under `Scripts/` |
| Quick semantic lookup from terminal | `./search_vault` |

Rule of thumb:

- Use **vector** for speed and broad semantic recall.
- Use **cascading** when you want a stronger synthesized answer.
- Use **deep research** when the task is open-ended or multi-step.
- Use **direct vault text search** when the note may be new, unindexed, code-heavy, or sensitive to literal text.

## 4. Before You Start

You need:

- A local clone of the repo
- Docker / Docker Compose
- A valid Obsidian vault path
- Optional provider API keys depending on your LLM setup

Minimum `.env` configuration:

```bash
OBSIDIAN_VAULT_PATH=/path/to/your/vault
ANTHROPIC_API_KEY=...   # optional
GEMINI_API_KEY=...      # optional
OPENROUTER_API_KEY=...  # optional
TAVILY_API_KEY=...      # optional
```

The single most important setting is:

- `OBSIDIAN_VAULT_PATH`

If this path is wrong, indexing, MCP note access, and most retrieval workflows will fail or behave inconsistently.

## 5. First-Time Setup

### 5.1 Start the stack

From the repo root:

```bash
docker compose up -d
```

### 5.2 Verify service health

Check the API gateway:

```bash
curl -s http://localhost:4000/api/v1/health
```

Check the MCP HTTP health route:

```bash
curl -s http://localhost:8811/health
```

### 5.3 Open the browser UI

Main webapp:

- `http://localhost:3030`

Legacy Streamlit UI:

- `http://localhost:8501`

### 5.4 Run your first query

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"nextion esp32","mode":"vector","max_results":5}'
```

If you get thin or empty results, you probably need indexing.

## 6. Indexing the Vault

Indexing is what makes semantic search and the higher-level retrieval stack useful.

### 6.1 Full indexing

Canonical full indexing entry point:

```bash
./Scripts/indexing/run_indexing.sh
```

This rebuilds:

- ChromaDB vector search
- NetworkX graph data
- LightRAG entity/relationship data

Use full indexing when:

- You are setting up a machine for the first time
- Search quality is clearly broken or stale
- You intentionally want a clean rebuild

### 6.2 Targeted indexing

Use targeted scripts when you only need one part refreshed:

- `./Scripts/indexing/update_vector_db.sh`
- `./Scripts/indexing/update_knowledge_graph.sh`
- `./Scripts/indexing/index_with_lightrag.sh`
- `./Scripts/indexing/partial_index_lightrag.sh --batch-size 5 --retry-failed-once --purge-deleted`

### 6.3 Daily indexing guidance

Recommended pattern:

1. Run the system normally for querying.
2. When you add many notes, update the vector DB.
3. When the graph-backed answer quality looks stale, refresh graph/LightRAG.
4. Use full indexing only when partial refresh is not enough.

### 6.4 When indexing is not required

Some MCP workflows can work directly from the vault on disk without waiting for semantic indexing:

- `search_vault_text`
- `read_vault_note`
- `batch_read_vault_notes`
- `update_vault_note`

This matters for new notes that exist on disk but have not been embedded yet.

## 7. Using the Webapp

The webapp is the main interactive interface.

Typical use:

1. Open `http://localhost:3030`
2. Enter a query
3. Choose a retrieval mode
4. Review the answer and cited sources

General guidance:

- Start with **vector** for fast lookup.
- Switch to **cascading** for more grounded synthesis.
- Use **deep research** for longer, broader analysis.
- If a result feels wrong, inspect sources before changing providers or prompts.

The UI distinguishes service state from data state:

- `Online`: reachable and populated
- `Empty`: reachable but not populated
- `Offline`: unreachable

If a service is `Empty`, fix indexing before debugging connectivity.

## 8. Using the API Gateway

Base URL:

- `http://localhost:4000`

Core endpoints:

- `GET /api/v1/health`
- `GET /api/v1/stats`
- `POST /api/v1/query`
- `WS /api/v1/deep-research`
- `GET /docs`

### 8.1 Standard query

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What have I written about ESPHome dashboards?",
    "mode": "cascading",
    "max_results": 8
  }'
```

### 8.2 Main request fields

- `query`
- `mode`: `vector` or `cascading`
- `max_results`
- `llm_provider`
- `model`
- `temperature`
- `relevance_threshold`
- `web_search`
- `llm_knowledge`
- `system_prompt`

Important:

- Deep research is not a normal HTTP `mode` on `POST /api/v1/query`.
- Use the WebSocket endpoint for deep research workflows.

## 9. Search Modes Explained

### 9.1 Vector

Best for:

- Fast recall
- Topic lookup
- Broad semantic matching

Use it when:

- You want the fastest answer path
- You already know the topic area
- You want to verify whether the vault contains something at all

### 9.2 Cascading

Best for:

- Multi-source grounded answers
- Better synthesis across related notes
- More targeted research questions

Use it when:

- A plain vector answer is too thin
- You want a stronger final answer with better evidence aggregation

### 9.3 Deep Research / Deep Thinking

Best for:

- Large or ambiguous questions
- Agentic, multi-step research
- Broader investigation where the system may need several retrieval passes

Use it when:

- You want a more deliberate research workflow
- Speed matters less than depth

## 10. Using MCP With ChatGPT or Claude

The MCP server is the right choice when you want desktop AI clients to work against the vault.

Primary MCP documentation:

- `Documentation/integrations/mcp/MCP_SETUP_INSTRUCTIONS.md`
- `Documentation/MCP_CLIENT_SETUP.md`
- `MCP_CONNECTION_QUICK_START.md`

### 10.1 What MCP is best at

MCP combines:

- Semantic vault search
- Full-note retrieval
- Direct text search
- Batch note reads
- Note updates
- Vault diagnostics
- Optional graph tools

### 10.2 Important MCP tools

#### Retrieval tools

- `obsidian_semantic_search`
- `search_vault_full`
- `search_vault_text`
- `obsidian_search_mode`
- `obsidian_unified_query`

#### Vault file tools

- `get_vault_path`
- `read_vault_note`
- `batch_read_vault_notes`
- `update_vault_note`
- `read_attachment_text`

#### Vault health / hygiene tools

- `obsidian_vault_stats`
- `obsidian_index_health`
- `scan_vault_content_warnings`

#### Note creation / capture tools

- `capture_note`
- `summarize_url_to_capture`
- `summarize_youtube_to_capture`
- `apply_existing_tags_frontmatter_only`

### 10.3 Best MCP workflow for non-indexed notes

This is the most important distinction for day-to-day use:

- **Semantic search tools depend on the index**
- **Direct vault text tools read from disk**

If you know a note exists but semantic search cannot find it:

1. Use `search_vault_text`
2. Limit the scope with a directory path if possible
3. Use `batch_read_vault_notes` or `read_vault_note`
4. Use `update_vault_note` if you need to edit it
5. Use `obsidian_index_health` to confirm stale or missing indexed state

Example task:

- "Search my vault text in `Projects` for ` ```mermaid ` with 1 line of context."

This is the correct workflow for exact strings, syntax, code blocks, Mermaid, YAML, JSON, or very new notes.

### 10.4 `search_vault_full` and stale paths

`search_vault_full` still starts from the semantic index. If indexed metadata points to an old path, it now attempts conservative path recovery and warns when the stored path appears stale.

Use `obsidian_index_health` when:

- Search results reference files that no longer exist at the returned path
- Search results look outdated after a move or rename
- The vault changed recently and answers lag behind reality

## 11. CLI Usage

For direct terminal-based semantic retrieval:

```bash
./search_vault "Home Assistant"
./search_vault "ESP32" 3
./search_vault "lymphoma treatment" 20
```

Results are saved in the repo root as:

- `search_results_<query>.txt`

Use CLI search when:

- You want quick semantic retrieval without MCP limits
- You want a saved local results file
- You are testing the embedding service directly

## 12. Common User Workflows

### 12.1 "I just want answers from my vault"

Use:

- Webapp on `http://localhost:3030`
- `vector` first
- `cascading` if the first answer is weak

### 12.2 "I added notes and search cannot find them"

Use:

1. `search_vault_text`
2. `read_vault_note` or `batch_read_vault_notes`
3. Reindex later if you want semantic discovery to include them

### 12.3 "I know the folder and need exact text matches"

Use:

- MCP `search_vault_text`

This is the right tool for:

- code
- Mermaid
- frontmatter
- tags
- filenames mentioned inside notes
- exact phrases

### 12.4 "I want to update an existing note from an agent workflow"

Use:

1. `read_vault_note`
2. `update_vault_note`

This is better than capture-only workflows when you need read-modify-write on an existing file.

### 12.5 "I want a longer research answer"

Use:

- API or webapp with `cascading`
- Deep research when the task is broader or multi-step

### 12.6 "I want to create quick captures"

Use:

- `capture_note`
- `summarize_url_to_capture`
- `summarize_youtube_to_capture`

These are capture-oriented tools, not general-purpose note editing tools.

## 13. Operating the System Day To Day

### Start services

```bash
./Scripts/setup/start_obsidian_rag.sh
```

### Stop services

```bash
./Scripts/setup/stop_obsidian_rag.sh
```

### Basic health check

```bash
python Scripts/debug/audit_search_modes.py
```

### Check graph freshness

```bash
./Scripts/debug/check_graph_status.py
```

### Full indexing

```bash
./Scripts/indexing/run_indexing.sh
```

## 14. Data Layout and Sync Model

The project documentation describes a snapshot-sync architecture:

- **Indexer machine** builds the indexes locally
- **Consumer machine** pulls a stable snapshot
- iCloud is used for transfer, not live database reads

Canonical data roots are documented in:

- `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md`

This matters because:

- Querying should happen against local data, not a mutable shared cloud DB
- Many "stale" or "locked DB" problems are operational, not retrieval-quality problems

## 15. Troubleshooting Guide

### 15.1 Empty or weak answers

Check in this order:

1. Is the vault path correct?
2. Are services healthy?
3. Is the relevant index populated?
4. Are you using the right retrieval mode?
5. Is the note new and not indexed yet?

For brand-new notes, use direct vault text search before debugging semantic search.

### 15.2 Semantic search misses a note you know exists

Likely causes:

- The note has not been indexed yet
- The note was moved or renamed and indexed metadata is stale
- The query is too literal for semantic retrieval

Fix:

1. Use `search_vault_text`
2. Use `obsidian_index_health`
3. Reindex if needed

### 15.3 MCP can search but cannot read files

Check:

- `OBSIDIAN_VAULT_PATH`
- file permissions
- transport mode
- whether you are using SSH transport against an iCloud path with macOS restrictions

Relevant docs:

- `Documentation/MCP_CLIENT_SETUP.md`
- `Documentation/SSH_MCP_SETUP.md`

### 15.4 Services are up but results are stale

Likely causes:

- Indexes were not refreshed
- Snapshot sync is outdated
- Local cache and vault contents drifted

Actions:

1. Run `obsidian_index_health`
2. Refresh the relevant index
3. If using multi-machine sync, re-run pull/push workflow

### 15.5 Graph or cascading issues

If vector works but cascading is weak or slow:

1. Check graph and LightRAG health
2. Run timing diagnostics
3. Review the search mode docs before changing providers

Relevant docs:

- `Documentation/reference/search/SEARCH_MODES_GUIDE.md`
- `Documentation/operations/troubleshooting/TROUBLESHOOTING_QUERY.md`

### 15.6 Docker or environment issues

Use:

- `Documentation/operations/troubleshooting/DOCKER_TROUBLESHOOTING.md`

## 16. Recommended Reading Order

If you are new:

1. This file
2. `Documentation/getting-started/SETUP_QUICKSTART.md`
3. `Documentation/getting-started/API_GATEWAY_QUICKSTART.md`
4. `Documentation/integrations/mcp/MCP_SETUP_INSTRUCTIONS.md`
5. `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md`

If you are focused on MCP:

1. This file
2. `Documentation/integrations/mcp/MCP_SETUP_INSTRUCTIONS.md`
3. `Documentation/MCP_CLIENT_SETUP.md`
4. `MCP_CONNECTION_QUICK_START.md`

If you are focused on indexing and maintenance:

1. This file
2. `Documentation/operations/setup/INDEXING_SCRIPTS_GUIDE.md`
3. `Documentation/operations/indexing/REINDEXING_PROCEDURE.md`
4. `Scripts/README.md`

## 17. Short Command Reference

```bash
# Start everything
docker compose up -d

# Gateway health
curl -s http://localhost:4000/api/v1/health

# MCP health
curl -s http://localhost:8811/health

# Full indexing
./Scripts/indexing/run_indexing.sh

# Start / stop helper scripts
./Scripts/setup/start_obsidian_rag.sh
./Scripts/setup/stop_obsidian_rag.sh

# Search modes audit
python Scripts/debug/audit_search_modes.py

# CLI semantic search
./search_vault "your query"
```

## 18. Final Guidance

The main mistake users make is using the wrong retrieval path for the job.

Remember:

- **Semantic search** is for indexed meaning-based retrieval
- **Direct vault text search** is for exact text and non-indexed notes
- **Cascading** is for stronger grounded synthesis
- **Deep research** is for long-form, agentic analysis
- **Index health tools** are for diagnosing stale metadata and path drift

When in doubt:

1. Verify the vault path
2. Verify service health
3. Decide whether the task is semantic or literal
4. Use direct vault tools for new or exact-match notes
5. Reindex only when the index is actually the problem
