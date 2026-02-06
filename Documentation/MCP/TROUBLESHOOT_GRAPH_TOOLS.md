# MCP Graph Tool Troubleshooting

## Quick Checks

```bash
docker compose ps
curl -s http://localhost:4000/api/v1/health
```

If graph queries return nothing:
- Ensure `data/graph_data/knowledge_graph_full.pkl` exists.
- Rebuild the graph with `./Scripts/indexing/update_knowledge_graph.sh`.
