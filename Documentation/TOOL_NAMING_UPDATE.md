# Tool Naming Update: obsidian_semantic_search

## Change Made

The unified server's search tool has been renamed from `obsidian_simple_search` to `obsidian_semantic_search` to distinguish it from the Docker toolkit's text search.

## Why This Change?

**Problem:** Both servers had the same tool name (`obsidian_simple_search`), causing Claude to prefer the Docker toolkit version even when explicitly asked to use the unified server.

**Solution:** Rename the unified server's tool to `obsidian_semantic_search` so both can coexist and Claude can choose the right one.

## Current Tool Names

| Server | Tool Name | Search Type | Results |
|--------|-----------|-------------|---------|
| **Docker Toolkit** | `obsidian_simple_search` | Text search | Varies |
| **Unified Server** | `obsidian_semantic_search` | **Semantic search** | 5-10 with snippets |

## How to Use

### For Semantic Search (Recommended)

Ask Claude:
```
Use obsidian_semantic_search to find information about lymphoma treatments
```

Or simply:
```
Search my vault for lymphoma treatments using semantic search
```

### For Text Search (Docker Toolkit)

Ask Claude:
```
Use obsidian_simple_search to find files containing "lymphoma"
```

### For Comparison

Ask Claude:
```
Use obsidian_semantic_search to search for: lymphoma treatments

Then use obsidian_simple_search for the same query.

Compare the results from both search methods.
```

## Benefits

✅ **Clear distinction** between semantic and text search  
✅ **Both tools available** - no need to disable either  
✅ **Claude can choose** the right tool for each task  
✅ **Easy comparison** - test both search methods side-by-side  

## Backward Compatibility

The unified server still accepts the old name for compatibility:
- `obsidian_semantic_search` ✅ (new, preferred)
- `obsidian_simple_search` ✅ (old, still works)
- `search_vault` ✅ (alternative name)

## Next Steps

1. **Restart Claude Desktop** to load the updated tool name
2. **Test semantic search**: "Use obsidian_semantic_search to find..."
3. **Compare results** with Docker toolkit's text search

