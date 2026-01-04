# Obsidian RAG System - Complete Overview (2025)

## Executive Summary
A production-grade, local-first RAG system for your 1,676-note Obsidian vault. Combines **dual knowledge graphs**, **vector semantic search**, **agentic deep thinking**, and **personal memory** for comprehensive knowledge retrieval and reasoning.

---

## System Architecture

### Core Services (6 Components)

| Service | Port | Container | Purpose | Status |
|---------|------|-----------|---------|--------|
| **Vector Search** | 8000 | obsidian-embedding | ChromaDB semantic similarity | ✅ Running |
| **LightRAG Graph** | 8001 | obsidian-lightrag | Entity-centric semantic graph | ✅ Running |
| **NetworkX Graph** | 8002 | obsidian-graph-service | Note-centric structure graph | ✅ Running |
| **API Gateway** | 4000 | obsidian-api-gateway | Unified routing & orchestration | ✅ Running |
| **Streamlit UI** | 8501 | obsidian-ui | Legacy web interface | ✅ Running |
| **Next.js WebApp** | 3001 | — | Modern React UI with 3D graphs | ✅ Running |

---

## 1. Dual Knowledge Graph System

Your system operates with **two complementary graphs**, not redundant systems:

### LightRAG Graph (Port 8001)
**Entity-Centric Semantic Knowledge**

- **Nodes**: 23,926 concepts, entities, and terms extracted from notes
- **Edges**: 35,030 semantic relationships between concepts
- **Database**: 152 MB (Docker volume `lightrag_storage`)
- **Indexing Model**: Kimi K2 via OpenRouter (`moonshotai/kimi-k2-0905`)
- **Embedding Model**: `nomic-embed-text` (Ollama local)

**Contents**:
- `graph_chunk_entity_relation.graphml` (7.5 MB) - Graph structure
- `vdb_entities.json` (46 MB) - Entity embeddings
- `vdb_relationships.json` (45 MB) - Relationship embeddings
- `vdb_chunks.json` (7.7 MB) - Text chunk vectors
- `kv_store_llm_response_cache.json` (38 MB) - Cached LLM responses
- `indexed_files.txt` - Tracks 2,000 indexed notes

**Query Modes**:
- `naive`: Simple keyword search
- `local`: Entity neighborhood exploration
- `global`: Community-level pattern detection
- `hybrid`: Combined approach (recommended)

**Best For**:
- "What concepts relate to CAR-T therapy side effects?"
- "How are ESPHome and Home Assistant connected across my notes?"
- Discovering implicit connections in unlinked notes
- Multi-hop reasoning queries
- Semantic concept exploration

