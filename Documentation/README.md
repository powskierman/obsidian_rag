# Obsidian RAG - Knowledge Graph System

A comprehensive RAG (Retrieval-Augmented Generation) system for your Obsidian vault that combines semantic search with knowledge graph querying powered by Claude AI.

## Features

- **Semantic Search**: Fast vector-based search using ChromaDB and sentence transformers
- **Knowledge Graph**: Entity-relationship graph built with Claude AI for intelligent querying
- **Deep Thinking Agent**: Agentic reasoning with multi-step planning and reflection (supports Perplexity, Ollama, OpenRouter, etc.)
- **Multiple Interfaces**: Web UI (Streamlit), CLI, and MCP integration for Claude Desktop/Cursor
- **Docker Support**: Full containerized deployment with docker-compose
- **Resume Capability**: Checkpoint-based graph building that can resume after interruptions

## Quick Start

### 1. Build the Knowledge Graph

```bash
python src/indexing/build_knowledge_graph.py
```

Choose your options:
- Load from vault files or ChromaDB
- Select model (Haiku for cost, Sonnet for quality)
- Interactive query mode available

### 2. Resume After Interruption

If graph building was interrupted:

```bash
python src/indexing/retry_failed_chunks.py
```

The script will:
- Auto-detect the latest checkpoint
- Identify which chunks still need processing
- Resume from where you left off

### 3. Query the Graph

**Web Interface (Modern):**
```bash
./Scripts/start_obsidian_rag.sh
# Open http://localhost:3000 (WebApp)
```

**Legacy UI:**
```bash
# Open http://localhost:8501 (Streamlit)
```

**CLI:**
```bash
python src/indexing/build_knowledge_graph.py
# Choose Option 5: Interactive query
```

**MCP (Claude Desktop/Cursor):**
- Configure `src/mcp/knowledge_graph_mcp.py` in your MCP settings
- Ask Claude: "Query my knowledge graph: What treatments are mentioned?"

## Multi-Machine Sync (Mac Mini ↔ MacBook)

To avoid iCloud corruption, use the Snapshot Sync workflow:
1.  **Index** on Mac Mini: `./Scripts/run_indexing.sh`
2.  **Push** from Mini: `./Scripts/sync/push.sh`
3.  **Pull** to MacBook: `./Scripts/sync/pull.sh`

Detailed guide: `Scripts/INDEXING_SCRIPTS_GUIDE.md`

## Project Structure

```
obsidian_rag/
├── src/                          # Source code
│   ├── indexing/                 # Graph building scripts
│   │   ├── build_knowledge_graph.py   # Main graph building script
│   │   ├── retry_failed_chunks.py     # Resume interrupted builds
│   │   ├── find_latest_checkpoint.py  # Find checkpoint files
│   │   ├── index_vault.py             # Vault indexing
│   │   └── query_vault.py             # Query interface
│   ├── services/                 # HTTP services
│   │   ├── claude_graph_builder.py    # Core graph builder with retry logic
│   │   ├── embedding_service.py       # Vector search service (port 8000)
│   │   ├── graph_query_service.py     # Graph query service (port 8002)
│   │   └── kimi_graph_builder.py      # Kimi-powered graph builder
│   ├── integrations/             # Service integrations
│   │   ├── claude_graph_reasoner.py   # Claude graph reasoning
│   │   └── lightrag_service.py        # LightRAG integration
│   ├── mcp/                      # MCP servers
│   │   ├── obsidian_rag_unified_mcp.py   # Unified MCP (vault + graph)
│   │   └── knowledge_graph_mcp.py        # Graph-only MCP
│   ├── ui/                       # User interfaces
│   │   ├── streamlit_ui_docker.py     # Main web UI (port 8501)
│   │   └── streamlit_ui_enhanced.py   # Alternative UI
│   └── utils/                    # Utilities
│       ├── logging_config.py
│       ├── query_feedback.py          # Query tracking and metrics
│       └── validate_claude_api_key.py
├── scripts/                      # Utility scripts
│   ├── docker/                   # Docker management scripts
│   ├── maintenance/              # Maintenance scripts
│   ├── vault_management/         # Obsidian vault scanners
│   │   ├── obsidian_scanner.py
│   │   ├── simple_scanner.py
│   │   └── watching_scanner.py
│   └── *.sh                      # Various shell scripts
├── config/                       # Configuration files
│   ├── docker/                   # Docker configs and Dockerfiles
│   ├── examples/                 # Example .env files
│   └── *.json                    # Rule configurations
├── Documentation/                # All documentation (see Documentation/README.md)
│   ├── Setup/                    # Installation and setup guides
│   ├── Guides/                   # Usage and development guides
│   ├── Reference/                # Reference documentation
│   ├── Troubleshooting/          # Problem solving
│   ├── Models/                   # LLM and embedding model docs
│   ├── Graph/                    # Knowledge graph specifics
│   ├── MCP/                      # MCP integration
│   └── architecture/             # System design
├── graph_data/                   # Graph checkpoints and final graph
└── chroma_db/                    # Vector database
```

