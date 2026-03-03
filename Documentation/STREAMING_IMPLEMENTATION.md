# Streaming Implementation

Streaming uses WebSocket for Deep Thinking and SSE for HTTP search streaming.

## API Gateway

- **Reasoning**: `ws://localhost:4000/api/v1/deep-research`
- **Standard Search**: `POST /api/v1/query` for regular JSON responses
- **HTTP Streaming**: `POST /api/v1/query` for SSE (`text/event-stream`)

## Graph Service (Internal)

- Internal endpoint: `POST http://localhost:8002/query_stream`
- This is deprecated for direct client use and is now behind the gateway stream proxy.
- Existing direct callers should migrate to `POST /api/v1/query`.

Use gateway endpoints for all client traffic.
