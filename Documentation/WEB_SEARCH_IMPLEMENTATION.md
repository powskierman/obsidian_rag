# Web Search Implementation

## Overview

The intelligent web search functionality has been integrated into the backend `graph_query_service.py` to provide context-aware web searches that leverage both knowledge graph analysis and vector search results.

## Architecture

### Backend-First Design

**Graph Service Backend**: Implements intelligent web search in `/query` endpoint
- Combines graph answer with vector search results for richer context
- Uses Kimi (OpenRouter) to extract specific medical/technical terms
- Performs Tavily web search with extracted terms
- Returns web search results alongside graph answer and vector sources

**Benefits**:
- Both Streamlit and Next.js apps get identical web search functionality
- Context-aware search terms rather than raw user queries
- Single source of truth for web search logic

## Implementation Details

### Backend: graph_query_service.py

**Updated `/query` endpoint parameters**:
```json
{
  "query": "review my 4 pet scans",
  "mode": "graph" | "hybrid",        // optional, default: "graph"
  "max_entities": 20,                // optional
  "n_results": 10,                   // optional, for hybrid mode
  "web_search": true                 // optional, enables web search
}
```

### Web Search Flow

1. **Query knowledge graph** to get graph-based analysis
2. **Optional: Enhance with vector search** if `mode: "hybrid"` is enabled
3. **Extract intelligent search terms** from combined context:
   - Combines graph answer with top 3 vector source snippets
   - Uses Kimi to extract 4-6 specific medical terms, medications, procedures, measurements
   - Focuses on technical concepts that would yield better web results
4. **Perform Tavily web search** with extracted terms (advanced depth, 5 results max)
5. **Return combined result** with all components

### Search Term Extraction Algorithm

The system uses Kimi (OpenRouter) to intelligently extract search terms:

```python
search_terms_prompt = """Based on this combined knowledge, extract 4-6 specific medical terms, medications, procedures, measurements, or technical concepts that would find the most relevant and detailed clinical information on the web. Focus on:
- Specific medical conditions, diseases, or syndromes mentioned
- Medications, treatments, or procedures
- Technical measurements, biomarkers, or test results
- Specific medical entities (not general terms)

Context:
{combined_context[:1500]}

Provide only the search terms separated by spaces, no explanation or formatting."""
```

**Example**:
- **User query**: "review my 4 pet scans"
- **Graph context**: Discussion about mitochondrial function, CAR-T therapy, cell death mechanisms
- **Vector context**: Snippets about degenerative diseases and biomarkers
- **Extracted terms**: `mitochondrial ATP production CAR-T cell therapy apoptosis biomarkers degenerative disease`

These terms are much more specific and clinically relevant than searching for "review my 4 pet scans" directly.

### Response Format

**With web search enabled (hybrid mode)**:
```json
{
  "answer": "Based on the knowledge graph analysis...",
  "query": "review my 4 pet scans",
  "mode": "hybrid",
  "sources": [
    {
      "filename": "Lane-Vital Question.md",
      "filepath": "/app/vault/Books/...",
      "relevance": 10.4,
      "snippet": "the greatest mutational health hazard..."
    }
  ],
  "extracted_entities": ["Mitochondria", "Cancer", "Aging"],
  "web_search": {
    "search_terms": "mitochondrial ATP production CAR-T cell therapy apoptosis biomarkers degenerative disease",
    "results": [
      {
        "title": "Mitochondrial ATP Production in Cancer Cells",
        "url": "https://example.com/article",
        "content": "Recent studies show that..."
      }
    ]
  }
}
```

**Without web search (standard hybrid mode)**:
```json
{
  "answer": "Based on the knowledge graph analysis...",
  "query": "review my 4 pet scans",
  "mode": "hybrid",
  "sources": [...],
  "extracted_entities": [...]
}
```

### Configuration Changes

**docker-compose.yml**:
```yaml
graph-service:
  environment:
    - EMBEDDING_SERVICE_URL=http://embedding-service:8000
    - TAVILY_API_KEY=${TAVILY_API_KEY:-}
  depends_on:
    - embedding-service
```

**Dockerfile.graph**:
```dockerfile
RUN pip install --no-cache-dir \
    openai \
    flask \
    flask-cors \
    networkx \
    tqdm \
    requests \
    tavily-python
```

## Testing

### Test Web Search with Hybrid Mode

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are mitochondrial health factors?",
    "mode": "hybrid",
    "max_entities": 20,
    "n_results": 10,
    "web_search": true
  }' | python3 -m json.tool
