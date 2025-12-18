# GraphRAG Setup Guide

## Overview

This setup provides **Microsoft GraphRAG** as a stable alternative to LightRAG for knowledge graph-based retrieval. GraphRAG offers better async handling and more reliable performance.

## Quick Start

### 1. Choose Graph Service

```bash
# Use GraphRAG (recommended)
export GRAPH_SERVICE=graphrag
docker-compose --profile graphrag up -d

# Or use LightRAG (legacy)
export GRAPH_SERVICE=lightrag
docker-compose --profile lightrag up -d
```

### 2. Access Services

- **Streamlit UI**: http://localhost:8501
- **Vector Search**: http://localhost:8000
- **GraphRAG Service**: http://localhost:8002 (when using GraphRAG profile)
- **LightRAG Service**: http://localhost:8001 (when using LightRAG profile)

## GraphRAG Advantages

✅ **Stable async processing** - No event loop errors
✅ **Better medical domain support** - Optimized entity extraction
✅ **Reliable indexing** - Proper pipeline handling
✅ **Production ready** - Microsoft-maintained
✅ **Enhanced query modes** - Global & Local search patterns

## Usage

### Initial Setup

1. **Start GraphRAG service**:
   ```bash
   docker-compose --profile graphrag up -d
   ```

2. **Index your vault** (via Streamlit UI):
   - Click "🔄 Index Vault for Graph" in the sidebar
   - Or use API: `POST http://localhost:8002/index-vault`

3. **Query your knowledge**:
   - Use graph-global or graph-local modes in Streamlit
   - Should now work properly with your personal vault content

### API Endpoints

#### GraphRAG Service (Port 8002)

- `GET /health` - Service health check
- `GET /stats` - Database statistics
- `POST /index-vault` - Index Obsidian vault
- `POST /build-index` - Build knowledge graph index
- `POST /query` - Query knowledge graph
  ```json
  {
    "query": "How has my lymphoma treatment evolved?",
    "mode": "global"  // or "local"
  }
  ```

### Switching Between Services

#### Use GraphRAG (recommended):
```bash
docker-compose --profile graphrag up -d
```

#### Use LightRAG (if needed):
```bash
docker-compose --profile lightrag up -d
```

#### Switch services:
```bash
# Stop current
docker-compose down

# Start different service
docker-compose --profile graphrag up -d
# or
docker-compose --profile lightrag up -d
```

## Configuration

### Model Settings

Edit `.env` file:
```bash
GRAPH_SERVICE=graphrag
LLM_MODEL=qwen2.5-coder:14b
EMBED_MODEL=nomic-embed-text
```

### GraphRAG Configuration

The service automatically creates optimized settings in `./graphrag_db/settings.yaml` with:

- **Medical entity types**: person, organization, medical_condition, treatment, medication, procedure
- **Ollama integration**: Direct connection to your local Ollama instance
- **Optimized chunking**: 1200 chars with 100 char overlap
- **Enhanced claims**: Medical fact extraction enabled

## Troubleshooting

### GraphRAG Issues

1. **"GraphRAG not installed"**:
   ```bash
   docker-compose build --no-cache graphrag-service
   ```

2. **Indexing fails**:
   - Check Ollama is running: `curl http://localhost:11434/api/tags`
   - Verify vault mount: `docker exec obsidian-graphrag ls /app/vault`
   - Check logs: `docker logs obsidian-graphrag`

3. **Query errors**:
   - Ensure indexing completed: Check for `.parquet` files
   - Try manual index: `POST /build-index`

### Performance

- **GraphRAG**: Slower initial indexing, faster queries
- **Memory usage**: ~2-3GB during indexing, ~500MB runtime
- **Recommended**: Use 14B models for best performance balance

## Comparison: GraphRAG vs LightRAG

| Feature | GraphRAG | LightRAG |
|---------|----------|----------|
| **Stability** | ✅ Production ready | ⚠️ Event loop issues |
| **Medical domain** | ✅ Optimized | ⚡ Basic |
| **Async handling** | ✅ Proper | ❌ Problematic |
| **Query reliability** | ✅ Consistent | ❌ Inconsistent |
| **Setup complexity** | ⚡ Moderate | ✅ Simple |
| **Performance** | ⚡ Good | ✅ Fast |

## Next Steps

1. **Test GraphRAG** with your lymphoma timeline query
2. **Compare results** between vector and graph modes
3. **Use graph-global** for comprehensive analysis
4. **Use graph-local** for specific entity exploration

GraphRAG should resolve the "can't access your notes" issue and provide proper access to your vault content.