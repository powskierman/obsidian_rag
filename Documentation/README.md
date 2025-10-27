# 🔍 Obsidian RAG System

*A production-ready, privacy-first RAG (Retrieval-Augmented Generation) system for searching your Obsidian vault using dual-mode AI search: Vector Search (ChromaDB) and Knowledge Graph Search (LightRAG).*

---

## 🎯 What This Does

- **🔍 Vector Search** - Fast semantic similarity search using ChromaDB
- **🌐 Graph Search** - Intelligent knowledge graph reasoning using LightRAG
- **🐳 Docker Integration** - One-command deployment with Docker Compose
- **💻 Native Deployment** - Direct execution for maximum performance
- **📊 Multiple Search Modes** - 5 different search strategies for different needs
- **🔒 100% Local** - Your data never leaves your machine

---

## ⚡ Quick Start (3 Steps)

### Prerequisites
- Docker Desktop installed and running
- Ollama installed with models
- macOS (this guide assumes Apple Silicon)

### 1️⃣ Configure Vault Path

Edit `docker-compose.yml` line 35:
```yaml
- "/Users/yourname/path/to/vault:/app/vault:ro"
```

### 2️⃣ Start Services
```bash
./Scripts/docker_start.sh
```

### 3️⃣ Access UI
Open http://localhost:8501 in your browser

**Done!** 🎉

---

## 🔍 Understanding Search Modes

| Mode | Speed | Best For | Example Query |
|------|-------|----------|---------------|
| **Vector** | ⚡⚡⚡ Very Fast (100-500ms) | Quick lookups, finding similar content | "What are CAR-T side effects?" |
| **Graph-Naive** | ⚡⚡ Fast (1-3s) | Simple entity lookup | "When was my PET scan?" |
| **Graph-Local** | ⚡ Medium (3-10s) | Understanding relationships | "How does treatment A relate to outcome B?" |
| **Graph-Global** | 🐌 Slow (10-30s) | Comprehensive synthesis | "Summarize my treatment journey" |
| **Graph-Hybrid** | 🐢 Medium-Slow (5-20s) | Best overall results | Complex multi-part questions |

### When to Use Each Mode

**Vector (Default)**: Start here! Best for most queries.
- Quick answers
- Finding specific information
- Content similarity search

**Graph-Naive**: Simple fact finding
- Entity lookups
- Date/time questions
- Property queries

**Graph-Local**: Understanding connections
- Relationship questions
- "How does X relate to Y?"
- Exploring local context

**Graph-Global**: Comprehensive answers
- High-level summaries
- Big picture understanding
- Multiple related topics

**Graph-Hybrid**: Best possible answer
- Complex questions
- When accuracy > speed
- Multi-part queries

---

## 🐳 Docker Deployment (Recommended)

### Overview
Docker Compose orchestrates three services:
1. **Embedding Service** (ChromaDB) - Port 8000
2. **LightRAG Service** - Port 8001  
3. **Streamlit UI** - Port 8501

### Quick Commands
```bash
# Start everything
./Scripts/docker_start.sh

# Check status
./Scripts/docker_status.sh

# View logs
docker-compose logs -f

# Stop everything
./Scripts/docker_stop.sh

# Rebuild after changes
./Scripts/docker_rebuild.sh

# Index vault for graph search
./Scripts/index_with_lightrag.sh
```

### Architecture
```
┌─────────────────────────────────────────────────┐
│         Browser (localhost:8501)                │
└───────────────────┬─────────────────────────────┘
                    │
        ┌───────────▼──────────────┐
        │   Streamlit UI           │
        │   - Mode selector        │
        │   - Chat interface       │
        │   - Source display       │
        └──────┬──────────┬────────┘
               │          │
    ┌──────────▼───┐  ┌──▼─────────────┐
    │ Embedding    │  │ LightRAG       │
    │ Service      │  │ Service        │
    │ (ChromaDB)   │  │ (Graph)        │
    │ :8000        │  │ :8001          │
    └──────┬───────┘  └───┬────────────┘
           │              │
           └──────┬───────┘
                  │
         ┌────────▼────────────┐
         │ Ollama (Host)       │
         │ :11434              │
         └─────────────────────┘
```

