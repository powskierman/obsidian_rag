# Obsidian RAG Project - Complete Index

## Files Generated in This Analysis

1. **obsidian_rag_analysis.md** - Comprehensive 12-section technical analysis
   - Full project structure, architecture, workflows
   - All dependencies and requirements listed
   - Complete initialization sequence
   - Docker and native deployment guides
   
2. **executive_summary.txt** - Quick reference guide (11 sections)
   - Entry points and workflows
   - Initialization checklist
   - All scripts and their purposes
   - Performance expectations
   - Quick command reference

3. **PROJECT_INDEX.md** - This file (navigation guide)

---

## Quick Navigation

### For First-Time Users
1. Read: **executive_summary.txt** (sections 1-2)
2. Run: `./Scripts/docker_start.sh`
3. Open: `http://localhost:8501`

### For Setup & Configuration
1. Check: **executive_summary.txt** (section 2 - checklist)
2. Read: **obsidian_rag_analysis.md** (section 4 - dependencies)
3. Verify: Environment variables in `.env.local`

### For Understanding Architecture
1. Read: **executive_summary.txt** (section 5)
2. Study: **obsidian_rag_analysis.md** (sections 3, 6)
3. Reference: `docker-compose.yml` in project root

### For Troubleshooting
1. Check: **executive_summary.txt** (section 9)
2. Run: `./Scripts/docker_status.sh`
3. View: `docker-compose logs -f <service>`

### For Advanced Usage
1. Read: **obsidian_rag_analysis.md** (section 5)
2. Explore: `build_knowledge_graph.py` (interactive menu)
3. Reference: **obsidian_rag_analysis.md** (section 8)

---

## Key Entry Points (The 5 Most Important Commands)

```bash
# 1. Start everything (Docker - Easiest)
./Scripts/docker_start.sh

# 2. Build knowledge graph with Claude (Best Quality)
python build_knowledge_graph.py

# 3. Resume interrupted build (If something fails)
python retry_failed_chunks.py

# 4. Check what's running (Troubleshooting)
./Scripts/docker_status.sh

# 5. Stop everything (Cleanup)
./Scripts/docker_stop.sh
```

---

## Project Structure at a Glance

```
obsidian_rag/
├── ENTRY POINTS (what to run)
│   ├── build_knowledge_graph.py          ⭐ Interactive graph builder
│   ├── embedding_service.py              ⭐ Vector search backend
│   ├── streamlit_ui_*.py                 ⭐ Web interface
│   └── retry_failed_chunks.py            ⭐ Resume builds
│
├── Scripts/ (utility scripts)
│   ├── docker_start.sh                   ⭐ START HERE (most users)
│   ├── docker_stop.sh                    ⭐ Stop everything
│   ├── docker_status.sh                  ⭐ Check status
│   ├── index_with_*.sh                   Index with different services
│   └── start_*.sh / stop_*.sh             Native Python startup/shutdown
│
├── CONFIGURATION (setup)
│   ├── docker-compose.yml                ⭐ Service definitions
│   ├── .env.local                        ⭐ Environment variables
│   ├── .env.example                      Template
│   └── requirements.txt / requirements_graphrag.txt
│
├── BACKEND SERVICES (don't run directly)
│   ├── graphrag_service.py               GraphRAG API
│   ├── lightrag_service.py               LightRAG API
│   ├── graph_query_service.py            Query API
│   └── claude_graph_builder.py           Core graph logic
│
├── MCP INTEGRATION (Claude Desktop)
│   ├── obsidian_rag_unified_mcp.py       ⭐ Recommended
│   └── knowledge_graph_mcp.py            Alternative
│
├── DATABASES (auto-created)
│   ├── chroma_db/                        Vector embeddings
│   ├── graphrag_db/                      Graph indices
│   ├── graphrag_local_db/                Local data
│   └── graph_data/                       Graph checkpoints
│
└── DOCUMENTATION
    ├── README.md                         Project overview
    ├── Documentation/                    Full guides
    └── obsidian_rag_analysis.md         (generated) Complete analysis
    └── executive_summary.txt             (generated) Quick reference
```

---

## Dependencies Summary

### Required Installations
```bash
# System
brew install docker             # For Docker path
brew install ollama            # For local models
brew install python3.8+        # For native path

# Python packages (automatic via pip)
flask, streamlit, chromadb     # Core RAG
sentence-transformers          # Embeddings
torch, transformers            # ML frameworks
graphrag (optional)            # Knowledge graphs

# Ollama models (manual, one-time)
ollama pull qwen2.5-coder:14b  # 8.5GB language model
ollama pull nomic-embed-text   # 300MB embedding model
```

### Required Environment Variables
```bash
ANTHROPIC_API_KEY=sk-ant-...   # Get from console.anthropic.com
```

### Optional Configuration
```bash
OLLAMA_HOST=http://host.docker.internal:11434  (default)
LLM_MODEL=qwen2.5-coder:14b                     (default)
EMBED_MODEL=nomic-embed-text                    (default)
```

---

## Initialization Steps (Detailed)

### First-Time Setup (30 minutes)
1. Install system dependencies (Docker, Ollama)
2. Pull Ollama models
3. Clone/configure project
4. Set environment variables
5. Test with `./Scripts/docker_start.sh`

### Daily Startup (10 seconds)
```bash
./Scripts/docker_start.sh
```

