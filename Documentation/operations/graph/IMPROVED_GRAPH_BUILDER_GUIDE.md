# Graph Builder Guide

This covers the NetworkX graph build process and how to retry failures.

## Build Options

### Option A: Docker helper (OpenRouter)

```bash
./Scripts/indexing/update_knowledge_graph.sh
```

Requires `OPENROUTER_API_KEY` in `.env`.

### Option B: Local script

```bash
python src/services/build_graph.py
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

- `Documentation/operations/graph/GRAPH_DATA_README.md`
- `Documentation/operations/graph/TRANSFER_BETWEEN_MACHINES.md`
- `Documentation/operations/graph/GRAPH_QUALITY_GUIDE.md`