**Example**:
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"garage automation with ESP32","mode":"hybrid"}'
```

---

### NetworkX Graph (Port 8002)
**Note-Centric Vault Structure**

- **Nodes**: 16,212 actual Obsidian note files
- **Edges**: 16,268 explicit wiki-links between notes
- **Database**: 39 MB (`data/graph_data/knowledge_graph_full.pkl`)
- **Query Model**: GPT-4o-mini via OpenRouter (`openai/gpt-4o-mini`)
- **Embedding Service**: Calls port 8000 for vector enhancement

**Best For**:
- "Which notes link to my Home Assistant setup?"
- "Find orphaned notes in my vault"
- "What's the shortest path between CAR-T notes and tech projects?"
- Graph analytics (centrality, clustering, communities)
- Understanding your vault's intentional organization

**Example**:
```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Home Assistant automation","mode":"hybrid"}'
```

---

### Why Both Graphs?

| Feature | LightRAG (8001) | NetworkX (8002) |
|---------|-----------------|-----------------|
| **Granularity** | Concepts/entities | Note files |
| **Node count** | 23,926 (fine-grained) | 16,212 (file-level) |
| **Relationships** | AI-extracted semantic | Explicit wiki-links |
| **Coverage** | Captures implicit knowledge | Shows intentional structure |
| **Use case** | "What do I know about X?" | "Where did I write about X?" |
| **Discovery** | Finds hidden connections | Reveals your thinking patterns |

**Complementary Power**:
1. **LightRAG** surfaces concepts from notes you never linked
2. **NetworkX** shows how YOU organized your knowledge
3. **Together** = Complete picture of both content AND structure

---

## 2. Vector Semantic Search (Port 8000)

**Traditional RAG Foundation**

- **Database**: ChromaDB (63 MB local storage)
- **Embedding Model**: `nomic-embed-text` via Ollama (768-dimensional)
- **Collection**: `obsidian_vault` (configurable via `CHROMA_COLLECTION`)
- **Features**:
  - Reranking with cross-encoder models
  - Deduplication
  - Obsidian folder filtering
  - HyDE (Hypothetical Document Embeddings) enhancement

**API Endpoints**:
- `/query` - Semantic similarity search
- `/health` - Service health check
- `/stats` - Database statistics

---

## 3. API Gateway (Port 4000)

**Unified Orchestration Layer**

Routes requests to appropriate backends and handles:
- Query mode routing (vector/graph/hybrid/cascading)
- LLM provider selection (Ollama, Claude, Gemini, Kimi)
- System prompt injection
- Response aggregation
- WebSocket support for Deep Thinking

**API V1 Endpoints**:
- `POST /api/v1/query` - Unified query interface
- `GET /api/v1/stats` - System statistics
- `WS /api/v1/deep-research` - WebSocket for agentic search

**Supported Modes**:
- `vector` - Pure semantic search
- `graph` - Knowledge graph reasoning
- `hybrid` - Combined vector + graph + LLM synthesis
- `cascading` - Adaptive multi-strategy retrieval
- `dual-graph` - Both LightRAG + NetworkX
- `notes` - NetworkX only
- `entities` - LightRAG only

---

## 4. Deep Thinking Agentic Search

**Multi-Step Reasoning Engine** (`deep_thinking/supervisor.py`)

### Architecture
```
User Query
    ↓
Query Decomposition (LLM breaks down complex questions)
    ↓
Sub-Question Routing (Supervisor chooses strategy per sub-question)
    ├─→ Vector Search (semantic similarity)
    ├─→ Graph Search (entity relationships)
    ├─→ Hybrid Search (vector + graph fusion)
    └─→ Web Search (Tavily API for external knowledge)
    ↓
Result Reranking (Cross-encoder model scores relevance)
    ↓
Personal Memory Integration (mem0 adds user context)
    ↓
LLM Synthesis (Combines all evidence into coherent answer)
    ↓
