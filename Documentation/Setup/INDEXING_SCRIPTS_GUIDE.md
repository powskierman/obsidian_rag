# Indexing Scripts Guide

## Overview

Your Obsidian RAG system has **two knowledge graphs** that need separate indexing:

| Graph | Script | LLM | Port | Purpose |
|-------|--------|-----|------|---------|
| **NetworkX** | `index_with_kimi.sh` | Kimi K2 | 8002 | Note-centric vault structure |
| **LightRAG** | `index_lightrag_with_kimi.sh` | Kimi K2 | 8001 | Entity-centric semantic graph |

---

## Scripts Explained

### 1. `index_with_kimi.sh` - NetworkX Graph (KEEP AS-IS)

**What it does:**
- Builds the **NetworkX knowledge graph** (note-centric)
- Creates nodes for each markdown file
- Creates edges from wiki-links between notes
- Uses Kimi K2 for reasoning about note relationships

**Output:**
- `graph_data/knowledge_graph_full.pkl`
- 16,212 note nodes
- 16,268 link edges

**Usage:**
```bash
./Scripts/index_with_kimi.sh
```

**Cost:** ~$0.50-1.00 for 1,676 notes
**Time:** ~10-20 minutes

---

### 2. `index_lightrag_with_kimi.sh` - LightRAG Graph (NEW!)

**What it does:**
- Builds the **LightRAG knowledge graph** (entity-centric)
- Extracts entities (concepts, terms) from note content
- Creates semantic relationships between entities
- Uses Kimi K2 for entity extraction and relationship mapping

**Output:**
- `lightrag_db/` directory (152 MB)
- 23,926 entity nodes
- 35,030 relationship edges
- Vector embeddings for entities and chunks

**Usage:**
```bash
./Scripts/index_lightrag_with_kimi.sh
```

**Cost:** ~$0.50-1.00 for 1,676 notes
**Time:** ~30-60 minutes

---

### 3. `index_with_claude.sh` - LightRAG (OLD/MISLEADING)

**Status:** ⚠️ MISLEADING NAME

**Reality:**
- Despite the name, this script calls the LightRAG service
- The LightRAG service is **already configured to use Kimi K2**, not Claude
- This script is essentially a duplicate of `index_lightrag_with_kimi.sh`

**Recommendation:**
- Use `index_lightrag_with_kimi.sh` instead (clearer naming)
- Consider deleting or renaming `index_with_claude.sh` to avoid confusion

---

## When to Use Each Script

### Use `index_with_kimi.sh` when:
- You want to rebuild the NetworkX graph (note structure)
- You've added/removed many wiki-links
- You want to analyze vault organization
- You need graph metrics (centrality, clustering, etc.)

### Use `index_lightrag_with_kimi.sh` when:
- You want to rebuild the LightRAG graph (entity knowledge)
- You've added many new notes with concepts
- You want semantic search and discovery
- You need to find relationships between concepts

---

## Cost Comparison

Both scripts use **Kimi K2** via OpenRouter, so costs are identical:

| Vault Size | NetworkX | LightRAG |
|------------|----------|----------|
| 1,000 notes | ~$0.30 | ~$0.50 |
| 1,676 notes | ~$0.50 | ~$0.75 |
| 3,000 notes | ~$1.00 | ~$1.50 |

**Much cheaper than Claude:**
- Claude 3.5 Haiku: ~$1-2 for 1,676 notes
- Claude 3.5 Sonnet: ~$10-20 for 1,676 notes

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Indexing Scripts                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  index_with_kimi.sh                                  │
│         │                                            │
│         ▼                                            │
│  ┌──────────────────┐                                │
│  │ graph-service    │  Port 8002                     │
│  │ (NetworkX)       │  Kimi K2                       │
│  └──────────────────┘                                │
│         │                                            │
│         ▼                                            │
│  graph_data/knowledge_graph_full.pkl                 │
│                                                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  index_lightrag_with_kimi.sh                         │
│         │                                            │
│         ▼                                            │
│  ┌──────────────────┐                                │
│  │ lightrag-service │  Port 8001                     │
│  │ (Entity Graph)   │  Kimi K2 + Ollama             │
│  └──────────────────┘                                │
│         │                                            │
│         ▼                                            │
│  lightrag_db/ (152 MB)                               │
│    - graph_chunk_entity_relation.graphml             │
│    - vdb_entities.json                               │
│    - vdb_relationships.json                          │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## Requirements

