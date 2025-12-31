# API Gateway Quick Start Guide

**Status**: ✅ **LIVE and OPERATIONAL**
**Date**: December 28, 2025
**Port**: `http://localhost:4000`

---

## Overview

The Unified API Gateway is now **running and tested**! You have a single endpoint that any client can use to access your RAG system.

### What's Available

✅ **Unified Search API** - Vector, Graph, and Hybrid modes
✅ **Standardized Responses** - Consistent JSON format
✅ **Health Checks** - Monitor all backend services
✅ **Auto Documentation** - Interactive API explorer
✅ **Streaming Support** - Real-time responses (SSE)
✅ **WebSocket** - Bi-directional communication

---

## Quick Test

### Health Check
```bash
curl http://localhost:4000/api/v1/health | python3 -m json.tool
```

**Response**:
```json
{
    "success": true,
    "data": {
        "gateway": "healthy",
        "services": {
            "embedding": {"status": "healthy"},
            "graph": {"status": "healthy"}
        },
        "overall_status": "healthy"
    }
}
```

### Vector Search
```bash
echo '{"query":"CAR-T therapy","mode":"vector","n_results":3}' | \
  curl -s -X POST http://localhost:4000/api/v1/search \
  -H "Content-Type: application/json" -d @-
```

### Graph Search
```bash
echo '{"query":"What is DLBCL?","mode":"graph","llm_provider":"kimi"}' | \
  curl -s -X POST http://localhost:4000/api/v1/search \
  -H "Content-Type: application/json" -d @-
```

### Hybrid Search (Best of Both)
```bash
echo '{"query":"treatment options","mode":"hybrid","n_results":5}' | \
  curl -s -X POST http://localhost:4000/api/v1/search \
  -H "Content-Type: application/json" -d @-
```

---

## API Endpoints

### Search & Query

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/search` | POST | Unified search (auto-routes by mode) |
| `/api/v1/search/stream` | POST | Streaming search (Server-Sent Events) |
| `/api/v1/search/ws` | WS | WebSocket streaming |

### System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health status of all services |
| `/api/v1/stats` | GET | Combined statistics |
| `/api/v1/feedback` | POST | Submit query feedback |

### Documentation

| Endpoint | Description |
|----------|-------------|
| `/docs` | Interactive API explorer (Swagger UI) |
| `/redoc` | API documentation (ReDoc) |
| `/` | API info and links |

---

## Search Modes

### Vector Mode
- **Speed**: Fast (~200ms)
- **Method**: Semantic similarity search
- **LLM**: None (pure vector search)
- **Best for**: Quick document retrieval, exact concept matching

```json
{
  "query": "CAR-T therapy side effects",
  "mode": "vector",
  "n_results": 10
}
```

### Graph Mode
- **Speed**: Slower (~10s)
- **Method**: Knowledge graph reasoning + LLM
- **LLM**: Required (Kimi, Claude, Ollama, etc.)
- **Best for**: Complex questions, relationship understanding

```json
{
  "query": "Explain the connection between DLBCL and CAR-T",
  "mode": "graph",
  "llm_provider": "kimi",
  "n_results": 10
}
```

### Hybrid Mode (Recommended)
- **Speed**: Medium (~8s)
- **Method**: Vector search + Graph reasoning
- **LLM**: Required
- **Best for**: Most questions, balanced speed/quality

```json
{
  "query": "What are my treatment options?",
  "mode": "hybrid",
  "llm_provider": "kimi",
  "n_results": 10
}
```

---

## Request Format

### Full Request Schema

```json
{
  "query": "Your question here",
  "mode": "hybrid",
  "n_results": 10,

  "llm_provider": "kimi",
  "model": "",
  "temperature": 0.7,
  "system_prompt": "Optional custom instructions",

  "web_search": false,
  "llm_knowledge": false,
  "reranking": true,
  "deduplicate": true
}
```

### LLM Providers

| Provider | Value | Notes |
|----------|-------|-------|
| **Kimi K2** | `"kimi"` | Default, best for medical queries |
| **Ollama** | `"ollama"` | Local models (qwen2.5, llama, etc.) |
| **Claude** | `"claude"` | Anthropic (requires API key) |
| **Gemini** | `"gemini"` | Google (requires API key) |
| **GPT-OSS** | `"gpt_oss"` | GPT4All local server |

---

## Response Format

### Success Response

```json
{
  "success": true,
  "data": {
    "answer": "CAR-T therapy is...",
    "sources": [
      {
        "filename": "note.md",
        "filepath": "/path/to/note.md",
        "relevance": 95.5,
        "snippet": "Relevant excerpt..."
      }
    ],
    "metadata": {
      "query_time_ms": 9385.25,
      "mode": "graph",
      "entities_found": 15,
      "llm_provider": "kimi",
      "model": "kimi-k2-0905"
    }
  },
  "error": null,
  "timestamp": "2025-12-28T20:32:19Z",
  "version": "v1"
}
```

### Error Response

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "SERVICE_ERROR",
    "message": "Backend service unavailable",
    "details": "Connection timeout"
  },
  "timestamp": "2025-12-28T20:32:19Z",
  "version": "v1"
}
```

