# Docker MCP Integration

Use MCP via the unified API gateway container.

## Start Services

```bash
docker compose up -d
```

## Health Check

```bash
curl -s http://localhost:4000/api/v1/health
```

If Claude Desktop cannot connect, ensure the gateway port `4000` is accessible locally.
