# GraphRAG Implementation Summary

## ✅ What Was Implemented

A functional GraphRAG (Microsoft GraphRAG) service integrated into your Obsidian RAG system.

### 1. Unified GraphRAG Service (`graphrag_unified_service.py`)
- **Full Ollama Integration**: Uses `graphrag_local_patch.py` to replace OpenAI API calls with Ollama
- **CLI-based Indexing**: Uses Microsoft GraphRAG CLI for reliable indexing
- **Two Query Modes**:
  - `local`: Entity-focused search (faster, 1-3 minutes)
  - `global`: Community-based analysis (slower, 5-15 minutes)
- **Proper Error Handling**: Clear error messages and graceful fallbacks
- **Health Checks**: Comprehensive status endpoints

### 2. Docker Integration
- **Updated Dockerfile.graphrag**: Uses unified service with proper dependencies
- **Updated docker-compose.yml**: 
  - GraphRAG service on port 8002
  - Proper volume mounts with `:cached` for iCloud Drive compatibility
  - Profile-based activation (`--profile graphrag`)

### 3. Streamlit UI Integration
- **New Search Modes**: Added `graphrag-local` and `graphrag-global` options
- **Service Status**: Shows GraphRAG index status in sidebar
- **Index Button**: One-click vault indexing from UI
- **Error Handling**: Clear messages when index not found or service unavailable

### 4. Helper Scripts
- **start_graphrag.sh**: Easy script to start GraphRAG service

## 🚀 How to Use

### Start GraphRAG Service

```bash
# Start with Docker Compose profile
docker-compose --profile graphrag up -d graphrag-service

# Or use the helper script
./Scripts/start_graphrag.sh
```

### Index Your Vault

**Option 1: Via Streamlit UI**
1. Open http://localhost:8501
2. In sidebar, click "🔄 Index Vault for GraphRAG"
3. Wait 10-30 minutes (depending on vault size)

**Option 2: Via API**
```bash
curl -X POST http://localhost:8002/index-vault \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Query GraphRAG

**Via Streamlit UI:**
1. Select `graphrag-local` or `graphrag-global` search mode
2. Enter your query
3. Get results based on knowledge graph analysis

**Via API:**
```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How has my lymphoma treatment evolved?",
    "mode": "global"
  }'
```

## 📊 Service Endpoints

- `GET /health` - Service health check
- `GET /stats` - Database statistics and index status
- `POST /index-vault` - Index Obsidian vault (auto-builds graph)
- `POST /build-index` - Build index from prepared input files
- `POST /query` - Query knowledge graph (local or global mode)

## 🔍 Search Mode Comparison

| Mode | Speed | Best For | Example |
|------|-------|----------|---------|
| **vector** | ⚡⚡⚡ Very Fast | Quick lookups | "What are CAR-T side effects?" |
| **graphrag-local** | ⚡⚡ Fast (1-3min) | Entity relationships | "How does ESP32 relate to Home Assistant?" |
| **graphrag-global** | 🐌 Slow (5-15min) | Comprehensive analysis | "Summarize my treatment journey" |
| **graph-naive/local** | ⚡⚡ Fast | LightRAG entity search | "When was my PET scan?" |

## ⚙️ Configuration

### Environment Variables

```bash
GRAPHRAG_DIR=./graphrag_db          # Working directory
OLLAMA_HOST=http://host.docker.internal:11434
LLM_MODEL=qwen2.5-coder:14b         # LLM for graph operations
EMBED_MODEL=nomic-embed-text        # Embedding model
VAULT_PATH=/app/vault               # Path to Obsidian vault
```

### Settings File

GraphRAG automatically creates `graphrag_db/settings.yaml` with:
- Ollama API configuration
- Medical entity types (medical_condition, treatment, medication, procedure)
- Optimized chunking (1200 chars, 100 overlap)

## 🐛 Troubleshooting

### Service Not Starting
```bash
# Check logs
docker logs obsidian-graphrag

# Rebuild container
docker-compose --profile graphrag build --no-cache graphrag-service
docker-compose --profile graphrag up -d graphrag-service
```

### Indexing Fails
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Verify vault mount
docker exec obsidian-graphrag ls /app/vault

# Check input files
docker exec obsidian-graphrag ls /app/graphrag_db/input
```

### Query Returns Empty
- Ensure indexing completed successfully
- Check for `.parquet` files: `ls graphrag_db/output/*.parquet`
- Try re-indexing with fewer files first
- Use `graphrag-local` mode for faster results

## 📝 Notes

- **Indexing Time**: First indexing takes 10-30 minutes for large vaults
- **Memory Usage**: ~2-3GB during indexing, ~500MB runtime
- **Model Recommendations**: Use 14B models for best performance balance
- **Cloud Drive**: Uses `:cached` volume mounts to prevent iCloud sync issues

## 🎯 Next Steps

1. **Start the service**: `docker-compose --profile graphrag up -d graphrag-service`
2. **Index your vault**: Use the UI button or API endpoint
3. **Test queries**: Try both `graphrag-local` and `graphrag-global` modes
4. **Compare results**: See how GraphRAG differs from vector search

GraphRAG provides deeper analysis by understanding entity relationships and community structures in your knowledge base, making it ideal for complex queries that require understanding connections between concepts.



