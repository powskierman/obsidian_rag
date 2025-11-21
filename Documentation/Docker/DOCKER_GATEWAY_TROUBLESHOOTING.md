# Docker Gateway Troubleshooting

## Quick Fix

**Problem**: Claude Desktop can't access Docker MCP servers

**Solution**: Remove broken `n8n-mcp` entry from registry

```bash
# Edit registry file
nano ~/.docker/mcp/registry.yaml
# Remove the n8n-mcp section
```

## Common Issues

### 1. "MCP server not found: n8n-mcp"
✅ **Fixed**: Removed from `~/.docker/mcp/registry.yaml`

### 2. Claude Desktop can't connect
**Check**:
```bash
docker ps  # Is Docker running?
docker mcp gateway run --dry-run  # Test gateway
```

**Logs**: `~/Library/Application Support/Claude/Logs/`

### 3. Use wrapper script instead

Update `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "docker-gateway": {
      "command": "/path/to/docker_gateway_wrapper.sh",
      "args": []
    }
  }
}
```

## Available MCP Servers

Via gateway: `docker`, `obsidian`, `filesystem`, `git`, `fetch`, `brave`, `duckduckgo`, etc.

## Config Files

- Gateway: `~/.docker/mcp/config.yaml`
- Registry: `~/.docker/mcp/registry.yaml`
- Claude: `~/Library/Application Support/Claude/claude_desktop_config.json`

## Next Steps

1. Restart Claude Desktop
2. Check logs for errors
3. Test with `--servers obsidian` flag
