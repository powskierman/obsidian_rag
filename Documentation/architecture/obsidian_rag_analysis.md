# Obsidian RAG Project - Complete Analysis

## Executive Summary

The Obsidian RAG project is a sophisticated retrieval-augmented generation system that combines semantic vector search with knowledge graph construction. It's designed for querying Obsidian vaults (personal knowledge bases) using Claude AI and multiple backend services.

**Key Architectures:**
- Docker-based microservices (recommended)
- Native Python scripts (alternative)
- MCP (Model Context Protocol) integration for Claude Desktop/Cursor

---

## 1. MAIN ENTRY POINTS & USER-FACING WORKFLOWS

### Primary User Workflows

#### **Workflow 1: Docker-Based (Recommended for Most Users)**
```
1. Start: ./Scripts/docker_start.sh
   ↓
2. Services initialize (Embedding, Graph, UI)
   ↓
3. Access UI: http://localhost:8501
   ↓
4. Index vault: Click button in sidebar OR run indexing script
   ↓
5. Query knowledge: Use search modes in UI sidebar
   ↓
6. Stop: ./Scripts/docker_stop.sh
```

#### **Workflow 2: Knowledge Graph Building (Claude-Based)**
```
1. Build graph: python build_knowledge_graph.py
   ↓
2. Choose options (load source, model, checkpoint)
   ↓
3. Query graph: Option 5 in menu OR use Streamlit UI
```

#### **Workflow 3: Local Setup (No Docker)**
```
1. Activate venv: source venv/bin/activate
   ↓
2. Start embedding: python embedding_service.py &
   ↓
3. Start UI: streamlit run obsidian_rag_ui.py
   ↓
4. Access: http://localhost:8501
```

---

## 2. ENTRY POINT SCRIPTS (Root Level)

### Primary User-Facing Scripts

| Script | Purpose | When to Use | Command |
|--------|---------|-------------|---------|
| `build_knowledge_graph.py` | Build and query knowledge graphs | Creating Claude-powered knowledge graphs | `python build_knowledge_graph.py` |
| `retry_failed_chunks.py` | Resume interrupted graph builds | After interruptions or failures | `python retry_failed_chunks.py` |
| `embedding_service.py` | Vector search backend service | Manual startup (usually in Docker) | `python embedding_service.py` |
| `streamlit_ui_docker.py` | Web interface | Docker deployment | Started by docker-compose |
| `streamlit_ui_enhanced.py` | Alternative web interface | Local development | `streamlit run streamlit_ui_enhanced.py` |

### Scripts in Scripts/ Directory (Utility Scripts)

#### Docker Management Scripts (User-Facing)
- **`docker_start.sh`** - Start all Docker containers ⭐
- **`docker_stop.sh`** - Stop all Docker containers
- **`docker_status.sh`** - Check service status
- **`docker_rebuild.sh`** - Rebuild images and restart
- **`check_status.sh`** - Check native service status

#### Indexing Scripts (User-Facing)
- **`index_with_graphrag.sh`** - Index with Microsoft GraphRAG
- **`index_with_graphrag_local.sh`** - Index with local GraphRAG + Ollama
- **`index_with_claude.sh`** - Index with Claude API ⭐
- **`index_with_claude_simple.sh`** - Simplified Claude indexing
- **`index_with_lightrag.sh`** - Index with LightRAG (legacy)
- **`run_openrouter_index.sh`** - Index with OpenRouter API

#### Application Scripts (Developer-Facing)
- **`start_obsidian_rag.sh`** - Start native Python services
- **`start_graphrag.sh`** - Start GraphRAG Docker service
- **`start_with_watcher.sh`** - Start with file watching enabled
- **`stop_obsidian_rag.sh`** - Stop native services

#### Utility Scripts (Developer-Facing)
- **`backup.sh`** - Backup database
- **`clean.sh`** - Clean up databases
- **`test.sh`** - Run tests

---

## 3. SERVICE ARCHITECTURE (Docker Compose)

### Service Topology

