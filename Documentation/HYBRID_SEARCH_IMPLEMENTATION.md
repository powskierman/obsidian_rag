# Hybrid Search Implementation

## Overview

The hybrid search functionality has been centralized in the **backend** `graph_query_service.py` to ensure consistent behavior across both the Streamlit and Next.js frontends.

## Architecture Change

### Before (Client-Side Hybrid)

**Streamlit App**: Implemented hybrid search logic in the UI code
- Called graph service to get graph context
- Extracted entities from the graph response
- Made a second call to vector service with enhanced query
- Combined results client-side

**Next.js App**: Had no hybrid implementation, causing inconsistent results

**Problem**: Duplicated logic, inconsistent behavior, difficult to maintain

### After (Server-Side Hybrid)

**Graph Service Backend**: Implements hybrid search in `/query` endpoint
- Single API call with `mode: "hybrid"` parameter
- Service handles both graph query and vector search internally
- Returns combined results with graph answer + vector sources

**Both UIs**: Simply call the backend with appropriate mode parameter
- Streamlit: `POST /query` with `{"mode": "hybrid"}`
- Next.js: `api.graphQuery(query, 'hybrid')`

**Benefits**: Single source of truth, consistent results, easier maintenance

## Implementation Details

### Backend: graph_query_service.py

**New `/query` endpoint parameters**:
```json
{
  "query": "What are the main health topics?",
  "mode": "graph" | "hybrid",        // optional, default: "graph"
  "max_entities": 20,                // optional
  "n_results": 10                    // optional, for hybrid mode
}
```

**Hybrid Mode Flow**:
1. **Query the knowledge graph** with Claude/Kimi to get graph-based answer
2. **Extract entities** from the graph answer using regex pattern matching
3. **Enhance the query** by appending extracted entities
4. **Call vector service** with enhanced query to get relevant document chunks
5. **Return combined result**:
   - `answer`: The graph-based answer
   - `sources`: Array of vector search results with relevance scores
   - `extracted_entities`: List of entities used to enhance the query

**Response format (hybrid mode)**:
```json
{
  "answer": "Based on the knowledge graph, the main health topics are...",
  "query": "What are the main health topics?",
  "mode": "hybrid",
  "sources": [
    {
      "filename": "Lane-Vital Question.md",
      "filepath": "/app/vault/Books/...",
      "relevance": 10.4,
      "snippet": "the greatest mutational health hazard..."
    }
  ],
  "extracted_entities": ["Mitochondria", "Cancer", "Aging", "Fertility"]
}
```

**Response format (graph-only mode)**:
```json
{
  "answer": "Based on the knowledge graph...",
  "query": "What are the main health topics?",
  "mode": "graph"
}
```

### Entity Extraction Algorithm

```python
def extract_entities_from_graph(graph_text: str) -> list:
    """Extract key entities from graph response text."""
    # Extract capitalized phrases (likely entities)
    entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', graph_text)

    # Filter out common stopwords
    stopwords = {'The', 'This', 'That', 'These', 'Those', 'There', 'Here',
                 'When', 'Where', 'What', 'How', 'Why', 'Based', 'Your'}

    entities = [e for e in entities if e not in stopwords]
    entities = list(set(entities))[:10]  # Top 10 unique entities

    return entities
```

### Configuration Changes

**docker-compose.yml**:
```yaml
graph-service:
  environment:
    - EMBEDDING_SERVICE_URL=http://embedding-service:8000
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
    requests  # Added for vector service HTTP calls
```

### Frontend Integration

#### Next.js API Client

**Updated signature**:
```typescript
graphQuery: async (
  query: string,
  mode: 'graph' | 'hybrid' = 'graph',
  n_results = 10
): Promise<{
  answer: string;
  sources?: SearchResult[];
  extracted_entities?: string[]
}>
```

**Usage example**:
```typescript
// Knowledge-graph only
const result = await api.graphQuery(query, 'graph');
console.log(result.answer);

// Hybrid mode
const result = await api.graphQuery(query, 'hybrid', 10);
console.log(result.answer);
console.log(result.sources);  // Vector search results
console.log(result.extracted_entities);  // Entities used
```

#### Streamlit App

