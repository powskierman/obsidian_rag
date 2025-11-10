# 🧠 Claude-Powered Knowledge Graph - Complete Implementation

## 📋 Summary

You have a working Obsidian RAG system with ChromaDB (7,113 chunks), but LightRAG and GraphRAG are broken. This solution replaces them with **Claude's reasoning** to build and query your knowledge graph.

## ✨ Updated: Filesystem Access

**New in this version:** Direct filesystem access! No HTTP services needed.

- ✅ Reads ChromaDB directly from disk
- ✅ Falls back to reading vault .md files
- ✅ No need to run embedding service
- ✅ Works with default paths (auto-detected)
- ✅ Simpler setup and deployment

---

## 🎯 What You Get

### The Problem
- ❌ LightRAG: Broken (event loop conflicts)
- ❌ GraphRAG: Broken
- ✅ ChromaDB: Working (vector search)
- Need: Graph-based reasoning and relationship discovery

### The Solution
- ✅ Use Claude API to extract entities & relationships
- ✅ Build NetworkX knowledge graph
- ✅ Query graph with Claude's reasoning
- ✅ Combine with existing vector search (hybrid)
- ✅ No complex dependencies

---

## 📦 Files Provided

All files are in `/mnt/user-data/outputs/` ready to download:

### Core Files
1. **claude_graph_builder.py** (450 lines)
   - `ClaudeGraphBuilder`: Extracts entities/relationships using Claude
   - `ClaudeGraphQuerier`: Query graph with Claude's reasoning
   - NetworkX graph storage

2. **build_knowledge_graph.py** (350 lines)
   - Integrates with your existing ChromaDB
   - Test mode: 50 chunks (~$0.50, 2 minutes)
   - Full mode: 7,113 chunks (~$25, 3-4 hours)
   - Interactive query terminal

3. **graph_query_service.py** (200 lines)
   - Flask REST API for graph queries
   - Runs in Docker alongside your services
   - Port 8002

4. **streamlit_ui_hybrid.py** (350 lines)
   - Enhanced UI with hybrid search
   - Combines vector + graph results
   - Graph exploration tools

### Docker Files
5. **Dockerfile.graph**
   - Container for graph service

6. **docker-compose.graph-addon.yml**
   - Add to your existing docker-compose.yml

### Documentation
7. **DEPLOYMENT_GUIDE.md**
   - Complete step-by-step instructions
   - Examples, troubleshooting, costs

8. **requirements-graph.txt**
   - Python dependencies

---

## 🚀 Quick Start Path

### Phase 1: Test (30 minutes)

```bash
# 1. Copy files to your system
cd /Users/michel/Library/Mobile\ Documents/com\~apple\~CloudDocs/ai/RAG/obsidian_rag
# Download files from Claude outputs

# 2. Install dependencies
source venv/bin/activate
pip install -r requirements-graph.txt

# 3. Set API key
export ANTHROPIC_API_KEY="your-key"

# 4. Build test graph (50 chunks from ChromaDB or vault files)
python build_knowledge_graph.py
# Choose option 1
# Press Enter for default paths or provide custom paths

# Paths auto-detected:
# ChromaDB: ~/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/chroma_db
# Vault: ~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel
```

**Expected output:**
- ✅ Loads chunks from ChromaDB or vault files
- ~100-150 entities
- ~200-300 relationships
- Test queries work
- Cost: ~$0.50

### Phase 2: Full Build (4 hours)

```bash
# Build full graph from all chunks
python build_knowledge_graph.py
# Choose option 2

# Wait ~3-4 hours...
# Cost: ~$25-30 one-time
```

**Expected output:**
- ~3,000-5,000 entities
- ~10,000-15,000 relationships
- Production-ready graph
- Saved to knowledge_graph_full.pkl

### Phase 3: Docker Integration (1 hour)

```bash
# 1. Add graph service to docker-compose.yml
# (merge docker-compose.graph-addon.yml)

# 2. Copy graph file
cp knowledge_graph_full.pkl knowledge_graph.pkl

# 3. Update Streamlit UI
cp streamlit_ui_hybrid.py streamlit_ui_docker.py

# 4. Start services
docker-compose up -d

# 5. Access hybrid UI
open http://localhost:8501
```

---

## 💡 How It Works

### Step 1: Data Loading (Filesystem)

```
Option A: ChromaDB (preferred)
  ↓
Load ChromaDB from disk (/path/to/chroma_db)
  ↓
Read all documents + metadata
  ↓
Convert to chunks with metadata

Option B: Vault Files (fallback)
  ↓
Find all .md files in vault
  ↓
Read file contents
  ↓
Split into chunks (1000 chars)
  ↓
Add metadata (filename, path)
```

### Step 2: Entity Extraction (Claude)

```
Input (chunk):
"CAR-T therapy is a treatment for lymphoma that uses modified T cells."

Claude extracts:
Entities:
  - "CAR-T Therapy" (type: treatment)
  - "Lymphoma" (type: condition)
  - "T Cells" (type: biology)

Relationships:
  - CAR-T Therapy --[treats]--> Lymphoma
  - CAR-T Therapy --[uses]--> T Cells
```

### Step 3: Graph Building (NetworkX)

```
7,113 chunks → Claude API → Entities + Relationships → NetworkX Graph
                                                            ↓
                                                   knowledge_graph.pkl
```

### Step 4: Query with Reasoning (Claude + Graph)