---

## 🎮 Common Usage

### Daily Startup
```bash
./Scripts/docker_start.sh
# Open http://localhost:8501
```

### Checking Status
```bash
./Scripts/docker_status.sh
```

### First-Time Graph Indexing
```bash
./Scripts/index_with_lightrag.sh
# Takes 1-3 hours depending on vault size
```

### Viewing Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs embedding-service
docker-compose logs lightrag-service
```

---

## 🤖 Model Selection

### Recommended: Claude Haiku 3.5 (API)
**Best value for money**
- Cost: ~$1-2 for 1600 notes
- Time: ~1 hour
- Quality: Excellent
- RAM: 0GB (cloud processing)

### Alternative: Qwen2.5:7b (Local)
**Best free option**
- Cost: Free
- Time: 2-3 hours
- Quality: Very good
- RAM: 8GB

### Default: Llama3.2:3b (Local)
**Fast & free (pre-configured)**
- Cost: Free
- Time: 1-2 hours
- Quality: Good
- RAM: 5GB

See [QUICKSTART_MODELS.md](./QUICKSTART_MODELS.md) for detailed comparison.

---

## 🆘 Troubleshooting

### Services Won't Start

```bash
# Check Docker is running
docker info

# Check for port conflicts
lsof -i :8000 :8001 :8501

# View logs for errors
docker-compose logs -f

# Rebuild from scratch
./Scripts/docker_rebuild.sh
```

### Can't Connect to Ollama

```bash
# Check Ollama is running
ollama list

# Start Ollama if needed
ollama serve

# Download required models
ollama pull qwen2.5-coder:32b
ollama pull nomic-embed-text
```

### Port Already in Use

```bash
# Stop all services
./Scripts/docker_stop.sh

# Kill specific processes
lsof -ti:8000 :8001 :8501 | xargs kill

# Restart
./Scripts/docker_start.sh
```

### Graph Indexing Fails

1. Check vault path in `docker-compose.yml`
2. Ensure path is **absolute**, not relative
3. Check permissions: `ls -la /path/to/vault`
4. View logs: `docker-compose logs lightrag-service`

### Slow Responses

**Solutions:**
- Reduce number of sources (10 → 5 → 3)
- Disable re-ranking temporarily
- Switch to faster model (e.g., `llama3.2:3b`)
- Close other applications to free RAM

### Out of Memory

**Solutions:**
- Use smaller model: `llama3.2:3b` instead of `32b`
- Reduce `num_ctx` in code
- Reduce number of sources
- Increase Docker RAM allocation

---

## 📚 Documentation

### Quick Start Guides
- **[START_HERE.md](./START_HERE.md)** - Your first steps
- **[QUICKSTART.md](./QUICKSTART.md)** - 5-minute setup guide
- **[QUICKSTART_MODELS.md](./QUICKSTART_MODELS.md)** - Model selection guide

### Technical Guides
- **[DOCKER_SETUP_SUMMARY.md](./DOCKER_SETUP_SUMMARY.md)** - Docker integration details
- **[MODEL_GUIDE.md](./MODEL_GUIDE.md)** - Detailed model comparison

### Organization Guides
- **[VAULT_ORGANIZATION_GUIDE.md](./VAULT_ORGANIZATION_GUIDE.md)** - Vault organization
- **[MCP_INTEGRATION_GUIDE.md](./MCP_INTEGRATION_GUIDE.md)** - MCP setup (advanced)

---

## 🎓 Understanding the Components

### ChromaDB (Vector Search)
- **What**: Stores document embeddings for semantic search
- **Pros**: Very fast, scales well, low memory
- **Best for**: Similarity search, quick lookups
- **Speed**: 100-500ms

### LightRAG (Knowledge Graph)
- **What**: Extracts entities and relationships from content
- **Pros**: Understands context, multi-hop reasoning
- **Best for**: Complex queries, synthesis, relationships
- **Speed**: 2-30 seconds (mode dependent)

### Ollama
- **What**: Local LLM runtime
- **Models**: Qwen, Llama, etc.
- **Role**: Generates responses and embeddings
- **Interface**: http://localhost:11434

---

## 💡 Best Practices

### Query Tips
1. **Start with vector search** - Fastest for testing
2. **Use graph modes for relationships** - When you need context
3. **Be specific** - "What are the side effects?" > "Tell me things"
4. **Use keywords** - Helps with both vector and graph search
5. **Follow up questions** - System remembers context

### Indexing Tips
1. **Index overnight first time** - Takes 1-3 hours
2. **Re-index after major vault changes** - Keeps graph current
3. **Monitor resources** - Graph modes use more memory
4. **Use appropriate model** - Balance quality vs speed

### Performance Tips
1. **Vector search for speed** - When fast response matters
2. **Graph search for depth** - When understanding matters
3. **Monitor logs** - `docker-compose logs -f` shows activity
4. **Close unused apps** - Frees RAM for AI processing

---

## 📂 Project Structure

```
obsidian_rag/
├── docker-compose.yml           # Service orchestration
├── Dockerfile.*                 # Individual service Dockerfiles
├── embedding_service.py         # Vector search API
├── lightrag_service.py          # Graph search API
├── streamlit_ui_docker.py      # Main UI
├── requirements.txt            # Dependencies
│
├── Scripts/
│   ├── docker_start.sh         # Start Docker services
│   ├── docker_stop.sh          # Stop services
│   ├── docker_status.sh        # Check health
│   ├── docker_rebuild.sh       # Rebuild images
│   ├── index_with_lightrag.sh  # Index vault
│   ├── start_obsidian_rag.sh    # Native start
│   └── check_status.sh          # Status check
│
├── chroma_db/                   # Vector database
├── lightrag_db/                 # Knowledge graph
└── Documentation/               # Guides and docs
```

---

## 🔧 Configuration

### Environment Variables
Set in `docker-compose.yml` or as environment variables:

```bash
# Vault path (required for LightRAG)
OBSIDIAN_VAULT_PATH=/path/to/vault

