# Streaming Implementation

Streaming is supported via Server-Sent Events (SSE) in both the API gateway and the graph service.

## API Gateway

- **Reasoning**: `ws://localhost:4000/api/v1/deep-research`
- **Standard Search**: Streaming is currently supported via the graph service direct endpoint for debugging, or the Deep Thinking WebSocket for agentic workflows.
- *Note: The unified HTTP streaming endpoint is planned for v2.*

## Graph Service (Direct)

- Endpoint: `POST http://localhost:8002/query_stream`
- Accepts the same payload as `/query`, plus `stream: true`.
- Streams LLM output (native streaming where supported; chunked fallback otherwise).

Use the gateway endpoint for normal client use; use graph service streaming when you need direct control.
