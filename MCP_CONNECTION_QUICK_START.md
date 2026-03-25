# MCP Connection Quick Start

Connect your MacBook to Canmore's Obsidian RAG via Tailscale.

## ✅ Status Check (Done on Canmore)

All services are running and accessible via Tailscale:

```
✅ MCP Server:      0.0.0.0:8811 (HTTP)
✅ API Gateway:     0.0.0.0:4000
✅ Canmore Tailscale IP: 100.110.65.38
```

## 🚀 Setup on MacBook (3 Steps)

### 1. Test Connection

```bash
curl http://100.110.65.38:8811/health
# Should return: ok
```

### 2. Configure Claude Desktop

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

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

### 3. Restart Claude Desktop

Quit completely, then reopen.

## 🧪 Test It

In Claude Desktop:

```
Search my Obsidian vault for "test"
```

Should work! ✨

## 🆘 If It Doesn't Work

```bash
# On MacBook - Check logs:
tail -f ~/Library/Logs/Claude/mcp*.log

# Test MCP directly:
curl -X POST http://100.110.65.38:8811/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## 📚 Full Docs

- Complete setup: `Documentation/MCP_CLIENT_SETUP.md`
- SSH alternative: `Documentation/SSH_MCP_SETUP.md`
- Troubleshooting: `QUICK_FIX_MCP_SSH.md`

---

**Why HTTP Instead of SSH?**

- ✅ Bypasses macOS Full Disk Access restrictions
- ✅ No SSH key setup needed
- ✅ Lower latency
- ✅ Easier to debug
- ✅ Works over Tailscale
