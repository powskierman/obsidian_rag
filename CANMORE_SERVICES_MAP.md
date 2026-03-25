# Canmore Services Access Map

Quick reference for all services running on Canmore and how to access them.

## 🌐 Network Information

### Canmore Interfaces
```
Hostname:      canmore
LAN IP:        192.168.2.195
Tailscale IP:  100.110.65.38
Localhost:     127.0.0.1
```

### From MacBook
- **Same Network**: Use `192.168.2.195` or `canmore.local`
- **Remote (Tailscale)**: Use `100.110.65.38` or `canmore`

## 🚀 Running Services

| Service | Port | Local URL | Tailscale URL | Status |
|---------|------|-----------|---------------|--------|
| **MCP Server** | 8811 | http://localhost:8811 | http://100.110.65.38:8811 | ✅ Running |
| **API Gateway** | 4000 | http://localhost:4000 | http://100.110.65.38:4000 | ✅ Running |
| **Web UI** | 3030 | http://localhost:3030 | http://100.110.65.38:3030 | ✅ Running |
| **Streamlit UI** | 8501 | http://localhost:8501 | http://100.110.65.38:8501 | ✅ Running |
| Embedding Service | 8000 | http://localhost:8000 | http://100.110.65.38:8000 | ✅ Running |
| Graph Service | 8002 | http://localhost:8002 | http://100.110.65.38:8002 | ✅ Running |
| LightRAG Service | 8001 | http://localhost:8001 | http://100.110.65.38:8001 | ✅ Running |

## 🔗 MCP Server Endpoints

### Main Endpoints
```
Health Check:  http://100.110.65.38:8811/health
MCP Endpoint:  http://100.110.65.38:8811/mcp
```

### Configuration
```yaml
Transport:  HTTP
Host:       0.0.0.0 (all interfaces)
Port:       8811
Path:       /mcp
```

### Available Tools
- `search_vault` - Search vault with embeddings
- `search_vault_full` - Search and retrieve full notes
- `read_note` - Read a specific note
- `create_note` - Create a new note
- `query_graph` - Query knowledge graph
- `deep_research` - Deep research mode
- And more...

## 📱 Web Interfaces

### Main Web UI (Next.js)
```
http://100.110.65.38:3030
```

Features:
- Search interface
- Query modes (vector, cascading, deep-research)
- Source display with Obsidian links
- Real-time streaming

### Streamlit UI (Alternative)
```
http://100.110.65.38:8501
```

Features:
- Simple query interface
- Graph visualization
- Index management

## 🔧 API Gateway

### Base URL
```
http://100.110.65.38:4000
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/query` | POST | Unified query endpoint |
| `/api/v1/stats` | GET | System statistics |

### Example Query
```bash
curl -X POST http://100.110.65.38:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are my notes about AI?",
    "mode": "cascading"
  }'
```

## 🗄️ Data Locations

### On Canmore
```
Vault:           /Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel
Data Directory:  /Users/michel/obsidian_rag_local_data
Project:         /Users/michel/dev/obsidian_rag
```

### In Docker Containers
```
Vault:           /app/vault
Graph Data:      /app/graph_data
Chroma DB:       /app/chroma_db
LightRAG DB:     /app/lightrag_db
```

## 🔐 Authentication

Currently no authentication required for local/Tailscale access.

Optional: Set `MCP_HTTP_API_KEY` to require API key authentication.

## 📊 Health Checks

### Quick Status Check
```bash
# All services
docker ps

# MCP Server
curl http://100.110.65.38:8811/health
# Returns: ok

# API Gateway
curl http://100.110.65.38:4000/api/v1/health
# Returns: {"status":"healthy","timestamp":"..."}

# All at once
for port in 8811 4000 3030 8501 8000 8001 8002; do
  echo "Port $port:"
  curl -s http://100.110.65.38:$port/health || echo "N/A"
done
```

## 🖥️ Client Configuration

### Claude Desktop (MacBook)
Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "obsidian-rag": {
      "transport": {
        "type": "http",
        "url": "http://100.110.65.38:8811/mcp"
      }
    }
  }
}
```

### Test from Command Line
```bash
# List available tools
curl -X POST http://100.110.65.38:8811/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# Search vault
curl -X POST http://100.110.65.38:8811/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"search_vault",
      "arguments":{"query":"test"}
    }
  }'
```

## 🔄 Starting/Stopping Services

### All Services
```bash
cd /Users/michel/dev/obsidian_rag

# Start
docker-compose up -d

# Stop
docker-compose down

# Restart specific service
docker-compose restart mcp-unified

# View logs
docker-compose logs -f mcp-unified
```

### Individual Services
```bash
# Restart MCP
docker restart obsidian-mcp-unified

# View MCP logs
docker logs obsidian-mcp-unified -f

# Check MCP status
docker ps | grep mcp
```

## 🐛 Troubleshooting

### Service Not Responding
```bash
# Check if running
docker ps | grep obsidian

# Check logs
docker logs obsidian-mcp-unified --tail 50

# Restart
docker restart obsidian-mcp-unified
```

### Network Issues
```bash
# From MacBook
ping 100.110.65.38
tailscale status | grep canmore

# Test port
nc -zv 100.110.65.38 8811
```

### Vault Access Issues
```bash
# On Canmore
cd /Users/michel/dev/obsidian_rag
./diagnose_mcp_access.sh
```

## 📚 Documentation

- **MCP Setup**: `Documentation/MCP_CLIENT_SETUP.md`
- **SSH Alternative**: `Documentation/SSH_MCP_SETUP.md`
- **Quick Start**: `MCP_CONNECTION_QUICK_START.md`
- **Troubleshooting**: `QUICK_FIX_MCP_SSH.md`

## 🎯 Quick Actions

### Start Everything
```bash
cd /Users/michel/dev/obsidian_rag && docker-compose up -d
```

### Check Everything
```bash
docker ps && curl http://localhost:8811/health && curl http://localhost:4000/api/v1/health
```

### Stop Everything
```bash
cd /Users/michel/dev/obsidian_rag && docker-compose down
```

### View All Logs
```bash
docker-compose logs -f
```

---

**Last Updated**: 2026-03-25
**Canmore Hostname**: canmore
**Canmore Tailscale IP**: 100.110.65.38
