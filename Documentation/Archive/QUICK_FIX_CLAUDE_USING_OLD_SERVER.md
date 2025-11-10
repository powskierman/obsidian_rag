# Quick Fix: Claude Using Old Server

## Problem
Claude is using `obsidian_simple_search` from the old server instead of the unified server.

## Solution (30 seconds)

1. **Open Claude Desktop config:**
   ```bash
   open ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

2. **Find and DELETE this entry:**
   ```json
   "obsidian-rag": {
     "command": "...",
     "args": ["obsidian_rag_mcp_fixed.py"],
     ...
   }
   ```

3. **Make sure you have this entry (add if missing):**
   ```json
   "obsidian-rag-unified": {
     "command": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/venv/bin/python",
     "args": ["/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/obsidian_rag_unified_mcp.py"],
     "env": {
       "ANTHROPIC_API_KEY": "your-api-key-here",
       "EMBEDDING_SERVICE_URL": "http://localhost:8000",
       "CLAUDE_GRAPH_SERVICE_URL": "http://localhost:8002"
     }
   }
   ```

4. **Restart Claude Desktop** (Cmd+Q, then reopen)

5. **Test:** Ask "Search my vault for lymphoma treatments"

## Why This Works

The unified server has the same tool name (`obsidian_simple_search`) but with:
- ✅ 5-10 results (vs 3)
- ✅ Content snippets
- ✅ Better error handling
- ✅ Knowledge graph tools

By removing the old server, Claude will only see the enhanced version.
