# Web Search Implementation

Web search is optional and triggered by the `web_search` flag in `src/services/graph_query_service.py`.

## Requirements

- Set `TAVILY_API_KEY` in the environment.
- Send `web_search: true` in the request.

## Behavior

- The graph service extracts query terms from the current context.
- Tavily is called to fetch top external sources.
- Results are attached to the response under `web_search`.

Example request:

```json
{
  "query": "connect nextion to esp32",
  "mode": "hybrid",
  "web_search": true
}
```
