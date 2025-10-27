# 🚀 Obsidian RAG - Quick Start Guide

Get up and running with LightRAG + ChromaDB in 5 minutes!

## ⚡ Super Quick Start (Docker)

### 1️⃣ Prerequisites
```bash
# Make sure these are running:
docker --version        # Docker Desktop
ollama list            # Ollama with models
```

### 2️⃣ Configure Vault Path
```bash
# Edit docker-compose.yml line 38-39, change:
- ~/Documents/ObsidianVault:/app/vault:ro

# To your actual vault path:
- /Users/michel/Documents/YourVault:/app/vault:ro
```

### 3️⃣ Start Everything
```bash
./Scripts/docker_start.sh
```

### 4️⃣ Access UI
Open: http://localhost:8501

### 5️⃣ Index for Graph Search (Optional)
```bash
./Scripts/index_with_lightrag.sh
```

Done! 🎉

---

## 🎯 Choose Your Setup Method

### Option A: Docker (Recommended)
**Best for**: Easy setup, isolated environment

```bash
# Start
./Scripts/docker_start.sh

# Check status
./Scripts/docker_status.sh

# Stop
./Scripts/docker_stop.sh
```

**Pros**: 
- ✅ One-command setup
- ✅ Clean isolation
- ✅ Easy updates

**Cons**:
- ⚠️ Slightly more resource usage
- ⚠️ Requires Docker Desktop

### Option B: Native (Advanced)
**Best for**: Maximum performance, development

```bash
# Install dependencies
pip install flask streamlit chromadb sentence-transformers watchdog requests torch

# Start services
./Scripts/start_obsidian_rag.sh

# Check status
./Scripts/check_status.sh

# Stop
./Scripts/stop_obsidian_rag.sh
```

**Pros**:
- ✅ Slightly faster
- ✅ Direct access to logs
- ✅ Easier debugging

**Cons**:
- ⚠️ Manual dependency management
- ⚠️ System-wide installations

---

## 🔍 Search Modes Explained

### 🔍 Vector Search (Default)
- **When**: Quick lookups, general questions
- **Speed**: ⚡ Very Fast
- **Example**: "What are CAR-T side effects?"

### 🌐 Graph-Naive
- **When**: Simple fact finding
- **Speed**: ⚡ Fast  
- **Example**: "When was my PET scan?"

### 📍 Graph-Local
- **When**: Understanding relationships
- **Speed**: 🐢 Medium
- **Example**: "How does treatment A relate to outcome B?"

### 🌍 Graph-Global
- **When**: Big picture synthesis
- **Speed**: 🐌 Slow
- **Example**: "Summarize my entire treatment journey"

### ⚡ Graph-Hybrid
- **When**: Best possible answer
- **Speed**: 🐢 Medium-Slow
- **Example**: Complex multi-part questions

---

## 🆘 Troubleshooting

### Services won't start

**Docker**:
```bash
docker info  # Check Docker is running
./Scripts/docker_rebuild.sh  # Rebuild if needed
```

**Native**:
```bash
./Scripts/stop_obsidian_rag.sh  # Stop old processes
./Scripts/start_obsidian_rag.sh  # Restart
```

### "Embedding service error"

1. Check service is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check logs:
   ```bash
   # Docker
   docker-compose logs embedding-service
   
   # Native
   tail -f embedding_service.log
   ```

### Ollama not found

```bash
# Start Ollama
ollama serve

# Check it's running
curl http://localhost:11434/api/tags

# Download required models
ollama pull qwen2.5-coder:32b
ollama pull nomic-embed-text
```

### Port already in use

**Docker**:
```bash
# Stop everything
docker-compose down

# Check what's using ports
lsof -i :8000 :8001 :8501

# Change ports in docker-compose.yml if needed
```

**Native**:
```bash
# Stop services
./Scripts/stop_obsidian_rag.sh

# Kill specific port
lsof -ti:8000 | xargs kill
```

---

## 💡 Usage Tips

### Best Practices

1. **Start with vector search** - Fast and accurate for most queries
2. **Use graph-local** - For understanding connections between concepts  
3. **Save graph-global** - For when you really need comprehensive synthesis
4. **Experiment** - Try different modes to see what works best!

### Example Queries

**Medical Questions**:
```
- "What are the side effects mentioned in my CAR-T notes?"
- "When is my next appointment?"
- "How did my PET scan results change over time?"
```

**Technical Questions**:
```
- "How do I configure the Raspberry Pi camera?"
- "What 3D printing issues have I encountered?"
- "Show me my Fusion 360 tips"
```

**Synthesis Questions** (use graph modes):
```
- "What's the relationship between my treatment and outcomes?"
- "Summarize my health journey from diagnosis to now"
- "How do my technical projects relate to each other?"
```

---

## 📚 What's Next?

### For Docker Users:
1. ✅ Services are running at http://localhost:8501
2. ✅ Try vector search first
3. ✅ Index with LightRAG: `./Scripts/index_with_lightrag.sh`
4. ✅ Try graph modes for deeper insights

### For Native Users:
1. ✅ Services are running at http://localhost:8501  
2. ✅ Monitor with: `./Scripts/check_status.sh`
3. ✅ View logs: `tail -f *.log`

### Advanced Setup:
- 📖 Read [DOCKER_README.md](./DOCKER_README.md) for detailed configuration
- 🔧 Customize models in `docker-compose.yml` or startup scripts
- 📊 Monitor performance with `./Scripts/docker_status.sh`

---

## 🎓 Learning Resources

### Understanding the Components

**ChromaDB (Vector Search)**:
- Stores document embeddings
- Fast semantic similarity
- Good for finding similar content

**LightRAG (Knowledge Graph)**:
- Extracts entities and relationships
- Understands context and connections
- Better for reasoning and synthesis

**Ollama**:
- Runs LLMs locally
- Generates responses
- Creates embeddings

### Architecture
```
Your Query → [Vector OR Graph Search] → Context → Ollama → Response
```

---

## ✅ Checklist

Before asking for help, verify:

- [ ] Docker Desktop is running (Docker method)
- [ ] Ollama is running: `ollama list`
- [ ] Models are downloaded: `qwen2.5-coder:32b`, `nomic-embed-text`
- [ ] Services are healthy: `./Scripts/docker_status.sh` or `./Scripts/check_status.sh`
- [ ] Vault path is correct in `docker-compose.yml` or as mounted
- [ ] Ports 8000, 8001, 8501 are available

---

## 🎉 You're Ready!

Open http://localhost:8501 and start exploring your knowledge base!

**First Query Suggestions**:
- "What topics do I write about most?"
- "Show me recent notes"
- "Summarize my [project/health/topic] notes"





