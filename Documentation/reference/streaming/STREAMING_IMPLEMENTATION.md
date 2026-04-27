# Streaming Implementation

The gateway streams progressively only on the WebSocket path. The HTTP query
endpoint always returns a single JSON response — there is no SSE channel.

## API Gateway

- **Investigate (agentic, streaming)**: `ws://localhost:4000/api/v1/deep-research`
  - Implemented in `src/services/api_gateway.py` (`@app.websocket("/api/v1/deep-research")`).
  - Sends a sequence of JSON messages: `progress`, `evidence`, `final`, `error`.
  - Closes the socket after `final` or on error.
- **Standard Search (non-streaming)**: `POST /api/v1/query`
  - Returns a single JSON body for `mode=ask` and `mode=research`.
  - The legacy mode strings (`vector`, `cascading`, `vault_review`, `mempalace`) also return single JSON bodies.

## Internal Graph Service

- The internal `POST http://localhost:8002/query_stream` endpoint exists for
  graph-service internal use. It is **not** proxied through the public gateway
  and clients should not call it directly. Use `POST /api/v1/query` instead.

## Client Notes

- For long investigate runs, keep the WebSocket open until you receive the
  `final` event.
- The webapp's `ThinkingIndicator` component listens for `progress` events to
  render intermediate plan/reflection updates.

Use gateway endpoints for all client traffic.
