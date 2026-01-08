# Query Troubleshooting (CLI)

For general troubleshooting, use `Documentation/TROUBLESHOOTING_QUERY.md`.

## Quick CLI Checks

```bash
curl -s http://localhost:8000/stats
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"test","n_results":3}'
```

## Rebuild Services

```bash
./Scripts/docker/docker_rebuild.sh
```
