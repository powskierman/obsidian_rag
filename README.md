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
python build_knowledge_graph.py
```

Choose your options:
- Load from vault files or ChromaDB
- Select model (Haiku for cost, Sonnet for quality)
- Interactive query mode available

### 2. Resume After Interruption

If graph building was interrupted:

```bash
python retry_failed_chunks.py
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
python build_knowledge_graph.py
# Choose Option 5: Interactive query
```

**MCP (Claude Desktop/Cursor):**
- Configure `knowledge_graph_mcp.py` in your MCP settings
- Ask Claude: "Query my knowledge graph: What treatments are mentioned?"

## Project Structure

```
obsidian_rag/
├── build_knowledge_graph.py      # Main graph building script
├── retry_failed_chunks.py        # Resume interrupted builds
├── claude_graph_builder.py        # Core graph builder (ClaudeGraphBuilder) - includes retry logic
├── graph_query_service.py        # Graph query service
├── embedding_service.py          # Vector search service
├── streamlit_ui_docker.py        # Web UI
├── obsidian_rag_unified_mcp.py   # Unified MCP server (vault search + graph queries)
├── knowledge_graph_mcp.py        # Graph-only MCP server (alternative)
├── Documentation/                # All documentation
│   ├── Graph/                    # Graph building guides
│   ├── Setup/                    # Setup and quickstart guides
│   ├── Troubleshooting/          # Troubleshooting guides
│   └── Embedding/                # Embedding model docs
├── graph_data/                   # Graph checkpoints and final graph
├── chroma_db/                    # Vector database
└── Scripts/                      # Utility scripts
```

## Core Components

### Graph Building
- **`claude_graph_builder.py`**: Core builder with ClaudeGraphBuilder and ClaudeGraphQuerier (includes retry logic, checkpointing, and error handling)
- **`build_knowledge_graph.py`**: Main entry point for building graphs
- **`retry_failed_chunks.py`**: Resume interrupted builds

### Services
- **`embedding_service.py`**: HTTP service for semantic search (port 8000)
- **`graph_query_service.py`**: HTTP service for graph queries (port 8001)
- **`streamlit_ui_docker.py`**: Web interface (port 8501)

### MCP Integration
- **`obsidian_rag_unified_mcp.py`**: Unified MCP server combining vault search and graph queries (recommended)
- **`knowledge_graph_mcp.py`**: Graph-only MCP server (alternative if you only need graph queries)

## Documentation

See `Documentation/` for detailed guides:

### Quick Start
- **Quick Start**: `Documentation/QUICKSTART.md` - Get started quickly

### Graph Building
- **Graph Builder Guide**: `Documentation/Graph/IMPROVED_GRAPH_BUILDER_GUIDE.md`
- **Resuming Builds**: `Documentation/Graph/TRANSFER_BETWEEN_MACHINES.md`
- **Graph Data Flow**: `Documentation/Graph/GRAPH_DATA_FLOW.md`
- **Quality Improvements**: `Documentation/Graph/QUALITY_IMPROVEMENTS.md`

### Setup
- **Next Steps**: `Documentation/Setup/NEXT_STEPS.md`
- **Cost Guide**: `Documentation/Setup/COST_DECISION_GUIDE.md`

### Troubleshooting
- **ChromaDB Issues**: `Documentation/Troubleshooting/CHROMADB_CORRUPTION_FIX.md`
- **Docker Gateway**: `Documentation/DOCKER_GATEWAY_TROUBLESHOOTING.md`

### Search Examples
- **Query Examples**: `Documentation/SEARCH_EXAMPLES.md` - Comprehensive examples for all query methods

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
python find_latest_checkpoint.py
```

## License

See individual files for license information.

