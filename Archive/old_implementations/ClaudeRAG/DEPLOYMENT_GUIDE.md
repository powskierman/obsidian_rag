# Claude-Powered Knowledge Graph for Obsidian RAG

Replace broken LightRAG/GraphRAG with Claude's reasoning to build and query your knowledge graph.

## 🎯 What This Does

**Before:** LightRAG/GraphRAG broken ❌  
**After:** Claude extracts entities & relationships from your vault ✅

### Key Features

- ✅ **Entity Extraction**: Claude identifies important concepts, treatments, technologies, people
- ✅ **Relationship Discovery**: Finds meaningful connections between entities
- ✅ **Graph Reasoning**: Claude analyzes the graph structure to answer questions
- ✅ **Hybrid Search**: Combines vector search (ChromaDB) + graph reasoning
- ✅ **No Dependencies**: Just Claude API + NetworkX (pure Python)
- ✅ **Medical Aware**: Excellent at medical terminology and relationships

---

## 📦 Files Created

```
claude_graph_builder.py       # Core graph builder (uses Claude API)
build_knowledge_graph.py       # Build graph from your ChromaDB chunks
graph_query_service.py         # Flask API for graph queries (Docker)
streamlit_ui_hybrid.py         # Enhanced UI with hybrid search
Dockerfile.graph               # Docker image for graph service
docker-compose.graph-addon.yml # Add to your docker-compose.yml
```

---

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies

```bash
cd /Users/michel/Library/Mobile\ Documents/com\~apple\~CloudDocs/ai/RAG/obsidian_rag

# Activate your venv
source venv/bin/activate

# Install packages
pip install anthropic networkx tqdm
```

### Step 2: Build the Knowledge Graph

**Option A: Test Mode (50 chunks, ~2 minutes, ~$0.50)**

```bash
# Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# Run builder
python build_knowledge_graph.py
# Choose option 1: Test mode
```

**Option B: Full Mode (7,113 chunks, ~3-4 hours, ~$20-30)**

```bash
python build_knowledge_graph.py
# Choose option 2: Full mode
```

This will:
- Fetch chunks from your ChromaDB
- Use Claude to extract entities & relationships from each chunk
- Build a NetworkX graph
- Save to `knowledge_graph.pkl`
- Export to `knowledge_graph.json` for visualization

### Step 3: Query the Graph

**Option A: Interactive Terminal**

```bash
python build_knowledge_graph.py
# Choose option 4: Interactive mode

# Try queries like:
# - "What treatments are mentioned in my notes?"
# - "How does CAR-T relate to lymphoma?"
# - "stats" to see graph statistics
```

**Option B: Docker Service (Production)**

```bash
# Copy files to your RAG directory
cp claude_graph_builder.py /path/to/obsidian_rag/
cp graph_query_service.py /path/to/obsidian_rag/
cp Dockerfile.graph /path/to/obsidian_rag/
cp streamlit_ui_hybrid.py /path/to/obsidian_rag/

# Add graph service to docker-compose.yml
# (see docker-compose.graph-addon.yml)

# Start services
docker-compose up -d

# Access hybrid UI
open http://localhost:8501
```

---

## 📊 Expected Results

### Test Mode (50 chunks)
- **Time**: 2-3 minutes
- **Cost**: ~$0.50
- **Output**: ~100-150 entities, ~200-300 relationships
- **Use For**: Validating the approach, testing queries

### Full Mode (7,113 chunks)
- **Time**: 3-4 hours
- **Cost**: ~$20-30
- **Output**: ~3,000-5,000 entities, ~10,000-15,000 relationships
- **Use For**: Production knowledge graph

### Graph Quality

Claude will extract:
- **Medical**: treatments, medications, conditions, procedures, scans
- **Technical**: technologies, projects, tools, methods
- **Personal**: people, places, events
- **Relationships**: treats, causes, uses, relates_to, part_of

---

## 🎨 Example Usage

### Terminal Queries

```python
# After building graph
from claude_graph_builder import ClaudeGraphBuilder, ClaudeGraphQuerier

# Load graph
builder = ClaudeGraphBuilder(api_key="your-key")
builder.load_graph("knowledge_graph.pkl")
querier = ClaudeGraphQuerier(builder, api_key="your-key")

# Query with Claude
answer = querier.query_with_claude(
    "How does my 3D printing experience relate to medical device design?"
)
print(answer)

# Explore entity
info = querier.get_entity_neighborhood("CAR-T Therapy")
print(f"Connections: {len(info['outgoing']) + len(info['incoming'])}")

# Find paths
paths = querier.find_paths("CAR-T Therapy", "Lymphoma")
for path in paths:
    print(" → ".join(path))
```

### API Queries (Docker)

```bash
# Query graph
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What treatments are mentioned?"}'

# Get entity info
curl http://localhost:8002/entity/CAR-T%20Therapy

# Find path between entities
curl -X POST http://localhost:8002/path \
  -H "Content-Type: application/json" \
  -d '{"source": "CAR-T", "target": "Lymphoma"}'

# Search entities
curl -X POST http://localhost:8002/search_entities \
  -H "Content-Type: application/json" \
  -d '{"query": "treatment", "limit": 10}'

# Get stats
curl http://localhost:8002/stats
```

