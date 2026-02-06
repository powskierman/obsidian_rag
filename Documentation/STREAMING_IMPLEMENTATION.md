# Streaming Implementation

Streaming currently uses WebSocket at the gateway and SSE-style chunked responses from the direct graph-service endpoint.

## API Gateway

- **Reasoning**: `ws://localhost:4000/api/v1/deep-research`
- **Standard Search**: use `POST /api/v1/query` for regular responses.
- *Note: The unified HTTP streaming endpoint is not exposed on the gateway today.*

## Graph Service (Direct)

- Endpoint: `POST http://localhost:8002/query_stream`
- Accepts the same payload as `/query`, plus `stream: true`.
- Streams LLM output (native streaming where supported; chunked fallback otherwise).

Use the gateway endpoint for normal client use; use graph service streaming when you need direct control.
