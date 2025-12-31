# Dual Graph Architecture - Restored

**Status**: ✅ Fully Operational
**Date Restored**: December 30, 2025
**Database Restored From**: December 22, 2025 backup

---

## Overview

Your Obsidian RAG system now operates with **two complementary knowledge graphs**, each serving distinct purposes for querying your 1,676-note vault.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│            Obsidian RAG System (Dual Graph)             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────┐  ┌──────────────────────────┐│
│  │   LightRAG Graph     │  │  NetworkX Graph          ││
│  │   Port: 8001         │  │  Port: 8002              ││
│  ├──────────────────────┤  ├──────────────────────────┤│
│  │ Type: Entity-centric │  │ Type: Note-centric       ││
│  │ Nodes: 23,926        │  │ Nodes: 16,212            ││
│  │ Edges: 35,030        │  │ Edges: 16,268            ││
│  │ Size: 152 MB         │  │ Size: 39 MB              ││
│  │                      │  │                          ││
│  │ Purpose:             │  │ Purpose:                 ││
│  │ • Semantic search    │  │ • Vault structure        ││
│  │ • Entity discovery   │  │ • Link analysis          ││
│  │ • Multi-hop queries  │  │ • Note navigation        ││
│  │ • Concept relations  │  │ • Orphan detection       ││
│  └──────────────────────┘  └──────────────────────────┘│
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │         ChromaDB Vector Store (Port 8000)        │   │
│  │         Size: 63 MB - Semantic Similarity        │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Graph Comparison

### LightRAG (Port 8001)

**What it represents:**
- **Nodes**: Concepts, entities, terms extracted from your notes
- **Edges**: Semantic relationships between concepts
- **Created by**: AI-powered entity extraction (Kimi K2 LLM)

**Database Contents** (152 MB):
- `graph_chunk_entity_relation.graphml` (7.5 MB) - Graph structure
- `vdb_entities.json` (46 MB) - 23,926 entity embeddings
- `vdb_relationships.json` (45 MB) - 35,030 relationship embeddings
- `vdb_chunks.json` (7.7 MB) - Text chunk vectors
- `kv_store_llm_response_cache.json` (38 MB) - Cached responses
- `indexed_files.txt` - 2,000 indexed notes

**Best for:**
- "What are all the concepts related to CAR-T therapy?"
- "How are ESPHome and Home Assistant connected in my notes?"
- "Show me all entities related to garage automation"
- Discovering implicit connections across unlinked notes
- Multi-hop reasoning queries

**Query Modes:**
- `naive`: Simple keyword search
- `local`: Local entity neighborhood
- `global`: Community-level patterns
- `hybrid`: Combined approach (recommended)

**Example Query:**
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"CAR-T therapy mechanisms","mode":"hybrid"}'
```

---

### NetworkX Graph (Port 8002)

**What it represents:**
- **Nodes**: Your actual Obsidian note files
- **Edges**: Explicit wiki-links between notes
- **Created by**: Parsing vault file structure

**Database Contents** (39 MB):
- `knowledge_graph_full.pkl` - Serialized NetworkX graph
- 16,212 note nodes
- 16,268 link edges

**Best for:**
- "Which notes link to my Home Assistant setup?"
- "Find orphaned notes in my vault"
- "What's the shortest path between my CAR-T notes and technical projects?"
- Graph analysis (centrality, clustering, communities)
- Understanding your vault's organization

**Example Query:**
```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query":"garage automation","use_vector":true}'
```

---

## Key Differences

| Feature | LightRAG | NetworkX |
|---------|----------|----------|
| **Granularity** | Concepts/entities | Note files |
| **Node count** | 23,926 (more) | 16,212 |
| **Relationships** | Semantic (AI-extracted) | Explicit (wiki-links) |
| **Completeness** | Captures implicit knowledge | Shows intentional structure |
| **Use case** | Discovery & exploration | Organization & navigation |
| **Query type** | "What do I know about X?" | "Where did I write about X?" |

---

## Why Both?

The two graphs are **complementary**, not redundant:

1. **LightRAG finds hidden connections**
   - Surfaces concepts from notes you didn't link
   - Example: Finds "CAR-T" mentions across medical notes even if not linked

2. **NetworkX shows your thinking structure**
   - Reveals how YOU organized your knowledge
   - Example: Shows which notes are central hubs vs isolated

3. **Together = Complete picture**
   - LightRAG: "What connections exist in the content?"
   - NetworkX: "How did I structure my notes?"

---

## Services Running

| Service | Port | Container | Status |
|---------|------|-----------|--------|
| **ChromaDB** | 8000 | obsidian-embedding | ✅ Running |
| **LightRAG** | 8001 | obsidian-lightrag | ✅ Running |
| **NetworkX** | 8002 | obsidian-graph-service | ✅ Running |
| **API Gateway** | 4000 | obsidian-api-gateway | ✅ Running |
| **Streamlit UI** | 8501 | obsidian-ui | ✅ Running |

---

## Health Checks

```bash
# LightRAG
curl http://localhost:8001/health
# Expected: {"status":"healthy","service":"lightrag",...}

