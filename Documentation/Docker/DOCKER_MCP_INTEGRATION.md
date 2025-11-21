# Integrating Unified MCP Server with Docker MCP Toolkit

## Overview

You have two options for using your unified MCP server:

1. **Direct Python Server** (Current) - Runs directly, not in Docker
2. **Docker MCP Toolkit** (Recommended) - Integrates with Docker MCP gateway

## Option 1: Simple Replacement (Current Setup)

Your `obsidian-rag` entry in Claude Desktop config is **NOT** part of the Docker toolkit - it's a separate Python server. Simply replace it:

**In `~/Library/Application Support/Claude/claude_desktop_config.json`:**

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

**Remove the old `obsidian-rag` entry.**

## Option 2: Docker MCP Toolkit Integration

Integrate your unified server into the Docker MCP toolkit so it's available through the `docker-gateway`.

### Step 1: Build Docker Image

```bash
cd /Users/michel/Library/Mobile\ Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag
docker build -f Dockerfile.mcp-unified -t obsidian-rag-unified:latest .
```

### Step 2: Add to Docker MCP Registry

Edit `~/.docker/mcp/registry.yaml`:

```yaml
registry:
  # ... existing entries ...
  obsidian-rag-unified:
    ref: "obsidian-rag-unified:latest"
```

### Step 3: Add to Catalog (Optional)

You can also add it to a catalog for better organization:

```bash
docker mcp catalog add obsidian-rag-unified \
  --image obsidian-rag-unified:latest \
  --env EMBEDDING_SERVICE_URL=http://host.docker.internal:8000 \
  --env CLAUDE_GRAPH_SERVICE_URL=http://host.docker.internal:8002 \
  --env ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

### Step 4: Update Claude Desktop Config

The server will be available through `docker-gateway`:

```json
{
  "mcpServers": {
    "docker-gateway": {
      "command": "docker",
      "args": ["mcp", "gateway", "run"]
    }
  }
}
```

Then Claude can use `obsidian-rag-unified` tools through the gateway.

## Option 3: Replace Default Obsidian Server

If you want to replace the default `obsidian` server in the Docker toolkit:

### Step 1: Build Image with Different Name

```bash
docker build -f Dockerfile.mcp-unified -t mcp/obsidian-rag:latest .
```

### Step 2: Update Registry

Edit `~/.docker/mcp/registry.yaml`:

```yaml
registry:
  obsidian:
    ref: "mcp/obsidian-rag:latest"  # Replace default obsidian
```

### Step 3: Restart Docker Gateway

The gateway will now use your custom server instead of the default `mcp/obsidian` image.

## Comparison

| Approach | Pros | Cons |
|----------|------|------|
| **Direct Python** | • Simple setup<br>• No Docker needed<br>• Direct access | • Not integrated with Docker toolkit<br>• Separate config entry |
| **Docker Toolkit** | • Integrated with gateway<br>• Consistent with other servers<br>• Easy to share | • Requires Docker<br>• More setup steps |

## Recommendation

**Use Option 1 (Direct Python)** if:
- You want the simplest setup
- You don't need Docker integration
- You want direct control

**Use Option 2 (Docker Toolkit)** if:
- You want everything through the gateway
- You're already using Docker MCP toolkit
- You want to share the server with others

## Testing

After setup, test with:

```bash
# Test direct server
python obsidian_rag_unified_mcp.py

# Test Docker image
docker run --rm -it \
  -e ANTHROPIC_API_KEY=your-key \
  -e EMBEDDING_SERVICE_URL=http://host.docker.internal:8000 \
  obsidian-rag-unified:latest

# Test gateway
docker mcp gateway run --dry-run
```

## Troubleshooting

### Docker Image Can't Access Services

If the Docker container can't reach `localhost:8000`, use:
- `host.docker.internal:8000` (Mac/Windows)
- `172.17.0.1:8000` (Linux)

### Gateway Not Showing Server

1. Check registry: `cat ~/.docker/mcp/registry.yaml`
2. Verify image exists: `docker images | grep obsidian-rag`
3. Restart gateway: Restart Claude Desktop

### Environment Variables Not Working

Make sure to set environment variables in:
- Docker image (ENV in Dockerfile)
- Registry entry (env section)
- Or pass via `--env` flags