## Core Components

### Graph Building (`src/indexing/`)
- **`claude_graph_builder.py`**: Core builder with GraphBuilder and ClaudeGraphQuerier (includes retry logic, checkpointing, and error handling)
- **`build_knowledge_graph.py`**: Main entry point for building graphs
- **`retry_failed_chunks.py`**: Resume interrupted builds

### Services (`src/services/`)
- **`embedding_service.py`**: HTTP service for semantic search (port 8000)
- **`graph_query_service.py`**: HTTP service for graph queries (port 8002)
- **`streamlit_ui_docker.py`**: Web interface (port 8501)

### MCP Integration (`src/mcp/`)
- **`obsidian_rag_unified_mcp.py`**: Unified MCP server combining vault search and graph queries (recommended)
- **`knowledge_graph_mcp.py`**: Graph-only MCP server (alternative if you only need graph queries)

## 📚 Documentation

Detailed guides are organized into logical sections to help you find what you need quickly.

### 🏁 Getting Started
- **[Quickstart](Documentation/Setup/QUICKSTART.md)** - Rapid setup guide
- **[System Overview](Documentation/SYSTEM_OVERVIEW_2025.md)** - Current architecture and services
- **[Indexing Strategy](Documentation/INDEXING_STRATEGY.md)** - Managing vault indexing
- **[Reindexing Procedure](Documentation/REINDEXING_PROCEDURE.md)** - Complete reindexing workflow

### ⚙️ Setup & Configuration
- **[Docker Setup](Documentation/Docker/DOCKER_MCP_INTEGRATION.md)** - Docker and MCP integration
- **[Cost Decision Guide](Documentation/Setup/COST_DECISION_GUIDE.md)** - Model selection and cost planning
- **[API Key Validation](Documentation/Setup/API_KEY_VALIDATION_GUIDE.md)** - Troubleshooting API keys

### 🏗️ Architecture & Development
- **[System Architecture](Documentation/architecture/SYSTEM_ARCHITECTURE_DIAGRAM.md)** - System design overview
- **[Deep Thinking Flow](Documentation/architecture/DEEP_THINKING_FLOW.md)** - Logic behind agentic search
- **[Project Constitution](Documentation/PROJECT_CONSTITUTION.md)** - Authoritative governance and scope
- **[Testing Guide](Documentation/Setup/TESTING.md)** - How to run and write tests

### 🚀 Usage & Integration
- **[Graph Builder Guide](Documentation/Graph/IMPROVED_GRAPH_BUILDER_GUIDE.md)** - Building and improving graphs
- **[Graph Quality Guide](Documentation/Graph/GRAPH_QUALITY_GUIDE.md)** - Optimizing graph quality
- **[CLI Search](Documentation/guides/README_CLI_SEARCH.md)** - Using the command-line interface
- **[MCP Setup](Documentation/MCP/MCP_SETUP_INSTRUCTIONS.md)** - Using with Claude Desktop/Cursor
- **[Troubleshooting](Documentation/guides/troubleshooting/DOCKER_TROUBLESHOOTING.md)** - Common issues and fixes

> [!TIP]
> For the most comprehensive view of the system, check out the **[Documentation Dashboard](Documentation/README.md)**.

## Requirements

- Python 3.8+
- Anthropic API key (set `ANTHROPIC_API_KEY` environment variable)
- See `requirements.txt` for dependencies

## Docker Deployment

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Checkpoints

The graph builder saves checkpoints every 10 chunks by default. Checkpoints are stored in `graph_data/graph_checkpoint_*.pkl`.

To find the latest checkpoint:
```bash
python src/indexing/find_latest_checkpoint.py
```

## License

See individual files for license information.

