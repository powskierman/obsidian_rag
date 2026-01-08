# Streaming Implementation

Streaming is supported via Server-Sent Events (SSE) in both the API gateway and the graph service.

## API Gateway

- Endpoint: `POST /api/v1/search/stream`
- Accepts the same payload as `/api/v1/search`.
- Returns SSE chunks (`data: {...}`) suitable for incremental rendering.

## Graph Service (Direct)

- Endpoint: `POST http://localhost:8002/query_stream`
- Accepts the same payload as `/query`, plus `stream: true`.
- Streams LLM output (native streaming where supported; chunked fallback otherwise).

Use the gateway endpoint for normal client use; use graph service streaming when you need direct control.
