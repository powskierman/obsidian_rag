# MCP Client Setup - Accessing Canmore from MacBook

This guide shows how to configure your MacBook to access the MCP server running on Canmore.

## Architecture

```
MacBook (Client)
    ↓
Tailscale Network (100.110.65.38)
    ↓
Canmore (Server)
    ├─ MCP Server (port 8811)
    ├─ API Gateway (port 4000)
    └─ Obsidian Vault (iCloud)
```

## Quick Setup: HTTP Transport (Recommended)

### 1. Verify Connectivity

**On MacBook:**

```bash
# Test Tailscale connection to Canmore
ping -c 3 100.110.65.38

# Test MCP server health
curl http://100.110.65.38:8811/health
# Should return: ok

# Test API Gateway
curl http://100.110.65.38:4000/api/v1/health
# Should return JSON with status
```

### 2. Configure Claude Desktop

**On MacBook** - Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "obsidian-rag": {
      "transport": {
        "type": "http",
        "url": "http://100.110.65.38:8811/mcp"
      }
    }
  }
}
```

Or use hostname:

```json
{
  "mcpServers": {
    "obsidian-rag": {
      "transport": {
        "type": "http",
        "url": "http://canmore:8811/mcp"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

Completely quit and restart Claude Desktop for the config to take effect.

### 4. Test in Claude

In Claude Desktop, test the MCP tools:

```
Search my Obsidian vault for "test"
```

Claude should be able to:
- ✅ Search the vector index
- ✅ Search vault text directly from disk, even for non-indexed notes
- ✅ Retrieve full note content
- ✅ Batch-read multiple notes
- ✅ Update existing text notes in the vault
- ✅ Read PDF attachments
- ✅ Create new notes
- ✅ Report stale index/path issues
- ✅ Query the knowledge graph

### Recommended Tool Flow for New Notes

When you know the directory or need to inspect notes that may not be indexed yet:

1. Use `search_vault_text` with a directory path and either a literal string or regex.
2. Use `batch_read_vault_notes` or `read_vault_note` to inspect the matches.
3. Use `update_vault_note` if you need to modify an existing note.
4. Use `obsidian_index_health` if semantic search returns a stale path or misses notes you know exist.

`obsidian_semantic_search` and `search_vault_full` still depend on the embedding index for discovery. `search_vault_text` is the correct starting point for direct filesystem discovery.

## Alternative: SSH Transport

If you prefer SSH transport, you need to solve the macOS Full Disk Access issue first.

### Prerequisites

1. **SSH Key Authentication**
   ```bash
   # On MacBook:
   ssh-copy-id michel@100.110.65.38
   ```

2. **Grant Full Disk Access to Terminal on Canmore**
   - System Settings → Privacy & Security → Full Disk Access
   - Add Terminal.app
   - Restart Terminal

3. **Or Use Symlink Workaround**
   ```bash
   # On Canmore:
   ln -s "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel" \
        /Users/michel/obsidian_vault
   ```

### SSH MCP Configuration

**On MacBook** - Edit Claude Desktop config:

```json
{
  "mcpServers": {
    "obsidian-rag": {
      "command": "ssh",
      "args": [
        "michel@100.110.65.38",
        "/Users/michel/dev/obsidian_rag/venv/bin/python",
        "/Users/michel/dev/obsidian_rag/src/mcp/obsidian_rag_unified_mcp.py"
      ],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/Users/michel/obsidian_vault",
        "MCP_GATEWAY_URL": "http://localhost:4000"
      }
    }
  }
}
```

## Canmore Server Configuration

The MCP server on Canmore is configured in `docker-compose.yml`:

```yaml
mcp-unified:
  container_name: obsidian-mcp-unified
  ports:
    - "8811:8811"              # Exposed on all interfaces
  environment:
    - MCP_HTTP_HOST=0.0.0.0    # Bind to all interfaces
    - MCP_HTTP_PORT=8811
    - MCP_HTTP_PATH=/mcp
    - MCP_TRANSPORT=http
    - OBSIDIAN_VAULT_PATH=/app/vault
    - MCP_GATEWAY_URL=http://api-gateway:3000
```

## Network Details

### Canmore Interfaces

```
Localhost:     127.0.0.1
LAN:          192.168.2.195
Tailscale:    100.110.65.38
```

### Exposed Services

| Service | Port | Protocol | Accessible via Tailscale |
|---------|------|----------|-------------------------|
| MCP Server | 8811 | HTTP | ✅ Yes |
| API Gateway | 4000 | HTTP | ✅ Yes |
| Webapp | 3030 | HTTP | ✅ Yes |
| Streamlit UI | 8501 | HTTP | ✅ Yes |
| Embedding Service | 8000 | HTTP | ✅ Yes |
| Graph Service | 8002 | HTTP | ✅ Yes |
| LightRAG Service | 8001 | HTTP | ✅ Yes |

### Access URLs from MacBook

```
MCP:        http://100.110.65.38:8811/mcp
API:        http://100.110.65.38:4000
Webapp:     http://100.110.65.38:3030
Streamlit:  http://100.110.65.38:8501
```

## Troubleshooting

### Issue: Connection Refused

**Check Tailscale:**
```bash
# On MacBook:
tailscale status | grep canmore

# On Canmore:
tailscale status
```

**Check Docker:**
```bash
# On Canmore:
docker ps | grep mcp
curl http://localhost:8811/health
```

### Issue: MCP Tools Not Appearing in Claude

1. Check Claude Desktop logs:
   ```bash
   tail -f ~/Library/Logs/Claude/mcp*.log
   ```

2. Verify MCP server is responding:
   ```bash
   curl -X POST http://100.110.65.38:8811/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
   ```

3. Restart Claude Desktop completely

### Issue: "Operation Not Permitted" on Vault Files

This only affects SSH transport. Solutions:

1. **Use HTTP transport** (recommended) - bypasses the issue
2. **Grant Full Disk Access** to Terminal on Canmore
3. **Use symlink** outside iCloud directory

### Issue: Slow Performance

HTTP transport over Tailscale should be fast, but if you experience slowness:

1. Check Tailscale connection:
   ```bash
   # On MacBook:
   ping -c 10 100.110.65.38

   # Check latency
   tailscale ping canmore
   ```

2. Consider direct connection if on same LAN:
   ```json
   {
     "mcpServers": {
       "obsidian-rag": {
         "transport": {
           "type": "http",
           "url": "http://192.168.2.195:8811/mcp"
         }
       }
     }
   }
   ```

## Testing

### Test MCP Tools List

```bash
curl -X POST http://100.110.65.38:8811/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }' | python3 -m json.tool
```

### Test Vault Search

```bash
curl -X POST http://100.110.65.38:8811/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_vault",
      "arguments": {
        "query": "test"
      }
    }
  }' | python3 -m json.tool
```

### Test Direct Vault Text Search

```bash
curl -X POST http://100.110.65.38:8811/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "search_vault_text",
      "arguments": {
        "pattern": "```mermaid",
        "regex": false,
        "context_lines": 1,
        "path": "Projects"
      }
    }
  }' | python3 -m json.tool
```

### Test Index Health

```bash
curl -X POST http://100.110.65.38:8811/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "obsidian_index_health",
      "arguments": {}
    }
  }' | python3 -m json.tool
```

## Security Notes

- MCP server is exposed on Tailscale network
- Tailscale provides encrypted WireGuard VPN
- Services are NOT exposed to public internet
- Consider adding authentication if needed (MCP_HTTP_API_KEY)

## Performance

HTTP transport over Tailscale:
- Latency: ~10-50ms (depends on network)
- Throughput: Full Tailscale bandwidth
- No SSH overhead
- Direct HTTP/JSON communication

## Support

If issues persist:

1. Run diagnostics on Canmore:
   ```bash
   cd /Users/michel/dev/obsidian_rag
   ./diagnose_mcp_access.sh
   ```

2. Check all services are healthy:
   ```bash
   docker ps
   curl http://localhost:8811/health
   curl http://localhost:4000/api/v1/health
   ```

3. Check Claude Desktop logs on MacBook

4. Test direct curl commands to verify MCP is responding

---

**Created**: 2026-03-25
**Last Updated**: 2026-03-30
**Canmore Tailscale IP**: 100.110.65.38
