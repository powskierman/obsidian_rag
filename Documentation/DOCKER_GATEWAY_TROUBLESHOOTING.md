# Docker MCP Gateway Troubleshooting Guide

## Issue: Claude Desktop Can't Access Docker Gateway Servers

### Problem Summary
The Docker MCP Gateway is configured in Claude Desktop, but Claude cannot access the MCP servers exposed through the gateway.

### Root Causes Identified

1. **Missing n8n-mcp Image**: The gateway registry references `n8n-mcp` but the Docker image doesn't exist, causing errors during startup.

2. **Gateway Configuration**: The gateway outputs verbose configuration messages to stderr (which is fine), but there may be connection issues.

### Solutions Applied

#### 1. Fixed n8n-mcp Registry Issue
- **File**: `~/.docker/mcp/registry.yaml`
- **Change**: Removed the `n8n-mcp` entry since the image doesn't exist
- **Status**: ✅ Fixed

#### 2. Verified Docker Images
All required MCP images are present with correct digests:
- ✅ `docker:cli@sha256:625d9431a9f54c5a2bc90f24f0e1c3d55b1349fd857dd85035f98c2c9acbdd4d`
- ✅ `mcp/obsidian@sha256:0eba4c05742ad35faeb91eca40b792454d440d86449c9f1b3cb6c387a510651b`
- ✅ `mcp/postman@sha256:53fb05f7a2f053e56ca6b007825eb2aae45895ebff7ab0695694d204504b5df4`
- ✅ All other MCP images present

### Current Configuration

**Claude Desktop Config** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
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

### Testing the Gateway

1. **Test Gateway Startup**:
   ```bash
   docker mcp gateway run --dry-run
   ```
   Should show no errors about missing servers.

2. **Test MCP Connection**:
   The gateway should start and wait for JSON-RPC messages on stdin.

### Common Issues and Fixes

#### Issue: "MCP server not found: n8n-mcp"
**Fix**: Remove `n8n-mcp` from `~/.docker/mcp/registry.yaml` (already done)

#### Issue: Gateway outputs to stdout
**Status**: Gateway correctly outputs config to stderr, MCP protocol uses stdout ✅

#### Issue: Claude Desktop can't connect
**Possible Causes**:
1. Docker not running
2. Gateway taking too long to initialize
3. Claude Desktop timeout

**Debug Steps**:
1. Check Docker is running: `docker ps`
2. Test gateway manually: `docker mcp gateway run --dry-run`
3. Check Claude Desktop logs: `~/Library/Application Support/Claude/Logs/`

### Alternative: Use Wrapper Script

If direct connection doesn't work, you can use the wrapper script:

**Update Claude Desktop Config**:
```json
{
  "mcpServers": {
    "docker-gateway": {
      "command": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Scripts/docker_gateway_wrapper.sh",
      "args": []
    }
  }
}
```

### Available MCP Servers Through Gateway

The gateway exposes these servers (when images are available):
- `brave` - Brave Search
- `context7` - Context7
- `docker` - Docker CLI
- `duckduckgo` - DuckDuckGo Search
- `fetch` - HTTP Fetch
- `filesystem` - File System Access
- `git` - Git Operations
- `markdownify` - Markdown Conversion
- `obsidian` - Obsidian Vault Access
- `openweather` - Weather API
- `perplexity-ask` - Perplexity AI
- `postman` - Postman API
- `puppeteer` - Browser Automation
- `sequentialthinking` - Sequential Thinking

### Next Steps

1. **Restart Claude Desktop** after making config changes
2. **Check Claude Desktop Logs** for connection errors
3. **Test Individual Servers**: Try enabling specific servers with `--servers` flag
4. **Verify Docker Access**: Ensure Docker is accessible from Claude Desktop's environment

### Configuration Files Location

- Gateway Config: `~/.docker/mcp/config.yaml`
- Gateway Registry: `~/.docker/mcp/registry.yaml`
- Gateway Catalogs: `~/.docker/mcp/catalogs/`
- Claude Desktop Config: `~/Library/Application Support/Claude/claude_desktop_config.json`