# Ollama configuration
OLLAMA_HOST=http://host.docker.internal:11434

# Model selection
LLM_MODEL=qwen2.5-coder:32b
EMBED_MODEL=nomic-embed-text

# Service ports
EMBEDDING_PORT=8000
LIGHTRAG_PORT=8001
STREAMLIT_PORT=8501
```

### Changing Models

**Quick model switch:**
```bash
export LLM_MODEL=llama3.2:3b
./Scripts/docker_rebuild.sh
```

**Available models:**
- `qwen2.5-coder:32b` - Best quality, high RAM
- `qwen2.5:7b` - Balanced, moderate RAM
- `llama3.2:3b` - Fastest, low RAM
- Custom Ollama models

---

## ✅ Checklist

Before starting, verify:

- [ ] Docker Desktop is running
- [ ] Ollama is running: `ollama list`
- [ ] Models downloaded (check `ollama list`)
- [ ] Vault path set in `docker-compose.yml`
- [ ] Ports 8000, 8001, 8501 are available
- [ ] At least 8GB RAM available
- [ ] Internet connection (for model downloads)

---

## 🎉 You're Ready!

Your Obsidian RAG system is ready to use!

**First Query Suggestions:**
- "What topics do I write about most?"
- "Show me my recent notes"
- "Summarize my health journey"
- "What are my Home Assistant automations?"

**Access the UI**: http://localhost:8501

---

## 📖 Additional Resources

- **LightRAG GitHub**: https://github.com/HKUDS/LightRAG
- **ChromaDB Docs**: https://docs.trychroma.com/
- **Ollama Models**: https://ollama.ai/library
- **Docker Compose**: https://docs.docker.com/compose/

---

## 🤝 Getting Help

### Check Logs
```bash
docker-compose logs -f
```

### Check Service Health
```bash
./Scripts/docker_status.sh
```

### Review Documentation
- Start with [START_HERE.md](./START_HERE.md)
- See [QUICKSTART.md](./QUICKSTART.md) for quick setup
- Refer to [DOCKER_SETUP_SUMMARY.md](./DOCKER_SETUP_SUMMARY.md) for details

---

## 📝 License

This project is designed for personal use with your own Obsidian vault.

---

**Last Updated**: January 2025  
**Version**: 1.0.0  
**Status**: Production Ready ✅