Memory Update (Stores interaction for future queries)
```

### Features
- **Adaptive Retrieval**: Chooses optimal strategy per sub-question
- **Cross-Encoder Reranking**: Reranks 40 results → top 15 most relevant
- **Personal Memory (mem0)**:
  - Searches conversation history for personalized context
  - Auto-updates after each interaction
  - Location: `src/utils/memory_manager.py`
- **Web Search**: Tavily integration for external sources
- **Streaming**: WebSocket-based real-time response streaming
- **Target Folder Filtering**: Obsidian folder-aware search

### Query Decomposition Example
**User**: "How does CAR-T therapy relate to my garage automation notes?"

**Supervisor Decomposes**:
1. Sub-question 1: "What is CAR-T therapy?" → Strategy: `graph` (medical entities)
2. Sub-question 2: "What garage automation systems do I use?" → Strategy: `vector` (tech notes)
3. Sub-question 3: "Any connections between medical monitoring and IoT?" → Strategy: `hybrid`

### Invocation
```typescript
// Next.js WebApp (port 3001)
const ws = new WebSocket('ws://127.0.0.1:4000/api/v1/deep-research');
ws.send(JSON.stringify({ query: "...", provider: "claude" }));
```

---

## 5. User Interfaces

### Next.js WebApp (Port 3001)
**Modern React Interface**

- **Framework**: Next.js 16 with React 19
- **Features**:
  - 3D force-directed knowledge graph visualization
  - Real-time WebSocket streaming for Deep Thinking
  - Dark mode UI
  - Source citations with relevance scores
  - Settings panel for LLM/model selection
  - Chat history with markdown rendering
- **Tech Stack**:
  - Three.js for 3D graphics
  - React Three Fiber for React integration
  - Lucide icons
  - TailwindCSS styling
- **Location**: `webapp/src/`

**Key Components**:
- `app/page.tsx` - Main chat interface
- `components/ForceGraph.tsx` - 2D entity graph
- `components/KnowledgeGraphSimple.tsx` - 3D visualization
- `components/sidebar/SettingsPanelModal.tsx` - Configuration

---

### Streamlit UI (Port 8501)
**Legacy Interface**

- Simpler single-page interface
- Side-by-side vector/graph results
- Good for quick queries without configuration overhead
- Location: `src/ui/streamlit_ui_docker.py`

---

## 6. LLM & Model Stack

### Indexing Models
- **LightRAG Graph**: Kimi K2 (`moonshotai/kimi-k2-0905`) via OpenRouter
  - Optimized for agentic entity extraction
  - Deep relationship understanding
- **NetworkX Graph**: GPT-4o-mini (`openai/gpt-4o-mini`) via OpenRouter
  - Fast note structure analysis
  - Cost-effective for large vaults

### Retrieval Models (User-Selectable)
Via OpenRouter or Ollama:
- **Claude**: `claude-sonnet-4-5-20250929` (highest quality)
- **DeepSeek**: `deepseek/deepseek-r1` (reasoning-optimized)
- **Qwen**: `qwen/qwen-2.5-72b-instruct` (fast, balanced)
- **Gemini**: `google/gemini-3-pro-preview` (multimodal)
- **Ollama Local**: `llama3.2`, `qwen2.5`, etc. (fully offline)

### Embedding Models
- **Primary**: `nomic-embed-text` (Ollama, 768-dim)
- **Fallback**: OpenAI `text-embedding-3-small` via OpenRouter

### Personal Memory
- **System**: mem0 (conversation memory persistence)
- **Integration**: Automatic in hybrid mode
- **Storage**: Managed by `src/utils/memory_manager.py`

---

## 7. Data Isolation & SOTA Mode

**Recent Feature**: Production/SOTA database switching

From recent commits:
- "implement SOTA data isolation and path configurability"
- "allow toggling between original and SOTA databases via environment variables"

**Purpose**: Test experimental graph builds without affecting production data

**Configuration**: Environment variables control database paths:
- `GRAPH_PATH` - NetworkX graph location
- `LIGHTRAG_DIR` - LightRAG database directory
- `CHROMA_COLLECTION` - ChromaDB collection name

---

## 8. Automation & Experience

### File Watcher
**Real-Time Incremental Indexing**

- **Script**: `Scripts/vault_management/watching_scanner.py`
- **Function**: Monitors vault for file saves
- **Action**: Instant re-indexing of changed notes to ChromaDB
- **Benefit**: Always-current semantic search without manual rebuilds

### One-Click Launcher
**macOS Desktop Integration**

- **File**: `Launch Obsidian RAG.command`
- **Features**:
  - Starts all Docker services
  - Custom branding/logging
  - Health checks
  - Opens browser to UI
- **Location**: Project root

### Shutdown Script
- **Script**: `Scripts/stop_obsidian_rag.sh`
- **Function**: Gracefully stops all services, clears PIDs and ports

---

## 9. Maintenance & Operations

### Health Checks

```bash
# Vector Search
curl http://localhost:8000/health

# LightRAG Graph
curl http://localhost:8001/health
curl http://localhost:8001/stats  # Database statistics

# NetworkX Graph
curl http://localhost:8002/health

# API Gateway
curl http://localhost:4000/api/v1/health
```

### Backup Databases

```bash
# LightRAG (Docker volume → local)
docker cp obsidian-lightrag:/app/lightrag_db ./backups/lightrag_$(date +%Y%m%d)

# NetworkX (already local)
cp -r data/graph_data ./backups/graph_data_$(date +%Y%m%d)

