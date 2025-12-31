# Unified API Implementation Plan

**Date**: December 28, 2025
**Status**: Planning
**Goal**: Create a simple HTTP/WS API that any UI (web, Obsidian plugin, terminal) can call

---

## Executive Summary

### Current State: **70% Complete** ✅

You're **closer than you might think**! Your backend already exposes clean HTTP APIs. The main gaps are:
1. No unified API gateway (UIs call services directly)
2. No WebSocket support for real-time streaming
3. No standardized response format across services
4. No API versioning or centralized documentation

### Recommendation

**Path Forward**: Add a lightweight API Gateway (Flask/FastAPI) that:
- Unifies the two existing services under one endpoint
- Adds WebSocket support for streaming
- Provides consistent response format
- Can be consumed by ANY client (web, plugin, CLI)

**Estimated Effort**: 2-3 days for MVP, 1 week for production-ready

---

## Current Architecture Analysis

### Existing Services

#### 1. Embedding Service (Port 8000)

**Technology**: Flask + ChromaDB
**Purpose**: Vector semantic search

**Endpoints**:
```
GET  /health              - Health check
GET  /stats               - Collection statistics
POST /add                 - Add documents to vector DB
POST /query               - Semantic search
POST /feedback            - Submit query feedback
GET  /metrics             - Performance metrics
POST /delete              - Remove documents
```

**Strengths**:
- ✅ Clean REST API
- ✅ CORS enabled
- ✅ Health checks
- ✅ Query feedback system

**Gaps**:
- ❌ No streaming support
- ❌ Responses not standardized
- ❌ No versioning

#### 2. Graph Service (Port 8002)

**Technology**: Flask + NetworkX + Kimi K2
**Purpose**: Knowledge graph reasoning

**Endpoints**:
```
GET  /health                    - Health check
POST /query                     - Graph query (standard)
POST /query_stream              - Graph query (streaming) ✅
GET  /entity/<name>             - Get entity details
POST /path                      - Find path between entities
GET  /stats                     - Graph statistics
POST /search_entities           - Search for entities
```

**Strengths**:
- ✅ Clean REST API
- ✅ **Streaming support** (query_stream)
- ✅ Multiple query modes (vector, graph, hybrid)
- ✅ Web search integration
- ✅ Multi-LLM support (Ollama, Kimi, Claude, Gemini)

**Gaps**:
- ❌ Streaming only on one endpoint
- ❌ Responses not standardized
- ❌ No versioning

#### 3. UI Clients

**Streamlit UI** (Port 8501):
- Calls both services directly via HTTP
- Environment variables for service URLs
- No abstraction layer

**Next.js Webapp**:
- Calls both services directly via HTTP
- Hardcoded URLs: `localhost:8000`, `localhost:8002`
- Simple TypeScript API client

**Current Integration Pattern**:
```
┌──────────────┐     ┌──────────────┐
│ Streamlit UI │     │  Next.js     │
└──────┬───────┘     └──────┬───────┘
       │                    │
       │ Direct HTTP        │ Direct HTTP
       ├────────────────────┤
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│  Embedding   │     │    Graph     │
│  Service     │     │   Service    │
│ (Port 8000)  │     │ (Port 8002)  │
└──────────────┘     └──────────────┘
```

---

## Gap Analysis

### What You Have ✅

1. **Clean HTTP APIs**: Both services expose RESTful endpoints
2. **Streaming Support**: Graph service has `/query_stream` endpoint
3. **CORS Enabled**: Browser clients can call directly
4. **Health Checks**: Both services have `/health` endpoints
5. **Multiple Query Modes**: vector, graph, hybrid
6. **Feedback System**: Query logging and metrics
7. **Docker Deployment**: Services are containerized

### What's Missing ❌

1. **Unified API Gateway**: UIs must know about 2 separate services
2. **Consistent Response Format**: Each service has different response structure
3. **WebSocket Support**: Only HTTP streaming on graph service
4. **API Versioning**: No `/v1/` style versioning
5. **Centralized Auth**: No authentication/authorization
6. **Rate Limiting**: No request throttling
7. **API Documentation**: No OpenAPI/Swagger spec
8. **Error Standardization**: Different error formats
9. **Request Validation**: No schema validation
10. **Service Discovery**: Hardcoded URLs in clients

