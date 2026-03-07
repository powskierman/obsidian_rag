# Search Mode Comparison

| Mode | Best For | Dependencies | Notes |
| --- | --- | --- | --- |
| vector | fast retrieval, exact topic lookup | embedding service | no graph required |
| cascading | targeted research with progressive expansion | graph + LightRAG + embedding | anchors → entities → expansion → vector |
| deep thinking | agentic multi-step research | deep thinking orchestrator + vector/graph/web tools | use `ws://localhost:4000/api/v1/deep-research` |

## Guidance

- Start with **vector** for recall and speed.
- Use **cascading** when you want a synthesized answer backed by staged retrieval across graph, LightRAG, and vector search.
- Use **deep thinking** for longer-running, agentic analysis and research workflows.
- For simple note summaries in deep thinking, the system now stays vault-first and keeps the evidence set intentionally small unless you explicitly ask for outside context.
- Deep thinking excludes prompt-template and instruction notes from normal evidence ranking, so helper files should not appear as answer sources.
