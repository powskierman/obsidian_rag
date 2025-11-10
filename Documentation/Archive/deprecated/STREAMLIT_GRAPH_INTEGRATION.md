# 🎨 Streamlit UI - Claude Graph Integration

## ✅ What Was Added

The Streamlit UI (`streamlit_ui_docker.py`) now supports **Claude-powered knowledge graph search** alongside existing vector search!

## 🆕 New Features

### 1. New Search Mode: `graph-claude`

Added to the search mode options:
- **vector**: Fast semantic search (ChromaDB) 🔍
- **graph-claude**: Claude-powered knowledge graph (NEW) 🧠
- **graph-fast**: FastGraph entity search ⚡
- **graph-naive/local/global/hybrid**: LightRAG modes

### 2. Service Integration

- **Claude Graph Service**: `http://graph-service:8002` (configurable via `CLAUDE_GRAPH_SERVICE_URL`)
- **Health Check**: Shows graph status in sidebar
- **Auto-detection**: Checks if graph is loaded

### 3. Smart Response Handling

- **Direct Answer**: Claude graph queries return complete answers (already synthesized)
- **No Double Processing**: Skips LLM step for graph-claude (answer is ready)
- **Error Handling**: Clear messages if service unavailable

## 🚀 How to Use

### In Streamlit UI

1. **Start services**:
   ```bash
   docker-compose up -d
   ```

2. **Open UI**: http://localhost:8501

3. **Select search mode**:
   - Choose **"graph-claude"** from sidebar
   - Or use **"vector"** for traditional search

4. **Ask questions**:
   - "What treatments are mentioned in my notes?"
   - "How does CAR-T relate to lymphoma?"
   - "What are the top entities in my graph?"

### Search Mode Comparison

| Mode | Speed | Quality | Use Case |
|------|-------|---------|----------|
| **vector** | ⚡⚡⚡ Fast | ⭐⭐⭐ Good | Keyword/content search |
| **graph-claude** | ⚡⚡ Medium | ⭐⭐⭐⭐⭐ Excellent | Relationship discovery, reasoning |

## 🔧 Configuration

### Environment Variables

```bash
# In docker-compose.yml or .env
CLAUDE_GRAPH_SERVICE_URL=http://graph-service:8002
ANTHROPIC_API_KEY=sk-ant-...
```

### Service URLs

The UI automatically detects:
- **Embedding Service**: `http://embedding-service:8000` (vector search)
- **Claude Graph Service**: `http://graph-service:8002` (graph search)
- **LightRAG Service**: `http://localhost:8001` (alternative graph)
- **FastGraph Service**: `http://localhost:8007` (fast entity search)

## 📊 Sidebar Status

The sidebar now shows:
- ✅ **Claude Graph**: X entities, Y relationships (if loaded)
- ⚠️ **Claude Graph**: Not loaded (if graph not built)
- ⚠️ **Claude Graph**: Offline (if service not running)

## 💡 Example Queries

### Vector Search (Fast)
```
"What notes mention 3D printing?"
"Show me documents about Fusion 360"
```

### Graph Search (Reasoning)
```
"How are my medical notes connected to technical projects?"
"What's the relationship between CAR-T and lymphoma?"
"What entities are most central in my knowledge base?"
```

## 🎯 How It Works

### Vector Search Flow
```
User Query
  ↓
ChromaDB Search (finds relevant chunks)
  ↓
LLM Synthesis (Ollama/Claude)
  ↓
Answer
```

### Graph Search Flow
```
User Query
  ↓
Claude Graph Service (finds entities + relationships)
  ↓
Claude Reasoning (synthesizes answer)
  ↓
Answer (already complete!)
```

## 🔄 Switching Between Modes

You can switch search modes **without restarting**:
1. Change mode in sidebar
2. Ask new question
3. Get results from selected mode

## 🐛 Troubleshooting

### "Claude Graph: Offline"
```bash
# Start graph service
docker-compose up -d graph-service

# Or check if it's running
docker ps | grep graph-service
```

### "Claude Graph: Not loaded"
```bash
# Build graph first
python build_knowledge_graph.py
# Choose option 2 (full build)

# Then copy to service location
cp knowledge_graph_full.pkl knowledge_graph.pkl
```

### "Cannot connect to Claude Graph service"
- Check service is running: `docker-compose ps`
- Check service URL in docker-compose.yml
- Verify port 8002 is accessible

## 📝 Code Changes Summary

1. **Added Claude Graph Service URL** (line 17)
2. **Added `graph-claude` to search modes** (line 60)
3. **Added health check** (lines 119-133)
4. **Added graph query handler** (lines 310-351)
5. **Smart response handling** (lines 442-445)

## 🎉 Benefits

- ✅ **Two search options**: Vector (fast) or Graph (reasoning)
- ✅ **Easy switching**: Change mode in sidebar
- ✅ **No code changes needed**: Just select mode
- ✅ **Clear status**: See which services are available
- ✅ **Error handling**: Helpful messages if services unavailable

---

**The UI is now ready to use both vector and graph search!** 🚀

Just select your preferred mode in the sidebar and start querying!

