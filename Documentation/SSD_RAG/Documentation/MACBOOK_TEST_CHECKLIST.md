# MacBook Test Checklist

## Preconditions

1. Plug in the SSD.
2. Confirm the bundle is present:
   ```bash
   ls /Volumes/work/canmore-obsidian-rag-project
   ```
3. Verify the mount path is exactly `/Volumes/work`:
   ```bash
   mount | grep ' /Volumes/work '
   ```
   If it mounted as `/Volumes/work 1` or similar, stop and fix that first.

## Bundle Validation

1. Confirm the key bundle paths exist:
   ```bash
   test -d /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag && echo repo-ok
   test -d /Volumes/work/canmore-obsidian-rag-project/vaults/Michel && echo vault-ok
   test -d /Volumes/work/canmore-obsidian-rag-project/state/obsidian-rag/lightrag_db && echo state-ok
   ```
2. Confirm Docker Desktop is installed and running:
   ```bash
   docker info >/dev/null && echo docker-ok
   ```
3. Check for port conflicts:
   ```bash
   for p in 3030 4000 8000 8001 8002 8501 8811 11434 8090; do lsof -nP -iTCP:$p -sTCP:LISTEN; done
   ```
4. Inspect the bundle-local environment:
   ```bash
   sed -n '1,120p' /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag/.env
   ```
   Confirm these point into `/Volumes/work/canmore-obsidian-rag-project/...`:
   - `OBSIDIAN_VAULT_PATH`
   - `OBSIDIAN_RAG_DATA_DIR`
   - `GRAPH_PATH`
   - `CHROMA_DB_PATH`
   - `LIGHTRAG_DIR`
5. Syntax-check the startup helpers:
   ```bash
   bash -n /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag/scripts/setup/start_obsidian_rag.sh
   bash -n /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag/scripts/setup/wait_for_obsidian_rag_ready.sh
   ```

## Direct Drive Startup Test

1. Start from the SSD copy:
   ```bash
   cd /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag
   ./scripts/setup/start_obsidian_rag.sh
   ```
2. Verify health:
   ```bash
   curl -s http://localhost:4000/api/v1/health
   curl -s http://localhost:8811/health
   docker compose ps
   ```
3. Optional UI checks:
   - `http://localhost:3030`
   - `http://localhost:8501`

## MCP Test

For the first MacBook test, use the bundled HTTP MCP config:

- `/Volumes/work/canmore-obsidian-rag-project/ai-config/claude-desktop/obsidian-rag-unified-http-local.json`

This avoids depending on a recreated repo-local `venv`.

## If `start_obsidian_rag.sh` Fails

1. Check Docker:
   ```bash
   docker info
   docker compose ps
   ```
2. Read the readiness log first:
   ```bash
   tail -n 200 /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag/scripts/setup/logs/ready-check.log
   ```
3. Read container logs:
   ```bash
   cd /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag
   docker compose logs --tail=200
   ```
4. Narrow to a failing service if needed:
   ```bash
   docker compose logs --tail=200 api-gateway
   docker compose logs --tail=200 embedding-service
   docker compose logs --tail=200 graph-service
   docker compose logs --tail=200 lightrag-service
   docker compose logs --tail=200 mcp-unified
   docker compose logs --tail=200 webapp
   ```
5. Confirm the SSD paths are still readable:
   ```bash
   ls /Volumes/work/canmore-obsidian-rag-project/vaults/Michel | head
   ls /Volumes/work/canmore-obsidian-rag-project/state/obsidian-rag
   ```
6. Check Ollama:
   ```bash
   lsof -nP -iTCP:11434 -sTCP:LISTEN
   curl -s http://localhost:11434/api/tags
   ```
7. Check MLX:
   ```bash
   lsof -nP -iTCP:8090 -sTCP:LISTEN
   curl -s http://localhost:8090/v1/models
   ```
8. Check gateway and MCP directly:
   ```bash
   curl -s http://localhost:4000/api/v1/health
   curl -s http://localhost:8811/health
   ```
9. Rerun the readiness check alone if startup partially worked:
   ```bash
   /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag/scripts/setup/wait_for_obsidian_rag_ready.sh
   ```

## Most Likely Failure Points

- Docker Desktop not running
- Port conflicts on `4000`, `8000`, `8001`, `8002`, `8811`, `3030`, `8501`
- Ollama not installed or not launching
- MLX runtime not available on the MacBook
- SSD mounted somewhere other than `/Volumes/work`

## Capture Block For Debugging

If startup fails and you need a compact evidence set:

```bash
cd /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag
docker compose ps
docker compose logs --tail=200 > /tmp/macbook-obsidian-rag-logs.txt
tail -n 200 scripts/setup/logs/ready-check.log
curl -s http://localhost:4000/api/v1/health
curl -s http://localhost:8811/health
```

## Remote Access Note

If you need to verify or operate on the MacBook remotely from another machine, the current Tailscale hostname is `macbook-pro.taila61df4.ts.net`.

Basic reachability checks from another machine:
```bash
ping -c 1 macbook-pro.taila61df4.ts.net
nc -vz macbook-pro.taila61df4.ts.net 22
```

Reachability is not the same as login access. Remote editing or shell access still requires either:
- working SSH key authorization on the MacBook
- or Tailscale SSH enabled for the source machine/user

Even with successful SSH login, macOS may still block remote access to `/Volumes/work` with `Operation not permitted`.
If that happens, use a local shell on the MacBook for SSD edits, or grant the relevant remote-login process access to removable volumes / Full Disk Access.
