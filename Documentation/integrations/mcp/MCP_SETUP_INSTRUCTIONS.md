# MCP Setup Instructions for ChatGPT Desktop

## Quick Setup: Unified MCP Server

### Step 1: Start Required Services

Start the services ChatGPT will query through the MCP server:

```bash
docker compose up -d embedding-service
```

Optional (Graph service is only needed for the graph API, not MCP graph queries):

```bash
docker compose up -d graph-service
```

Optional (LightRAG is not required for MCP tools):

```bash
docker compose up -d lightrag-service
```

### Step 2: Verify the MCP Server venv

```bash
/Users/michel/dev/obsidian_rag/venv/bin/python \
  -c "import requests, mcp; print('deps ok')"
```

### Step 3: Update ChatGPT Desktop MCP Config

Open ChatGPT Desktop → **Settings → Developer → MCP** and open the config file.

Add or update the `obsidian-rag-unified` block:

```json
{
  "mcpServers": {
    "obsidian-rag-unified": {
      "command": "/Users/michel/dev/obsidian_rag/venv/bin/python",
      "args": [
        "-u",
        "/Users/michel/dev/obsidian_rag/src/mcp/obsidian_rag_unified_mcp.py"
      ],
      "env": {
        "EMBEDDING_SERVICE_URL": "http://localhost:8000",
        "KNOWLEDGE_GRAPH_PATH": "/Users/michel/dev/obsidian_rag/data/graph_data/knowledge_graph_full.pkl",
        "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
      }
    }
  }
}
```

Notes:
- The MCP server loads the repo `.env` automatically.
- Graph tools require `OPENAI_API_KEY` (either in the MCP env block or in the repo `.env`).
- Set `OPENAI_MODEL` in `.env` to choose the model (example: `gpt-5-mini`).
- If you only need semantic search, omit `OPENAI_API_KEY` and graph tools will not load.

### Step 4: Restart ChatGPT Desktop

1. Quit ChatGPT Desktop completely (Cmd+Q)
2. Reopen ChatGPT Desktop
3. Check MCP status in settings

### Step 5: Test It

Ask ChatGPT:
- "Search my vault for CAR-T therapy"
- "What treatments are mentioned in my notes?"
- "How does ESP32 relate to Home Assistant?"

## ChatGPT Connector (HTTPS)

ChatGPT connectors require a public HTTPS `/mcp` endpoint. Run the server in HTTP mode locally, then expose it with a tunnel (ngrok or Cloudflare Tunnel).

1. Set an API key for the HTTP server (recommended):
   ```bash
   export MCP_HTTP_API_KEY="your-strong-key"
   ```

2. Start the HTTP MCP server:
   ```bash
/Users/michel/dev/obsidian_rag/venv/bin/python \
  /Users/michel/dev/obsidian_rag/src/mcp/obsidian_rag_unified_mcp.py \
  --transport http --host 0.0.0.0 --port 8811 --path /mcp
   ```

3. Expose it with ngrok:
   ```bash
   ngrok http 8811
   ```

4. In ChatGPT: Settings → Connectors → Create
   - Connector URL: `https://<your-ngrok-subdomain>.ngrok-free.app/mcp`
   - Auth: API key
     - Header: `Authorization`
     - Value: `Bearer your-strong-key`
     - Alternatively, use header `X-API-Key` with the same value.

Notes:
- If the HTTP server fails to start, install `uvicorn` in the venv.
- Keep the tunnel running while you use the connector.
- Use `0.0.0.0` when you need access over Tailscale or another remote interface. Use `127.0.0.1` only for local-only testing.

### OAuth Mode (for ChatGPT connectors that require OAuth)

If the connector UI only offers OAuth, enable OAuth mode and restart the server using your public HTTPS base URL.

1. Start ngrok first and copy the HTTPS URL:
   ```bash
   ngrok http 8811
   ```

2. Export the public URL and enable OAuth:
   ```bash
   export MCP_HTTP_AUTH_MODE="oauth"
   export MCP_HTTP_PUBLIC_URL="https://<your-ngrok-subdomain>.ngrok-free.app"
   ```