---

## Proposed Unified Architecture

### Target Architecture

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Streamlit UI │  │  Next.js     │  │ Obsidian     │  │   Terminal   │
│              │  │              │  │   Plugin     │  │     CLI      │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       │                 │                 │                 │
       └─────────────────┴─────────────────┴─────────────────┘
                                 │
                    HTTP/WebSocket (Port 3000)
                                 │
                         ┌───────▼───────┐
                         │  API Gateway  │
                         │  (Unified API)│
                         │   Port 3000   │
                         └───────┬───────┘
                                 │
                    Internal Network (Docker)
                                 │
            ┌────────────────────┴────────────────────┐
            │                                         │
     ┌──────▼────────┐                       ┌───────▼────────┐
     │   Embedding   │                       │     Graph      │
     │    Service    │                       │    Service     │
     │  (Port 8000)  │                       │  (Port 8002)   │
     └───────────────┘                       └────────────────┘
```

### Unified API Specification

#### Base URL
```
http://localhost:3000/api/v1
```

#### Endpoints

**Search & Query**:
```
POST   /api/v1/search               - Unified search (auto-routing)
POST   /api/v1/search/vector        - Vector-only search
POST   /api/v1/search/graph         - Graph-only search
POST   /api/v1/search/hybrid        - Hybrid search
WS     /api/v1/search/stream        - Streaming search (WebSocket)
```

**Entities**:
```
GET    /api/v1/entities/<name>      - Get entity details
POST   /api/v1/entities/search      - Search entities
POST   /api/v1/entities/path        - Find path between entities
```

**System**:
```
GET    /api/v1/health               - Overall health status
GET    /api/v1/stats                - Combined statistics
GET    /api/v1/metrics              - Performance metrics
```

**Feedback**:
```
POST   /api/v1/feedback             - Submit query feedback
```

**Admin** (Optional):
```
POST   /api/v1/index/add            - Add documents
POST   /api/v1/index/delete         - Remove documents
POST   /api/v1/index/rebuild        - Rebuild indices
```

### Standardized Response Format

All responses follow this structure:

```json
{
  "success": true,
  "data": {
    "answer": "Your answer here...",
    "sources": [
      {
        "filename": "note.md",
        "filepath": "/path/to/note.md",
        "relevance": 95.5,
        "snippet": "Relevant text..."
      }
    ],
    "metadata": {
      "query_time_ms": 234,
      "mode": "hybrid",
      "entities_found": 5,
      "llm_provider": "kimi",
      "model": "kimi-k2-0905"
    }
  },
  "error": null,
  "timestamp": "2025-12-28T12:34:56Z",
  "version": "v1"
}
```

**Error Response**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "QUERY_FAILED",
    "message": "Failed to execute query",
    "details": "Connection timeout to graph service"
  },
  "timestamp": "2025-12-28T12:34:56Z",
  "version": "v1"
}
```

### WebSocket Protocol

**Connect**:
```javascript
const ws = new WebSocket('ws://localhost:3000/api/v1/search/stream');
```

**Send Query**:
```json
{
  "action": "query",
  "data": {
    "query": "What is CAR-T therapy?",
    "mode": "hybrid",
    "options": {
      "n_results": 10,
      "llm_provider": "kimi"
    }
  }
}
```

**Receive Chunks**:
```json
{
  "type": "chunk",
  "data": {
    "text": "CAR-T therapy is...",
    "done": false
  }
}

{
  "type": "sources",
  "data": {
    "sources": [/* ... */]
  }
}

{
  "type": "complete",
  "data": {
    "metadata": {/* ... */},
    "done": true
  }
}
```

---

## Implementation Roadmap

### Phase 1: API Gateway MVP (2-3 days)

**Goal**: Create a unified endpoint that routes to existing services

