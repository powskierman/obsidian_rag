# MCP Server Capabilities Comparison

## Overview

You have access to **two complementary MCP servers**:

1. **Docker Toolkit's `obsidian`** - File operations
2. **Your Unified `obsidian-rag-unified`** - Semantic search + Knowledge graph

## Capability Comparison

| Tool | Docker Toolkit `obsidian` | Unified `obsidian-rag-unified` | Notes |
|------|---------------------------|-------------------------------|-------|
| **Search** | | | |
| `obsidian_simple_search` | ✅ Simple text search | ✅ **Semantic search** (5-10 results, snippets) | Unified is **better** for search |
| `obsidian_complex_search` | ✅ JsonLogic queries | ❌ Not available | Docker toolkit only |
| **File Operations** | | | |
| `obsidian_get_file_contents` | ✅ Get single file | ❌ Not available | Docker toolkit only |
| `obsidian_batch_get_file_contents` | ✅ Get multiple files | ❌ Not available | Docker toolkit only |
| `obsidian_append_content` | ✅ Append to file | ❌ Not available | Docker toolkit only |
| `obsidian_patch_content` | ✅ Patch content | ❌ Not available | Docker toolkit only |
| `obsidian_delete_file` | ✅ Delete file | ❌ Not available | Docker toolkit only |
| `obsidian_list_files_in_vault` | ✅ List all files | ❌ Not available | Docker toolkit only |
| `obsidian_list_files_in_dir` | ✅ List directory | ❌ Not available | Docker toolkit only |
| **Knowledge Graph** | | | |
| `obsidian_graph_query` | ❌ Not available | ✅ **Claude-powered graph queries** | Unified only |
| `get_entity_info` | ❌ Not available | ✅ Entity details | Unified only |
| `find_entity_path` | ❌ Not available | ✅ Find connections | Unified only |
| `search_entities` | ❌ Not available | ✅ Search entities | Unified only |
| `get_graph_stats` | ❌ Not available | ✅ Graph statistics | Unified only |
| **Other** | | | |
| `obsidian_get_periodic_note` | ✅ Periodic notes | ❌ Not available | Docker toolkit only |
| `obsidian_get_recent_changes` | ✅ Recent changes | ❌ Not available | Docker toolkit only |
| `obsidian_vault_stats` | ❌ Not available | ✅ Vault statistics | Unified only |

## Recommendation: Use Both!

These servers are **complementary**, not competing:

- **Docker Toolkit `obsidian`**: Use for **file operations** (read, write, delete, list)
- **Unified `obsidian-rag-unified`**: Use for **semantic search** and **knowledge graph queries**

## Configuration: Keep Both Servers

### Option 1: Keep Both (Recommended)

**Claude Desktop Config:**

```json
{
  "mcpServers": {
    "docker-gateway": {
      "command": "docker",
      "args": ["mcp", "gateway", "run"]
    },
    "obsidian-rag-unified": {
      "command": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/venv/bin/python",
      "args": ["/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/obsidian_rag_unified_mcp.py"],
      "env": {
        "ANTHROPIC_API_KEY": "your-key-here",
        "EMBEDDING_SERVICE_URL": "http://localhost:8000",
        "CLAUDE_GRAPH_SERVICE_URL": "http://localhost:8002"
      }
    }
  }
}
```

**Docker Registry (`~/.docker/mcp/registry.yaml`):**

Keep `obsidian` enabled for file operations, but Claude will prefer your unified server for search because:
- Your `obsidian_simple_search` has better description
- Semantic search is more powerful than text search
- Claude can choose the best tool for each task

### Option 2: Disable Docker Toolkit's Search

If you want to force Claude to use your unified server for ALL searches:

1. **Disable `obsidian_simple_search`** in Docker toolkit (not possible - it's part of the server)
2. **OR** Rename your tool to something unique like `obsidian_semantic_search`

## Use Cases

### When to Use Docker Toolkit `obsidian`:

- ✅ **Read files**: "Get the contents of file X"
- ✅ **Write files**: "Append this to my notes"
- ✅ **List files**: "Show me all files in directory Y"
- ✅ **Delete files**: "Delete this file"
- ✅ **Periodic notes**: "Get today's daily note"
- ✅ **Recent changes**: "What files changed recently?"
- ✅ **Complex queries**: "Find all files with tag X and property Y"

### When to Use Unified `obsidian-rag-unified`:

- ✅ **Semantic search**: "Search for lymphoma treatments" (better than text search)
- ✅ **Knowledge graph**: "What treatments are mentioned?"
- ✅ **Entity exploration**: "What do I know about CAR-T therapy?"
- ✅ **Relationships**: "How does ESP32 relate to Home Assistant?"
- ✅ **Vault statistics**: "How many entities are in my graph?"

## Example: Combined Usage

Claude can use both servers together:

```
User: "Search for lymphoma treatments and then read the most relevant file"

Claude will:
1. Use obsidian-rag-unified → obsidian_simple_search (semantic search)
2. Get top result: "Lymphoma_Treatment_Notes.md"
3. Use docker-gateway → obsidian_get_file_contents (read file)
4. Return full file content
```

## Future Enhancement: Add File Operations

If you want your unified server to also support file operations, we can add:

- `obsidian_get_file_contents` - Read files
- `obsidian_list_files_in_vault` - List files
- `obsidian_append_content` - Write files
- etc.

This would make it a **complete replacement** for the Docker toolkit's obsidian server.

## Summary

**Current State:**
- ✅ Docker toolkit: File operations (12 tools)
- ✅ Unified server: Semantic search + Knowledge graph (7 tools)
- ✅ **Total: 19 tools** when using both

**Best Approach:**
- Keep both servers enabled
- Claude will automatically choose the best tool for each task
- Your unified server provides **better search** (semantic vs text)
- Docker toolkit provides **file operations** you need