### For Both Scripts:

1. **OpenRouter API Key:**
   ```bash
   export OPENROUTER_API_KEY='your-key-here'
   ```
   Get one at: https://openrouter.ai/keys

2. **Docker Services Running:**
   ```bash
   cd config/docker
   docker compose up -d
   ```

3. **Vault Path Set:**
   ```bash
   export OBSIDIAN_VAULT_PATH='/path/to/your/vault'
   # OR create symlink:
   ln -s /path/to/your/vault ./vault
   ```

### Additionally for LightRAG:

4. **Ollama Running** (for embeddings):
   - Mac: Ollama Desktop app should be running
   - Or: `ollama serve` in terminal
   - Model: `nomic-embed-text` (auto-downloaded on first use)

---

## Verification

### After NetworkX Indexing:

```bash
# Check graph file exists
ls -lh graph_data/knowledge_graph_full.pkl

# Test graph service
curl http://localhost:8002/health

# Test query
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query":"test","use_vector":true}'
```

### After LightRAG Indexing:

```bash
# Check database directory
ls -lh lightrag_db/

# Check service health
curl http://localhost:8001/health

# Check stats
curl http://localhost:8001/stats

# Test query
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"test","mode":"hybrid"}'
```

---

## Troubleshooting

### Script fails with "API key not set"

**Solution:**
```bash
# Add to .env file
echo "OPENROUTER_API_KEY=your-key-here" >> .env

# Or export directly
export OPENROUTER_API_KEY='your-key-here'
```

### "Service not responding"

**Check container status:**
```bash
docker ps | grep obsidian
```

**Check logs:**
```bash
docker logs obsidian-graph-service   # NetworkX
docker logs obsidian-lightrag        # LightRAG
```

**Restart services:**
```bash
cd config/docker
docker compose restart
```

### Ollama not found (LightRAG only)

**Mac:**
- Download from: https://ollama.ai/download
- Or: `brew install ollama`
- Start: Ollama app or `ollama serve`

**Verify:**
```bash
curl http://localhost:11434/api/tags
```

### Out of memory / slow indexing

**For large vaults (>3,000 notes):**

1. **Increase Docker memory:**
   - Docker Desktop → Settings → Resources
   - Recommended: 8 GB RAM

2. **Index in batches:**
   ```bash
   # Split vault into subdirectories
   # Index each separately
   ```

3. **Monitor progress:**
   ```bash
   docker logs -f obsidian-lightrag
   ```

---

## Best Practices

1. **Index both graphs initially** to get full system functionality
2. **Re-index periodically** as your vault grows (monthly or when adding >100 notes)
3. **Backup before re-indexing** (graph databases are gitignored):
   ```bash
   cp -r lightrag_db lightrag_db_backup_$(date +%Y%m%d)
   cp graph_data/knowledge_graph_full.pkl graph_data/backup_$(date +%Y%m%d).pkl
   ```
4. **Test queries after indexing** to ensure quality
5. **Monitor costs** at https://openrouter.ai/activity

---

## Summary

✅ **Two scripts, two graphs, both using Kimi K2:**

- `index_with_kimi.sh` → NetworkX (notes & links)
- `index_lightrag_with_kimi.sh` → LightRAG (entities & concepts)

✅ **Both are cheap (~$0.50-1.00 for 1,676 notes)**

✅ **Keep both indexed for full system capabilities**

🗑️ **Consider removing `index_with_claude.sh`** (misleading name, uses Kimi anyway)

---

**Created:** December 30, 2025
**Author:** Claude Code (Sonnet 4.5)
