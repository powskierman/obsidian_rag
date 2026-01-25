# Search Examples

Short, representative queries for each mode.

## Vector (fast retrieval)

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"ESP32 UART wiring","mode":"vector","max_results":5}'
```

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"CAR-T timeline","mode":"vector","max_results":5}'
```

## Graph (relationship reasoning)

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"How are Nextion and ESPHome connected?","mode":"graph","llm_provider":"kimi"}'
```

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Notes linking to propane stove control","mode":"graph"}'
```

## Hybrid (graph answer + vector sources)

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"nextion esp32 update process","mode":"hybrid","max_results":5}'
```

## Dual-Graph (gateway only)

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"garage automation","mode":"dual-graph","max_results":10}'
```