**Tasks**:
1. Create new `api-gateway` service (FastAPI recommended)
2. Implement request routing to embedding/graph services
3. Add standardized response wrapper
4. Deploy as Docker container on port 3000
5. Update UIs to call gateway instead of direct services

**Files to Create**:
```
src/services/api_gateway.py              # Main gateway service
config/docker/Dockerfile.gateway         # Gateway container
```

**Files to Update**:
```
docker-compose.yml                       # Add gateway service
webapp/src/lib/api.ts                    # Update to call gateway
src/ui/streamlit_ui_docker.py            # Update to call gateway
```

**Code Skeleton** (api_gateway.py):
```python
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import httpx
from datetime import datetime

app = FastAPI(title="Obsidian RAG API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# Service URLs (internal Docker network)
EMBEDDING_URL = "http://embedding-service:8000"
GRAPH_URL = "http://graph-service:8002"

@app.post("/api/v1/search")
async def unified_search(request: SearchRequest):
    """Unified search endpoint - auto-routes based on mode"""
    # Route to appropriate service
    # Wrap response in standard format
    pass

@app.websocket("/api/v1/search/stream")
async def search_stream(websocket: WebSocket):
    """WebSocket streaming search"""
    await websocket.accept()
    # Stream from graph service
    pass

@app.get("/api/v1/health")
async def health():
    """Combined health check"""
    return {
        "success": True,
        "data": {
            "gateway": "healthy",
            "embedding_service": await check_service(EMBEDDING_URL),
            "graph_service": await check_service(GRAPH_URL)
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "v1"
    }
```

**docker-compose.yml Addition**:
```yaml
  api-gateway:
    build:
      context: .
      dockerfile: config/docker/Dockerfile.gateway
    container_name: obsidian-api-gateway
    ports:
      - "3000:3000"
    environment:
      - EMBEDDING_SERVICE_URL=http://embedding-service:8000
      - GRAPH_SERVICE_URL=http://graph-service:8002
    networks:
      - rag-network
    depends_on:
      - embedding-service
      - graph-service
```

### Phase 2: WebSocket Enhancement (1-2 days)

**Goal**: Add WebSocket support for all streaming operations

**Tasks**:
1. Implement WebSocket server in gateway
2. Connect to graph service `/query_stream` endpoint
3. Add client-side WebSocket handlers
4. Test real-time streaming

**Benefits**:
- True bi-directional communication
- Lower latency for streaming
- Connection keep-alive
- Better error handling

### Phase 3: OpenAPI Documentation (1 day)

**Goal**: Auto-generated API documentation

**Tasks**:
1. Add OpenAPI/Swagger annotations to FastAPI
2. Enable interactive docs at `/docs`
3. Generate TypeScript types for Next.js
4. Generate Python client for CLI tools

**Output**:
- Interactive API explorer: `http://localhost:3000/docs`
- ReDoc documentation: `http://localhost:3000/redoc`
- Auto-generated client libraries

### Phase 4: Enhanced Features (1-2 days)

**Goal**: Production-ready features

**Tasks**:
1. Add request validation (Pydantic models)
2. Implement error standardization
3. Add basic rate limiting
4. Add request logging
5. Add metrics endpoint (`/api/v1/metrics`)

**Optional Enhancements**:
- API key authentication
- Request caching
- Circuit breaker for service failures
- Request/response compression

---

## Current vs Target

### Before (Current)

**Pros**:
- ✅ Works well
- ✅ Clean separation of concerns
- ✅ Docker deployment

**Cons**:
- ❌ UIs tightly coupled to services
- ❌ Must know about 2 URLs
- ❌ No streaming for vector search
- ❌ Different response formats
- ❌ Hard to add new UI clients

### After (Target)

**Pros**:
- ✅ Single API endpoint (localhost:3000)
- ✅ Consistent response format
- ✅ WebSocket streaming for all queries
- ✅ Easy to add new clients (Obsidian plugin, CLI, etc.)
- ✅ API documentation
- ✅ Versioned API (future-proof)
- ✅ Production-ready

**Cons**:
- Additional gateway service (minimal overhead)
- One more container to manage

