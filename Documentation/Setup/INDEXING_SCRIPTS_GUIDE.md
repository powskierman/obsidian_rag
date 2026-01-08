# Indexing Scripts Guide

Use these scripts in `Scripts/` to build or rebuild indexes.

## Common Choices

- `index_with_lightrag.sh`: build the LightRAG entity graph.
- `index_with_graphrag.sh`: run GraphRAG indexing (if configured).
- `index_with_kimi.sh`: index using Kimi/OpenRouter.
- `build_knowledge_graph.sh`: build the NetworkX graph.

## When to Run

- After large vault changes or folder reorganizations.
- After cloning to a new machine.

Pick the script that matches your desired graph mode. If unsure, start with `index_with_lightrag.sh`.
