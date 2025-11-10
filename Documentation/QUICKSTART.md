# Quick Start Guide

## Building Your Knowledge Graph

### Step 1: Initial Setup

1. **Set your API key:**
   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Step 2: Build the Graph

```bash
python build_knowledge_graph.py
```

**Options:**
- **Source**: Choose vault files (recommended) or ChromaDB
- **Model**: 
  - `claude-haiku-4-5` (default, cost-effective)
  - `claude-sonnet-4-5-20250929` (better quality, more expensive)
- **Interactive Query**: Option 5 lets you query immediately after building

### Step 3: Resume if Interrupted

If the build was interrupted:

```bash
python retry_failed_chunks.py
```

The script will:
- ✅ Auto-detect the latest checkpoint
- ✅ Identify which chunks still need processing
- ✅ Resume from where you left off

**Find latest checkpoint manually:**
```bash
python find_latest_checkpoint.py
```

## Querying Your Graph

### Option 1: Web UI (Recommended)

```bash
docker-compose up -d
# Open http://localhost:8501
```

### Option 2: CLI

```bash
python build_knowledge_graph.py
# Choose Option 5: Interactive query
```

### Option 3: MCP (Claude Desktop/Cursor)

1. Configure `knowledge_graph_mcp.py` in your MCP settings
2. Ask Claude: "Query my knowledge graph: What treatments are mentioned?"

## Checkpoints

Checkpoints are saved every 10 chunks in `graph_data/graph_checkpoint_*.pkl`.

The latest checkpoint is automatically detected by `retry_failed_chunks.py`.

## Troubleshooting

- **Graph not loading?** See `Documentation/Troubleshooting/CHROMADB_CORRUPTION_FIX.md`
- **Resume issues?** See `Documentation/Graph/TRANSFER_BETWEEN_MACHINES.md`
- **Quality issues?** See `Documentation/Graph/QUALITY_IMPROVEMENTS.md`

## Next Steps

- See `Documentation/Setup/NEXT_STEPS.md` for detailed next steps
- See `Documentation/Graph/IMPROVED_GRAPH_BUILDER_GUIDE.md` for advanced usage

