# Dual-Graph Query API - Complete Guide

## Overview

The Obsidian RAG system now features a **unified query API** that intelligently combines two complementary knowledge graphs:

| Graph | Type | Best For | Nodes | Edges |
|-------|------|----------|-------|-------|
| **NetworkX** | Note-centric | Note structure, wiki-links, vault organization | 16,212 | 16,268 |
| **LightRAG** | Entity-centric | Concepts, semantic search, cross-note discovery | 22,107 | 24,754 |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Frontend (Next.js webapp)                   │
│                   Port 3000                              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│            API Gateway (FastAPI)                         │
│                Port 4000                                 │
│  Endpoint: POST /api/v1/query                            │
│  Modes: networkx | lightrag | hybrid                     │
└────────┬────────────────────────┬─────────────────────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐      ┌──────────────────┐
│ NetworkX Service │      │ LightRAG Service │
│   Port 8002      │      │   Port 8001      │
│                  │      │                  │
│ • Wiki-links     │      │ • Entities       │
│ • Note structure │      │ • Semantic       │
│ • Kimi K2 LLM    │      │ • Kimi K2 LLM    │
│ • ChromaDB       │      │ • Ollama embed   │
└──────────────────┘      └──────────────────┘
```

---

## API Endpoints

### 1. Health Check

```http
GET /api/v1/health
```

**Response:**
```json
{
  "success": true,
  "data": {
    "gateway": "healthy",
    "services": {
      "embedding": {
        "status": "healthy",
        "url": "http://localhost:8000",
        "count": 1676
      },
      "networkx": {
        "status": "healthy",
        "url": "http://localhost:8002",
        "nodes": 16212,
        "edges": 16268
      },
      "lightrag": {
        "status": "healthy",
        "url": "http://localhost:8001",
        "nodes": 22107,
        "edges": 24754,
        "indexed_notes": 1686
      }
    }
  }
}
```

### 2. Unified Query

```http
POST /api/v1/query
Content-Type: application/json

{
  "query": "What is RAG?",
  "mode": "hybrid",
  "max_results": 10
}
```

**Modes:**

#### `networkx` - Note-Centric

Best for:
- Finding related notes
- Following wiki-link connections
- Understanding vault structure
- "What notes discuss X?"

**Response:**
```json
{
  "query": "What is RAG?",
  "mode": "networkx",
  "results": {
    "answer": "RAG (Retrieval Augmented Generation)...",
    "related_notes": [
      {
        "title": "RAG Systems.md",
        "score": 0.95,
        "connections": ["LLMs.md", "Vector Databases.md"]
      }
    ]
  },
  "metadata": {
    "source": "NetworkX Graph",
    "description": "Note-centric graph with wiki-link relationships"
  }
}
```

#### `lightrag` - Entity-Centric

Best for:
- Semantic concept search
- Finding entity relationships
- Cross-note concept discovery
- "What does my vault say about X?"

**Response:**
```json
{
  "query": "What is RAG?",
  "mode": "lightrag",
  "results": {
    "query": "What is RAG?",
    "mode": "hybrid",
    "result": "Based on your knowledge base, RAG (Retrieval Augmented Generation) is..."
  },
  "metadata": {
    "source": "LightRAG Graph",
    "description": "Entity-centric graph with semantic relationships"
  }
}
```

#### `hybrid` - Best of Both (Default)

Queries both graphs in parallel and combines results.

**Response:**
```json
{
  "query": "What is RAG?",
  "mode": "hybrid",
  "networkx": {
    "available": true,
    "data": { ... }
  },
  "lightrag": {
    "available": true,
    "data": { ... }
  },
  "metadata": {
    "description": "Combined results from both NetworkX and LightRAG"
  }
}
```

---

## Usage Examples

### Python

```python
import requests

# Hybrid query (recommended)
response = requests.post(
    "http://localhost:4000/api/v1/query",
    json={
        "query": "What are the main concepts in my vault?",
        "mode": "hybrid",
        "max_results": 10
    }
)

result = response.json()
print(result)
```

### cURL

```bash
# NetworkX mode
curl -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is deep learning?","mode":"networkx"}'

# LightRAG mode
curl -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is deep learning?","mode":"lightrag"}'

# Hybrid mode
curl -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is deep learning?","mode":"hybrid"}'
```

### JavaScript/TypeScript

```typescript
async function queryKnowledgeBase(query: string, mode: string = "hybrid") {
  const response = await fetch("/api/v1/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      mode,
      max_results: 10
    })
  })

  return response.json()
}

// Usage
const result = await queryKnowledgeBase("What is machine learning?", "hybrid")
```

---

## Testing

Use the provided test script:

```bash
# Test with default query
python Scripts/test_unified_query.py

# Test with custom query
python Scripts/test_unified_query.py "What are my main research topics?"
```

**What it tests:**
1. ✅ Health check (all services)
2. ✅ NetworkX query
3. ✅ LightRAG query
4. ✅ Hybrid query

---

## When to Use Each Mode

### Use `networkx` when:
- Exploring vault organization
- Following note connections
- Understanding link structure
- Looking for specific notes
- **Example:** "What notes link to 'Machine Learning'?"

### Use `lightrag` when:
- Searching for concepts
- Finding semantic relationships
- Discovering cross-note themes
- Asking general questions
- **Example:** "What does my vault say about neural networks?"

### Use `hybrid` when:
- You want comprehensive answers
- You're exploring a topic
- You need both structure + semantics
- You're unsure which graph is better
- **Example:** "Explain my notes on transformers"

**Recommendation:** Default to `hybrid` for most queries!

---

## Performance

| Mode | Latency | Thoroughness | Best Use |
|------|---------|--------------|----------|
| NetworkX | ~2-5s | Medium | Quick note lookups |
| LightRAG | ~5-15s | High | Deep semantic search |
| Hybrid | ~5-15s | Highest | Comprehensive answers |

**Note:** Hybrid queries run in parallel, so they're as fast as the slowest service.

---

## Configuration

### Docker Compose

```yaml
api-gateway:
  environment:
    - EMBEDDING_SERVICE_URL=http://embedding-service:8000
    - GRAPH_SERVICE_URL=http://graph-service:8002
    - LIGHTRAG_SERVICE_URL=http://lightrag-service:8001
```

### Local Development

```bash
export EMBEDDING_SERVICE_URL=http://localhost:8000
export GRAPH_SERVICE_URL=http://localhost:8002
export LIGHTRAG_SERVICE_URL=http://localhost:8001
```

---

## Troubleshooting

### "NetworkX service unreachable"

```bash
# Check if service is running
curl http://localhost:8002/health

# Restart if needed
cd config/docker
docker compose restart graph-service
```

### "LightRAG service unreachable"

```bash
# Check if service is running
curl http://localhost:8001/health

# Restart if needed
docker compose restart lightrag-service

# Check database is loaded
docker exec obsidian-lightrag ls -lh /app/lightrag_db/
```

### "Hybrid mode returns partial results"

This is normal! Hybrid mode gracefully degrades:
- If NetworkX fails, LightRAG results still returned
- If LightRAG fails, NetworkX results still returned
- Check `available: true/false` in response

---

## Next Steps

1. **Frontend Integration**
   - Add mode selector to UI
   - Display results from both graphs
   - Show graph visualizations

2. **Advanced Features**
   - Result ranking/scoring
   - Smart mode selection based on query
   - Caching for common queries

3. **Monitoring**
   - Track query latencies
   - Monitor service health
   - Log usage patterns

---

**Created:** December 31, 2025
**Status:** ✅ Production Ready
**Author:** Claude Code (Sonnet 4.5)
