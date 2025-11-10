# Fix: Claude Using Old MCP Server

## Problem

Claude is using `obsidian_simple_search` from the old `obsidian_rag_mcp_fixed.py` instead of the unified server, even though both are configured.

## Solution: Remove Old Server

You have **both servers** configured in Claude Desktop. Remove the old one and keep only the unified server.

## Step 1: Edit Claude Desktop Config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

**Remove this entry:**
```json
"obsidian-rag": {
  "command": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/venv/bin/python",
  "args": ["/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/obsidian_rag_mcp_fixed.py"],
  ...
}
```

**Keep only this:**
```json
"obsidian-rag-unified": {
  "command": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/venv/bin/python",
  "args": ["/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/obsidian_rag_unified_mcp.py"],
  "env": {
    "ANTHROPIC_API_KEY": "your-key-here",
    "EMBEDDING_SERVICE_URL": "http://localhost:8000",
    "CLAUDE_GRAPH_SERVICE_URL": "http://localhost:8002"
  }
}
```

## Step 2: Restart Claude Desktop

1. **Quit Claude Desktop** completely (Cmd+Q)
2. **Reopen Claude Desktop**
3. **Check MCP Status** - Should show only "obsidian-rag-unified" connected

## Step 3: Test

Ask Claude:
- "Search my vault for lymphoma treatments and results"

Claude should now use the unified server with:
- ✅ 5-10 results (vs 3 in old server)
- ✅ Content snippets included
- ✅ Better error messages
- ✅ Knowledge graph tools available

## Why This Happens

When multiple MCP servers provide tools with the same name, Claude may choose the first one it encounters. By removing the old server, Claude will only see the unified server's enhanced tools.

## Tool Compatibility

The unified server supports the same tool names as the old server:
- ✅ `obsidian_simple_search` - Enhanced (5-10 results vs 3)
- ✅ `obsidian_vault_stats` - Vault statistics
- ✅ `obsidian_graph_query` - Knowledge graph queries (if graph loaded)

Plus new tools:
- ✅ `query_knowledge_graph` - Enhanced graph queries
- ✅ `get_entity_info` - Entity details
- ✅ `find_entity_path` - Find connections
- ✅ `search_entities` - Search entities
- ✅ `get_graph_stats` - Graph statistics

