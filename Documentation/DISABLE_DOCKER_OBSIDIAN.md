# Disable Docker Toolkit's Obsidian Server

## Problem

Claude is using `obsidian_simple_search` from the Docker MCP toolkit's `obsidian` server instead of your unified `obsidian-rag-unified` server.

## Solution: Remove Obsidian from Docker Registry

The Docker toolkit exposes an `obsidian` server that provides `obsidian_simple_search`. To make Claude use your unified server instead, remove it from the registry.

### Step 1: Edit Docker MCP Registry

Edit `~/.docker/mcp/registry.yaml`:

**Remove or comment out the `obsidian` entry:**

```yaml
registry:
  brave:
    ref: ""
  context7:
    ref: ""
  docker:
    ref: ""
  duckduckgo:
    ref: ""
  fetch:
    ref: ""
  filesystem:
    ref: ""
  git:
    ref: ""
  markdownify:
    ref: ""
  # obsidian:  # <-- Comment out or remove this line
  #   ref: ""
  openweather:
    ref: ""
  perplexity-ask:
    ref: ""
  postman:
    ref: ""
  puppeteer:
    ref: ""
  sequentialthinking:
    ref: ""
```

### Step 2: Ensure Unified Server is Configured

Make sure your Claude Desktop config has the unified server:

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

### Step 3: Restart Claude Desktop

1. **Quit Claude Desktop** completely (Cmd+Q)
2. **Reopen Claude Desktop**
3. **Verify** - Claude should now use `obsidian-rag-unified` instead of Docker's `obsidian`

## Alternative: Replace with Your Custom Server

If you want to keep using the Docker gateway but with your unified server:

### Step 1: Build Docker Image

```bash
cd /Users/michel/Library/Mobile\ Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag
docker build -f Dockerfile.mcp-unified -t mcp/obsidian-rag:latest .
```

### Step 2: Update Registry

Edit `~/.docker/mcp/registry.yaml`:

```yaml
registry:
  obsidian:
    ref: "mcp/obsidian-rag:latest"  # Use your custom image
```

### Step 3: Restart

Restart Claude Desktop. The gateway will now use your unified server.

## Verification

After making changes, test:

1. **Check registry:**
   ```bash
   cat ~/.docker/mcp/registry.yaml | grep obsidian
   ```

2. **Test gateway:**
   ```bash
   docker mcp gateway run --dry-run
   ```

3. **Ask Claude:**
   - "Search my vault for lymphoma treatments"
   - Claude should use `obsidian-rag-unified` tools, not `obsidian_simple_search`

## Why This Works

When multiple MCP servers provide tools with the same name (`obsidian_simple_search`), Claude may choose based on:
- Server priority/order
- Tool availability
- Server reliability

By removing the Docker toolkit's `obsidian` server, Claude will only see your unified server's enhanced tools.

