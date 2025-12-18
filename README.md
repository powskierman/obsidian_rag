# Obsidian RAG - Knowledge Graph System

A comprehensive RAG (Retrieval-Augmented Generation) system for your Obsidian vault that combines semantic search with knowledge graph querying powered by Claude AI.

## Features

- **Semantic Search**: Fast vector-based search using ChromaDB and sentence transformers
- **Knowledge Graph**: Entity-relationship graph built with Claude AI for intelligent querying
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

**Web UI (Recommended):**
```bash
docker-compose up -d
# Open http://localhost:8501
```

**CLI:**
```bash
python src/indexing/build_knowledge_graph.py
# Choose Option 5: Interactive query
```

**MCP (Claude Desktop/Cursor):**
- Configure `src/mcp/knowledge_graph_mcp.py` in your MCP settings
- Ask Claude: "Query my knowledge graph: What treatments are mentioned?"

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
│   │   └── graphrag_claude_service.py # GraphRAG wrapper
│   ├── integrations/             # Service integrations
│   │   ├── claude_graph_reasoner.py   # Claude graph reasoning
│   │   ├── graphrag_unified_service.py # Unified GraphRAG service
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
- **`claude_graph_builder.py`**: Core builder with ClaudeGraphBuilder and ClaudeGraphQuerier (includes retry logic, checkpointing, and error handling)
- **`build_knowledge_graph.py`**: Main entry point for building graphs
- **`retry_failed_chunks.py`**: Resume interrupted builds

### Services (`src/services/`)
- **`embedding_service.py`**: HTTP service for semantic search (port 8000)
- **`graph_query_service.py`**: HTTP service for graph queries (port 8002)
- **`streamlit_ui_docker.py`**: Web interface (port 8501)

### MCP Integration (`src/mcp/`)
- **`obsidian_rag_unified_mcp.py`**: Unified MCP server combining vault search and graph queries (recommended)
- **`knowledge_graph_mcp.py`**: Graph-only MCP server (alternative if you only need graph queries)

## Documentation

📚 **[Complete Documentation →](Documentation/README.md)**

The `Documentation/` directory contains comprehensive guides organized by topic:

- **[Quick Start](Documentation/README.md#quick-start)** - Get up and running fast
- **[Setup & Installation](Documentation/README.md#setup--installation)** - Docker, models, API keys
- **[Architecture](Documentation/README.md#architecture--design)** - System design and flow
- **[Features](Documentation/README.md#features--capabilities)** - Enhanced search, knowledge graphs
- **[Troubleshooting](Documentation/README.md#troubleshooting)** - Common issues and solutions
- **[Development](Documentation/README.md#development--contributing)** - Contributing and testing

**For new users:** Start with [`Documentation/START_HERE.md`](Documentation/START_HERE.md)

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

