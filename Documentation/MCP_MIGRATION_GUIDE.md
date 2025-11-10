# MCP Server Migration Guide

## Problem: Claude Using Old Server

If Claude is using `obsidian_simple_search` from the old `obsidian_rag_mcp_fixed.py` instead of the unified server, follow these steps:

## Solution: Update Tool Names for Compatibility

The unified server (`obsidian_rag_unified_mcp.py`) now uses the same tool names as the old server for compatibility:

- ✅ `obsidian_simple_search` - Enhanced vault search (5-10 results vs 3)
- ✅ `obsidian_vault_stats` - Vault statistics  
- ✅ `obsidian_graph_query` - Knowledge graph queries

## Step 1: Remove Old Server from Config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

**Remove this entry:**
```json
"obsidian-rag": {
  "command": "...",
  "args": ["obsidian_rag_mcp_fixed.py"],
  ...
}
```

**Keep only the unified server:**
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
3. **Check MCP Status** - Should show "obsidian-rag-unified" connected

## Step 3: Test

Ask Claude:
- "Search my vault for lymphoma treatments"
- "What treatments are mentioned in my notes?"

Claude should now use the unified server with enhanced features.

## Tool Name Compatibility

The unified server supports both old and new tool names:

| Old Name | New Name | Status |
|----------|----------|--------|
| `obsidian_simple_search` | `search_vault` | ✅ Both work |
| `obsidian_vault_stats` | `get_vault_stats` | ✅ Both work |
| `obsidian_graph_query` | `query_knowledge_graph` | ✅ Both work |

## Benefits of Unified Server

✅ **More Results**: 5-10 results vs 3 in old server
✅ **Content Snippets**: Includes actual note content
✅ **Better Error Handling**: Clear error messages
✅ **Graph Integration**: All tools in one place
✅ **Backward Compatible**: Works with existing tool names

## Troubleshooting

### Claude Still Uses Old Server

1. **Check Config**: Make sure old server is removed
2. **Restart**: Quit and reopen Claude Desktop completely
3. **Check Logs**: Look for MCP connection errors

### Tools Not Available

1. **Check Services**: Make sure embedding service is running
   ```bash
   docker-compose up embedding-service -d
   ```

2. **Check Environment**: Verify `ANTHROPIC_API_KEY` is set

3. **Test Server**: Run server manually to check for errors
   ```bash
   python obsidian_rag_unified_mcp.py
   ```