---

## Client Examples

### Next.js (TypeScript)

**Before**:
```typescript
// Calls two different services
const vectorResults = await fetch('http://localhost:8000/query', {...});
const graphResults = await fetch('http://localhost:8002/query', {...});
```

**After**:
```typescript
// Single unified endpoint
const results = await fetch('http://localhost:3000/api/v1/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: "What is CAR-T therapy?",
    mode: "hybrid",  // auto-routes internally
    options: {
      n_results: 10,
      llm_provider: "kimi"
    }
  })
});

const { success, data, error } = await results.json();
if (success) {
  console.log(data.answer);
  console.log(data.sources);
}
```

**WebSocket Streaming**:
```typescript
const ws = new WebSocket('ws://localhost:3000/api/v1/search/stream');

ws.onopen = () => {
  ws.send(JSON.stringify({
    action: 'query',
    data: { query: "Explain DLBCL treatment", mode: "graph" }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'chunk') {
    appendToUI(msg.data.text);
  } else if (msg.type === 'complete') {
    showSources(msg.data.metadata.sources);
  }
};
```

### Python CLI

```python
import requests

# Simple unified API call
response = requests.post(
    'http://localhost:3000/api/v1/search',
    json={
        'query': 'What is my treatment plan?',
        'mode': 'hybrid',
        'options': {
            'n_results': 5,
            'llm_provider': 'ollama',
            'model': 'qwen2.5-coder:32b'
        }
    }
)

result = response.json()
if result['success']:
    print(result['data']['answer'])
    for source in result['data']['sources']:
        print(f"  - {source['filename']} (relevance: {source['relevance']}%)")
```

### Obsidian Plugin (Future)

```javascript
// Obsidian plugin calls same API
const response = await fetch('http://localhost:3000/api/v1/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: currentNote.getContent(),
    mode: 'vector',
    options: { n_results: 5 }
  })
});

const { data } = await response.json();
// Display related notes in sidebar
showRelatedNotes(data.sources);
```

---

## Migration Strategy

### Option 1: Gradual Migration (Recommended)

**Week 1**: Deploy gateway alongside existing setup
- ✅ No disruption
- ✅ Test in parallel
- ✅ Gradual UI migration

**Steps**:
1. Deploy API gateway (port 3000)
2. Keep existing services (ports 8000, 8002)
3. Update Next.js to use gateway
4. Test thoroughly
5. Update Streamlit to use gateway
6. Eventually make ports 8000/8002 internal-only

### Option 2: Big Bang Migration

**Weekend Deploy**: Replace everything at once
- ⚠️ Higher risk
- ✅ Faster completion
- ✅ Cleaner architecture immediately

**Not recommended** unless you have comprehensive tests

---

## Technical Decisions

### Gateway Framework: FastAPI vs Flask

**Recommendation**: **FastAPI**

| Feature | FastAPI | Flask |
|---------|---------|-------|
| **Async Support** | ✅ Native | ⚠️ Requires extensions |
| **WebSocket** | ✅ Built-in | ❌ Requires extensions |
| **Auto Docs** | ✅ OpenAPI/Swagger | ❌ Manual |
| **Type Validation** | ✅ Pydantic | ❌ Manual |
| **Performance** | ✅ High (Starlette/Uvicorn) | ⚠️ Moderate |
| **Learning Curve** | ⚠️ Steeper | ✅ Easy |

**Verdict**: FastAPI for production, Flask if team only knows Flask

### WebSocket vs SSE (Server-Sent Events)

**Recommendation**: **WebSocket**

| Feature | WebSocket | SSE |
|---------|-----------|-----|
| **Bi-directional** | ✅ Yes | ❌ Server → Client only |
| **Browser Support** | ✅ Universal | ✅ Universal |
| **Reconnection** | Manual | ✅ Automatic |
| **Protocol** | WS/WSS | HTTP/HTTPS |
| **Complexity** | ⚠️ Higher | ✅ Simpler |

**Verdict**: WebSocket for full-duplex streaming

### Response Format: JSON:API vs Custom