```
┌─────────────────────────────────────────────────────────┐
│                  Streamlit UI (8501)                    │
│           (streamlit_ui_docker.py)                      │
│  - Search interface with 7 query modes                  │
│  - Model selection (LLM + Embedding)                    │
│  - Index vault button                                   │
└──────────────────────┬──────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ↓             ↓             ↓
    ┌────────┐   ┌──────────┐  ┌─────────┐
    │Embedding│  │LightRAG  │  │GraphRAG │
    │Service  │  │Service   │  │Service  │
    │ (8000)  │  │ (8001)   │  │ (8002)  │
    └────────┘   └──────────┘  └─────────┘
         ↑             ↑             ↑
         └─────────────┴─────────────┘
         (Connected to Ollama 11434)
```

### Enabled Services by Configuration

**Default Profile (embedding + graphrag):**
- embedding-service (8000) - ChromaDB + Sentence Transformers
- graphrag-service (8002) - Microsoft GraphRAG with Ollama
- streamlit-ui (8501) - Web interface

**Alternative Profiles (via docker-compose --profile):**
- `lightrag` - LightRAG service (legacy)
- `graphrag-local` - Local GraphRAG with Ollama
- `graphrag-claude` - GraphRAG with Claude API
- `graphrag-gpt-oss` - GraphRAG with custom GPT model

### Database Volumes

```
./chroma_db/              → Vector embeddings (ChromaDB)
./graphrag_db/            → GraphRAG indices
./graphrag_local_db/      → Local GraphRAG data
./graphrag_claude_db/     → Claude-powered GraphRAG
./lightrag_db/            → LightRAG data (legacy)
```

---

## 4. DEPENDENCY MANAGEMENT

### Main Dependencies (requirements.txt)

```
Core RAG:
  - flask==3.0.0           (REST API framework)
  - streamlit==1.29.0      (Web UI)
  - chromadb==0.4.18       (Vector DB)
  - sentence-transformers>=2.3.0  (Embeddings)
  - watchdog==3.0.0        (File monitoring)

ML/AI:
  - torch>=2.2.0           (PyTorch)
  - transformers>=4.35.0   (Hugging Face)

Utilities:
  - python-dotenv==1.0.0   (Environment variables)
  - pyyaml==6.0.1          (Config files)
  - requests==2.31.0       (HTTP client)
```

### GraphRAG-Specific Dependencies (requirements_graphrag.txt)

```
graphrag>=0.3.5           (Main library)
aiofiles, aiohttp         (Async operations)
pydantic>=2.0.0           (Data validation)
pandas, numpy             (Data processing)
tiktoken                  (Token counting)
networkx>=3.0             (Graph processing)
openai>=1.0.0             (API client)
azure-core, azure-identity, azure-storage-blob  (Azure integration)
flask, requests           (Web services)
```

### Environment Variables Required

**Claude API:**
```bash
ANTHROPIC_API_KEY=sk-ant-...  # Required for Claude-based indexing
```

**Ollama (Local Models):**
```bash
OLLAMA_HOST=http://host.docker.internal:11434  # For Docker
# or
OLLAMA_HOST=http://localhost:11434              # For native
```

**Model Selection:**
```bash
LLM_MODEL=qwen2.5-coder:14b       # Language model
EMBED_MODEL=nomic-embed-text      # Embedding model
```

**OpenAI (Optional):**
```bash
OPENAI_API_KEY=sk-...             # For embeddings (if not using Ollama)
```

### Initialization Sequence

1. **Environment Variables**
   ```bash
   # Required
   export ANTHROPIC_API_KEY="your-key"
   
   # Optional (defaults provided)
   export OLLAMA_HOST="http://localhost:11434"
   export LLM_MODEL="qwen2.5-coder:14b"
   ```

2. **Virtual Environment (Native)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Docker Setup**
   ```bash
   docker-compose pull      # Optional: update images
   docker-compose build     # Build services
   ```

4. **Database Initialization**
   - ChromaDB: Auto-created on first embedding
   - GraphRAG: Auto-initialized on first index operation
   - Vector DB: Populated via indexing scripts

5. **Model Downloads**
   - Embedding models: Auto-downloaded on first use
   - LLM models: Must be pre-pulled in Ollama
   ```bash
   ollama pull qwen2.5-coder:14b
   ollama pull nomic-embed-text
   ```

---

## 5. RECOMMENDED USER WORKFLOW (Complete Steps)