# ChromaDB (already local)
cp -r chroma_db ./backups/chroma_db_$(date +%Y%m%d)
```

### Rebuild Graphs

**LightRAG** (slow, hours for full vault):
```bash
curl -X POST http://localhost:8001/index-vault \
  -H "Content-Type: application/json" \
  -d '{"vault_path":"/app/vault"}'
```

**NetworkX** (fast, minutes):
```bash
cd Scripts
./index_with_kimi.sh
```

**Vector DB** (automatic via file watcher, or manual):
```bash
python src/indexing/index_vault.py
```

---

## 10. Performance Characteristics

| Operation | Vector (8000) | LightRAG (8001) | NetworkX (8002) |
|-----------|---------------|-----------------|-----------------|
| **Query Speed** | Fast (<1s) | Moderate (2-5s) | Fast (<1s) |
| **Index Time** | Fast (minutes) | Slow (hours) | Fast (minutes) |
| **Memory Usage** | Low (~100MB) | High (~500MB) | Low (~100MB) |
| **Accuracy** | High (semantic) | Very High (reasoning) | Exact (structure) |
| **Offline** | ✅ Full | ⚠️ Needs LLM | ⚠️ Needs LLM |

---

## 11. Docker Configuration

### Service Dependencies
```
API Gateway (4000)
    ├─→ Embedding Service (8000)
    ├─→ LightRAG Service (8001)
    └─→ Graph Service (8002) ──→ Embedding Service (8000)

Streamlit UI (8501)
    └─→ API Gateway (4000)

Next.js WebApp (3001)
    └─→ API Gateway (4000)
```

### Environment Variables

**Core Services** (`.env`):
```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=...
TAVILY_API_KEY=tvly-...

# Paths
OBSIDIAN_VAULT_PATH=/path/to/vault
GRAPH_PATH=/app/graph_data/knowledge_graph_full.pkl
LIGHTRAG_DIR=/app/lightrag_db

# Models
KIMI_MODEL=moonshotai/kimi-k2-0905
EMBED_MODEL=nomic-embed-text
CHROMA_COLLECTION=obsidian_vault

