# Graph Builder Guide

This covers the NetworkX graph build process and how to retry failures.

## Build Options

### Option A: Docker helper (OpenRouter)

```bash
./Scripts/build_knowledge_graph.sh
```

Requires `OPENROUTER_API_KEY` in `.env`.

### Option B: Local script

```bash
python src/indexing/build_knowledge_graph.py
```

Follow the prompts to run a full build or resume from a checkpoint.

## Outputs

- `data/graph_data/knowledge_graph_full.pkl`
- Checkpoints: `data/graph_data/graph_checkpoint_*.pkl`

## Retry Failed Chunks

```bash
python src/indexing/retry_failed_chunks.py
```

## Related Docs

- `Documentation/Graph/GRAPH_DATA_README.md`
- `Documentation/Graph/TRANSFER_BETWEEN_MACHINES.md`
- `Documentation/Graph/GRAPH_QUALITY_GUIDE.md`
