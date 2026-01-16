# MCP Setup Instructions for ChatGPT Desktop

## Quick Setup: Unified MCP Server

### Step 1: Start Required Services

Start the services ChatGPT will query through the MCP server:

```bash
docker compose up -d embedding-service
```

Optional (Graph service is only needed for the graph API, not MCP graph queries):

```bash
docker compose up -d graph-service
```

Optional (LightRAG is not required for MCP tools):

```bash
docker compose up -d lightrag-service
```

### Step 2: Verify the MCP Server venv

```bash
/Users/michel/Library/Mobile\ Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/venv/bin/python \
  -c "import requests, mcp; print('deps ok')"
```

### Step 3: Update ChatGPT Desktop MCP Config

Open ChatGPT Desktop → **Settings → Developer → MCP** and open the config file.

Add or update the `obsidian-rag-unified` block:

```json
{
  "mcpServers": {
    "obsidian-rag-unified": {
      "command": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/venv/bin/python",
      "args": [
        "-u",
        "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/obsidian_rag_unified_mcp.py"
      ],
      "env": {
        "EMBEDDING_SERVICE_URL": "http://localhost:8000",
        "KNOWLEDGE_GRAPH_PATH": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/graph_data/knowledge_graph_full.pkl",
        "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
      }
    }
  }
}
```

Notes:
- The MCP server loads the repo `.env` automatically.
- Graph tools require `OPENAI_API_KEY` (either in the MCP env block or in the repo `.env`).
- Set `OPENAI_MODEL` in `.env` to choose the model (example: `gpt-5-mini`).
- If you only need semantic search, omit `OPENAI_API_KEY` and graph tools will not load.

### Step 4: Restart ChatGPT Desktop

1. Quit ChatGPT Desktop completely (Cmd+Q)
2. Reopen ChatGPT Desktop
3. Check MCP status in settings

### Step 5: Test It

Ask ChatGPT:
- "Search my vault for CAR-T therapy"
- "What treatments are mentioned in my notes?"
- "How does ESP32 relate to Home Assistant?"

## Available Tools

### Vault Search
- **`search_vault`** - Semantic search with 5-10 results, content snippets

### Knowledge Graph
- **`query_knowledge_graph`** - Ask questions about relationships
- **`get_entity_info`** - Get entity details
- **`find_entity_path`** - Find connections between entities
- **`search_entities`** - Search for entities
- **`get_graph_stats`** - Graph statistics

### Vault Stats
- **`get_vault_stats`** - Vault statistics

## Troubleshooting

### MCP Server Not Loading

1. **Check Python Path:**
   ```bash
   which python
   # Should match the command in config
   ```

2. **Test Server Manually:**
   ```bash
   python obsidian_rag_unified_mcp.py
   # Should start without errors
   ```

3. **Check Environment Variables:**
   - `EMBEDDING_SERVICE_URL` should point to running service
   - `OPENAI_API_KEY` is required only for graph tools

### Services Not Available

1. **Start Embedding Service:**
   ```bash
   docker-compose up embedding-service -d
   ```

2. **Start Graph Service:**
   ```bash
   docker-compose up graph-service -d
   ```

3. **Check Service URLs:**
   - Embedding: http://localhost:8000
   - Graph: http://localhost:8002

### Graph Not Loading

1. **Check Graph File:**
   ```bash
   ls -lh graph_data/knowledge_graph_full.pkl
   ```

2. **Set KNOWLEDGE_GRAPH_PATH:**
   - In Claude Desktop config env section
   - Or ensure file is in default location

## Migration from Old Setup

If you're using the old `obsidian_rag_mcp_fixed.py`:

1. **Replace in config:**
   - Old: `obsidian_rag_mcp_fixed.py`
   - New: `obsidian_rag_unified_mcp.py`

2. **Update server name:**
   - Old: `"obsidian-rag"`
   - New: `"obsidian-rag-unified"`

3. **Add environment variables:**
   - `EMBEDDING_SERVICE_URL`
   - `OPENAI_API_KEY` (optional, only for graph tools)

## Benefits of Unified Server

✅ **One server** instead of two
✅ **Better vault search** (5-10 results vs 3)
✅ **Content snippets** included
✅ **All tools** in one place
✅ **Easier maintenance** - single file
✅ **Better error messages**