### First Indexing (45-90 minutes)
```bash
# Option A: Web UI
# 1. Open http://localhost:8501
# 2. Click "Index Vault" button

# Option B: Command Line
./Scripts/index_with_claude.sh
```

---

## Architecture Overview

### Service Topology
```
USER
  ↓
Web Browser (localhost:8501)
  ↓
Streamlit UI
  ├─→ Embedding Service (8000)
  ├─→ GraphRAG Service (8002)
  └─→ LightRAG Service (8001)
       ↓
     Ollama (11434)
```

### Data Flow
```
VAULT FILES
  ↓
[Chunking/Embedding]
  ↓
ChromaDB (vector search)
  ↓
Knowledge Graph (entity extraction)
  ↓
Query Interface (7 search modes)
```

---

## Common Workflows

### Workflow 1: Fast Vector Search (Seconds)
```
1. Index vault → ChromaDB
2. Query → vector similarity
3. Get results instantly
4. Good for: finding facts, quick lookups
```

### Workflow 2: Comprehensive Graph Search (Minutes)
```
1. Build graph → Claude/GraphRAG (45-90 min)
2. Query → entity relationships + synthesis
3. Get comprehensive answer
4. Good for: complex analysis, connections
```

### Workflow 3: Hybrid Approach (Recommended)
```
1. Index both: vector + graph
2. Query → get fast + comprehensive results
3. Best of both worlds
4. Good for: most use cases
```

---

## Performance Expectations

### Time Estimates (1600 notes)
| Operation | Time | Cost |
|-----------|------|------|
| Vector Index | 5-15 min | Free |
| Graph with Haiku | 45-75 min | $1-2 |
| Graph with Sonnet | 60-90 min | $10-20 |
| Graph with Ollama | 2-3 hours | Free |
| Vector Query | <1 sec | Free |
| Graph Query | 5-10 sec | Free |

### System Requirements
- CPU: 2+ cores (4+ for building)
- RAM: 8GB min (16GB recommended)
- Disk: 50GB min
- Internet: For API calls only

---

## Decision Matrix: Which Path to Choose?

| Use Case | Path | Command |
|----------|------|---------|
| Quick start, simple use | Docker | `./Scripts/docker_start.sh` |
| Best quality results | Graph + Claude | `python build_knowledge_graph.py` |
| Free/offline-only | Ollama | `./Scripts/index_with_graphrag_local.sh` |
| Development/customization | Native Python | `python embedding_service.py &` |
| Integration with Claude | MCP | Configure obsidian_rag_unified_mcp.py |
| Resume failed build | Retry | `python retry_failed_chunks.py` |

---

## Important Files Reference

### Must-Know Configuration Files
- `docker-compose.yml` - Service definitions (don't edit usually)
- `.env.local` - Your settings (edit once during setup)
- `requirements.txt` - Python dependencies (don't edit)

### Must-Know Entry Points
- `./Scripts/docker_start.sh` - Start here!
- `python build_knowledge_graph.py` - Build graphs
- `./Scripts/docker_status.sh` - Check status

### Must-Know Documentation
- `README.md` - Project overview
- `obsidian_rag_analysis.md` - Technical deep-dive
- `executive_summary.txt` - Quick reference
- `Documentation/QUICKSTART.md` - Getting started

---

## Troubleshooting Quick Links

| Problem | Solution |
|---------|----------|
| "Services won't start" | Check Ollama: `curl http://localhost:11434/api/tags` |
| "API key not found" | Set: `export ANTHROPIC_API_KEY="your-key"` |
| "Docker not running" | Start Docker Desktop |
| "Search returns nothing" | Run indexing first via web UI |
| "Indexing too slow" | Use Haiku model instead of Sonnet |
| "Out of memory" | Reduce chunk size or index in batches |
| "No results" | Verify vault path and markdown files exist |

---

## Quick Reference: 10 Most Common Commands

```bash
# 1. Start everything
./Scripts/docker_start.sh

# 2. Check status
./Scripts/docker_status.sh

# 3. Stop everything
./Scripts/docker_stop.sh

# 4. View logs
docker-compose logs -f embedding-service

# 5. Build knowledge graph
python build_knowledge_graph.py

# 6. Resume interrupted build
python retry_failed_chunks.py

# 7. Index with Claude
./Scripts/index_with_claude.sh

# 8. Index with GraphRAG
./Scripts/index_with_graphrag.sh

# 9. Rebuild Docker images
./Scripts/docker_rebuild.sh

# 10. Clean up databases
./Scripts/clean.sh
```

---

## Next Steps

1. **First-time users:** Follow **executive_summary.txt** section 1-2
2. **Want more detail:** Read **obsidian_rag_analysis.md**
3. **Ready to start:** Run `./Scripts/docker_start.sh`
4. **Need help:** Check section 9 (Troubleshooting) in executive_summary.txt

---

## Summary

The Obsidian RAG project provides intelligent search over personal knowledge bases using:
- **Vector Search** (fast, simple)
- **Knowledge Graphs** (comprehensive, entity-aware)
- **Multiple Interfaces** (web UI, CLI, MCP)

**Recommended start:** `./Scripts/docker_start.sh` → Open browser → Index vault → Query

**Time to first working system:** 10-15 minutes (after initial setup)

**Cost for full features:** $1-2 with Claude Haiku (recommended)

---

*Analysis generated: 2025-11-18*
*Project: /Users/michel/iCloud Drive/ai/RAG/obsidian_rag*