```

**Expected Response**:
- ✅ `answer`: Graph-based synthesis
- ✅ `sources`: Array of vector search results
- ✅ `extracted_entities`: Entities from graph
- ✅ `web_search.search_terms`: Intelligent extracted terms
- ✅ `web_search.results`: Array of 3 web results with title, url, content

### Verified Logs

```
2025-12-27 20:38:48 - __main__ - INFO - Web search terms extracted: mitochondrial ATP production CAR-T cell therapy apoptosis biomarkers degenerative disease
2025-12-27 20:38:54 - __main__ - INFO - Web search returned 3 results
2025-12-27 20:38:54 - werkzeug - INFO - 142.251.34.202 - - [27/Dec/2025 20:38:54] "POST /query HTTP/1.1" 200 -
```

## Error Handling

The backend implements **graceful degradation** for web search:

1. **TAVILY_API_KEY not configured**: Returns error in `web_search` field
   ```json
   "web_search": {
     "error": "TAVILY_API_KEY not configured"
   }
   ```

2. **tavily-python not installed**: Returns error in `web_search` field
   ```json
   "web_search": {
     "error": "tavily-python not installed"
   }
   ```

3. **No web results found**: Returns empty results with message
   ```json
   "web_search": {
     "search_terms": "...",
     "results": [],
     "message": "No web results found"
   }
   ```

4. **Web search exception**: Returns error message, but graph and vector results still work
   ```json
   "web_search": {
     "error": "Connection timeout"
   }
   ```

## Frontend Integration

### Streamlit App

The Streamlit app should be updated to pass `web_search: true` when "Extended Search" is enabled:

```python
response = requests.post(
    f'{CLAUDE_GRAPH_SERVICE_URL}/query',
    json={
        'query': prompt,
        'mode': 'hybrid',
        'max_entities': 20,
        'n_results': num_sources,
        'web_search': extended_search_enabled  # Add this parameter
    }
)

result = response.json()
graph_answer = result['answer']
vector_sources = result.get('sources', [])
entities = result.get('extracted_entities', [])
web_search = result.get('web_search', {})

if web_search and 'results' in web_search:
    st.write(f"**Web Search Terms**: {web_search['search_terms']}")
    for web_result in web_search['results']:
        st.write(f"- [{web_result['title']}]({web_result['url']})")
        st.write(f"  {web_result['content'][:200]}...")
```

### Next.js App

The Next.js API client can be extended to support web search:

```typescript
graphQuery: async (
  query: string,
  mode: 'graph' | 'hybrid' = 'graph',
  n_results = 10,
  web_search = false
): Promise<{
  answer: string;
  sources?: SearchResult[];
  extracted_entities?: string[];
  web_search?: {
    search_terms: string;
    results: Array<{ title: string; url: string; content: string }>;
  };
}> => {
  const response = await fetch(`${GRAPH_URL}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      max_entities: 20,
      mode,
      n_results,
      web_search
    })
  });

  return await response.json();
}
```

## Benefits

### 1. **Context-Aware Search Terms**
Instead of searching the web with raw user queries like "review my 4 pet scans", the system extracts specific medical terms like "mitochondrial ATP production CAR-T cell therapy apoptosis biomarkers" that yield much more relevant clinical information.

### 2. **Multi-Source Intelligence**
Combines three sources of knowledge:
- **Knowledge Graph**: Structural relationships and conceptual links
- **Vector Search**: Relevant document snippets from your vault
- **Web Search**: Latest clinical research and medical information

### 3. **Consistency Across UIs**
Both Streamlit and Next.js apps get identical web search functionality since it's implemented in the backend.

### 4. **Fallback Safety**
If web search fails, the graph answer and vector sources are still returned, ensuring users always get value.

### 5. **Efficient Search**
Only searches the web when explicitly requested via `web_search: true` parameter, avoiding unnecessary API calls and costs.

## Use Cases

### Medical Research Query
**User Query**: "What's the latest on mitochondrial dysfunction?"

**Flow**:
1. Graph analyzes relationships between mitochondria, aging, disease
2. Vector search finds relevant vault notes
3. Extracts terms: "mitochondrial dysfunction ATP synthesis oxidative stress aging"
4. Web search finds latest clinical research
5. Returns comprehensive answer with vault context + latest research

### Treatment Review
**User Query**: "Review CAR-T therapy options"

**Flow**:
1. Graph identifies CAR-T relationships with cancer, treatments, outcomes
2. Vector search finds personal notes on CAR-T
3. Extracts terms: "CAR-T cell therapy B-cell lymphoma cytokine release syndrome"
4. Web search finds latest treatment protocols and clinical trials
5. Returns personalized answer combining vault knowledge + current medical literature

## Future Enhancements

### 1. Configurable Search Depth
Allow clients to specify Tavily search depth: `basic`, `advanced`

### 2. Citation Integration
Automatically add web search citations to the LLM-generated answer

### 3. Caching
Cache web search results for identical search terms to reduce API costs

### 4. Search Result Ranking
Combine relevance scores from graph, vector, and web sources for unified ranking

### 5. Streaming Web Results
Stream web search results as they arrive for faster perceived performance

## Related Files

- **Backend**: [src/services/graph_query_service.py](../src/services/graph_query_service.py)
- **Graph Builder**: [src/services/kimi_graph_builder.py](../src/services/kimi_graph_builder.py)
- **Next.js API**: [webapp/src/lib/api.ts](../webapp/src/lib/api.ts)
- **Streamlit UI**: [src/ui/streamlit_ui_docker.py](../src/ui/streamlit_ui_docker.py)
- **Docker Config**: [docker-compose.yml](../docker-compose.yml)
- **Dockerfile**: [config/docker/Dockerfile.graph](../config/docker/Dockerfile.graph)

---

**Implementation Date**: December 27, 2025
**Status**: ✅ Complete and tested
**Breaking Changes**: None (backward compatible - `web_search` parameter is optional)
**Verified**: Logs show successful extraction of "mitochondrial ATP production CAR-T cell therapy apoptosis biomarkers degenerative disease" and 3 web results returned
