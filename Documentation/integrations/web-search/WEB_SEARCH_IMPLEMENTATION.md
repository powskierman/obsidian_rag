# Web Search Implementation

Web search is optional and triggered by the `web_search` flag on `POST /api/v1/query`.

## Requirements

- Set `TAVILY_API_KEY` in the environment.
- Send `web_search: true` in the request.

## Behavior

- The API gateway calls Tavily directly from `src/services/api_gateway.py`.
- Results are attached to the response under `web_search`.
- `vector` and `cascading` can both return web-search results.
- Web results are supplemental evidence. The webapp renders vault sources first and web sources after them.
- If no results are available, the response may still include a `message` explaining whether the search was skipped, failed, or returned nothing.

Example request:

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