---

## Interactive Documentation

### Swagger UI (Interactive)

Open in browser:
```
http://localhost:4000/docs
```

Features:
- Try endpoints directly in browser
- See request/response schemas
- Auto-generated examples
- Test different parameters

### ReDoc (Documentation)

Open in browser:
```
http://localhost:4000/redoc
```

Features:
- Clean, readable documentation
- Comprehensive schema definitions
- Code examples
- Easy to navigate

---

## Client Examples

### Python

```python
import requests

response = requests.post(
    'http://localhost:4000/api/v1/search',
    json={
        'query': 'What is CAR-T therapy?',
        'mode': 'hybrid',
        'n_results': 5,
        'llm_provider': 'kimi'
    }
)

result = response.json()
if result['success']:
    print(result['data']['answer'])
    for source in result['data']['sources']:
        print(f"  - {source['filename']} ({source['relevance']}%)")
```

### JavaScript / TypeScript

```typescript
const response = await fetch('http://localhost:4000/api/v1/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'What is DLBCL?',
    mode: 'hybrid',
    n_results: 10,
    llm_provider: 'kimi'
  })
});

const { success, data, error } = await response.json();
if (success) {
  console.log(data.answer);
  data.sources.forEach(source => {
    console.log(`  - ${source.filename} (${source.relevance}%)`);
  });
}
```

### curl (Terminal)

```bash
# Simple query
curl -X POST http://localhost:4000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "treatment options",
    "mode": "hybrid",
    "llm_provider": "kimi"
  }' | python3 -m json.tool

# From file
echo '{"query":"CAR-T","mode":"vector","n_results":5}' | \
  curl -s -X POST http://localhost:4000/api/v1/search \
  -H "Content-Type: application/json" -d @-
```

---

## Streaming Examples

### Server-Sent Events (SSE)

```python
import requests

response = requests.post(
    'http://localhost:4000/api/v1/search/stream',
    json={
        'query': 'Explain lymphoma treatment',
        'mode': 'graph',
        'llm_provider': 'kimi'
    },
    stream=True
)

for line in response.iter_lines():
    if line.startswith(b'data: '):
        chunk = line[6:].decode('utf-8')
        print(chunk, end='', flush=True)
```

### WebSocket

```javascript
const ws = new WebSocket('ws://localhost:4000/api/v1/search/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    action: 'query',
    data: {
      query: 'What is CAR-T therapy?',
      mode: 'graph',
      options: {
        llm_provider: 'kimi',
        n_results: 10
      }
    }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'chunk') {
    console.log(msg.data.text);
  } else if (msg.type === 'complete') {
    console.log('Done!', msg.data.metadata);
  }
};
```

---

## Docker Management

### View Logs

```bash
# API Gateway logs
docker logs obsidian-api-gateway -f

# All services
docker compose logs -f
```

### Restart Gateway

```bash
docker compose restart api-gateway
```

### Rebuild Gateway

```bash
docker compose build api-gateway
docker compose up -d api-gateway
```

### Check Status

```bash
# Container status
docker ps | grep obsidian

# Health check
curl http://localhost:4000/api/v1/health
```

---

## Architecture

### Current Setup

```
┌──────────────┐
│ Any Client   │ (Browser, CLI, Obsidian Plugin, etc.)
└──────┬───────┘
       │
       │ HTTP/WS
       │ localhost:4000
       │
┌──────▼────────┐
│ API Gateway   │ (FastAPI - Port 4000→3000)
│               │ - Unified endpoint
│               │ - Request routing
│               │ - Response standardization
└──────┬────────┘
       │
       │ Internal Docker Network
       │
    ┌──┴──┐
    │     │
┌───▼─────▼──┐     ┌──────────────┐
│ Embedding  │     │    Graph     │
│  Service   │     │   Service    │
│ (Port 8000)│     │ (Port 8002)  │
│            │     │              │
│ ChromaDB   │     │ NetworkX     │
│ Vector     │     │ + Kimi K2    │
└────────────┘     └──────────────┘
```