### Step 1: Prerequisites
```bash
# 1. Install Ollama and pull models
brew install ollama
ollama pull qwen2.5-coder:14b
ollama pull nomic-embed-text
ollama serve  # Start Ollama in background

# 2. Clone project and setup
git clone <repo>
cd obsidian_rag

# 3. Configure environment
cp .env.example .env.local
export ANTHROPIC_API_KEY="your-key"  # If using Claude
```

### Step 2: Choose Your Path

**Path A: Docker (Recommended)**
```bash
# Start services
./Scripts/docker_start.sh

# Wait for services to be ready
sleep 10

# Check status
./Scripts/docker_status.sh

# Open UI in browser
open http://localhost:8501

# Index your vault (UI button or):
./Scripts/index_with_graphrag.sh

# Query using UI sidebar (7 search modes available)
```

**Path B: Native Python**
```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start services
python embedding_service.py &                    # Terminal 1
streamlit run streamlit_ui_enhanced.py          # Terminal 2

# Index and query through web UI or:
python build_knowledge_graph.py                  # Interactive menu
```

**Path C: Knowledge Graph Only (Claude)**
```bash
# Direct graph building
python build_knowledge_graph.py

# Menu options:
# 1. Load from vault files
# 2. Select Claude model (Haiku for cost, Sonnet for quality)
# 3. Start building (creates checkpoints)
# 4. Resume from checkpoints if interrupted
# 5. Interactive query mode

# Estimated costs:
# - Claude Haiku: $1-2 for 1600 notes
# - Claude Sonnet: $10-20 for 1600 notes
```

### Step 3: Query Your Knowledge

**Via Web UI (Easiest)**
- Vector: Fast semantic search
- Graph-Local: Entity-focused (LightRAG)
- Graph-Global: Comprehensive synthesis (LightRAG)
- GraphRAG-Local: Entity search (GraphRAG)
- GraphRAG-Global: Community-based (GraphRAG)
- Hybrid: Best of both

**Via CLI**
```bash
python build_knowledge_graph.py
# Choose option 5: Interactive Query
```

**Via MCP (Claude Desktop)**
```bash
# Configure obsidian_rag_unified_mcp.py in:
~/.config/Claude/claude_desktop_config.json

# Then in Claude: "Query my knowledge graph: ..."
```

---

## 6. DOCKER COMPOSE CONFIGURATION

### Quick Reference

```bash
# Start all default services
docker-compose up -d

# Start with specific profile
docker-compose --profile graphrag-claude up -d

# Check running services
docker-compose ps

# View logs
docker-compose logs -f embedding-service
docker-compose logs -f streamlit-ui

# Stop all
docker-compose down

# Remove volumes (wipe data)
docker-compose down -v

# Rebuild images
docker-compose build --no-cache
```

### Service Details

| Service | Port | Profile | Purpose |
|---------|------|---------|---------|
| embedding | 8000 | default | Vector search (ChromaDB) |
| graphrag | 8002 | graphrag | MS GraphRAG indexing |
| graphrag-local | 8003 | graphrag-local | Local GraphRAG + Ollama |
| graphrag-claude | 8004 | graphrag-claude | GraphRAG + Claude API |
| lightrag | 8001 | lightrag | LightRAG (legacy) |
| streamlit-ui | 8501 | default | Web interface |

### Environment for Services

Each service receives:
```bash
PYTHONUNBUFFERED=1           # Unbuffered output
OLLAMA_HOST=...              # Ollama endpoint
LLM_MODEL=...                # Language model
EMBED_MODEL=...              # Embedding model
GRAPHRAG_DIR=/app/...        # Working directory
VAULT_PATH=/app/vault        # Obsidian vault
ANTHROPIC_API_KEY=...        # Claude API (if needed)
```

---

## 7. PROJECT FILE STRUCTURE

