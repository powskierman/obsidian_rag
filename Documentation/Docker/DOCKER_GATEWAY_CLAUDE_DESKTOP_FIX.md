# Claude Desktop + Gateway Fix

If Claude Desktop cannot reach the gateway:

1. Ensure services are running:
   ```bash
   docker compose up -d
   ```
2. Confirm the gateway responds:
   ```bash
   curl -s http://localhost:4000/api/v1/health
   ```
3. Verify the MCP config uses `http://localhost:4000`.
