# Search Mode Comparison

| Mode | Best For | Dependencies | Notes |
| --- | --- | --- | --- |
| vector | fast retrieval, exact topic lookup | embedding service | can optionally attach supplemental web search |
| cascading | targeted research with progressive expansion | graph + LightRAG + embedding | anchors → entities → expansion → vector → synthesis |
| deep thinking | agentic multi-step research | deep thinking orchestrator + vector/graph/web tools | use `ws://localhost:4000/api/v1/deep-research` |

## Guidance

- NetworkX and LightRAG remain part of the internal retrieval stack, but they are not exposed as separate public search modes.
- Start with **vector** for recall and speed.
- Use **cascading** when you want a synthesized answer backed by staged retrieval across graph, LightRAG, and vector search.
- In the webapp, **Enhanced Search** adds supplemental web search and memory context to `vector` and `cascading`.
- In the webapp, **Brief Concept Index** controls answer style for `vector` and `cascading`:
  - `on`: terse overview / concept-index style
  - `off`: fuller grounded answer
- Use **deep thinking** for longer-running, agentic analysis and research workflows.
- For simple note summaries in deep thinking, the system now stays vault-first and keeps the evidence set intentionally small unless you explicitly ask for outside context.
- Deep thinking excludes prompt-template and instruction notes from normal evidence ranking, so helper files should not appear as answer sources.
- Cascading now uses query-aware synthesis prompts for procedural and relation-style questions and falls back to extractive answers when the model returns incomplete or unsupported-grounded output.
- Cascading also applies provider-specific synthesis caps for local backends. Ollama can use a longer timeout plus tighter prompt-source limits than the shared default, which reduces synthesis timeouts on large note clusters without changing the request contract.
- When diagnosing slow cascading searches, check the `cascading_query.*` and `cascading_synthesis.*` timing logs before changing retrieval logic. They show whether latency came from retrieval, prompt preparation, or the model call itself.