```
obsidian_rag/
├── Core Entry Points
│   ├── build_knowledge_graph.py        ⭐ Main graph builder
│   ├── retry_failed_chunks.py          ⭐ Resume interrupted builds
│   ├── embedding_service.py            ⭐ Vector search backend
│   ├── streamlit_ui_docker.py          ⭐ Web UI (Docker)
│   ├── streamlit_ui_enhanced.py        ⭐ Web UI (native)
│   └── index_vault.py                  ⭐ Vault indexing utility
│
├── Backend Services
│   ├── claude_graph_builder.py         Core graph logic (ClaudeGraphBuilder)
│   ├── graphrag_service.py             GraphRAG Flask API
│   ├── graphrag_local_service.py       Local GraphRAG service
│   ├── graphrag_claude_service.py      Claude-based GraphRAG
│   ├── lightrag_service.py             LightRAG service (legacy)
│   └── graph_query_service.py          Graph query API
│
├── MCP Integration
│   ├── obsidian_rag_unified_mcp.py    ⭐ Unified MCP server (vault + graph)
│   ├── knowledge_graph_mcp.py         Graph-only MCP server
│   └── obsidian_rag_mcp_fixed.py      Alternative MCP
│
├── Utilities
│   ├── find_latest_checkpoint.py      Find latest graph checkpoint
│   ├── fix_secrets_in_history.py      Git history cleanup
│   ├── logging_config.py              Logging setup
│   ├── obsidian_scanner.py            Vault scanner
│   └── query_feedback.py              Analytics
│
├── Scripts/
│   ├── docker_start.sh                ⭐ Start Docker services
│   ├── docker_stop.sh                 ⭐ Stop Docker services
│   ├── docker_status.sh               ⭐ Check status
│   ├── docker_rebuild.sh              ⭐ Rebuild and restart
│   ├── check_status.sh                Check native services
│   │
│   ├── index_with_graphrag.sh         ⭐ Index with GraphRAG
│   ├── index_with_claude.sh           ⭐ Index with Claude
│   ├── index_with_graphrag_local.sh   Index with local Ollama
│   ├── index_with_lightrag.sh         Index with LightRAG
│   │
│   ├── start_obsidian_rag.sh          Start native services
│   ├── start_graphrag.sh              Start GraphRAG service
│   ├── start_with_watcher.sh          Start with file watcher
│   ├── stop_obsidian_rag.sh           Stop native services
│   │
│   └── (misc scripts)
│
├── Database Directories
│   ├── chroma_db/                     Vector embeddings
│   ├── graphrag_db/                   GraphRAG indices
│   ├── graphrag_local_db/             Local GraphRAG
│   ├── graphrag_claude_db/            Claude GraphRAG
│   └── graph_data/                    Graph checkpoints
│
├── Configuration
│   ├── .env.example                   Example environment
│   ├── .env.claude.example            Claude API example
│   ├── .env.local                     Current settings
│   ├── docker-compose.yml             ⭐ Service definitions
│   ├── Dockerfile.*                   Container images
│   └── config/                        Config files
│
├── Documentation/
│   ├── QUICKSTART.md                  Getting started
│   ├── Graph/                         Graph building guides
│   ├── Setup/                         Setup instructions
│   ├── Troubleshooting/               Troubleshooting
│   └── Embedding/                     Embedding models
│
└── README.md                          ⭐ Main documentation

⭐ = User-facing entry points
```

---

## 8. QUICK REFERENCE: WHAT TO RUN WHEN

### "I want to start using it now"
```bash
./Scripts/docker_start.sh
# Wait 10 seconds
open http://localhost:8501
# Click "Index Vault" in sidebar
```

### "I want to build a knowledge graph with Claude"
```bash
export ANTHROPIC_API_KEY="your-key"
python build_knowledge_graph.py
# Choose option 1 or 2 based on your preference
```

### "I want to resume a failed graph build"
```bash
python retry_failed_chunks.py
# Auto-finds latest checkpoint and resumes
```

### "I want to index with different service"
```bash
./Scripts/index_with_graphrag.sh        # Microsoft GraphRAG
./Scripts/index_with_claude.sh          # Claude API
./Scripts/index_with_graphrag_local.sh  # Local Ollama
```

### "I want to check service status"
```bash
# Docker
./Scripts/docker_status.sh

# Native
./Scripts/check_status.sh
```

### "I want to use it with Claude Desktop"
```bash
# Edit ~/.config/Claude/claude_desktop_config.json
# Add obsidian_rag_unified_mcp.py configuration
# Then ask: "Query my knowledge graph for..."
```

### "I want to stop everything"
```bash
./Scripts/docker_stop.sh    # Docker
# or
./Scripts/stop_obsidian_rag.sh  # Native
```

