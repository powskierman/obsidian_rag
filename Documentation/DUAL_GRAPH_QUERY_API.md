# Dual Graph Query API

Dual-graph mode is exposed via the API gateway and combines NetworkX (notes) and LightRAG (entities).

## Request

```json
{
  "query": "garage automation",
  "mode": "dual-graph",
  "max_results": 10
}
```

## Response (shape)

```json
{
  "query": "...",
  "mode": "dual-graph",
  "notes": {"available": true, "data": {...}},
  "entities": {"available": true, "data": {...}}
}
```

Use `Documentation/API_GATEWAY_QUICKSTART.md` for gateway basics.
