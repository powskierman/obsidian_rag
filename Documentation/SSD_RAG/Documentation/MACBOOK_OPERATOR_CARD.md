# MacBook Operator Card

## Start Test

1. Plug in the SSD.
2. Confirm the bundle is present:
   ```bash
   ls /Volumes/work/canmore-obsidian-rag-project
   ```
3. Confirm Docker is running:
   ```bash
   docker info >/dev/null && echo docker-ok
   ```
4. Check for port conflicts:
   ```bash
   for p in 3030 4000 8000 8001 8002 8501 8811 11434 8090; do lsof -nP -iTCP:$p -sTCP:LISTEN; done
   ```
5. Start from the SSD:
   ```bash
   cd /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag
   ./scripts/setup/start_obsidian_rag.sh
   ```
6. Verify:
   ```bash
   curl -s http://localhost:4000/api/v1/health
   curl -s http://localhost:8811/health
   docker compose ps
   ```

## Optional UI Checks

- `http://localhost:3030`
- `http://localhost:8501`

## MCP Test

Use:

- `/Volumes/work/canmore-obsidian-rag-project/ai-config/claude-desktop/obsidian-rag-unified-http-local.json`

## If Start Fails

1. Read readiness log:
   ```bash
   tail -n 200 /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag/scripts/setup/logs/ready-check.log
   ```
2. Read container logs:
   ```bash
   cd /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag
   docker compose logs --tail=200
   ```
3. Check MLX:
   ```bash
   curl -s http://localhost:8090/v1/models
   ```
4. Check Ollama:
   ```bash
   curl -s http://localhost:11434/api/tags
   ```
5. Check gateway and MCP:
   ```bash
   curl -s http://localhost:4000/api/v1/health
   curl -s http://localhost:8811/health
   ```

## Most Likely Failure

- Docker not running
- Port already in use
- No working MLX runtime on `8090`
- No Ollama on `11434`
- SSD not mounted as `/Volumes/work`

## Quick Debug Capture

```bash
cd /Volumes/work/canmore-obsidian-rag-project/repos/obsidian_rag
docker compose ps
docker compose logs --tail=200 > /tmp/macbook-obsidian-rag-logs.txt
tail -n 200 scripts/setup/logs/ready-check.log
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
