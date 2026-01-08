# Graph Data Flow

## Inputs

- Vault markdown files (mounted read-only in Docker).

## Processing

- Indexing scripts extract entities and relationships.
- Graph checkpoints are written during processing.

## Outputs

- `data/graph_data/knowledge_graph_full.pkl`
- `data/graph_data/graph_checkpoint_*.pkl`

Use `Documentation/Graph/GRAPH_DATA_README.md` for file details.
