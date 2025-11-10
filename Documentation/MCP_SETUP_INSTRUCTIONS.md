# MCP Setup Instructions for Claude Desktop

## Quick Setup: Unified MCP Server

### Step 1: Update Claude Desktop Config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "obsidian-rag-unified": {
      "command": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/venv/bin/python",
      "args": ["/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/obsidian_rag_unified_mcp.py"],
      "env": {
        "ANTHROPIC_API_KEY": "your-api-key-here",
        "EMBEDDING_SERVICE_URL": "http://localhost:8000",
        "CLAUDE_GRAPH_SERVICE_URL": "http://localhost:8002",
        "KNOWLEDGE_GRAPH_PATH": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/graph_data/knowledge_graph_full.pkl"
      }
    }
  }
}
```

### Step 2: Restart Claude Desktop

1. Quit Claude Desktop completely (Cmd+Q)
2. Reopen Claude Desktop
3. Check MCP status in settings

### Step 3: Test It

Ask Claude:
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
   - `ANTHROPIC_API_KEY` must be set
   - `EMBEDDING_SERVICE_URL` should point to running service

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
   - `ANTHROPIC_API_KEY`
   - `EMBEDDING_SERVICE_URL`
   - `CLAUDE_GRAPH_SERVICE_URL`

## Benefits of Unified Server

✅ **One server** instead of two
✅ **Better vault search** (5-10 results vs 3)
✅ **Content snippets** included
✅ **All tools** in one place
✅ **Easier maintenance** - single file
✅ **Better error messages**