```
User: "How does CAR-T relate to my treatment timeline?"
  ↓
Graph: Find CAR-T + connected entities
  ↓
Claude: Reason over graph structure + synthesize answer
  ↓
Answer: "CAR-T therapy in your notes is connected to..."
```

---

## 🎨 Example Queries

### Medical
```
"What's the progression of my lymphoma treatment?"
"How are my PET scans related to treatment decisions?"
"What medications interact with my current treatment?"
```

### Technical
```
"What 3D printing technologies have I explored?"
"How do my Fusion 360 projects connect?"
"What programming languages appear across my projects?"
```

### Cross-Domain
```
"How do engineering principles apply to medical device design in my notes?"
"What patterns exist between my technical and medical documentation?"
```

---

## 📊 Architecture Comparison

### Before (Broken)
```
ChromaDB → Vector Search → Ollama → Answer
             ✅             ✅       ✅

LightRAG → Graph Search → ???
             ❌            ❌

GraphRAG → Knowledge Graph → ???
             ❌              ❌
```

### After (Working)
```
ChromaDB → Vector Search ─┐
             ✅           │
                          ├→ Hybrid → Enhanced Answer
                          │
Claude Graph → Reasoning ─┘
    ✅            ✅
```

---

## 💰 Cost Breakdown

### One-Time (Building Graph)
- **Test (50 chunks)**: $0.50
- **Full (7,113 chunks)**: $25-30

### Ongoing (Querying)
- **Simple query**: $0.02
- **Complex query**: $0.05
- **Monthly (50 queries/day)**: ~$3-5

### Cost Optimization (Future)
- Add prompt caching → 90% savings on queries
- Monthly with caching: ~$0.50-1

---

## 🔧 Integration Points

### 1. Standalone (Current)
```bash
# Build graph
python build_knowledge_graph.py

# Query interactively
python build_knowledge_graph.py
```

### 2. API Service (Docker)
```bash
# Start service
docker-compose up graph-service

# Query via API
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What treatments?"}'
```

### 3. Hybrid UI (Streamlit)
```bash
# Access UI
open http://localhost:8501

# Use both:
# - Vector search (fast, keyword-based)
# - Graph reasoning (relationships, context)
```

---

## 🎯 Success Metrics

After building the graph, you should see:

✅ **Entities**: 3,000-5,000 unique concepts  
✅ **Relationships**: 10,000-15,000 connections  
✅ **Query Time**: 5-10 seconds (includes Claude API)  
✅ **Quality**: Meaningful entities extracted  
✅ **Medical Terms**: Properly identified  
✅ **Relationships**: Accurate and useful  

---

## 🐛 Common Issues & Fixes

### Issue: "Can't connect to embedding service"
```bash
# Start embedding service
docker-compose up embedding-service

# Or check it's running
curl http://localhost:8000/stats
```

### Issue: "ANTHROPIC_API_KEY not set"
```bash
# Export in terminal
export ANTHROPIC_API_KEY="sk-ant-..."

# Or add to .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

### Issue: "Graph file not found"
```bash
# Build graph first
python build_knowledge_graph.py
# Choose option 1 (test) or 2 (full)
```

### Issue: "Out of memory during graph build"
```bash
# Process in smaller batches
# Edit build_knowledge_graph.py:
# Change: batch_size=10 to batch_size=5
```

---

## 🎓 Next Steps

1. **Download all files** from outputs directory
2. **Test with 50 chunks** (~$0.50, 2 minutes)
3. **Review entity quality** - Are they meaningful?
4. **Try test queries** - Do answers make sense?
5. **Build full graph** if satisfied (~$25, 4 hours)
6. **Integrate with Docker** for production use

---

## 📈 Future Enhancements

Possible additions:

1. **Incremental Updates**
   - Only process new/changed chunks
   - Merge with existing graph

2. **Prompt Caching**
   - Cache graph context
   - 90% cost reduction on queries

3. **Graph Visualization**
   - Interactive graph explorer
   - Entity relationship viewer

4. **Advanced Reasoning**
   - Multi-hop path analysis
   - Temporal reasoning
   - Causal inference

5. **Custom Entity Types**
   - Domain-specific extraction
   - Better medical terminology

---

## ✅ Validation Checklist

Before full deployment:

- [ ] Test mode runs successfully (50 chunks)
- [ ] Entities look meaningful and accurate
- [ ] Relationships make sense
- [ ] Test queries produce good answers
- [ ] Cost is acceptable (~$25 one-time + $3-5/month)
- [ ] Docker integration tested (optional)
- [ ] Backup plan if graph needs rebuild

---

## 📞 Support Resources

**Documentation:**
- DEPLOYMENT_GUIDE.md - Detailed instructions
- Code comments - Inline documentation
- Example queries - In all files

**Debugging:**
- Check logs: `docker-compose logs graph-service`
- Test API: `curl http://localhost:8002/health`
- Verify files: `ls -lh knowledge_graph*.pkl`

**Anthropic API:**
- Status: https://status.anthropic.com
- Docs: https://docs.anthropic.com
- Pricing: https://www.anthropic.com/pricing

---

## 🎉 Summary

You now have a complete Claude-powered knowledge graph system that:

✅ Replaces broken LightRAG/GraphRAG  
✅ Works with your existing ChromaDB  
✅ Extracts meaningful entities & relationships  
✅ Provides graph-based reasoning  
✅ Integrates with Docker  
✅ Costs ~$25 to build + $3-5/month to query  

**Start with test mode (50 chunks) to validate, then scale up!**

---

*All files ready in `/mnt/user-data/outputs/`* 🚀