### Service URLs

| Service | Internal (Docker) | External (Host) |
|---------|-------------------|-----------------|
| API Gateway | `http://api-gateway:3000` | `http://localhost:4000` |
| Embedding | `http://embedding-service:8000` | `http://localhost:8000` |
| Graph | `http://graph-service:8002` | `http://localhost:8002` |

**Note**: Clients should use `localhost:4000` (API Gateway). Direct access to ports 8000/8002 still works but is not recommended.

---

## Next Steps

### For Development

1. **Update Next.js webapp** to use `localhost:4000` instead of separate services
2. **Update Streamlit UI** to use unified API
3. **Test all query modes** (vector, graph, hybrid)
4. **Try streaming endpoints**

### For Production

1. Add authentication (API keys)
2. Implement rate limiting
3. Add request caching (Redis)
4. Enable HTTPS/TLS
5. Set up monitoring (Prometheus/Grafana)

### For New Clients

1. **Build Obsidian plugin** using the unified API
2. **Create CLI tool** for terminal queries
3. **Mobile app** can consume the same API
4. **Voice assistant** integration

---

## Troubleshooting

### Gateway not starting

```bash
# Check if port 4000 is available
lsof -i :4000

# View logs
docker logs obsidian-api-gateway

# Rebuild
docker compose build api-gateway
docker compose up -d api-gateway
```

### Backend services unhealthy

```bash
# Check health
curl http://localhost:4000/api/v1/health

# Check individual services
curl http://localhost:8000/health  # Embedding
curl http://localhost:8002/health  # Graph

# Restart all services
docker compose restart
```

### Slow responses

- Vector mode is fastest (~200ms)
- Graph mode is slower (~10s) due to LLM processing
- Use hybrid for balanced performance
- Check LLM provider status (Kimi, Ollama, etc.)

---

## Testing Checklist

✅ Health endpoint works
✅ Vector search works
✅ Graph search works
✅ Hybrid search works
✅ Error handling works
✅ Swagger docs accessible
✅ Standardized response format

---

## Configuration

### Environment Variables

Set in `.env` file:

```bash
# API Gateway (optional, has defaults)
EMBEDDING_SERVICE_URL=http://embedding-service:8000
GRAPH_SERVICE_URL=http://graph-service:8002

# Backend Services (existing)
OPENROUTER_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here

OLLAMA_HOST=http://host.docker.internal:11434
OBSIDIAN_VAULT_PATH=/path/to/vault
```

### Docker Compose Ports

```yaml
services:
  api-gateway:
    ports:
      - "4000:3000"  # Host:Container
```

To change external port, edit `docker-compose.yml`:
```yaml
ports:
  - "5000:3000"  # Now accessible on localhost:5000
```

---

## Summary

🎉 **Your unified API gateway is live!**

**Endpoint**: `http://localhost:4000/api/v1`
**Docs**: `http://localhost:4000/docs`
**Status**: Fully operational

### What You Can Do Now

1. ✅ Call a single endpoint from ANY client
2. ✅ Get consistent response format
3. ✅ Use vector, graph, or hybrid search
4. ✅ Stream responses in real-time
5. ✅ Build new clients (Obsidian plugin, CLI, mobile)

### What's Next

- Update existing UIs to use gateway
- Build new clients using the API
- Add authentication if needed
- Explore WebSocket streaming

**You're now 90% complete with the unified API vision!** 🚀

The gateway provides a clean, professional API that any client can consume. Whether it's a web app, Obsidian plugin, terminal CLI, or mobile app - they all speak the same language now.

---

## Support

### Documentation
- Implementation Plan: [UNIFIED_API_IMPLEMENTATION.md](UNIFIED_API_IMPLEMENTATION.md)
- Architecture: See diagrams in main docs
- API Reference: `http://localhost:4000/docs`

### Logs
```bash
docker logs obsidian-api-gateway -f
```

### Questions
Refer to the comprehensive implementation document for detailed technical information, architecture decisions, and future enhancements.
