# Docker MCP Integration

Use MCP with the unified MCP server (`src/mcp/obsidian_rag_unified_mcp.py`).
The API gateway (`:4000`) is not an MCP endpoint; it serves `/api/v1/*` HTTP APIs.

## Start Services

```bash
docker compose up -d embedding-service graph-service lightrag-service
```

## Start MCP (HTTP transport)

```bash
./venv/bin/python src/mcp/obsidian_rag_unified_mcp.py \
  --transport http --host 127.0.0.1 --port 8811 --path /mcp
```

## Health Checks

```bash
curl -s http://localhost:4000/api/v1/health
curl -s http://localhost:8000/health
curl -s http://localhost:8002/health
```

For ChatGPT connectors, expose `http://127.0.0.1:8811/mcp` via HTTPS tunnel and connect to the tunnel URL.