---

## 9. DEPENDENCY INSTALLATION DETAILS

### Minimal Setup (Native)
```bash
pip install -r requirements.txt
# ~500MB, includes:
# - Flask, Streamlit, ChromaDB
# - Sentence Transformers (embedding model)
# - PyTorch, Transformers
```

### Full Setup (GraphRAG)
```bash
pip install -r requirements_graphrag.txt
# ~2GB, adds:
# - Microsoft GraphRAG
# - Async libraries (aiofiles, aiohttp)
# - Azure SDK
# - OpenAI client
# - NetworkX (graph processing)
```

### First-Run Downloads
```
Embedding Model (all-MiniLM-L6-v2): ~90MB
Sentence Transformers: ~500MB
Ollama Models (if used):
  - nomic-embed-text: ~300MB
  - qwen2.5-coder:14b: ~8.5GB
  - llama3.1:8b: ~4GB
```

### Key Initialization Scripts
```python
# Automatic initialization on first run:
embedding_service.py      # Downloads models, creates ChromaDB
build_knowledge_graph.py  # Creates graph_data/ directory
streamlit_ui_*.py         # Sets up session state
```

---

## 10. KEY CONFIGURATION FILES

### docker-compose.yml
- **Defines:** All services, ports, volumes, networks
- **Profiles:** Allow selective service startup
- **Environment:** Model selection, API keys, paths
- **Networks:** `rag-network` bridge for service communication

### .env.local (Current)
```bash
GRAPH_SERVICE=graphrag              # Service choice
LLM_MODEL=qwen2.5-coder:14b        # Language model
EMBED_MODEL=nomic-embed-text       # Embedding model
OLLAMA_HOST=http://host.docker.internal:11434
ANTHROPIC_API_KEY=sk-ant-...       # Claude API
```

### Dockerfile.* (Service Images)
- `Dockerfile.embedding` → embedding-service
- `Dockerfile.streamlit` → streamlit-ui
- `Dockerfile.graphrag` → graphrag-service
- `Dockerfile.graphrag-local` → local services
- `Dockerfile.lightrag` → lightrag-service

### .streamlit/config.toml
- Streamlit configuration (theme, port, etc.)

---

## 11. TROUBLESHOOTING QUICK LINKS

```
Problem                          Solution
─────────────────────────────────────────────────────────
Services won't start            → Check Ollama is running
                                → Check ANTHROPIC_API_KEY
                                → Check Docker is running

Indexing too slow               → Use Haiku model
                                → Index smaller subset
                                → Check RAM available

Out of memory                   → Reduce chunk size
                                → Index in smaller batches
                                → Check for background apps

Knowledge graph empty           → Run indexing script
                                → Check vault path
                                → Verify markdown files exist

Search returns no results       → Index vault first
                                → Check search mode
                                → Verify query terms
```

---

## 12. PERFORMANCE NOTES

### Estimated Times (1600 notes)
- **Embedding Index:** 5-15 minutes
- **Knowledge Graph Build (Haiku):** 45-75 minutes
- **Knowledge Graph Build (Sonnet):** 60-90 minutes
- **Search Query:** <1 second (vector), 5-10 seconds (graph)

### Estimated Costs (1600 notes)
- **Haiku:** $1-2 (cheap, fast)
- **Sonnet:** $10-20 (expensive, better quality)
- **Ollama Local:** $0 (slow, no API key needed)
- **GraphRAG with Claude:** ~$5-10 for full analysis

### System Requirements
- **CPU:** 2+ cores (4+ recommended)
- **RAM:** 8GB minimum (16GB recommended)
- **Disk:** 50GB+ for all databases
- **Internet:** Required for API calls only

---

## Summary

The Obsidian RAG system provides multiple paths to the same goal: intelligent search over your personal knowledge base. The **Docker approach** is recommended for most users (simplest setup, all services managed), while the **Python native approach** offers flexibility for development, and the **Claude graph building** approach provides the best quality analysis at reasonable cost.

**Most common user journey:**
1. Run `./Scripts/docker_start.sh`
2. Wait for services
3. Open browser to `http://localhost:8501`
4. Click "Index Vault" button
5. Query using sidebar options
6. Stop with `./Scripts/docker_stop.sh`
