# Troubleshooting: Graph Tools Not Available

## Problem

Claude says `obsidian_graph_query` tool is not available, even though the graph file exists.

## Root Causes

1. **Graph not loaded** - The MCP server couldn't load the graph file
2. **Path resolution** - Graph file path not found from MCP server's working directory
3. **Missing API key** - `ANTHROPIC_API_KEY` not set in MCP server environment
4. **Graph file not accessible** - Read-only filesystem or permissions issue

## Solution: Update Claude Desktop Config

The MCP server needs the graph path and API key in its environment.

### Step 1: Check Current Config

Check your Claude Desktop config at:
`~/Library/Application Support/Claude/claude_desktop_config.json`

### Step 2: Update Config with Full Paths

Make sure your `obsidian-rag-unified` entry has:

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

**Key additions:**
- ✅ `ANTHROPIC_API_KEY` - Required for graph queries
- ✅ `KNOWLEDGE_GRAPH_PATH` - **Full absolute path** to graph file

### Step 3: Restart Claude Desktop

1. **Quit Claude Desktop** completely (Cmd+Q)
2. **Reopen Claude Desktop**
3. **Check MCP Status** - Should show graph tools available

## Alternative: Use Graph Service

If the MCP server can't load the graph directly, use the graph service instead:

### Step 1: Start Graph Service

```bash
cd /Users/michel/Library/Mobile\ Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag
docker-compose up -d graph-service
```

### Step 2: Verify Service

```bash
curl http://localhost:8002/health
```

Should return:
```json
{
  "status": "healthy",
  "graph_loaded": true,
  "nodes": 35048,
  "edges": 80200
}
```

### Step 3: Use Graph Service via API

The graph service provides the same functionality via HTTP API, which the MCP server can use as a fallback.

## Verification Steps

### Check Graph File Exists

```bash
ls -lh "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/graph_data/knowledge_graph_full.pkl"
```

Should show the file (about 10MB).

### Test Graph Loading Manually

```bash
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"
python3 -c "
from claude_graph_builder import ClaudeGraphBuilder
import os

api_key = os.environ.get('ANTHROPIC_API_KEY')
if not api_key:
    print('❌ ANTHROPIC_API_KEY not set')
else:
    builder = ClaudeGraphBuilder(api_key=api_key)
    builder.load_graph('graph_data/knowledge_graph_full.pkl')
    print(f'✅ Graph loaded: {builder.graph.number_of_nodes()} nodes, {builder.graph.number_of_edges()} edges')
"
```

### Check MCP Server Logs

If graph tools still don't appear, check Claude Desktop logs:
`~/Library/Application Support/Claude/Logs/`

Look for errors about:
- Graph loading failures
- Missing API key
- Path not found

## Expected Behavior

After fixing, Claude should see these tools:
- ✅ `obsidian_graph_query` - Query knowledge graph
- ✅ `get_entity_info` - Get entity details
- ✅ `find_entity_path` - Find connections
- ✅ `search_entities` - Search entities
- ✅ `get_graph_stats` - Graph statistics

## Quick Fix Checklist

- [ ] Graph file exists at expected location
- [ ] `ANTHROPIC_API_KEY` set in Claude Desktop config
- [ ] `KNOWLEDGE_GRAPH_PATH` set with **full absolute path**
- [ ] Claude Desktop restarted after config changes
- [ ] MCP server shows as connected in Claude Desktop
- [ ] Graph tools appear in available tools list

