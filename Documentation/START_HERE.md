# 🎯 START HERE - Your Next Steps

## 🎉 LightRAG + Docker Integration Complete!

Your Obsidian RAG system now has **dual-mode AI search**:
- 🔍 **Vector Search** (ChromaDB) - Fast semantic similarity
- 🌐 **Graph Search** (LightRAG) - Intelligent reasoning with entity relationships

---

## ⚡ Quick Start (3 Steps)

### Step 1: Set Your Vault Path

Edit `docker-compose.yml` (line 38-39):
```yaml
volumes:
  - ~/Documents/YOUR_VAULT_PATH:/app/vault:ro
```

**Or** set environment variable:
```bash
export OBSIDIAN_VAULT_PATH=~/Documents/YourVault
```

### Step 2: Start Services

```bash
./Scripts/docker_start.sh
```

This starts:
- ✅ ChromaDB vector service (port 8000)
- ✅ LightRAG graph service (port 8001)  
- ✅ Streamlit UI (port 8501)

### Step 3: Open & Use

**Access the UI**: http://localhost:8501

**Try a query**: 
- Select "vector" mode (default)
- Ask: "What topics do I write about?"

---

## 🌐 Enable Graph Search (Optional but Recommended)

After services are running:

```bash
./Scripts/index_with_lightrag.sh
```

This builds a knowledge graph from your vault (takes 5-15 minutes).

Once complete, you can use:
- **graph-local** - Understand relationships
- **graph-global** - Big picture synthesis  
- **graph-hybrid** - Best of both worlds

---

## 📊 Check Status Anytime

```bash
./Scripts/docker_status.sh
```

Shows:
- Service health
- Port status
- Database stats
- Available models

---

## 🔄 Common Commands

```bash
# Start everything
./Scripts/docker_start.sh

# Check status
./Scripts/docker_status.sh

# View logs
docker-compose logs -f

# Stop everything
./Scripts/docker_stop.sh

# Rebuild after code changes
./Scripts/docker_rebuild.sh

# Index vault for graphs
./Scripts/index_with_lightrag.sh
```

---

## 🎓 Understanding Search Modes

### 🔍 Vector (ChromaDB)
- **Speed**: ⚡ Very Fast (100-500ms)
- **Best for**: Quick lookups, finding similar notes
- **How**: Semantic similarity via embeddings
- **Example**: "Show me CAR-T side effects"

### 🌐 Graph-Naive (LightRAG)
- **Speed**: ⚡ Fast (1-3 seconds)
- **Best for**: Simple entity lookup
- **How**: Basic graph traversal
- **Example**: "When was my PET scan?"

### 📍 Graph-Local (LightRAG)
- **Speed**: 🐢 Medium (3-10 seconds)
- **Best for**: Understanding local relationships
- **How**: Entity + immediate connections
- **Example**: "How does treatment A relate to outcome B?"

### 🌍 Graph-Global (LightRAG)
- **Speed**: 🐌 Slow (10-30 seconds)
- **Best for**: Comprehensive synthesis
- **How**: Full graph reasoning
- **Example**: "Summarize my treatment journey"

### ⚡ Graph-Hybrid (LightRAG)
- **Speed**: 🐢 Medium-Slow (5-20 seconds)
- **Best for**: Best overall results
- **How**: Combines multiple strategies
- **Example**: Complex multi-part questions

---

## 🆘 Troubleshooting

### Services won't start

```bash
# Check Docker
docker info

# View logs
docker-compose logs -f

# Rebuild
./Scripts/docker_rebuild.sh
```

### Can't connect to Ollama

```bash
# Check Ollama is running
ollama list

# Start if needed
ollama serve

# Download required models
ollama pull qwen2.5-coder:32b
ollama pull nomic-embed-text
```

### Port conflicts

```bash
# Stop everything
./Scripts/docker_stop.sh

# Kill processes on ports
lsof -ti:8000 :8001 :8501 | xargs kill

# Restart
./Scripts/docker_start.sh
```

### Graph indexing fails

1. Check vault path in `docker-compose.yml`
2. Make sure path is absolute, not relative
3. Check permissions: `ls -la /path/to/vault`
4. View logs: `docker-compose logs lightrag-service`

---

## 📚 Learn More

- **Quick Start**: Read [QUICKSTART.md](./QUICKSTART.md)
- **Docker Guide**: Read [DOCKER_README.md](./DOCKER_README.md)
- **Full Details**: Read [DOCKER_SETUP_SUMMARY.md](./DOCKER_SETUP_SUMMARY.md)

---

## ✅ Checklist Before First Use

- [ ] Docker Desktop is running
- [ ] Ollama is running: `ollama list`
- [ ] Models downloaded: `qwen2.5-coder:32b`, `nomic-embed-text`
- [ ] Vault path set in `docker-compose.yml`
- [ ] Started services: `./Scripts/docker_start.sh`
- [ ] Services healthy: `./Scripts/docker_status.sh`
- [ ] UI accessible: http://localhost:8501

---

## 🎯 Your First Session

1. **Start services**: `./Scripts/docker_start.sh`
2. **Open UI**: http://localhost:8501
3. **Try vector search**: Ask any question
4. **Index for graphs**: `./Scripts/index_with_lightrag.sh` (in another terminal)
5. **Try graph modes**: Select different modes and compare results!

---

## 💡 Pro Tips

✅ **Start with vector** - It's faster for testing  
✅ **Index overnight** - LightRAG can take 10-15 min for large vaults  
✅ **Experiment** - Try different modes to see what works best  
✅ **Monitor resources** - Graph modes use more memory  
✅ **Check logs** - `docker-compose logs -f` shows real-time activity  

---

## 🎉 You're All Set!

You now have:
- ✅ Fast vector similarity search
- ✅ Intelligent knowledge graph reasoning
- ✅ Easy Docker deployment
- ✅ Unified web interface
- ✅ Multiple search strategies
- ✅ Comprehensive documentation

**Next**: Run `./Scripts/docker_start.sh` and open http://localhost:8501

🚀 **Happy searching!**


