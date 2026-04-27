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
# Canonical mode names: ask | research | investigate (WS only).
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"test","mode":"ask","max_results":3}'
```

For the staged research pipeline:

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"test","mode":"research","depth":"auto","max_results":5}'
```

For the agentic investigate path (WebSocket), see
`Documentation/reference/architecture/DEEP_THINKING_FLOW.md`.

## Authoritative Audit

```bash
python Scripts/debug/audit_search_modes.py
```

This is the canonical health check used by the project constitution
(`reference/governance/PROJECT_CONSTITUTION.md`).

## Optional Script

```bash
./Scripts/debug/test.sh
```

If the script reports missing components you no longer use, ignore those sections.
