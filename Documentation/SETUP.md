# Obsidian RAG - Quick Setup Guide

**Last Updated**: December 28, 2025

---

## Prerequisites

Before you begin, ensure you have:

- **Docker & Docker Compose** - [Install Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Obsidian vault** with your notes
- **API Keys** (at least one):
  - **OpenRouter** (for Kimi K2 graph building) - [Get key](https://openrouter.ai/)
  - **Anthropic** (for Claude models) - [Get key](https://console.anthropic.com/)
  - **Google Gemini** (for Gemini models) - [Get key](https://aistudio.google.com/app/apikey)
  - **Tavily** (for web search) - [Get key](https://tavily.com/)

---

## Quick Start (Docker - Recommended)

### 1. Clone Repository

```bash
git clone <repository-url>
cd obsidian_rag
```

### 2. Configure Environment

Copy the example environment file and edit it:

```bash
cp .env.example .env
nano .env  # or your preferred editor
```

**Required settings** in `.env`:

```bash
# Your Obsidian vault path (absolute path)
VAULT_PATH=/path/to/your/obsidian/vault

# OpenRouter (for knowledge graph building with Kimi K2)
OPENROUTER_API_KEY=your-openrouter-key-here

# At least one LLM provider (choose what you prefer)
ANTHROPIC_API_KEY=your-anthropic-key-here      # For Claude
GEMINI_API_KEY=your-gemini-key-here            # For Gemini
OLLAMA_HOST=http://host.docker.internal:11434  # For Ollama (if running locally)

# Optional: Web search
TAVILY_API_KEY=your-tavily-key-here
```

### 3. Start Services

**Option A: Docker Compose** (Recommended)

```bash
docker-compose up -d
```

**Option B: macOS App Launcher**

Double-click: `Launch Obsidian RAG.command`

### 4. Access the Application

**Next.js Web App** (Primary UI):
- URL: [http://localhost:3000](http://localhost:3000)
- Modern, fast interface
- Enhanced search with LLM knowledge + web search
- Custom system prompts
- Three search modes: Vector, Knowledge Graph, Hybrid

**Streamlit UI** (Alternative):
- URL: [http://localhost:8501](http://localhost:8501)
- Traditional interface
- Same features as Next.js

### 5. Index Your Vault

The first time you start, the system will automatically:
1. Build vector embeddings for semantic search
2. Extract entities and relationships for the knowledge graph

**Progress**: Check Docker logs:
```bash
docker logs obsidian-graph-service -f
```

**Graph building**: Takes ~10-60 minutes depending on vault size. You'll see:
```
Indexing chunk 100/5000...
Building knowledge graph...
Graph saved: 23,926 nodes, 35,030 edges
```

---

## Service Architecture

When you run `docker-compose up`, these services start:

| Service | Port | Purpose |
|---------|------|---------|
| **obsidian-webapp** | 3000 | Next.js web UI |
| **obsidian-streamlit** | 8501 | Streamlit UI (alternative) |
| **obsidian-graph-service** | 8002 | Knowledge graph queries |
| **obsidian-embedding** | 8000 | Vector search |

**Health checks**:
```bash
curl http://localhost:8002/health  # Graph service
curl http://localhost:8000/health  # Embedding service
```

---

## First Query

Try these example queries to test the system:

### Medical Query (if you have health notes)
```
What were my recent medical test results and what do they indicate?
```

### Technical Query
```
What projects am I working on that involve Python and AI?
```

### Timeline Query
```
What happened in my life during September 2024?
```

### Custom System Prompt

For personalized responses, click the **Prompt** button in the UI and enter:

```
You are a personal AI assistant with access to Michel's knowledge base.

When answering:
1. Reference specific notes, dates, and context from the vault
2. Use a compassionate tone for medical/health topics
3. Be technical and precise for coding/engineering topics
4. Cite which notes you're using
5. Adapt to expert-level understanding
```

---

## Configuration Options

### Search Modes

1. **Vector Mode**: Semantic similarity search
   - Best for: Finding similar content, document discovery
   - Speed: Fast (2-5 seconds)

2. **Knowledge Graph Mode**: Entity relationship reasoning
   - Best for: Connections, timeline analysis, "how are X and Y related?"
   - Speed: Medium (5-10 seconds)

3. **Hybrid Mode**: Vector + Graph combined
   - Best for: Comprehensive answers with context
   - Speed: Slower (10-20 seconds)
   - Recommended default

### Enhanced Search (Gemini/Claude only)

Toggle **Enhanced Search** to add:
- 🧠 **LLM Knowledge**: Built-in medical/technical knowledge
- 🌐 **Web Search**: Current information from the web

### LLM Providers

Choose your preferred model:
- **Gemini Pro**: Fast, good quality, web search support
- **Claude Sonnet 4**: Highest quality reasoning
- **Ollama**: Privacy-first, runs locally (requires Ollama installed)

---

## Troubleshooting

### Services Won't Start

**Check Docker is running**:
```bash
docker ps
```

**View logs**:
```bash
docker-compose logs -f
```

**Restart services**:
```bash
docker-compose down
docker-compose up -d
```

### "Graph not loaded" Error

The knowledge graph is still building. Wait for completion:
```bash
docker logs obsidian-graph-service -f
```

Look for: `Graph loaded: 23926 nodes, 35030 edges`

### Empty/Poor Results

**Rebuild the index**:
```bash
# Stop services
docker-compose down

# Remove old databases
rm -rf chroma_db/ graph_data/*.pkl

# Restart (will rebuild)
docker-compose up -d
```

### Port Already in Use

If port 3000 or 8501 is already in use, edit `docker-compose.yml`:

```yaml
services:
  webapp:
    ports:
      - "3001:3000"  # Change left port number
```

---

## Updating

### Pull Latest Changes

```bash
git pull origin main
docker-compose down
docker-compose build
docker-compose up -d
```

### Rebuild Knowledge Graph

If you've added many new notes:

```bash
# Backup current graph
cp graph_data/knowledge_graph_full.pkl graph_data/knowledge_graph_backup.pkl

# Rebuild
docker-compose down
rm -rf graph_data/*.pkl
docker-compose up -d
```

---

## Advanced Configuration

### Custom Models

Edit `.env` to use different models:

```bash
# Use different Kimi model for graph building
KIMI_MODEL=moonshotai/kimi-k2-1205

# Use specific Ollama model
OLLAMA_MODEL=llama3.2:latest
```

### Adjust Graph Building

Edit `config/docker/Dockerfile.graph` to change graph building parameters:

```dockerfile
ENV MAX_ENTITIES=20
ENV CHECKPOINT_INTERVAL=100
```

### File Watcher (Auto-reindex)

To automatically reindex when vault changes:

```bash
./Scripts/start_with_watcher.sh
```

---

## Getting Help

### Documentation

- **Architecture**: [Documentation/architecture/](Documentation/architecture/)
- **Features**: [Documentation/FEATURES.md](Documentation/FEATURES.md)
- **Troubleshooting**: [Documentation/TROUBLESHOOTING.md](Documentation/TROUBLESHOOTING.md)
- **API Docs**: [Documentation/API.md](Documentation/API.md)

### Common Issues

Check [Documentation/TROUBLESHOOTING.md](Documentation/TROUBLESHOOTING.md) for solutions to:
- Connection errors
- Slow queries
- Memory issues
- API rate limits

### Logs

**View all logs**:
```bash
docker-compose logs -f
```

**Specific service**:
```bash
docker logs obsidian-graph-service -f
docker logs obsidian-webapp -f
```

---

## Next Steps

Once setup is complete:

1. **Customize System Prompt** - Click "Prompt" button for personalized responses
2. **Try Different Search Modes** - Vector, Graph, Hybrid
3. **Enable Enhanced Search** - For LLM knowledge + web search
4. **Explore Your Vault** - Ask questions about your notes
5. **Review Documentation** - Learn about advanced features

---

## Quick Reference

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart single service
docker restart obsidian-graph-service

# Check service health
curl http://localhost:8002/health
curl http://localhost:8000/health

# Access UIs
open http://localhost:3000      # Next.js
open http://localhost:8501      # Streamlit
```

---

## System Requirements

**Minimum**:
- 8 GB RAM
- 10 GB disk space
- Modern CPU (4+ cores)

**Recommended**:
- 16 GB RAM (for large vaults)
- 20 GB disk space
- 8+ core CPU

**For Ollama** (local LLMs):
- 32 GB RAM (for 14B models)
- 64 GB RAM (for 32B models)
- GPU recommended but not required

---

## Success!

You should now have:
- ✅ Docker services running
- ✅ Next.js UI accessible at http://localhost:3000
- ✅ Knowledge graph indexed
- ✅ Ready to query your vault

**First query**: Try asking about a recent note or project!

For more help, see [Documentation/](Documentation/) or check the logs.