**Simplified hybrid search**:
```python
# Before: 50+ lines of client-side logic

# After: Single API call
response = requests.post(
    f'{CLAUDE_GRAPH_SERVICE_URL}/query',
    json={
        'query': prompt,
        'mode': 'hybrid',
        'max_entities': 20,
        'n_results': num_sources
    }
)

result = response.json()
graph_answer = result['answer']
vector_sources = result.get('sources', [])
entities = result.get('extracted_entities', [])
```

## Testing

### Test Hybrid Mode

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main health topics?",
    "mode": "hybrid",
    "max_entities": 10,
    "n_results": 5
  }' | python3 -m json.tool
```

**Expected Response**:
- ✅ `answer`: Graph-based synthesis
- ✅ `sources`: Array of 5 vector search results
- ✅ `extracted_entities`: Array of entity strings
- ✅ `mode`: "hybrid"

### Test Graph-Only Mode

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main health topics?",
    "max_entities": 10
  }' | python3 -m json.tool
```

**Expected Response**:
- ✅ `answer`: Graph-based synthesis
- ✅ `mode`: "graph"
- ❌ No `sources` field

## Benefits

### 1. **Consistency**
Both Streamlit and Next.js apps get identical hybrid search results because they use the same backend implementation.

### 2. **Maintainability**
Hybrid search logic lives in one place. Bug fixes and improvements automatically benefit both UIs.

### 3. **Performance**
Internal network communication between Docker containers is faster than client → service1 → client → service2 round trips.

### 4. **Simplified Frontend**
UIs just need to call one endpoint with a mode parameter instead of orchestrating multiple service calls.

### 5. **Extensibility**
Easy to add more modes (e.g., `mode: "vector"` for vector-only, `mode: "deep-thinking"` for web-enhanced).

## Migration Path

### For Streamlit App

**Remove client-side hybrid logic**:
- Delete entity extraction code (~50 lines)
- Delete dual API call orchestration (~80 lines)
- Replace with single `mode: "hybrid"` parameter

**Total code reduction**: ~130 lines

### For Next.js App

**Update call sites**:
```typescript
// Before
const answer = await api.graphQuery(query);

// After
const result = await api.graphQuery(query, searchMode === 'hybrid' ? 'hybrid' : 'graph');
const answer = result.answer;
const sources = result.sources || [];
```

## Error Handling

The backend implements **graceful degradation**:

1. **Vector service unavailable**: Returns graph-only result with warning
2. **Entity extraction fails**: Returns graph-only result with warning
3. **Vector search returns no results**: Returns graph answer without sources

**Example fallback response**:
```json
{
  "answer": "Based on the knowledge graph...",
  "query": "...",
  "mode": "graph",
  "warning": "Vector search unavailable, returned graph-only result"
}
```

## Future Enhancements

### 1. Mode: Vector-Only
Add `mode: "vector"` to graph service that delegates entirely to vector service.

### 2. Caching
Cache extracted entities for common queries to avoid repeated graph calls.

### 3. Weighted Hybrid
Allow clients to specify weights: `{"mode": "hybrid", "graph_weight": 0.7, "vector_weight": 0.3}`.

### 4. Streaming Hybrid
Stream graph answer first, then append vector sources as they arrive.

### 5. Cross-Service LLM
Use vector context as `additional_context` parameter in graph querier for even deeper integration.

## Related Files

- **Backend**: [`src/services/graph_query_service.py`](../src/services/graph_query_service.py)
- **Graph Builder**: [`src/services/kimi_graph_builder.py`](../src/services/kimi_graph_builder.py)
- **Next.js API**: [`webapp/src/lib/api.ts`](../webapp/src/lib/api.ts)
- **Streamlit UI**: [`src/ui/streamlit_ui_docker.py`](../src/ui/streamlit_ui_docker.py)
- **Docker Config**: [`docker-compose.yml`](../docker-compose.yml)
- **Dockerfile**: [`config/docker/Dockerfile.graph`](../config/docker/Dockerfile.graph)

---

**Implementation Date**: December 27, 2025
**Status**: ✅ Complete and tested
**Breaking Changes**: None (backward compatible - `mode` parameter is optional)