**Recommendation**: **Simplified Custom Format**

Your use case doesn't need full JSON:API spec. The proposed format is:
- ✅ Simple
- ✅ Consistent
- ✅ Easy to extend
- ✅ Clear error handling

---

## Success Criteria

### MVP Success

- [ ] Single endpoint serves all search queries
- [ ] Next.js webapp calls only localhost:3000
- [ ] Streamlit UI calls only localhost:3000
- [ ] WebSocket streaming works for graph queries
- [ ] Consistent response format across all endpoints
- [ ] Health check shows all service status
- [ ] Basic error handling in place

### Production Ready

- [ ] All endpoints documented (OpenAPI)
- [ ] Request validation with Pydantic
- [ ] Comprehensive error handling
- [ ] Rate limiting implemented
- [ ] Metrics and logging
- [ ] Load tested (100+ concurrent users)
- [ ] CLI client working
- [ ] Sample Obsidian plugin (proof of concept)

---

## Effort Estimation

### Phase 1: API Gateway MVP
**Time**: 2-3 days
**Complexity**: Medium
**Deliverable**: Working gateway on port 3000

**Breakdown**:
- Gateway service setup: 4 hours
- Request routing logic: 4 hours
- Response standardization: 3 hours
- Docker configuration: 2 hours
- UI client updates: 3 hours
- Testing: 4 hours

**Total**: ~20 hours

### Phase 2: WebSocket Enhancement
**Time**: 1-2 days
**Complexity**: Medium
**Deliverable**: WebSocket streaming for all queries

**Breakdown**:
- WebSocket server: 4 hours
- Client handlers: 3 hours
- Connection management: 3 hours
- Testing: 2 hours

**Total**: ~12 hours

### Phase 3: OpenAPI Documentation
**Time**: 1 day
**Complexity**: Low
**Deliverable**: Interactive API docs

**Breakdown**:
- FastAPI annotations: 3 hours
- Schema definitions: 2 hours
- Examples and descriptions: 2 hours
- Client generation: 1 hour

**Total**: ~8 hours

### Phase 4: Production Features
**Time**: 1-2 days
**Complexity**: Medium
**Deliverable**: Production-ready API

**Breakdown**:
- Request validation: 4 hours
- Error handling: 3 hours
- Rate limiting: 2 hours
- Logging/metrics: 3 hours
- Testing: 4 hours

**Total**: ~16 hours

---

## Risk Assessment

### Low Risk ✅

1. **Technology Stack**: FastAPI is mature and well-documented
2. **Existing Services**: No changes needed to embedding/graph services
3. **Backward Compatible**: Can run alongside current setup
4. **Incremental Migration**: UIs can be updated one at a time

### Medium Risk ⚠️

1. **WebSocket Complexity**: More complex than HTTP polling
   - *Mitigation*: Start with HTTP streaming, add WS later
2. **Performance Overhead**: Extra hop through gateway
   - *Mitigation*: Use async/await, minimal processing in gateway
3. **Service Discovery**: Gateway must know about backend services
   - *Mitigation*: Docker internal networking, env variables

### High Risk ❌

- **None identified** - This is a low-risk architectural improvement

---

## Alternatives Considered

### Alternative 1: Keep Direct Service Calls

**Pros**:
- No changes needed
- Lower latency (no gateway)
- Simpler architecture

**Cons**:
- UIs must know about multiple services
- Hard to add new clients
- No unified streaming
- No consistent API

**Verdict**: ❌ Not recommended for long-term

### Alternative 2: Merge Services into Monolith

**Pros**:
- Single service
- No gateway needed
- Simpler deployment

**Cons**:
- Violates separation of concerns
- Harder to scale individual components
- More complex codebase

**Verdict**: ❌ Not recommended - current separation is good

### Alternative 3: Use nginx as Reverse Proxy

**Pros**:
- Simple routing
- High performance
- Industry standard

**Cons**:
- No request/response transformation
- No WebSocket connection management
- No business logic
- Needs separate service for API logic

**Verdict**: ⚠️ Could complement gateway, but not replace it