# LightRAG Stats
curl http://localhost:8001/stats
# Expected: {"database_exists":true,"total_files":13,...}

# NetworkX Graph
curl http://localhost:8002/health
# Expected: {"status":"healthy",...}

# Embedding Service
curl http://localhost:8000/health
# Expected: {"status":"healthy",...}
```

---

## Database Locations

### LightRAG
- **Docker volume**: `docker_lightrag_storage`
- **Container path**: `/app/lightrag_db/`
- **Local backup**: `/Users/michel/.../obsidian_rag/lightrag_db/` (gitignored)

### NetworkX
- **Local path**: `/Users/michel/.../obsidian_rag/data/graph_data/`
- **Main file**: `knowledge_graph_full.pkl`

### ChromaDB
- **Local path**: `/Users/michel/.../obsidian_rag/chroma_db/`
- **Size**: 63 MB

---

## Restoration History

**December 28, 2025**: LightRAG removed during cleanup (Phase 3)
- Rationale: Considered redundant with NetworkX
- Space freed: ~200 MB

**December 30, 2025**: LightRAG restored
- Reason: Analysis showed complementary purposes, not redundant
- Restored from: December 22 backup on `/Volumes/max`
- Database copied into Docker volume

---

## Query Examples

### LightRAG Queries

**Local mode** (entities in neighborhood):
```json
{
  "query": "CAR-T therapy side effects",
  "mode": "local"
}
```

**Global mode** (community patterns):
```json
{
  "query": "immune system research",
  "mode": "global"
}
```

**Hybrid mode** (best results):
```json
{
  "query": "garage door automation with ESP32",
  "mode": "hybrid"
}
```

### NetworkX Queries

**Find related notes**:
```json
{
  "query": "Home Assistant",
  "use_vector": true
}
```

---

## Configuration

### LightRAG (`docker-compose.yml`)

```yaml
lightrag-service:
  container_name: obsidian-lightrag
  ports:
    - "8001:8001"
  volumes:
    - lightrag_storage:/app/lightrag_db
  environment:
    - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    - KIMI_MODEL=moonshotai/kimi-k2-0905
    - EMBED_MODEL=nomic-embed-text
    - OLLAMA_HOST=http://host.docker.internal:11434
```

### NetworkX (`docker-compose.yml`)

```yaml
graph-service:
  container_name: obsidian-graph-service
  ports:
    - "8002:8002"
  volumes:
    - ./data/graph_data:/app/graph_data
  environment:
    - KIMI_MODEL=moonshotai/kimi-k2-0905
    - EMBEDDING_SERVICE_URL=http://embedding-service:8000
```

---

## Maintenance

### Backup LightRAG Database

```bash
docker cp obsidian-lightrag:/app/lightrag_db ./lightrag_db_backup_$(date +%Y%m%d)
```

### Update LightRAG Index

```bash
curl -X POST http://localhost:8001/index-vault \
  -H "Content-Type: application/json" \
  -d '{"vault_path":"/app/vault"}'
```

### Rebuild NetworkX Graph

```bash
# Run indexing script
cd Scripts
./index_with_kimi.sh
```

---

## Performance

| Operation | LightRAG | NetworkX |
|-----------|----------|----------|
| **Query speed** | Moderate (2-5s) | Fast (<1s) |
| **Index time** | Slow (hours for full vault) | Fast (minutes) |
| **Memory** | High (~500MB) | Low (~100MB) |
| **Accuracy** | High (semantic) | Exact (links) |

---

## Best Practices

1. **Start with LightRAG hybrid mode** for exploratory queries
2. **Use NetworkX** for vault maintenance and structure analysis
3. **Combine both** for comprehensive research:
   - LightRAG to find related concepts
   - NetworkX to locate the actual notes
4. **Re-index periodically** as your vault grows
5. **Backup databases regularly** (they're gitignored)

---

## Troubleshooting

### LightRAG shows 0 files

**Problem**: Database volume is empty
**Solution**:
```bash
docker cp ./lightrag_db/. obsidian-lightrag:/app/lightrag_db/
docker restart obsidian-lightrag
```

### Container not starting

**Check logs**:
```bash
docker logs obsidian-lightrag
```

### Port conflicts

**Check if port is in use**:
```bash
lsof -i :8001  # LightRAG
lsof -i :8002  # NetworkX
```

---

## Next Steps

- ✅ LightRAG service restored and running
- ✅ Database (152 MB, 23,926 nodes) restored from backup
- ✅ Health checks passing
- ⏳ Consider re-indexing if vault has changed since Nov 22
- ⏳ Test queries to verify graph quality

---

## References

- LightRAG source: https://github.com/HKUDS/LightRAG
- Service code: `src/integrations/lightrag_service.py`
- Dockerfile: `Dockerfile.lightrag`
- Backup location: `/Volumes/max/Users/michel/.../obsidian_rag/lightrag_db/`

---

**Generated**: December 30, 2025
**Author**: Claude Code (Sonnet 4.5)