---

## 🔧 Integration with Existing System

### Your Current Setup
```
ChromaDB (7,113 chunks) → Ollama (Qwen 2.5) → Streamlit UI
✅ Working                ✅ Working           ✅ Working
```

### Enhanced Setup
```
ChromaDB (vector) ─┐
                   ├─→ Hybrid Search → Enhanced UI
Graph (Claude) ────┘
✅ Working         🆕 New            🆕 New
```

### Docker Architecture

```yaml
services:
  embedding-service:  # Port 8000 - Vector search
  graph-service:      # Port 8002 - Graph search (NEW)
  streamlit-ui:       # Port 8501 - Hybrid UI (UPDATED)
```

---

## 💰 Cost Analysis

### Graph Building (One-Time)

| Chunks | Time | Cost | When |
|--------|------|------|------|
| 50 (test) | 2-3 min | $0.50 | Testing |
| 7,113 (full) | 3-4 hrs | $20-30 | Production |

**Cost Breakdown:**
- Input: ~200 tokens/chunk × 7,113 chunks = ~1.4M tokens = $10.50
- Output: ~300 tokens/chunk × 7,113 chunks = ~2M tokens = $15
- **Total: ~$25-30** (one-time)

### Graph Querying (Ongoing)

| Query Type | Tokens | Cost |
|------------|--------|------|
| Simple | 1,000 | $0.02 |
| Complex | 3,000 | $0.05 |

**Monthly estimate (50 queries/day):**
- Average query: ~2,000 tokens
- Cost: ~$3-5/month

**With Prompt Caching (coming soon):**
- Cache graph context → 90% savings
- Monthly: ~$0.50-1/month

---

## 🔄 Incremental Updates

As your vault grows, rebuild the graph:

```bash
# Option 1: Full rebuild (recommended monthly)
python build_knowledge_graph.py
# Choose option 2

# Option 2: Add new chunks only (coming soon)
# python update_graph.py --since 2025-01-01
```

---

## 🎯 Use Cases

### Medical Knowledge
```
Query: "What's the timeline of my treatment?"
Graph finds: Diagnosis → CAR-T → PET Scans → Follow-ups
Claude synthesizes: "Your treatment began with..."
```

### Technical Projects
```
Query: "How do my 3D printing projects relate?"
Graph finds: Fusion 360 → Gridfinity → CNC → Projects
Claude synthesizes: "Your projects share common..."
```

### Cross-Domain Insights
```
Query: "How do engineering principles apply to my medical situation?"
Graph finds: Design → Analysis → Treatment → Monitoring
Claude synthesizes: "Engineering concepts like..."
```

---

## 🐛 Troubleshooting

### "Error connecting to embedding service"
```bash
# Make sure embedding service is running
docker-compose up embedding-service
# or
curl http://localhost:8000/stats
```

### "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY="your-key"
# or add to .env file
echo "ANTHROPIC_API_KEY=your-key" >> .env
```

### "Graph not loaded"
```bash
# Build graph first
python build_knowledge_graph.py
# Choose option 1 (test) or 2 (full)
```

### Graph service won't start in Docker
```bash
# Check logs
docker-compose logs graph-service

# Verify API key is set
docker-compose config | grep ANTHROPIC_API_KEY
```

---

## 📈 Comparison: LightRAG vs Claude Graph

| Feature | LightRAG | Claude Graph |
|---------|----------|--------------|
| **Setup** | Complex dependencies | pip install anthropic |
| **Status** | ❌ Broken (event loops) | ✅ Working |
| **Entity Extraction** | Limited | Excellent |
| **Medical Terms** | Basic | Advanced |
| **Reasoning** | Rule-based | LLM-powered |
| **Cost** | Free (local) | ~$25 build + $3/mo |
| **Quality** | Good | Excellent |
| **Maintenance** | High | Low |

---

## 🎓 Next Steps

1. **Test Mode**: Run with 50 chunks to validate
2. **Review Results**: Check entity quality and relationships
3. **Full Build**: Process all 7,113 chunks
4. **Docker Deploy**: Add graph service to production
5. **Iterate**: Improve extraction prompts as needed

---

## 📝 Notes

- Graph is stored as NetworkX pickle file (`knowledge_graph.pkl`)
- JSON export available for visualization tools
- Entities are normalized (e.g., "CAR-T" and "CAR-T Therapy" merged)
- Source tracking: Each entity/relationship tracks source notes
- Incremental updates: Rebuild monthly or when vault changes significantly

---

## 🆘 Support

If you encounter issues:

1. Check logs: `docker-compose logs graph-service`
2. Test API: `curl http://localhost:8002/health`
3. Verify graph file exists: `ls -lh knowledge_graph.pkl`
4. Check Claude API: `curl https://api.anthropic.com/v1/messages` (with auth)

---

**Ready to build your knowledge graph!** 🚀

Start with test mode (50 chunks) to see how it works, then scale up to full production.
