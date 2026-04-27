# Web Search Implementation

Web search is optional and triggered either by adding `"web"` to the canonical `sources` array on `POST /api/v1/query`, or by setting the legacy `web_search: true` shorthand.

## Requirements

- Set `TAVILY_API_KEY` in the environment.
- Send `sources: ["vault", "web"]` (canonical) or `web_search: true` (legacy shorthand) in the request.

## Behavior

- The API gateway calls Tavily directly from `src/services/api_gateway.py`.
- Results are attached to the response under `web_search`.
- Both `ask` and `research` modes (legacy: `vector` and `cascading`) can return web-search results.
- Web results are supplemental evidence. The webapp renders vault sources first and web sources after them.
- If no results are available, the response may still include a `message` explaining whether the search was skipped, failed, or returned nothing.
- The `investigate` WebSocket also calls Tavily during its multi-step plan when web evidence is requested or when the policy agent decides external context is needed.

Example request (canonical):

```json
{
  "query": "connect nextion to esp32",
  "mode": "research",
  "depth": "auto",
  "sources": ["vault", "web"]
}
```

Equivalent legacy form (still accepted; emits a `X-Deprecated-Mode` header):

```json
{
  "query": "connect nextion to esp32",
  "mode": "cascading",
  "web_search": true
}
```

Example response shape:

```json
{
  "answer": "...",
  "sources": [
    {
      "filename": "Example.md",
      "filepath": "Notes/Example.md",
      "relevance": 92.0,
      "snippet": "..."
    }
  ],
  "web_search": {
    "search_terms": "connect nextion to esp32",
    "results": [
      {
        "title": "Example external source",
        "url": "https://example.com",
        "content": "..."
      }
    ]
  }
}
```
