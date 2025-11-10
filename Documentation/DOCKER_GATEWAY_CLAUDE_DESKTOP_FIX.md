# Docker Gateway Claude Desktop Connection Fix

## Problem
Claude Desktop cannot connect to the Docker MCP Gateway, even though the gateway works fine when run manually from the terminal.

## Root Cause
Claude Desktop runs in a different environment than your terminal:
- **Different PATH**: Claude Desktop may not have `/usr/local/bin` in its PATH
- **Environment Variables**: Missing environment variables that your shell has
- **Initialization Time**: Gateway takes ~2 seconds to initialize, may timeout

## Solution Applied

### 1. Updated Claude Desktop Config
**File**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Changes**:
- Use **full path** to docker: `/usr/local/bin/docker` instead of just `docker`
- Added **PATH environment variable** to ensure docker can be found
- This ensures Claude Desktop can find and execute docker

**Updated Config**:
```json
{
  "mcpServers": {
    "docker-gateway": {
      "command": "/usr/local/bin/docker",
      "args": ["mcp", "gateway", "run"],
      "env": {
        "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
      }
    }
  }
}
```

### 2. Created Wrapper Script (Alternative)
**File**: `Scripts/docker_gateway_wrapper.sh`

If the direct approach doesn't work, you can use the wrapper script:
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

## Verification Steps

1. **Verify Docker Path**:
   ```bash
   which docker
   # Should show: /usr/local/bin/docker
   ```

2. **Test Gateway Manually**:
   ```bash
   docker mcp gateway run --dry-run
   # Should show no errors
   ```

3. **Check Config Syntax**:
   ```bash
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | python3 -m json.tool
   # Should show valid JSON with no errors
   ```

4. **Restart Claude Desktop**:
   - Quit Claude Desktop completely (Cmd+Q)
   - Restart Claude Desktop
   - Check MCP server status

## Troubleshooting

### If Still Not Working

1. **Check Docker Location**:
   ```bash
   which docker
   ```
   If it's not `/usr/local/bin/docker`, update the config with the correct path.

2. **Test Wrapper Script**:
   ```bash
   "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Scripts/docker_gateway_wrapper.sh"
   ```
   Should start the gateway (will hang waiting for input, that's normal).

3. **Check Claude Desktop Logs**:
   - Look for MCP connection errors
   - Check for PATH or command not found errors

4. **Verify Docker is Running**:
   ```bash
   docker ps
   ```
   Should show running containers.

5. **Try Alternative Docker Paths**:
   If docker is installed via Homebrew, it might be at:
   - `/opt/homebrew/bin/docker` (Apple Silicon)
   - `/usr/local/bin/docker` (Intel Mac)
   
   Update the config accordingly.

## Expected Behavior

After applying the fix:
1. Claude Desktop should connect to the gateway
2. You should see "docker-gateway" in the MCP servers list
3. You should have access to tools from:
   - obsidian (12 tools)
   - postman (39 tools)
   - git (12 tools)
   - filesystem (11 tools)
   - And other MCP servers

## Gateway Initialization

The gateway takes approximately 2 seconds to initialize. This is normal. Claude Desktop should wait for the initialization to complete before timing out.

## Additional Notes

- The gateway outputs configuration messages to **stderr**, which is correct for MCP
- MCP protocol messages use **stdout**
- The gateway exposes 88+ tools from various MCP servers
- Some servers may fail to start (like perplexity-ask, brave) - this is expected if they require API keys or have other issues



