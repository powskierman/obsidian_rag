# Starting Required Services for MCP

## Quick Start

Your unified MCP server requires the **embedding service** to be running for semantic search.

### Start Embedding Service

```bash
cd /Users/michel/Library/Mobile\ Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag
docker-compose up -d embedding-service
```

### Verify It's Running

```bash
# Check service status
docker ps | grep obsidian-embedding

# Test health endpoint
curl http://localhost:8000/health

# Check logs if needed
docker-compose logs embedding-service
```

## All Services

### Embedding Service (Required for Search)

```bash
docker-compose up -d embedding-service
```

**Port:** 8000  
**Purpose:** Semantic search via ChromaDB

### Graph Service (Optional, for Knowledge Graph)

```bash
docker-compose up -d graph-service
```

**Port:** 8002  
**Purpose:** Knowledge graph queries

### Start All Services

```bash
docker-compose up -d
```

## Service Status Check

```bash
# Quick status
docker-compose ps

# Detailed status
docker ps --filter "name=obsidian" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## Troubleshooting

### Service Won't Start

1. **Check Docker is running:**
   ```bash
   docker ps
   ```

2. **Check for port conflicts:**
   ```bash
   lsof -i :8000  # Embedding service
   lsof -i :8002  # Graph service
   ```

3. **View logs:**
   ```bash
   docker-compose logs embedding-service
   ```

### Service Starts But Can't Connect

1. **Check service is healthy:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Verify MCP server config:**
   - `EMBEDDING_SERVICE_URL=http://localhost:8000`
   - Service must be accessible from where MCP server runs

3. **Test from MCP server location:**
   ```bash
   # If MCP server runs in Docker, use:
   # EMBEDDING_SERVICE_URL=http://host.docker.internal:8000
   ```

## Auto-Start on Boot

To start services automatically:

```bash
# Add to your shell profile (~/.zshrc or ~/.bashrc)
alias start-rag-services='cd /Users/michel/Library/Mobile\ Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag && docker-compose up -d'
```

Or use Docker's restart policy (already set to `unless-stopped` in docker-compose.yml).

## Quick Reference

| Service | Port | Required For | Start Command |
|---------|------|--------------|---------------|
| embedding-service | 8000 | Semantic search | `docker-compose up -d embedding-service` |
| graph-service | 8002 | Knowledge graph | `docker-compose up -d graph-service` |
| streamlit-ui | 8501 | Web UI | `docker-compose up -d streamlit-ui` |

