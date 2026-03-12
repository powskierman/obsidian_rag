# Testing

## Quick Health Checks

```bash
docker compose ps
curl -s http://localhost:8000/health
curl -s http://localhost:8002/health
curl -s http://localhost:4000/api/v1/health
```

## Smoke Test

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"test","mode":"vector","max_results":3}'
```

## Optional Script

```bash
./Scripts/debug/test.sh
```

If the script reports missing components you no longer use, ignore those sections.