3. Start the server:
   ```bash
/Users/michel/dev/obsidian_rag/venv/bin/python \
  /Users/michel/dev/obsidian_rag/src/mcp/obsidian_rag_unified_mcp.py \
  --transport http --host 0.0.0.0 --port 8811 --path /mcp
   ```

4. In ChatGPT: Settings → Connectors → Create
   - Connector URL: `https://<your-ngrok-subdomain>.ngrok-free.app/mcp`
   - Auth: OAuth

Optional: pre-register a client (skip if you want dynamic registration):
```bash
export MCP_OAUTH_CLIENT_ID="my-client"
export MCP_OAUTH_CLIENT_SECRET="my-secret"
export MCP_OAUTH_REDIRECT_URIS="https://example.com/oauth/callback"
```

## Available Tools

### Vault Search
- **`obsidian_semantic_search`** - Semantic search with 1-10 results and snippets
- **`search_vault_full`** - Semantic search + full note text (+ optional embedded PDF extraction)
- **`obsidian_search_mode`** - Gateway mode tool supporting:
  - `vector`
  - `cascading`
  - `deep-research`
  - Legacy aliases may still be accepted for backward compatibility, but they are not part of the supported public mode contract.

### Knowledge Graph
- **`obsidian_graph_query`** - Advanced/internal graph query helper (tries graph service first, then local graph fallback)
- **`get_entity_info`** - Get entity details
- **`find_entity_path`** - Find connections between entities
- **`search_entities`** - Search for entities
- **`get_graph_stats`** - Graph statistics

### Vault Stats
- **`obsidian_vault_stats`** - Vault statistics

Compatibility aliases still accepted by the server: `search_vault`, `get_vault_stats`, `query_knowledge_graph`.

## Troubleshooting

### MCP Server Not Loading

1. **Check Python Path:**
   ```bash
   which python
   # Should match the command in config
   ```

2. **Test Server Manually:**
   ```bash
   python src/mcp/obsidian_rag_unified_mcp.py
   # Should start without errors
   ```

3. **Check Environment Variables:**
   - `EMBEDDING_SERVICE_URL` should point to running service
   - Graph service URL can be set with `CLAUDE_GRAPH_SERVICE_URL` or `GRAPH_SERVICE_URL`
   - Gateway URL can be set with `MCP_GATEWAY_URL` (default: `http://localhost:4000`)
   - `OPENAI_API_KEY` (or `GEMINI_API_KEY` with `MCP_GRAPH_PROVIDER=gemini`) is only needed for local graph synthesis

### Services Not Available

1. **Start Embedding Service:**
   ```bash
   docker-compose up embedding-service -d
   ```

2. **Start Graph Service:**
   ```bash
   docker-compose up graph-service -d
   ```

3. **Check Service URLs:**
   - Embedding: http://localhost:8000
   - Graph: http://localhost:8002

### Graph Not Loading

1. **Check Graph File:**
   ```bash
   ls -lh graph_data/knowledge_graph_full.pkl data/graph_data/knowledge_graph_full.pkl
   ```

2. **Set KNOWLEDGE_GRAPH_PATH:**
   - In Claude Desktop config env section
   - Or ensure file is in default location

## Migration from Old Setup

If you're using the old `obsidian_rag_mcp_fixed.py`:

1. **Replace in config:**
   - Old: `obsidian_rag_mcp_fixed.py`
   - New: `obsidian_rag_unified_mcp.py`

2. **Update server name:**
   - Old: `"obsidian-rag"`
   - New: `"obsidian-rag-unified"`

3. **Add environment variables:**
   - `EMBEDDING_SERVICE_URL`
   - `OPENAI_API_KEY` (optional, only for graph tools)

## Benefits of Unified Server

✅ **One server** instead of two
✅ **Better vault search** (5-10 results vs 3)
✅ **Content snippets** included
✅ **All tools** in one place
✅ **Easier maintenance** - single file
✅ **Better error messages**