# Ollama
OLLAMA_HOST=http://host.docker.internal:11434
```

### Volume Mounts
- `lightrag_storage` - LightRAG database (Docker-managed)
- `./chroma_db` - ChromaDB vector store
- `./data/graph_data` - NetworkX graph files
- `${OBSIDIAN_VAULT_PATH}` - Your Obsidian vault (read-only)

---

## 12. Query Strategy Decision Matrix

| Your Question | Recommended Mode | Reason |
|---------------|------------------|--------|
| "What treatments are mentioned for X?" | `graph` (LightRAG) | Entity-focused concept extraction |
| "Which notes discuss Y?" | `notes` (NetworkX) | File-level navigation |
| "Explain concept Z from my notes" | `hybrid` | Best of vector + graph + LLM synthesis |
| "Deep research on complex topic" | Deep Thinking (WebSocket) | Multi-step reasoning with reranking |
| "Quick semantic search" | `vector` | Fastest, good for simple queries |
| "What links to note X?" | `notes` (NetworkX) | Graph structure analysis |
| "Find connections between A and B" | `dual-graph` | Both graphs for comprehensive view |

---

## 13. Recent Improvements (Changelog)

From commit history:

1. **SOTA Data Isolation** - Toggle between production/experimental databases
2. **Production Fallback** - Environment-based database switching
3. **Deep Thinking Citation Fix** - Proper source mapping to UI format
4. **Document Retrieval Fix** - `folder_parts` metadata for filtering
5. **Missing Sources Fix** - Gateway timeout increase + graph fallback
6. **Dual Graph Restoration** - Brought back LightRAG after cleanup analysis

---

## 14. File Locations Reference

### Core Services
- **LightRAG Service**: `src/integrations/lightrag_service.py`
- **NetworkX Graph Service**: `src/services/graph_query_service.py`
- **Kimi Graph Builder**: `src/services/kimi_graph_builder.py`
- **Embedding Service**: `src/services/embedding_service.py`
- **API Gateway**: `src/services/api_gateway.py`

### Deep Thinking
- **Supervisor**: `deep_thinking/supervisor.py`
- **State Management**: `deep_thinking/state.py`
- **Reranker**: `deep_thinking/reranker.py`

### UIs
- **Next.js WebApp**: `webapp/src/`
- **Streamlit**: `src/ui/streamlit_ui_docker.py`

### Utilities
- **Memory Manager**: `src/utils/memory_manager.py`
- **Logging Config**: `src/utils/logging_config.py`
- **Query Feedback**: `src/utils/query_feedback.py`

### Indexing
- **Vault Indexer**: `src/indexing/index_vault.py`
- **Graph Builder**: `src/indexing/build_knowledge_graph.py`

### Documentation
- **Full Docs**: `Documentation/` (see `Documentation/README.md`)
- **Architecture**: `Documentation/architecture/`
- **Setup Guides**: `Documentation/Setup/`
- **Dual Graph Guide**: `Documentation/DUAL_GRAPH_ARCHITECTURE.md`

---

## 15. Best Practices

1. **Query Strategy**:
   - Start with Deep Thinking for complex research questions
   - Use `hybrid` mode for balanced queries
   - Use `graph` for entity-focused exploration
   - Use `notes` for vault structure navigation

2. **Maintenance**:
   - Backup databases weekly (they're gitignored)
   - Re-index LightRAG monthly or when vault grows significantly
   - Let file watcher handle vector DB updates automatically
   - Monitor Docker container health

3. **Performance**:
   - Use Ollama local models for cost-free queries
   - Reserve Claude/Gemini for complex reasoning
   - Enable reranking for better result quality
   - Set appropriate `n_results` (10-15 is optimal)

4. **Personal Memory**:
   - Deep Thinking mode auto-updates mem0
   - Review memory context in responses to verify relevance
   - Clear memory periodically if context becomes stale

5. **Development**:
   - Use SOTA mode for testing new graph builds
   - Keep production databases separate
   - Test new models on small query sets first

---

## 16. Troubleshooting Quick Reference

### Service Won't Start
```bash
# Check logs
docker logs obsidian-<service-name>

# Check port conflicts
lsof -i :8000  # Repeat for 8001, 8002, 4000, 8501
```

### No Graph Results
```bash
# Verify graph loaded
curl http://localhost:8002/health  # Check graph_loaded: true

# Rebuild if needed
cd Scripts && ./index_with_kimi.sh
```

### LightRAG Empty
```bash
# Copy database into volume
docker cp ./lightrag_db/. obsidian-lightrag:/app/lightrag_db/
docker restart obsidian-lightrag
```

### Deep Thinking Timeouts
- Increase gateway timeout in `docker-compose.yml`
- Check Ollama/OpenRouter API availability
- Verify `OPENROUTER_API_KEY` is valid

---

## 17. System Statistics (Current)

- **Total Notes**: 1,676 Obsidian files
- **Vector Database**: 63 MB (ChromaDB)
- **LightRAG Graph**: 152 MB (23,926 entities, 35,030 relationships)
- **NetworkX Graph**: 39 MB (16,212 notes, 16,268 links)
- **Total System Size**: ~254 MB (databases only)
- **Indexed Files**: 2,000 notes in LightRAG
- **Services**: 6 containers + 1 webapp

---

## 18. Future Roadmap

Potential enhancements:
- [ ] GraphRAG integration (Microsoft's open-source graph RAG)
- [ ] Multi-modal support (images, PDFs in vault)
- [ ] Advanced graph analytics dashboard
- [ ] Automated graph update scheduling
- [ ] Query result caching layer
- [ ] MCP server integration for Claude Desktop
- [ ] Mobile-responsive Next.js UI
- [ ] Export query results to Obsidian notes

---

**Last Updated**: January 4, 2025
**System Version**: feat/sota-rag-refinement branch
**Author**: Claude Code (Sonnet 4.5)
**Documentation**: See `Documentation/README.md` for comprehensive guides
