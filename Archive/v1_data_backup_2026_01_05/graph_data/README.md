# Graph Data Directory

This directory contains all knowledge graph files:

## Files

- **`knowledge_graph_full.pkl`** - Main graph file (full build)
- **`knowledge_graph_test.pkl`** - Test graph file (50 chunks)
- **`graph_checkpoint_*.pkl`** - Progress checkpoints (can be deleted after completion)
- **`knowledge_graph*.json`** - JSON exports for visualization

## Organization

All graph-related files are stored here to keep the main directory clean.

## Cleanup

After completing a full build, you can safely delete checkpoint files:

```bash
# Delete all checkpoints (keep only final graph)
rm graph_data/graph_checkpoint_*.pkl
```

This will free up space while keeping your final graph intact.

