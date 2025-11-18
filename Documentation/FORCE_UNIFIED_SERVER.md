# Force Claude to Use Unified Server for Comparison

## Quick Method: Temporarily Disable Docker Toolkit's Obsidian

### Step 1: Disable Obsidian in Docker Registry

Edit `~/.docker/mcp/registry.yaml`:

```yaml
registry:
  brave:
    ref: ""
  # ... other entries ...
  # obsidian:    # <-- Comment out or delete
  #   ref: ""
  openweather:
    ref: ""
```

### Step 2: Restart Claude Desktop

1. Quit Claude Desktop (Cmd+Q)
2. Reopen Claude Desktop
3. Verify only `obsidian-rag-unified` is available

### Step 3: Test and Compare

Ask Claude:
- "Search my vault for lymphoma treatments"
- Claude will use `obsidian_simple_search` from your unified server

### Step 4: Re-enable for Comparison

To compare both:

1. **Re-enable obsidian** in registry
2. **Restart Claude Desktop**
3. **Ask the same question** - Claude may use Docker toolkit's version
4. **Compare results**

## Method 2: Explicit Tool Selection

You can explicitly tell Claude which tool to use:

### Prompt Template

```
Use obsidian_semantic_search to search my vault for: [your query]

Then use the docker-gateway's obsidian_simple_search tool to search for the same query.

Compare the results from both searches.
```

### Example

```
Use obsidian-rag-unified's obsidian_simple_search to find information about lymphoma treatments.

Then use docker-gateway's obsidian_simple_search for the same query.

Show me the differences between the two search results.
```

## Method 3: Rename Tool for Testing

Temporarily rename your tool to make it unique:

### Step 1: Edit Unified Server

Edit `obsidian_rag_unified_mcp.py`:

```python
Tool(
    name="obsidian_semantic_search",  # Changed from obsidian_simple_search
    description="Search your Obsidian vault using semantic search...",
    ...
)
```

### Step 2: Update Tool Handler

```python
if name == "obsidian_semantic_search" or name == "obsidian_simple_search" or name == "search_vault":
    return await search_vault(arguments)
```

### Step 3: Test

Now Claude will see:
- `obsidian_simple_search` from Docker toolkit (text search)
- `obsidian_semantic_search` from unified server (semantic search)

You can ask Claude to use both and compare.

## Method 4: Side-by-Side Comparison Script

Create a test script to compare both:

```python
#!/usr/bin/env python3
"""Compare Docker toolkit vs Unified server search results"""

import requests
import json

query = "lymphoma treatments"

# Test 1: Unified server (via embedding service directly)
print("=" * 60)
print("UNIFIED SERVER (Semantic Search)")
print("=" * 60)
response1 = requests.post(
    "http://localhost:8000/query",
    json={"query": query, "n_results": 5, "reranking": True}
)
results1 = response1.json()
print(json.dumps(results1, indent=2))

# Test 2: Docker toolkit (would need MCP client)
# This requires actual MCP protocol communication
print("\n" + "=" * 60)
print("DOCKER TOOLKIT (Text Search)")
print("=" * 60)
print("Note: Docker toolkit uses Obsidian's native search")
print("This would require MCP client to test directly")
```

## Method 5: Use MCP Inspector

Use an MCP inspector tool to see which tools Claude has access to:

1. Check available tools from each server
2. See which one Claude prefers
3. Manually test each tool

## Recommended Testing Workflow

### Phase 1: Test Unified Server Only

1. **Disable Docker toolkit obsidian** (Method 1)
2. **Ask Claude**: "Search my vault for [query]"
3. **Document results**: Number of results, quality, relevance

### Phase 2: Test Docker Toolkit Only

1. **Disable unified server** (remove from Claude Desktop config)
2. **Re-enable Docker toolkit obsidian**
3. **Restart Claude Desktop**
4. **Ask same query**
5. **Document results**

### Phase 3: Compare Side-by-Side

1. **Enable both servers**
2. **Use explicit prompts** (Method 2) to test both
3. **Compare**:
   - Number of results
   - Relevance scores
   - Content snippets
   - Response time

## Quick Comparison Checklist

When comparing, note:

- [ ] **Number of results**: Unified (5-10) vs Docker (varies)
- [ ] **Search method**: Semantic (unified) vs Text (Docker)
- [ ] **Content snippets**: Unified includes snippets
- [ ] **Relevance scores**: Unified shows percentages
- [ ] **Response time**: Which is faster?
- [ ] **Result quality**: Which finds better matches?

## Restore Normal Operation

After testing:

1. **Re-enable obsidian** in Docker registry
2. **Keep both servers** in Claude Desktop config
3. **Let Claude choose** the best tool automatically

## Troubleshooting

### Claude Still Uses Docker Toolkit

- Check registry: `cat ~/.docker/mcp/registry.yaml | grep obsidian`
- Verify unified server is running: Check Claude Desktop MCP status
- Restart Claude Desktop completely

### Can't Compare Results

- Use explicit prompts (Method 2)
- Test one at a time (Method 1)
- Use the comparison script (Method 4)