---

## Next Steps

### Immediate (This Week)

1. **Review this document** - Approve or adjust the plan
2. **Set up development environment** - Prepare for gateway development
3. **Create Phase 1 branch** - `feature/api-gateway-mvp`

### Short Term (Next 2 Weeks)

1. **Implement Phase 1** - API Gateway MVP
2. **Test with Next.js** - Update one UI client
3. **Gather feedback** - Does it meet your needs?

### Medium Term (Next Month)

1. **Complete Phases 2-4** - WebSocket, docs, production features
2. **Update all clients** - Streamlit, Next.js
3. **Create CLI tool** - Demonstrate API versatility

### Long Term (Next Quarter)

1. **Build Obsidian plugin** - True test of API design
2. **Add authentication** - If sharing with others
3. **Performance optimization** - Based on real usage

---

## Conclusion

### You're 70% There! 🎉

**What you have**:
- ✅ Clean backend services with REST APIs
- ✅ Streaming support (graph service)
- ✅ Docker deployment
- ✅ Multiple query modes
- ✅ Feedback system

**What you need**:
- ⏳ Unified API gateway (2-3 days)
- ⏳ WebSocket streaming (1-2 days)
- ⏳ Standardized responses (included in gateway)
- ⏳ API documentation (1 day)

**Total Effort**: ~1 week for production-ready unified API

### Recommendation

**Start with Phase 1**: Build the API gateway MVP. This gives you:
1. Single endpoint for all clients
2. Consistent response format
3. Easy to add new UIs (Obsidian plugin, CLI, mobile, etc.)
4. Foundation for future enhancements

**Keep it simple**: Don't over-engineer. FastAPI + basic routing + response wrapping = 80% of value with 20% of effort.

---

## Questions & Considerations

### 1. Do you need authentication?

**Current**: No auth, localhost-only
**Future**: If exposing externally, add API keys or OAuth

### 2. Do you need multi-user support?

**Current**: Single user
**Future**: Add user context to requests

### 3. Do you need request caching?

**Current**: Every request hits backend
**Future**: Add Redis for frequently asked questions

### 4. Do you need API versioning?

**Recommendation**: Yes - `/api/v1/` allows future breaking changes

### 5. Do you need observability?

**Current**: Basic logging
**Future**: Add structured logging, tracing (OpenTelemetry)

---

## References & Resources

### FastAPI
- Docs: https://fastapi.tiangolo.com/
- WebSocket: https://fastapi.tiangolo.com/advanced/websockets/
- OpenAPI: https://fastapi.tiangolo.com/tutorial/metadata/

### WebSocket
- MDN Guide: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket
- Browser Support: https://caniuse.com/websockets

### API Design
- REST Best Practices: https://restfulapi.net/
- JSON:API: https://jsonapi.org/ (if you want full spec)

### Docker Networking
- Compose Networks: https://docs.docker.com/compose/networking/

---

## Appendix: Quick Start Commands

### Create API Gateway Service

```bash
# Create new service file
touch src/services/api_gateway.py

# Create Dockerfile
touch config/docker/Dockerfile.gateway

# Install dependencies in requirements.txt
pip install fastapi uvicorn[standard] httpx websockets
```

### Build and Deploy

```bash
# Add gateway to docker-compose.yml (see example above)

# Build and start services
docker compose build api-gateway
docker compose up -d api-gateway

# Check health
curl http://localhost:3000/api/v1/health

# Test unified search
curl -X POST http://localhost:3000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"What is CAR-T?","mode":"hybrid"}'
```

### Update Next.js Client

```typescript
// Update webapp/src/lib/api.ts
const API_BASE = 'http://localhost:3000/api/v1';

export const api = {
  search: async (query: string, mode = 'hybrid') => {
    const response = await fetch(`${API_BASE}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, mode })
    });
    const { success, data, error } = await response.json();
    if (!success) throw new Error(error.message);
    return data;
  }
};
```

---

**Status**: Ready for implementation
**Next Action**: Review and approve plan, then create `feature/api-gateway-mvp` branch
